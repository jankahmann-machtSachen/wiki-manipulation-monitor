"""
Wikipedia Manipulation Monitor - Dashboard
==========================================
MIT EINGEBAUTEM SCAN-BUTTON
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import time
from datetime import datetime

# Lokale Imports
from src.config import config
from src.database import (
    init_database, 
    get_cases, 
    get_statistics, 
    update_case_status,
    add_watched_article,
    get_watched_articles,
    insert_case
)

# Datenbank initialisieren
init_database()

# ==========================================
# Seiten-Konfiguration
# ==========================================

st.set_page_config(
    page_title="Wikipedia Manipulation Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Sidebar - Navigation
# ==========================================

st.sidebar.title("🔍 Wiki Monitor")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "🔍 Scan starten", "📋 Fälle", "➕ Artikel hinzufügen", "📈 Statistiken"]
)

st.sidebar.markdown("---")

# Filter
st.sidebar.subheader("Filter")
filter_lang = st.sidebar.multiselect(
    "Sprache",
    options=['de', 'en'],
    default=['de', 'en']
)

filter_severity = st.sidebar.slider(
    "Min. Schweregrad",
    min_value=1,
    max_value=10,
    value=1
)

# ==========================================
# Hilfsfunktionen
# ==========================================

def load_cases_df():
    cases = get_cases(limit=500)
    if not cases:
        return pd.DataFrame()
    df = pd.DataFrame(cases)
    if 'severity' in df.columns:
        df = df[df['severity'] >= filter_severity]
    if 'wiki_lang' in df.columns and filter_lang:
        df = df[df['wiki_lang'].isin(filter_lang)]
    return df


def run_quick_scan(articles_de, articles_en, progress_bar, status_text):
    """Führt einen Scan der angegebenen Artikel durch"""
    
    from src.wiki_api import get_wiki_api
    from src.detectors import ManipulationDetector
    
    total_articles = len(articles_de) + len(articles_en)
    current = 0
    cases_found = 0
    
    all_articles = [('de', a) for a in articles_de] + [('en', a) for a in articles_en]
    
    for lang, title in all_articles:
        current += 1
        progress = current / total_articles
        progress_bar.progress(progress)
        status_text.text(f"Analysiere [{current}/{total_articles}]: {title}")
        
        try:
            api = get_wiki_api(lang)
            detector = ManipulationDetector(api)
            results = detector.analyze_article(title)
            
            if results:
                cases_found += len(results)
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
                    
        except Exception as e:
            st.warning(f"Fehler bei {title}: {e}")
        
        time.sleep(0.5)  # Rate limiting
    
    return cases_found


# ==========================================
# Seite: Dashboard
# ==========================================

if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    
    stats = get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Erkannte Fälle", stats.get('total_cases', 0))
    with col2:
        st.metric("Neue Fälle", stats.get('new_cases', 0))
    with col3:
        st.metric("Überwachte Artikel", stats.get('watched_articles', 0))
    with col4:
        critical = sum(c for s, c in stats.get('by_severity', {}).items() if s and s >= 7)
        st.metric("Kritisch (≥7)", critical)
    
    st.markdown("---")
    
    if stats.get('total_cases', 0) == 0:
        st.warning("⚠️ Noch keine Fälle in der Datenbank! Gehe zu **'🔍 Scan starten'** um den ersten Scan durchzuführen.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Nach Schweregrad")
            severity_data = stats.get('by_severity', {})
            if severity_data:
                df_sev = pd.DataFrame([
                    {'Schweregrad': k, 'Anzahl': v}
                    for k, v in sorted(severity_data.items()) if k
                ])
                fig = px.bar(df_sev, x='Schweregrad', y='Anzahl', color='Schweregrad',
                            color_continuous_scale='RdYlGn_r')
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Nach Typ")
            type_data = stats.get('by_type', {})
            if type_data:
                df_type = pd.DataFrame([
                    {'Typ': k, 'Anzahl': v} for k, v in type_data.items()
                ])
                fig = px.pie(df_type, values='Anzahl', names='Typ', hole=0.4)
                st.plotly_chart(fig, use_container_width=True)


# ==========================================
# Seite: Scan starten (NEU!)
# ==========================================

elif page == "🔍 Scan starten":
    st.title("🔍 Scan starten")
    st.markdown("Analysiere Wikipedia-Artikel auf Manipulation und Konflikte.")
    
    st.markdown("---")
    
    # Vordefinierte Artikel-Sets
    st.subheader("📦 Vordefinierte Artikel-Sets")
    
    preset = st.selectbox(
        "Wähle ein Set:",
        [
            "Bekannte kontroverse Themen (10 Artikel)",
            "Deutsche Politiker (10 Artikel)", 
            "US-Politik (10 Artikel)",
            "Wissenschaft & Kontroversen (10 Artikel)",
            "Eigene Auswahl"
        ]
    )
    
    # Artikel basierend auf Auswahl
    if preset == "Bekannte kontroverse Themen (10 Artikel)":
        articles_de = ['Adolf Hitler', 'Alternative für Deutschland', 'COVID-19-Pandemie in Deutschland', 
                       'Klimawandel', 'Russisch-Ukrainischer Krieg']
        articles_en = ['Donald Trump', 'Climate change', 'COVID-19 pandemic', 
                       'Vladimir Putin', 'Elon Musk']
    
    elif preset == "Deutsche Politiker (10 Artikel)":
        articles_de = ['Angela Merkel', 'Olaf Scholz', 'Friedrich Merz', 
                       'Robert Habeck', 'Christian Lindner']
        articles_en = ['Angela Merkel', 'Olaf Scholz', 'German government',
                       'Bundestag', 'German federal election']
    
    elif preset == "US-Politik (10 Artikel)":
        articles_de = ['Joe Biden', 'Donald Trump', 'Präsidentschaftswahl in den Vereinigten Staaten 2024']
        articles_en = ['Joe Biden', 'Donald Trump', 'Kamala Harris',
                       '2024 United States presidential election', 'January 6 United States Capitol attack',
                       'Republican Party (United States)', 'Democratic Party (United States)']
    
    elif preset == "Wissenschaft & Kontroversen (10 Artikel)":
        articles_de = ['Klimawandel', 'Impfung', 'Homöopathie', 'Gentechnik', 'Kernenergie']
        articles_en = ['Climate change', 'Vaccination', 'Homeopathy', 'GMO', 'Nuclear power']
    
    else:  # Eigene Auswahl
        st.markdown("**Deutsche Wikipedia:**")
        articles_de_input = st.text_area(
            "Artikel (einer pro Zeile):",
            "Adolf Hitler\nKlimawandel\nCOVID-19-Pandemie in Deutschland",
            height=100,
            key="de_articles"
        )
        articles_de = [a.strip() for a in articles_de_input.split('\n') if a.strip()]
        
        st.markdown("**Englische Wikipedia:**")
        articles_en_input = st.text_area(
            "Artikel (einer pro Zeile):",
            "Donald Trump\nClimate change\nCOVID-19 pandemic",
            height=100,
            key="en_articles"
        )
        articles_en = [a.strip() for a in articles_en_input.split('\n') if a.strip()]
    
    # Vorschau
    st.markdown("---")
    st.subheader("📋 Zu scannende Artikel")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🇩🇪 Deutsche Wikipedia:**")
        for a in articles_de:
            st.markdown(f"- {a}")
    with col2:
        st.markdown("**🇬🇧 Englische Wikipedia:**")
        for a in articles_en:
            st.markdown(f"- {a}")
    
    st.markdown(f"**Gesamt: {len(articles_de) + len(articles_en)} Artikel**")
    
    # Scan starten
    st.markdown("---")
    
    if st.button("🚀 Scan starten", type="primary", use_container_width=True):
        st.markdown("---")
        st.subheader("⏳ Scan läuft...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        cases_found = run_quick_scan(articles_de, articles_en, progress_bar, status_text)
        
        progress_bar.progress(1.0)
        status_text.text("Fertig!")
        
        if cases_found > 0:
            st.success(f"✅ Scan abgeschlossen! **{cases_found} Fälle** gefunden.")
            st.balloons()
        else:
            st.info("✅ Scan abgeschlossen. Keine Auffälligkeiten gefunden.")
        
        st.markdown("👉 Gehe zu **'📋 Fälle'** um die Ergebnisse zu sehen.")


# ==========================================
# Seite: Fälle
# ==========================================

elif page == "📋 Fälle":
    st.title("📋 Erkannte Fälle")
    
    df = load_cases_df()
    
    if df.empty:
        st.warning("Keine Fälle gefunden. Führe zuerst einen Scan durch!")
    else:
        st.info(f"{len(df)} Fälle gefunden")
        
        # Sortierung
        sort_col = st.selectbox(
            "Sortieren nach",
            options=['severity', 'detected_at', 'case_type'],
            format_func=lambda x: {'severity': 'Schweregrad', 'detected_at': 'Datum', 'case_type': 'Typ'}.get(x, x)
        )
        
        df = df.sort_values(sort_col, ascending=False)
        
        for idx, row in df.iterrows():
            severity = row.get('severity', 0) or 0
            emoji = '🔴' if severity >= 7 else '🟡' if severity >= 4 else '🟢'
            title = row.get('title', row.get('case_type', 'Unbekannt'))
            
            with st.expander(f"{emoji} [{severity}/10] {title} - {row.get('article_title', 'Unbekannt')}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Artikel:** [{row.get('article_title', 'N/A')}]({row.get('article_url', '#')})")
                    st.markdown(f"**Typ:** {row.get('case_type', 'N/A')}")
                    st.markdown(f"**Beschreibung:** {row.get('description', 'Keine')}")
                
                with col2:
                    st.markdown(f"**Schweregrad:** {severity}/10")
                    st.markdown(f"**Sprache:** {row.get('wiki_lang', 'N/A')}")
                    st.markdown(f"**Status:** {row.get('status', 'neu')}")


# ==========================================
# Seite: Artikel hinzufügen
# ==========================================

elif page == "➕ Artikel hinzufügen":
    st.title("➕ Artikel hinzufügen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        article_title = st.text_input("Artikel-Name", placeholder="z.B. Angela Merkel")
    
    with col2:
        article_lang = st.selectbox("Sprache", ['de', 'en'])
    
    if st.button("Hinzufügen"):
        if article_title:
            success = add_watched_article(
                article_title=article_title,
                wiki_lang=article_lang,
                source='manual',
                priority=8
            )
            if success:
                st.success(f"'{article_title}' hinzugefügt!")
            else:
                st.info("Artikel bereits in der Liste")
        else:
            st.warning("Bitte Artikel-Namen eingeben")


# ==========================================
# Seite: Statistiken
# ==========================================

elif page == "📈 Statistiken":
    st.title("📈 Statistiken")
    
    stats = get_statistics()
    df = load_cases_df()
    
    st.subheader("📊 Übersicht")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Gesamt Fälle", stats.get('total_cases', 0))
    with col2:
        st.metric("Neue Fälle", stats.get('new_cases', 0))
    with col3:
        st.metric("Überwachte Artikel", stats.get('watched_articles', 0))
    
    if not df.empty:
        st.markdown("---")
        st.subheader("Top Artikel")
        
        top = stats.get('top_articles', [])
        if top:
            st.dataframe(pd.DataFrame(top))


# ==========================================
# Footer
# ==========================================

st.sidebar.markdown("---")
st.sidebar.markdown("*Wikipedia Manipulation Monitor v1.0*")
