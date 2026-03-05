"""
Article Finder - ERWEITERTE VERSION
====================================
Findet automatisch Artikel für die Analyse aus:
- Wikipedia-Listen (umstrittene Artikel, geschützte Seiten)
- Kategorien
- Aktuelle Konflikte (RecentChanges mit vielen Reverts)
- HISTORISCH KONTROVERSE ARTIKEL (NEU!)
- Manuelle Eingabe
"""

from typing import List, Dict, Set
from datetime import datetime, timedelta
import time
import re

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
]

# Englische Wikipedia
CATEGORIES_EN = [
    "Category:Living people",
    "Category:21st-century American politicians",
    "Category:Conspiracy theories",
    "Category:Companies based in the United States",
]

# ==========================================
# NEU: Wikipedia-Seiten mit kontroversen Artikeln
# ==========================================

# Diese Wikipedia-Seiten listen bekannte kontroverse Artikel auf
CONTROVERSIAL_PAGES_DE = [
    "Wikipedia:Vandalismusmeldung/Archiv",
    "Wikipedia:Gesperrte Seiten",
    "Wikipedia:Edit-War",
]

CONTROVERSIAL_PAGES_EN = [
    "Wikipedia:Lamest edit wars",
    "Wikipedia:List of controversial issues", 
    "Wikipedia:Long-term abuse",
]


class ArticleFinder:
    """Findet Artikel für die Überwachung - ERWEITERTE VERSION"""
    
    def __init__(self, lang: str = 'de'):
        self.lang = lang
        self.api = get_wiki_api(lang)
        self.found_articles: Set[str] = set()
    
    def find_all(self, max_articles: int = None) -> List[Dict]:
        """
        Findet Artikel aus allen Quellen inkl. historisch kontroverser.
        """
        max_articles = max_articles or config.MAX_ARTICLES
        articles = []
        
        print(f"🔍 Suche Artikel für {self.lang}.wikipedia.org...")
        
        # 1. Artikel mit aktuellen Konflikten
        print("  → Suche aktuelle Edit-Wars...")
        conflict_articles = self._find_current_conflicts()
        articles.extend(conflict_articles)
        print(f"    ✓ {len(conflict_articles)} Artikel mit aktiven Konflikten")
        
        # 2. NEU: Historisch kontroverse Artikel
        print("  → Suche historisch kontroverse Artikel...")
        historical = self._find_historical_controversial()
        articles.extend(historical)
        print(f"    ✓ {len(historical)} historisch kontroverse Artikel")
        
        # 3. NEU: Artikel mit den meisten Bearbeitungen
        print("  → Suche meistbearbeitete Artikel...")
        most_edited = self._find_most_edited_articles()
        articles.extend(most_edited)
        print(f"    ✓ {len(most_edited)} meistbearbeitete Artikel")
        
        # 4. Geschützte Seiten (aktuell + historisch)
        print("  → Suche geschützte Seiten...")
        protected = self._find_protected_pages()
        articles.extend(protected)
        print(f"    ✓ {len(protected)} geschützte Seiten")
        
        # 5. Artikel aus Kategorien
        print("  → Durchsuche Kategorien...")
        category_articles = self._find_from_categories()
        articles.extend(category_articles)
        print(f"    ✓ {len(category_articles)} Artikel aus Kategorien")
        
        # 6. NEU: Artikel aus Wikipedia's Kontroversen-Listen
        print("  → Suche in Wikipedia Kontroversen-Listen...")
        from_lists = self._find_from_controversy_lists()
        articles.extend(from_lists)
        print(f"    ✓ {len(from_lists)} Artikel aus Kontroversen-Listen")
        
        # Duplikate entfernen und begrenzen
        unique_articles = self._deduplicate(articles)
        limited = unique_articles[:max_articles]
        
        print(f"✅ Gesamt: {len(limited)} eindeutige Artikel gefunden")
        
        return limited
    
    # ==========================================
    # NEU: Historisch kontroverse Artikel finden
    # ==========================================
    
    def _find_historical_controversial(self) -> List[Dict]:
        """
        Findet Artikel die historisch kontrovers waren.
        Nutzt Wikipedia's eigene Logs und Statistiken.
        """
        articles = []
        
        # Methode 1: Artikel mit vielen Revisionen in der Vergangenheit
        # die auch Reverts enthalten
        try:
            articles.extend(self._find_articles_with_historical_reverts())
        except Exception as e:
            print(f"    ⚠ Fehler bei historischen Reverts: {e}")
        
        # Methode 2: Artikel die in der Vergangenheit geschützt waren
        try:
            articles.extend(self._find_previously_protected())
        except Exception as e:
            print(f"    ⚠ Fehler bei ehemals geschützten: {e}")
        
        return articles
    
    def _find_articles_with_historical_reverts(self) -> List[Dict]:
        """
        Sucht nach Artikeln die in der Vergangenheit viele Reverts hatten.
        Nutzt den Log-API-Endpunkt.
        """
        articles = []
        
        # Suche nach Reverts in den letzten 5 Jahren über verschiedene Zeiträume
        time_periods = [
            (365, "letztes Jahr"),
            (365*2, "letzte 2 Jahre"),
            (365*3, "letzte 3 Jahre"),
        ]
        
        for days_back, period_name in time_periods:
            try:
                # Hole Revert-Aktivitäten aus der Vergangenheit
                end_time = datetime.utcnow() - timedelta(days=days_back-365)
                start_time = end_time - timedelta(days=365)
                
                params = {
                    'action': 'query',
                    'list': 'recentchanges',
                    'rcstart': end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'rcend': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'rclimit': 500,
                    'rcprop': 'title|tags|comment',
                    'rcnamespace': 0,
                    'rctype': 'edit',
                    'format': 'json'
                }
                
                response = self.api.session.get(self.api.api_url, params=params, timeout=30)
                data = response.json()
                
                changes = data.get('query', {}).get('recentchanges', [])
                
                # Zähle Reverts pro Artikel
                article_reverts = {}
                for change in changes:
                    title = change.get('title', '')
                    comment = change.get('comment', '').lower()
                    tags = change.get('tags', [])
                    
                    is_revert = (
                        'mw-reverted' in tags or
                        'mw-undo' in tags or
                        'revert' in comment or
                        'rückgängig' in comment or
                        'zurückgesetzt' in comment
                    )
                    
                    if is_revert and title:
                        article_reverts[title] = article_reverts.get(title, 0) + 1
                
                # Füge Artikel mit mehreren Reverts hinzu
                for title, count in sorted(article_reverts.items(), key=lambda x: x[1], reverse=True)[:30]:
                    if count >= 2 and title not in self.found_articles:
                        articles.append({
                            'title': title,
                            'source': 'historical_conflict',
                            'source_detail': f'{count} Reverts ({period_name})',
                            'priority': min(10, 5 + count)
                        })
                        self.found_articles.add(title)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"      ⚠ Fehler für Zeitraum {period_name}: {e}")
                continue
        
        return articles
    
    def _find_previously_protected(self) -> List[Dict]:
        """
        Findet Artikel die in der Vergangenheit geschützt wurden.
        """
        articles = []
        
        try:
            # Log-Einträge für Seitenschutz abrufen
            params = {
                'action': 'query',
                'list': 'logevents',
                'letype': 'protect',
                'lelimit': 200,
                'leprop': 'title|timestamp|comment',
                'format': 'json'
            }
            
            response = self.api.session.get(self.api.api_url, params=params, timeout=30)
            data = response.json()
            
            log_entries = data.get('query', {}).get('logevents', [])
            
            for entry in log_entries:
                title = entry.get('title', '')
                
                # Nur Artikel (keine Diskussionsseiten etc.)
                if ':' in title:
                    continue
                    
                if title and title not in self.found_articles:
                    comment = entry.get('comment', '')
                    articles.append({
                        'title': title,
                        'source': 'previously_protected',
                        'source_detail': f"Geschützt: {comment[:50]}..." if comment else "War geschützt",
                        'priority': 7
                    })
                    self.found_articles.add(title)
            
        except Exception as e:
            print(f"    ⚠ Fehler beim Abruf der Schutz-Logs: {e}")
        
        return articles[:50]  # Max 50
    
    def _find_most_edited_articles(self) -> List[Dict]:
        """
        Findet Artikel mit den meisten Bearbeitungen.
        Diese sind oft kontrovers.
        """
        articles = []
        
        # Wikipedia hat spezielle Seiten die meistbearbeitete Artikel listen
        # Wir können auch die Revision-Count aus Artikel-Info nutzen
        
        # Alternative: Nutze bekannte kontroverse Themen als Seed
        controversial_seeds = {
            'de': [
                'Adolf Hitler', 'Holocaust', 'Zweiter Weltkrieg',
                'Alternative für Deutschland', 'COVID-19-Pandemie',
                'Klimawandel', 'Russisch-Ukrainischer Krieg',
                'Israel', 'Palästina', 'Hamas',
                'Donald Trump', 'Wladimir Putin',
                'Impfung', 'Homöopathie', 'Scientology',
                'Wikipedia', 'Löschkandidaten',
            ],
            'en': [
                'Adolf Hitler', 'Holocaust', 'World War II',
                'Donald Trump', 'Joe Biden', 'Barack Obama',
                'Climate change', 'COVID-19 pandemic',
                'Israel', 'Palestine', 'Hamas',
                'Russia', 'Vladimir Putin',
                'Abortion', 'Gun control', 'Vaccination',
                'Wikipedia', 'Elon Musk', 'Kanye West',
            ]
        }
        
        seeds = controversial_seeds.get(self.lang, controversial_seeds['en'])
        
        for title in seeds:
            if title not in self.found_articles:
                # Prüfe ob Artikel existiert
                info = self.api.get_article_info(title)
                if info:
                    articles.append({
                        'title': title,
                        'source': 'known_controversial',
                        'source_detail': 'Bekanntes kontroverses Thema',
                        'priority': 8
                    })
                    self.found_articles.add(title)
            
            time.sleep(0.2)  # Rate limiting
        
        return articles
    
    def _find_from_controversy_lists(self) -> List[Dict]:
        """
        Extrahiert Artikel aus Wikipedia's eigenen Kontroversen-Listen.
        """
        articles = []
        
        pages = CONTROVERSIAL_PAGES_DE if self.lang == 'de' else CONTROVERSIAL_PAGES_EN
        
        for page_title in pages:
            try:
                content = self.api.get_talk_page_content(page_title.replace('Wikipedia:', ''))
                
                if not content:
                    # Versuche als normale Seite zu laden
                    params = {
                        'action': 'query',
                        'titles': page_title,
                        'prop': 'revisions',
                        'rvprop': 'content',
                        'rvlimit': 1,
                        'format': 'json'
                    }
                    response = self.api.session.get(self.api.api_url, params=params, timeout=30)
                    data = response.json()
                    
                    pages_data = data.get('query', {}).get('pages', {})
                    for page_id, page_data in pages_data.items():
                        if page_id != '-1':
                            revisions = page_data.get('revisions', [])
                            if revisions:
                                content = revisions[0].get('*', '')
                
                if content:
                    # Extrahiere Wikilinks [[Artikel]]
                    links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                    
                    for link in links[:30]:  # Max 30 pro Liste
                        # Filtere Wikipedia-Namensräume aus
                        if ':' in link and not link.startswith('Datei:'):
                            continue
                        
                        link = link.strip()
                        if link and link not in self.found_articles and len(link) > 2:
                            articles.append({
                                'title': link,
                                'source': 'wikipedia_list',
                                'source_detail': f'Aus: {page_title}',
                                'priority': 6
                            })
                            self.found_articles.add(link)
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    ⚠ Fehler bei {page_title}: {e}")
        
        return articles
    
    # ==========================================
    # Bestehende Methoden (unverändert)
    # ==========================================
    
    def _find_current_conflicts(self, hours_back: int = 48) -> List[Dict]:
        """Findet Artikel mit aktuellen Edit-Wars"""
        articles = []
        
        recent = self.api.get_recent_changes(
            limit=500,
            hours_back=hours_back,
            only_reverts=False
        )
        
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
        
        for title, revert_count in sorted(
            article_reverts.items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            if revert_count >= 2:
                priority = min(10, 5 + revert_count)
                articles.append({
                    'title': title,
                    'source': 'auto_detected',
                    'source_detail': f'{revert_count} Reverts in {hours_back}h',
                    'priority': priority
                })
                self.found_articles.add(title)
        
        return articles[:50]
    
    def _find_protected_pages(self) -> List[Dict]:
        """Findet aktuell geschützte Seiten"""
        articles = []
        
        try:
            protected = self.api.get_protected_pages(limit=100)
            
            for title in protected:
                if title not in self.found_articles:
                    articles.append({
                        'title': title,
                        'source': 'protected',
                        'source_detail': 'Aktuell geschützte Seite',
                        'priority': 7
                    })
                    self.found_articles.add(title)
        except Exception as e:
            print(f"    ⚠ Fehler beim Laden geschützter Seiten: {e}")
        
        return articles
    
    def _find_from_categories(self) -> List[Dict]:
        """Findet Artikel aus vordefinierten Kategorien"""
        articles = []
        categories = CATEGORIES_DE if self.lang == 'de' else CATEGORIES_EN
        
        for category in categories:
            try:
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
        
        return sorted(seen.values(), key=lambda x: x['priority'], reverse=True)
    
    def add_manual_article(self, title: str, reason: str = None) -> bool:
        """Fügt einen Artikel manuell zur Watchlist hinzu"""
        info = self.api.get_article_info(title)
        
        if not info:
            print(f"⚠ Artikel '{title}' nicht gefunden")
            return False
        
        success = add_watched_article(
            article_title=title,
            wiki_lang=self.lang,
            source='manual',
            source_detail=reason or 'Manuell hinzugefügt',
            priority=8
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
    JETZT INKL. HISTORISCHER KONFLIKTE!
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


if __name__ == "__main__":
    populate_watchlist()
