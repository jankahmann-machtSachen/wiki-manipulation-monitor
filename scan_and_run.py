"""
Kombiniertes Script: Erst Scan, dann Dashboard
==============================================
Für Render.com - führt beim Start einen kurzen Scan aus
"""

import os
import sys
import threading
import time

def run_initial_scan():
    """Führt einen kleinen Initial-Scan im Hintergrund aus"""
    try:
        print("🔍 Starte Initial-Scan im Hintergrund...")
        
        # Imports
        from src.database import init_database
        from src.wiki_api import get_wiki_api
        from src.detectors import ManipulationDetector
        from src.config import config
        
        # Datenbank initialisieren
        init_database()
        print("✓ Datenbank initialisiert")
        
        # Nur ein paar bekannte kontroverse Artikel scannen
        test_articles = {
            'de': [
                'Adolf Hitler',
                'Alternative für Deutschland', 
                'COVID-19-Pandemie in Deutschland',
                'Klimawandel',
                'Russisch-Ukrainischer Krieg',
            ],
            'en': [
                'Donald Trump',
                'Climate change',
                'COVID-19 pandemic',
                'Russia–Ukraine war',
                'Elon Musk',
            ]
        }
        
        from src.database import insert_case
        import json
        
        for lang in ['de', 'en']:
            print(f"\n--- Analysiere {lang}.wikipedia.org ---")
            api = get_wiki_api(lang)
            detector = ManipulationDetector(api)
            
            for i, title in enumerate(test_articles[lang]):
                print(f"  [{i+1}/{len(test_articles[lang])}] {title}...")
                
                try:
                    results = detector.analyze_article(title)
                    
                    if results:
                        print(f"    ⚠ {len(results)} Fälle gefunden!")
                        for result in results:
                            case_data = {
                                'case_type': result.case_type,
                                'severity': result.severity,
                                'article_title': title,
                                'article_url': f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                'wiki_lang': lang,
                                'title': result.title,
                                'description': result.description,
                                'involved_users': json.dumps(result.involved_users),
                                'evidence': json.dumps(result.evidence, default=str),
                                'confidence': result.confidence,
                            }
                            insert_case(case_data)
                    else:
                        print(f"    ✓ Keine Auffälligkeiten")
                        
                except Exception as e:
                    print(f"    ✗ Fehler: {e}")
                
                time.sleep(1)  # Rate limiting
        
        print("\n✅ Initial-Scan abgeschlossen!")
        
    except Exception as e:
        print(f"❌ Scan-Fehler: {e}")
        import traceback
        traceback.print_exc()


def run_streamlit():
    """Startet das Streamlit Dashboard"""
    port = os.environ.get('PORT', '8501')
    os.system(f"streamlit run app.py --server.port {port} --server.address 0.0.0.0 --server.headless true")


if __name__ == "__main__":
    # Scan im Hintergrund starten
    scan_thread = threading.Thread(target=run_initial_scan, daemon=True)
    scan_thread.start()
    
    # Kurz warten damit der Scan beginnt
    time.sleep(2)
    
    # Dashboard starten (blockiert)
    run_streamlit()
