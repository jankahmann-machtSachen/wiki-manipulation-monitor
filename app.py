"""
Wikipedia Manipulation Monitor - Dashboard (VEREINFACHT)
"""

import streamlit as st
import pandas as pd
import json
import os
import time
import sqlite3
from datetime import datetime

# ==========================================
# Datenbank-Funktionen (eingebaut)
# ==========================================

DB_PATH = "data/wiki_monitor.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            case_type TEXT,
            severity INTEGER,
            article_title TEXT,
            article_url TEXT,
            wiki_lang TEXT DEFAULT 'de',
            title TEXT,
            description TEXT,
            involved_users TEXT,
            evidence TEXT,
            confidence REAL,
            status TEXT DEFAULT 'neu'
        )
    """)
    conn.commit()
    conn.close()

def get_all_cases():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cases ORDER BY severity DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except:
        return []

def insert_case(case_data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cases (case_type, severity, article_title, article_url, wiki_lang, title, description, involved_users, evidence, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        case_data.get('case_type'),
        case_data.get('severity'),
        case_data.get('article_title'),
        case_data.get('article_url'),
        case_data.get('wiki_lang', 'de'),
        case_data.get('title'),
        case_data.get('description'),
        case_data.get('involved_users'),
        case_data.get('evidence'),
        case_data.get('confidence')
    ))
    conn.commit()
    conn.close()

def count_cases():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cases")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

# ==========================================
# Scan-Funktion
# ==========================================

def run_scan(articles_de, articles_en, progress_bar, status_text):
    """Scannt Artikel auf Konflikte"""
    
    # Importiere hier um Startup-Fehler zu vermeiden
    try:
        from src.wiki_api import get_wiki_api
        from src.detectors import ManipulationDetector
    except ImportError as e:
        st.error(f"Import-Fehler: {e}")
        return 0
    
    total = len(articles_de) + len(articles_en)
    current = 0
    cases_found = 0
    
    all_articles = [('de', a) for a in articles_de] + [('en', a) for a in articles_en]
    
    for lang, title in all_articles:
        current += 1
        progress_bar.progress(current / total)
        status_text.text(f"[{current}/{total}] Analysiere: {title}")
        
        try:
            api = get_wiki_api(lang)
            detector = ManipulationDetector(api)
            results = detector.analyze_article(title)
            
            if results:
                cases_found += len(results)
                for r in results:
                    insert_case({
                        'case_type': r.case_type,
                        'severity': r.severity,
                        'article_title': title,
                        'article_url': f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        'wiki_lang': lang,
                        'title': r.title,
                        'description': r.description,
                        'involved_users': json.dumps(r.involved_users),
                        'evidence': json.dumps(r.evidence, default=str),
                        'confidence': r.confidence
                    })
        except Exception as e:
            st.warning(f"Fehler bei {title}: {str(e)[:50]}")
        
        time.sleep(0.5)
    
    return cases_found

# ==========================================
# App initialisieren
# ==========================================

st.set_page_config(page_title="Wiki Monitor", page_icon="🔍", layout="wide")
init_db()

# ==========================================
# Sidebar
# ==========================================

st.sidebar.title("🔍 Wiki Monitor")
page = st.sidebar.radio("Navigation", ["📊 Dashboard", "🔍 Scan starten", "📋 Fälle"])

# ==========================================
# Seiten
# ==========================================

if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    
    total = count_cases()
    st.metric("Erkannte Fälle", total)
    
    if total == 0:
        st.warning("⚠️ Noch keine Fälle! Gehe zu **'🔍 Scan starten'**")
    else:
        st.success(f"✅ {total} Fälle in der Datenbank")


elif page == "🔍 Scan starten":
    st.title("🔍 Scan starten")
    
    preset = st.selectbox("Artikel-Set wählen:", [
        "Bekannte kontroverse Themen",
        "Deutsche Politiker",
        "Eigene Auswahl"
    ])
    
    if preset == "Bekannte kontroverse Themen":
        articles_de = ['Adolf Hitler', 'Alternative für Deutschland', 'Klimawandel', 'COVID-19-Pandemie in Deutschland']
        articles_en = ['Donald Trump', 'Climate change', 'COVID-19 pandemic', 'Elon Musk']
    elif preset == "Deutsche Politiker":
        articles_de = ['Angela Merkel', 'Olaf Scholz', 'Friedrich Merz', 'Robert Habeck']
        articles_en = ['Angela Merkel', 'Olaf Scholz']
    else:
        articles_de = st.text_area("Deutsche Artikel (pro Zeile):", "Adolf Hitler\nKlimawandel").split('\n')
        articles_en = st.text_area("Englische Artikel (pro Zeile):", "Donald Trump\nClimate change").split('\n')
        articles_de = [a.strip() for a in articles_de if a.strip()]
        articles_en = [a.strip() for a in articles_en if a.strip()]
    
    st.markdown(f"**{len(articles_de) + len(articles_en)} Artikel werden gescannt**")
    
    if st.button("🚀 Scan starten", type="primary"):
        progress = st.progress(0)
        status = st.empty()
        
        found = run_scan(articles_de, articles_en, progress, status)
        
        status.text("Fertig!")
        if found > 0:
            st.success(f"✅ {found} Fälle gefunden!")
            st.balloons()
        else:
            st.info("Keine Auffälligkeiten gefunden.")


elif page == "📋 Fälle":
    st.title("📋 Erkannte Fälle")
    
    cases = get_all_cases()
    
    if not cases:
        st.warning("Keine Fälle. Führe erst einen Scan durch!")
    else:
        for case in cases:
            sev = case.get('severity', 0) or 0
            emoji = '🔴' if sev >= 7 else '🟡' if sev >= 4 else '🟢'
            
            with st.expander(f"{emoji} [{sev}/10] {case.get('article_title', '?')} - {case.get('case_type', '?')}"):
                st.markdown(f"**Artikel:** [{case.get('article_title')}]({case.get('article_url', '#')})")
                st.markdown(f"**Typ:** {case.get('case_type')}")
                st.markdown(f"**Beschreibung:** {case.get('description', 'Keine')}")
                st.markdown(f"**Sprache:** {case.get('wiki_lang')}")
