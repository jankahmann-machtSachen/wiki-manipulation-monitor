"""
Article Finder
==============
Findet automatisch Artikel für die Analyse aus:
- Wikipedia-Listen (umstrittene Artikel, geschützte Seiten)
- Kategorien
- Aktuelle Konflikte (RecentChanges mit vielen Reverts)
- Manuelle Eingabe
"""

from typing import List, Dict, Set
from datetime import datetime
import time

from .config import config
from .wiki_api import WikipediaAPI, get_wiki_api
from .database import add_watched_article, get_watched_articles


# ==========================================
# Vordefinierte Kategorien und Listen
# ==========================================

# Deutsche Wikipedia
CATEGORIES_DE = [
    "Kategorie:Politiker (21. Jahrhundert)",
    "Kategorie:Lebende Person",
    "Kategorie:Unternehmen (Deutschland)",
    "Kategorie:Partei (Deutschland)",
    "Kategorie:Verschwörungstheorie",
    "Kategorie:Umstrittene Person",
]

# Englische Wikipedia
CATEGORIES_EN = [
    "Category:Living people",
    "Category:21st-century American politicians",
    "Category:Conspiracy theories",
    "Category:Controversial politicians",
    "Category:Companies based in the United States",
]

# Wikipedia-interne Listen mit umstrittenen Artikeln
CONTROVERSY_LISTS_DE = [
    "Wikipedia:Artikelwünsche",  # Artikel mit Diskussionsbedarf
]

CONTROVERSY_LISTS_EN = [
    "Wikipedia:List of controversial issues",
    "Wikipedia:Lamest edit wars",
]


class ArticleFinder:
    """Findet Artikel für die Überwachung"""
    
    def __init__(self, lang: str = 'de'):
        self.lang = lang
        self.api = get_wiki_api(lang)
        self.found_articles: Set[str] = set()
    
    def find_all(self, max_articles: int = None) -> List[Dict]:
        """
        Findet Artikel aus allen Quellen.
        
        Returns:
            Liste von Dictionaries mit 'title', 'source', 'priority'
        """
        max_articles = max_articles or config.MAX_ARTICLES
        articles = []
        
        print(f"🔍 Suche Artikel für {self.lang}.wikipedia.org...")
        
        # 1. Artikel mit aktuellen Konflikten (höchste Priorität)
        print("  → Suche aktuelle Edit-Wars...")
        conflict_articles = self._find_current_conflicts()
        articles.extend(conflict_articles)
        print(f"    ✓ {len(conflict_articles)} Artikel mit aktiven Konflikten")
        
        # 2. Geschützte Seiten
        print("  → Suche geschützte Seiten...")
        protected = self._find_protected_pages()
        articles.extend(protected)
        print(f"    ✓ {len(protected)} geschützte Seiten")
        
        # 3. Artikel aus Kategorien
        print("  → Durchsuche Kategorien...")
        category_articles = self._find_from_categories()
        articles.extend(category_articles)
        print(f"    ✓ {len(category_articles)} Artikel aus Kategorien")
        
        # Duplikate entfernen und begrenzen
        unique_articles = self._deduplicate(articles)
        limited = unique_articles[:max_articles]
        
        print(f"✅ Gesamt: {len(limited)} eindeutige Artikel gefunden")
        
        return limited
    
    def _find_current_conflicts(self, hours_back: int = 48) -> List[Dict]:
        """Findet Artikel mit aktuellen Edit-Wars"""
        
        articles = []
        
        # Hole kürzliche Änderungen mit Reverts
        recent = self.api.get_recent_changes(
            limit=500,
            hours_back=hours_back,
            only_reverts=False
        )
        
        # Zähle Reverts pro Artikel
        article_reverts = {}
        for change in recent:
            title = change.get('title', '')
            comment = change.get('comment', '').lower()
            tags = change.get('tags', [])
            
            is_revert = (
                'mw-reverted' in tags or
                'mw-undo' in tags or
                'revert' in comment or
                'rückgängig' in comment
            )
            
            if is_revert:
                if title not in article_reverts:
                    article_reverts[title] = 0
                article_reverts[title] += 1
        
        # Artikel mit mehreren Reverts hinzufügen
        for title, revert_count in sorted(
            article_reverts.items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            if revert_count >= 2:  # Mindestens 2 Reverts
                priority = min(10, 5 + revert_count)
                articles.append({
                    'title': title,
                    'source': 'auto_detected',
                    'source_detail': f'{revert_count} Reverts in {hours_back}h',
                    'priority': priority
                })
                self.found_articles.add(title)
        
        return articles[:50]  # Max 50 aus dieser Quelle
    
    def _find_protected_pages(self) -> List[Dict]:
        """Findet geschützte Seiten"""
        
        articles = []
        
        try:
            protected = self.api.get_protected_pages(limit=100)
            
            for title in protected:
                if title not in self.found_articles:
                    articles.append({
                        'title': title,
                        'source': 'wikipedia_list',
                        'source_detail': 'Geschützte Seite',
                        'priority': 7
                    })
                    self.found_articles.add(title)
        except Exception as e:
            print(f"    ⚠ Fehler beim Laden geschützter Seiten: {e}")
        
        return articles
    
    def _find_from_categories(self) -> List[Dict]:
        """Findet Artikel aus vordefinierten Kategorien"""
        
        articles = []
        
        # Wähle Kategorien basierend auf Sprache
        categories = CATEGORIES_DE if self.lang == 'de' else CATEGORIES_EN
        
        for category in categories:
            try:
                # Begrenzt pro Kategorie um API nicht zu überlasten
                members = self.api.get_category_members(
                    category, 
                    limit=30,
                    member_type='page'
                )
                
                for title in members:
                    if title not in self.found_articles:
                        articles.append({
                            'title': title,
                            'source': 'category',
                            'source_detail': category,
                            'priority': 5
                        })
                        self.found_articles.add(title)
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    ⚠ Fehler bei Kategorie {category}: {e}")
        
        return articles
    
    def _deduplicate(self, articles: List[Dict]) -> List[Dict]:
        """Entfernt Duplikate, behält höchste Priorität"""
        
        seen = {}
        
        for article in articles:
            title = article['title']
            if title not in seen:
                seen[title] = article
            elif article['priority'] > seen[title]['priority']:
                seen[title] = article
        
        # Sortiere nach Priorität
        return sorted(seen.values(), key=lambda x: x['priority'], reverse=True)
    
    def add_manual_article(self, title: str, reason: str = None) -> bool:
        """Fügt einen Artikel manuell zur Watchlist hinzu"""
        
        # Prüfe ob Artikel existiert
        info = self.api.get_article_info(title)
        
        if not info:
            print(f"⚠ Artikel '{title}' nicht gefunden")
            return False
        
        success = add_watched_article(
            article_title=title,
            wiki_lang=self.lang,
            source='manual',
            source_detail=reason or 'Manuell hinzugefügt',
            priority=8  # Manuelle Artikel haben hohe Priorität
        )
        
        if success:
            print(f"✓ Artikel '{title}' zur Watchlist hinzugefügt")
        
        return success
    
    def search_and_add(self, query: str, limit: int = 10) -> List[str]:
        """Sucht nach Artikeln und fügt sie zur Watchlist hinzu"""
        
        results = self.api.search_articles(query, limit=limit)
        added = []
        
        for title in results:
            success = add_watched_article(
                article_title=title,
                wiki_lang=self.lang,
                source='search',
                source_detail=f'Suche: {query}',
                priority=6
            )
            if success:
                added.append(title)
        
        return added


def populate_watchlist(languages: List[str] = None, max_per_lang: int = 250) -> int:
    """
    Befüllt die Watchlist mit Artikeln aus allen Quellen.
    
    Args:
        languages: Liste der Sprachen (default: aus Config)
        max_per_lang: Max Artikel pro Sprache
    
    Returns:
        Anzahl der hinzugefügten Artikel
    """
    languages = languages or config.ENABLED_LANGUAGES
    total_added = 0
    
    for lang in languages:
        print(f"\n{'='*50}")
        print(f"Sprache: {lang}")
        print('='*50)
        
        finder = ArticleFinder(lang)
        articles = finder.find_all(max_articles=max_per_lang)
        
        for article in articles:
            success = add_watched_article(
                article_title=article['title'],
                wiki_lang=lang,
                source=article['source'],
                source_detail=article.get('source_detail'),
                priority=article['priority']
            )
            if success:
                total_added += 1
    
    print(f"\n✅ Gesamt {total_added} neue Artikel zur Watchlist hinzugefügt")
    return total_added


# Für direktes Ausführen
if __name__ == "__main__":
    populate_watchlist()
