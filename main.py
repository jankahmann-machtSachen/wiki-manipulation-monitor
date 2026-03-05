#!/usr/bin/env python3
"""
Wikipedia Manipulation Monitor - Hauptskript
=============================================
Wird von GitHub Actions täglich ausgeführt.

Ablauf:
1. Datenbank initialisieren
2. Neue Artikel finden und zur Watchlist hinzufügen
3. Artikel aus Watchlist analysieren
4. Erkannte Fälle mit KI bewerten
5. Ergebnisse in Datenbank speichern
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict

# Lokale Imports
from src.config import config
from src.database import (
    init_database, 
    get_db_connection,
    insert_case, 
    get_watched_articles,
    get_statistics
)
from src.wiki_api import get_wiki_api
from src.detectors import ManipulationDetector, DetectionResult
from src.ai_analyzer import analyze_case_with_ai
from src.article_finder import populate_watchlist, ArticleFinder


def log(message: str):
    """Logging mit Timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def run_full_scan():
    """Führt einen vollständigen Scan durch"""
    
    log("="*60)
    log("Wikipedia Manipulation Monitor - Vollständiger Scan")
    log("="*60)
    
    # 1. Datenbank initialisieren
    log("Schritt 1: Datenbank initialisieren...")
    init_database()
    
    # 2. Watchlist aktualisieren
    log("Schritt 2: Watchlist mit neuen Artikeln befüllen...")
    new_articles = populate_watchlist(
        languages=config.ENABLED_LANGUAGES,
        max_per_lang=250
    )
    log(f"  → {new_articles} neue Artikel hinzugefügt")
    
    # 3. Artikel analysieren
    log("Schritt 3: Artikel analysieren...")
    total_cases = analyze_watchlist(limit=config.ARTICLES_PER_RUN)
    
    # 4. Statistiken ausgeben
    log("Schritt 4: Statistiken...")
    print_statistics()
    
    log("="*60)
    log("Scan abgeschlossen!")
    log("="*60)


def analyze_watchlist(limit: int = 50) -> int:
    """
    Analysiert Artikel aus der Watchlist.
    
    Args:
        limit: Maximale Anzahl zu analysierender Artikel
    
    Returns:
        Anzahl der gefundenen Fälle
    """
    total_cases = 0
    
    for lang in config.ENABLED_LANGUAGES:
        log(f"\n--- Analysiere {lang}.wikipedia.org ---")
        
        # Hole Artikel zur Analyse
        articles = get_watched_articles(wiki_lang=lang, limit=limit // len(config.ENABLED_LANGUAGES))
        
        if not articles:
            log(f"  Keine Artikel in Watchlist für {lang}")
            continue
        
        log(f"  {len(articles)} Artikel zu analysieren")
        
        # API und Detektor initialisieren
        api = get_wiki_api(lang)
        detector = ManipulationDetector(api)
        
        for i, article in enumerate(articles):
            title = article['article_title']
            log(f"  [{i+1}/{len(articles)}] Analysiere: {title}")
            
            try:
                # Detektoren ausführen
                results = detector.analyze_article(title)
                
                if results:
                    log(f"    ⚠ {len(results)} mögliche Fälle gefunden")
                    
                    for result in results:
                        # KI-Analyse durchführen
                        case_data = result_to_dict(result, title, lang)
                        
                        try:
                            ai_result = analyze_case_with_ai(case_data)
                            case_data.update({
                                'ai_summary': ai_result.summary,
                                'ai_conflict_score': ai_result.conflict_score,
                                'ai_manipulation_score': ai_result.manipulation_score,
                                'ai_power_abuse_score': ai_result.power_abuse_score,
                                'ai_reasoning': ai_result.reasoning,
                                'severity': ai_result.recommended_severity,
                                'confidence': ai_result.confidence
                            })
                        except Exception as e:
                            log(f"    ⚠ KI-Analyse fehlgeschlagen: {e}")
                        
                        # In Datenbank speichern
                        case_id = insert_case(case_data)
                        if case_id:
                            total_cases += 1
                            severity_label = config.SEVERITY_LEVELS.get(
                                case_data.get('severity', 5), {}
                            ).get('label', 'mittel')
                            log(f"    ✓ Fall #{case_id} gespeichert (Schwere: {severity_label})")
                else:
                    log(f"    ✓ Keine Auffälligkeiten")
                    
            except Exception as e:
                log(f"    ✗ Fehler: {e}")
        
        # Update last_checked für analysierte Artikel
        update_last_checked([a['article_title'] for a in articles], lang)
    
    return total_cases


def result_to_dict(result: DetectionResult, article_title: str, lang: str) -> Dict:
    """Konvertiert DetectionResult zu Dictionary für Datenbank"""
    
    article_url = f"https://{lang}.wikipedia.org/wiki/{article_title.replace(' ', '_')}"
    talk_url = f"https://{lang}.wikipedia.org/wiki/{'Diskussion' if lang == 'de' else 'Talk'}:{article_title.replace(' ', '_')}"
    
    return {
        'case_type': result.case_type,
        'severity': result.severity,
        'severity_label': config.SEVERITY_LEVELS.get(result.severity, {}).get('label', 'mittel'),
        'confidence': result.confidence,
        'article_title': article_title,
        'article_url': article_url,
        'wiki_lang': lang,
        'title': result.title,
        'description': result.description,
        'involved_users': json.dumps(result.involved_users, ensure_ascii=False),
        'evidence': json.dumps(result.evidence, ensure_ascii=False, default=str),
        'talk_page_url': talk_url,
        'incident_start': result.incident_start.isoformat() if result.incident_start else None,
        'incident_end': result.incident_end.isoformat() if result.incident_end else None,
        'admin_involved': result.admin_involved
    }


def update_last_checked(article_titles: List[str], lang: str):
    """Aktualisiert last_checked Timestamp für Artikel"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    for title in article_titles:
        cursor.execute("""
            UPDATE watched_articles 
            SET last_checked = ?
            WHERE article_title = ? AND wiki_lang = ?
        """, (now, title, lang))
    
    conn.commit()
    conn.close()


def print_statistics():
    """Gibt Statistiken aus"""
    
    stats = get_statistics()
    
    log("\n📊 STATISTIKEN")
    log("-" * 40)
    log(f"Gesamt erkannte Fälle: {stats['total_cases']}")
    log(f"Neue/ungeprüfte Fälle: {stats['new_cases']}")
    log(f"Überwachte Artikel: {stats['watched_articles']}")
    
    if stats['by_severity']:
        log("\nNach Schweregrad:")
        for severity, count in sorted(stats['by_severity'].items(), reverse=True):
            label = config.SEVERITY_LEVELS.get(severity, {}).get('label', '?')
            log(f"  Stufe {severity} ({label}): {count}")
    
    if stats['by_type']:
        log("\nNach Typ:")
        for case_type, count in stats['by_type'].items():
            log(f"  {case_type}: {count}")
    
    if stats['top_articles']:
        log("\nTop-Artikel mit meisten Fällen:")
        for article in stats['top_articles'][:5]:
            log(f"  {article['article_title']} ({article['wiki_lang']}): {article['case_count']} Fälle")


def add_article_manually(title: str, lang: str = 'de'):
    """Fügt einen Artikel manuell hinzu und analysiert ihn sofort"""
    
    log(f"Manuelles Hinzufügen: {title} ({lang})")
    
    init_database()
    
    finder = ArticleFinder(lang)
    success = finder.add_manual_article(title)
    
    if success:
        log("Artikel hinzugefügt, starte Analyse...")
        
        api = get_wiki_api(lang)
        detector = ManipulationDetector(api)
        results = detector.analyze_article(title)
        
        if results:
            log(f"⚠ {len(results)} mögliche Fälle gefunden!")
            for result in results:
                case_data = result_to_dict(result, title, lang)
                
                try:
                    ai_result = analyze_case_with_ai(case_data)
                    case_data.update({
                        'ai_summary': ai_result.summary,
                        'ai_conflict_score': ai_result.conflict_score,
                        'ai_manipulation_score': ai_result.manipulation_score,
                        'ai_power_abuse_score': ai_result.power_abuse_score,
                        'severity': ai_result.recommended_severity
                    })
                except:
                    pass
                
                case_id = insert_case(case_data)
                if case_id:
                    log(f"  ✓ Fall #{case_id}: {result.title}")
        else:
            log("✓ Keine Auffälligkeiten gefunden")


# ==========================================
# Kommandozeilen-Interface
# ==========================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "scan":
            run_full_scan()
        
        elif command == "add" and len(sys.argv) >= 3:
            article = sys.argv[2]
            lang = sys.argv[3] if len(sys.argv) > 3 else 'de'
            add_article_manually(article, lang)
        
        elif command == "stats":
            init_database()
            print_statistics()
        
        elif command == "init":
            init_database()
            log("Datenbank initialisiert")
        
        else:
            print("Verwendung:")
            print("  python main.py scan          - Vollständiger Scan")
            print("  python main.py add <Artikel> [Sprache] - Artikel hinzufügen")
            print("  python main.py stats         - Statistiken anzeigen")
            print("  python main.py init          - Nur Datenbank initialisieren")
    else:
        # Standard: Vollständiger Scan
        run_full_scan()
