"""
Wikipedia Manipulation Monitor - Dashboard
==========================================
Interaktives Web-Dashboard mit Streamlit.
Kostenlos hostbar auf Streamlit Cloud.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os

# Lokale Imports
from src.config import config
from src.database import (
    init_database, 
    get_cases, 
    get_statistics, 
    update_case_status,
    add_watched_article,
    get_watched_articles,
    get_db_connection
)
from src.article_finder import ArticleFinder
from src.wiki_api import get_wiki_api
from src.detectors import ManipulationDetector
from src.ai_analyzer import analyze_case_with_ai

# ==========================================
# Seiten-Konfiguration
# ==========================================

st.set_page_config(
    page_title="Wikipedia Manipulation Monitor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Datenbank initialisieren
init_database()

# ==========================================
# Sidebar - Navigation & Filter
# ==========================================

st.sidebar.title("🔍 Wiki Monitor")
st.sidebar.markdown("---")

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["📊 Dashboard", "📋 Fälle", "➕ Artikel hinzufügen", "📈 Statistiken", "⚙️ Einstellungen"]
)

st.sidebar.markdown("---")

# Globale Filter
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

filter_status = st.sidebar.multiselect(
    "Status",
    options=['neu', 'überprüft', 'bestätigt', 'falsch_positiv', 'archiviert'],
    default=['neu', 'überprüft', 'bestätigt']
)


# ==========================================
# Hilfsfunktionen
# ==========================================

def severity_color(severity: int) -> str:
    """Gibt Farbe für Schweregrad zurück"""
    colors = {
        1: '#90EE90', 2: '#90EE90',
        3: '#FFFF00', 4: '#FFFF00',
        5: '#FFA500', 6: '#FFA500',
        7: '#FF4500', 8: '#FF4500',
        9: '#FF0000', 10: '#8B0000'
    }
    return colors.get(severity, '#808080')


def severity_badge(severity: int) -> str:
    """Erstellt HTML-Badge für Schweregrad"""
    color = severity_color(severity)
    label = config.SEVERITY_LEVELS.get(severity, {}).get('label', '?')
    return f'<span style="background-color:{color}; padding:2px 8px; border-radius:4px; color:black;">{severity}/10 ({label})</span>'


def load_cases_df(min_severity: int = 1, status_filter: list = None, lang_filter: list = None):
    """Lädt Fälle als DataFrame"""
    
    cases = get_cases(limit=500)
    
    if not cases:
        return pd.DataFrame()
    
    df = pd.DataFrame(cases)
    
    # Filter anwenden
    if min_severity > 1:
        df = df[df['severity'] >= min_severity]
    
    if status_filter:
        df = df[df['status'].isin(status_filter)]
    
    if lang_filter:
        df = df[df['wiki_lang'].isin(lang_filter)]
    
    return df


# ==========================================
# Seite: Dashboard
# ==========================================

if page == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.markdown("Übersicht über erkannte Wikipedia-Manipulationen")
    
    # Statistiken laden
    stats = get_statistics()
    
    # KPI-Karten
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Erkannte Fälle",
            stats.get('total_cases', 0),
            delta=f"+{stats.get('new_cases', 0)} neu"
        )
    
    with col2:
        st.metric(
            "Überwachte Artikel",
            stats.get('watched_articles', 0)
        )
    
    with col3:
        critical_count = sum(
            count for sev, count in stats.get('by_severity', {}).items() 
            if sev >= 7
        )
        st.metric(
            "Kritische Fälle",
            critical_count,
            delta="Schweregrad ≥ 7"
        )
    
    with col4:
        st.metric(
            "Sprachen",
            len(stats.get('by_language', {}))
        )
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Fälle nach Schweregrad")
        
        severity_data = stats.get('by_severity', {})
        if severity_data:
            df_sev = pd.DataFrame([
                {'Schweregrad': k, 'Anzahl': v, 'Farbe': severity_color(k)}
                for k, v in sorted(severity_data.items())
            ])
            
            fig = px.bar(
                df_sev, 
                x='Schweregrad', 
                y='Anzahl',
                color='Schweregrad',
                color_continuous_scale='RdYlGn_r'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Noch keine Daten")
    
    with col2:
        st.subheader("Fälle nach Typ")
        
        type_data = stats.get('by_type', {})
        if type_data:
            df_type = pd.DataFrame([
                {'Typ': k, 'Anzahl': v}
                for k, v in type_data.items()
            ])
            
            fig = px.pie(df_type, values='Anzahl', names='Typ', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Noch keine Daten")
    
    # Top-Artikel
    st.subheader("🔥 Top-Artikel mit meisten Auffälligkeiten")
    
    top_articles = stats.get('top_articles', [])
    if top_articles:
        df_top = pd.DataFrame(top_articles)
        df_top['Link'] = df_top.apply(
            lambda row: f"https://{row['wiki_lang']}.wikipedia.org/wiki/{row['article_title'].replace(' ', '_')}", 
            axis=1
        )
        st.dataframe(
            df_top[['article_title', 'wiki_lang', 'case_count', 'max_severity']],
            column_config={
                'article_title': 'Artikel',
                'wiki_lang': 'Sprache',
                'case_count': 'Fälle',
                'max_severity': 'Max. Schwere'
            },
            use_container_width=True
        )
    else:
        st.info("Noch keine Daten vorhanden. Führe einen Scan durch!")


# ==========================================
# Seite: Fälle
# ==========================================

elif page == "📋 Fälle":
    st.title("📋 Erkannte Fälle")
    
    # Fälle laden
    df = load_cases_df(
        min_severity=filter_severity,
        status_filter=filter_status,
        lang_filter=filter_lang
    )
    
    if df.empty:
        st.warning("Keine Fälle gefunden. Passe die Filter an oder führe einen Scan durch.")
    else:
        st.info(f"{len(df)} Fälle gefunden")
        
        # Sortierung
        sort_col = st.selectbox(
            "Sortieren nach",
            options=['severity', 'detected_at', 'ai_conflict_score', 'case_type'],
            format_func=lambda x: {
                'severity': 'Schweregrad',
                'detected_at': 'Datum',
                'ai_conflict_score': 'KI-Konflikt-Score',
                'case_type': 'Typ'
            }.get(x, x)
        )
        
        df = df.sort_values(sort_col, ascending=False)
        
        # Fälle anzeigen
        for idx, row in df.iterrows():
            with st.expander(
                f"{'🔴' if row['severity'] >= 7 else '🟡' if row['severity'] >= 4 else '🟢'} "
                f"[{row['severity']}/10] {row.get('title', row['case_type'])} - {row['article_title']}"
            ):
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**Artikel:** [{row['article_title']}]({row.get('article_url', '#')})")
                    st.markdown(f"**Typ:** {row['case_type']}")
                    st.markdown(f"**Beschreibung:** {row.get('description', 'Keine Beschreibung')}")
                    
                    if row.get('ai_summary'):
                        st.markdown(f"**KI-Zusammenfassung:** {row['ai_summary']}")
                    
                    if row.get('ai_reasoning'):
                        st.markdown(f"**KI-Begründung:** {row['ai_reasoning']}")
                
                with col2:
                    st.markdown(f"**Schweregrad:** {row['severity']}/10")
                    st.markdown(f"**Status:** {row['status']}")
                    st.markdown(f"**Sprache:** {row['wiki_lang']}")
                    
                    if row.get('ai_conflict_score'):
                        st.markdown(f"**Konflikt-Score:** {row['ai_conflict_score']}/10")
                    if row.get('ai_manipulation_score'):
                        st.markdown(f"**Manipulations-Score:** {row['ai_manipulation_score']}/10")
                
                with col3:
                    # Status ändern
                    new_status = st.selectbox(
                        "Status ändern",
                        options=['neu', 'überprüft', 'bestätigt', 'falsch_positiv', 'archiviert'],
                        index=['neu', 'überprüft', 'bestätigt', 'falsch_positiv', 'archiviert'].index(row['status']),
                        key=f"status_{row['id']}"
                    )
                    
                    if new_status != row['status']:
                        if st.button("Speichern", key=f"save_{row['id']}"):
                            update_case_status(row['id'], new_status)
                            st.success("Status aktualisiert!")
                            st.rerun()
                
                # Evidence anzeigen
                if row.get('evidence'):
                    with st.expander("📎 Beweismaterial"):
                        try:
                            evidence = json.loads(row['evidence']) if isinstance(row['evidence'], str) else row['evidence']
                            st.json(evidence)
                        except:
                            st.text(row['evidence'])


# ==========================================
# Seite: Artikel hinzufügen
# ==========================================

elif page == "➕ Artikel hinzufügen":
    st.title("➕ Artikel zur Überwachung hinzufügen")
    
    tab1, tab2 = st.tabs(["🔍 Suchen & Hinzufügen", "📝 Direkt eingeben"])
    
    with tab1:
        st.subheader("Artikel suchen")
        
        search_lang = st.selectbox("Sprache", options=['de', 'en'], key="search_lang")
        search_query = st.text_input("Suchbegriff", placeholder="z.B. 'Angela Merkel' oder 'Klimawandel'")
        
        if st.button("🔍 Suchen") and search_query:
            with st.spinner("Suche läuft..."):
                api = get_wiki_api(search_lang)
                results = api.search_articles(search_query, limit=20)
                
                if results:
                    st.success(f"{len(results)} Artikel gefunden")
                    
                    for title in results:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            url = f"https://{search_lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                            st.markdown(f"[{title}]({url})")
                        with col2:
                            if st.button("➕ Hinzufügen", key=f"add_{title}"):
                                success = add_watched_article(
                                    article_title=title,
                                    wiki_lang=search_lang,
                                    source='manual',
                                    source_detail='Dashboard-Suche',
                                    priority=8
                                )
                                if success:
                                    st.success(f"'{title}' hinzugefügt!")
                                else:
                                    st.info("Artikel bereits in Watchlist")
                else:
                    st.warning("Keine Artikel gefunden")
    
    with tab2:
        st.subheader("Artikel direkt eingeben")
        
        direct_lang = st.selectbox("Sprache", options=['de', 'en'], key="direct_lang")
        direct_title = st.text_input("Exakter Artikelname", placeholder="z.B. 'Angela Merkel'")
        direct_reason = st.text_input("Grund (optional)", placeholder="z.B. 'Verdacht auf bezahlte Bearbeitung'")
        
        if st.button("➕ Zur Watchlist hinzufügen") and direct_title:
            with st.spinner("Prüfe Artikel..."):
                api = get_wiki_api(direct_lang)
                info = api.get_article_info(direct_title)
                
                if info:
                    success = add_watched_article(
                        article_title=direct_title,
                        wiki_lang=direct_lang,
                        source='manual',
                        source_detail=direct_reason or 'Manuell hinzugefügt',
                        priority=8
                    )
                    if success:
                        st.success(f"'{direct_title}' zur Watchlist hinzugefügt!")
                        
                        # Sofort analysieren?
                        if st.button("🔍 Jetzt analysieren"):
                            with st.spinner("Analysiere..."):
                                detector = ManipulationDetector(api)
                                results = detector.analyze_article(direct_title)
                                
                                if results:
                                    st.warning(f"⚠ {len(results)} mögliche Probleme gefunden!")
                                    for r in results:
                                        st.write(f"- **{r.case_type}**: {r.description}")
                                else:
                                    st.success("✓ Keine Auffälligkeiten gefunden")
                    else:
                        st.info("Artikel bereits in Watchlist")
                else:
                    st.error(f"Artikel '{direct_title}' nicht gefunden. Prüfe die Schreibweise.")


# ==========================================
# Seite: Statistiken
# ==========================================

elif page == "📈 Statistiken":
    st.title("📈 Detaillierte Statistiken")
    
    stats = get_statistics()
    df = load_cases_df()
    
    # Zeitliche Entwicklung
    st.subheader("📅 Zeitliche Entwicklung")
    
    if not df.empty and 'detected_at' in df.columns:
        df['date'] = pd.to_datetime(df['detected_at']).dt.date
        daily_counts = df.groupby('date').size().reset_index(name='count')
        
        fig = px.line(daily_counts, x='date', y='count', markers=True)
        fig.update_layout(xaxis_title="Datum", yaxis_title="Neue Fälle")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nicht genügend Daten für Zeitverlauf")
    
    # Heatmap: Typ vs Schweregrad
    st.subheader("🗺️ Heatmap: Typ vs Schweregrad")
    
    if not df.empty:
        heatmap_data = df.groupby(['case_type', 'severity']).size().unstack(fill_value=0)
        
        fig = px.imshow(
            heatmap_data.values,
            labels=dict(x="Schweregrad", y="Falltyp", color="Anzahl"),
            x=heatmap_data.columns.tolist(),
            y=heatmap_data.index.tolist(),
            color_continuous_scale='YlOrRd'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Watchlist-Statistiken
    st.subheader("📋 Watchlist")
    
    watched = get_watched_articles(limit=1000)
    if watched:
        df_watched = pd.DataFrame(watched)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Artikel in Watchlist", len(df_watched))
            
            # Nach Quelle
            if 'source' in df_watched.columns:
                source_counts = df_watched['source'].value_counts()
                fig = px.pie(values=source_counts.values, names=source_counts.index, title="Nach Quelle")
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Nach Sprache
            if 'wiki_lang' in df_watched.columns:
                lang_counts = df_watched['wiki_lang'].value_counts()
                fig = px.bar(x=lang_counts.index, y=lang_counts.values, title="Nach Sprache")
                st.plotly_chart(fig, use_container_width=True)


# ==========================================
# Seite: Einstellungen
# ==========================================

elif page == "⚙️ Einstellungen":
    st.title("⚙️ Einstellungen")
    
    st.subheader("🔑 API-Konfiguration")
    
    hf_token = os.environ.get('HF_API_TOKEN', '')
    st.text_input(
        "Hugging Face API Token",
        value="*" * len(hf_token) if hf_token else "",
        disabled=True,
        help="Wird über GitHub Secrets konfiguriert"
    )
    
    if hf_token:
        st.success("✓ Hugging Face Token konfiguriert")
    else:
        st.warning("⚠ Kein Hugging Face Token. KI-Analyse eingeschränkt.")
    
    st.markdown("---")
    
    st.subheader("📊 Aktuelle Konfiguration")
    
    config_df = pd.DataFrame([
        {"Einstellung": "Max. Artikel", "Wert": config.MAX_ARTICLES},
        {"Einstellung": "Artikel pro Scan", "Wert": config.ARTICLES_PER_RUN},
        {"Einstellung": "Historie (Jahre)", "Wert": config.HISTORY_YEARS},
        {"Einstellung": "Revert-Schwelle", "Wert": config.REVERT_THRESHOLD},
        {"Einstellung": "Sprachen", "Wert": ", ".join(config.ENABLED_LANGUAGES)},
    ])
    
    st.table(config_df)
    
    st.markdown("---")
    
    st.subheader("🔄 Manuelle Aktionen")
    
    if st.button("🗑️ Datenbank zurücksetzen", type="secondary"):
        if st.checkbox("Ja, ich bin sicher"):
            os.remove(config.DB_PATH) if os.path.exists(config.DB_PATH) else None
            init_database()
            st.success("Datenbank wurde zurückgesetzt!")
            st.rerun()


# ==========================================
# Footer
# ==========================================

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <small>
    Wikipedia Manipulation Monitor v1.0<br>
    Entwickelt für Transparenz & Integrität
    </small>
    """,
    unsafe_allow_html=True
)
