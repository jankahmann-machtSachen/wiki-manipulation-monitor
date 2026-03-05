"""
Datenbank-Modul für den Wikipedia Manipulation Monitor
=======================================================
Erstellt und verwaltet die SQLite-Datenbank.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from .config import config


def get_db_connection() -> sqlite3.Connection:
    """Erstellt eine Datenbankverbindung mit Row-Factory"""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database() -> None:
    """Initialisiert alle Datenbank-Tabellen"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ==========================================
    # TABELLE 1: Erkannte Fälle (Haupttabelle)
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- Zeitstempel
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            incident_start TIMESTAMP,
            incident_end TIMESTAMP,
            
            -- Klassifizierung
            case_type TEXT NOT NULL,
            severity INTEGER CHECK(severity BETWEEN 1 AND 10),
            severity_label TEXT,
            confidence REAL CHECK(confidence BETWEEN 0 AND 1),
            
            -- Artikel-Info
            article_title TEXT NOT NULL,
            article_id INTEGER,
            article_url TEXT,
            wiki_lang TEXT DEFAULT 'de',
            
            -- Beteiligte Nutzer
            involved_users TEXT,  -- JSON-Array
            primary_aggressor TEXT,
            victim_users TEXT,  -- JSON-Array
            admin_involved TEXT,
            
            -- Statistiken
            total_edits INTEGER DEFAULT 0,
            total_reverts INTEGER DEFAULT 0,
            edit_war_rounds INTEGER DEFAULT 0,
            
            -- Beschreibung
            title TEXT,
            description TEXT,
            evidence TEXT,  -- JSON
            
            -- Diskussionsseite
            talk_page_url TEXT,
            talk_page_excerpt TEXT,
            
            -- KI-Analyse
            ai_summary TEXT,
            ai_conflict_score REAL,
            ai_manipulation_score REAL,
            ai_power_abuse_score REAL,
            ai_reasoning TEXT,
            
            -- Status
            status TEXT DEFAULT 'neu',
            is_false_positive BOOLEAN DEFAULT FALSE,
            reviewer_notes TEXT,
            reviewed_at TIMESTAMP,
            
            -- Duplikat-Erkennung
            fingerprint TEXT UNIQUE
        )
    """)
    
    # ==========================================
    # TABELLE 2: Überwachte Artikel
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watched_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            article_title TEXT NOT NULL,
            article_id INTEGER,
            wiki_lang TEXT DEFAULT 'de',
            article_url TEXT,
            
            -- Quelle
            source TEXT,  -- 'manual', 'category', 'wikipedia_list', 'auto_detected'
            source_detail TEXT,
            
            -- Timing
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checked TIMESTAMP,
            last_incident TIMESTAMP,
            
            -- Priorität
            priority INTEGER DEFAULT 5,
            is_active BOOLEAN DEFAULT TRUE,
            
            -- Statistiken
            total_cases_found INTEGER DEFAULT 0,
            current_conflict_level INTEGER DEFAULT 0,
            
            UNIQUE(article_title, wiki_lang)
        )
    """)
    
    # ==========================================
    # TABELLE 3: Nutzer-Profile
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            username TEXT NOT NULL,
            wiki_lang TEXT DEFAULT 'de',
            
            -- Account-Info
            user_id INTEGER,
            registration_date TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            is_bot BOOLEAN DEFAULT FALSE,
            
            -- Statistiken
            total_edits_tracked INTEGER DEFAULT 0,
            total_reverts_made INTEGER DEFAULT 0,
            total_reverts_received INTEGER DEFAULT 0,
            articles_edited INTEGER DEFAULT 0,
            
            -- Verdachts-Scores
            spa_score REAL DEFAULT 0,  -- Single Purpose Account Score
            conflict_score REAL DEFAULT 0,
            
            -- Tracking
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP,
            cases_involved INTEGER DEFAULT 0,
            
            UNIQUE(username, wiki_lang)
        )
    """)
    
    # ==========================================
    # TABELLE 4: Edit-Historie (Detail-Daten)
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            revision_id INTEGER,
            parent_id INTEGER,
            
            article_title TEXT,
            wiki_lang TEXT DEFAULT 'de',
            
            timestamp TIMESTAMP,
            username TEXT,
            user_id INTEGER,
            
            comment TEXT,
            size_before INTEGER,
            size_after INTEGER,
            size_diff INTEGER,
            
            is_revert BOOLEAN DEFAULT FALSE,
            is_minor BOOLEAN DEFAULT FALSE,
            tags TEXT,  -- JSON-Array
            
            -- Verknüpfung zu Fällen
            case_id INTEGER,
            
            UNIQUE(revision_id, wiki_lang)
        )
    """)
    
    # ==========================================
    # TABELLE 5: Analyse-Log
    # ==========================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            
            articles_checked INTEGER DEFAULT 0,
            cases_found INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            
            log_messages TEXT  -- JSON-Array
        )
    """)
    
    # ==========================================
    # INDIZES für schnelle Suche
    # ==========================================
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_severity ON cases(severity DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_type ON cases(case_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_article ON cases(article_title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_date ON cases(detected_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_watched_active ON watched_articles(is_active)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_conflict ON user_profiles(conflict_score DESC)")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Datenbank initialisiert: {config.DB_PATH}")


# ==========================================
# CRUD-Funktionen für Fälle
# ==========================================

def insert_case(case_data: Dict[str, Any]) -> int:
    """Fügt einen neuen Fall ein und gibt die ID zurück"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # JSON-Felder konvertieren
    for field in ['involved_users', 'victim_users', 'evidence']:
        if field in case_data and isinstance(case_data[field], (list, dict)):
            case_data[field] = json.dumps(case_data[field], ensure_ascii=False)
    
    # Fingerprint für Duplikat-Erkennung
    fingerprint = f"{case_data.get('article_title')}_{case_data.get('case_type')}_{case_data.get('incident_start')}"
    case_data['fingerprint'] = fingerprint
    
    columns = ', '.join(case_data.keys())
    placeholders = ', '.join(['?' for _ in case_data])
    
    try:
        cursor.execute(
            f"INSERT OR IGNORE INTO cases ({columns}) VALUES ({placeholders})",
            list(case_data.values())
        )
        conn.commit()
        case_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # Duplikat gefunden
        case_id = 0
    finally:
        conn.close()
    
    return case_id


def get_cases(
    status: Optional[str] = None,
    min_severity: Optional[int] = None,
    case_type: Optional[str] = None,
    wiki_lang: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = 'severity DESC, detected_at DESC'
) -> List[Dict]:
    """Holt Fälle mit optionalen Filtern"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM cases WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if min_severity:
        query += " AND severity >= ?"
        params.append(min_severity)
    
    if case_type:
        query += " AND case_type = ?"
        params.append(case_type)
    
    if wiki_lang:
        query += " AND wiki_lang = ?"
        params.append(wiki_lang)
    
    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def update_case_status(case_id: int, status: str, notes: str = None) -> bool:
    """Aktualisiert den Status eines Falls"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE cases 
        SET status = ?, reviewer_notes = ?, reviewed_at = ?
        WHERE id = ?
    """, (status, notes, datetime.now().isoformat(), case_id))
    
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    
    return success


# ==========================================
# CRUD-Funktionen für Artikel-Watchlist
# ==========================================

def add_watched_article(
    article_title: str,
    wiki_lang: str = 'de',
    source: str = 'manual',
    source_detail: str = None,
    priority: int = 5
) -> bool:
    """Fügt einen Artikel zur Watchlist hinzu"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    article_url = f"https://{wiki_lang}.wikipedia.org/wiki/{article_title.replace(' ', '_')}"
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO watched_articles 
            (article_title, wiki_lang, article_url, source, source_detail, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (article_title, wiki_lang, article_url, source, source_detail, priority))
        conn.commit()
        success = cursor.rowcount > 0
    except:
        success = False
    finally:
        conn.close()
    
    return success


def get_watched_articles(
    wiki_lang: Optional[str] = None,
    is_active: bool = True,
    limit: int = 500
) -> List[Dict]:
    """Holt alle überwachten Artikel"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM watched_articles WHERE is_active = ?"
    params = [is_active]
    
    if wiki_lang:
        query += " AND wiki_lang = ?"
        params.append(wiki_lang)
    
    query += " ORDER BY priority DESC, last_checked ASC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# ==========================================
# Statistik-Funktionen
# ==========================================

def get_statistics() -> Dict[str, Any]:
    """Erstellt eine Übersicht der Datenbank-Statistiken"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Gesamtzahlen
    cursor.execute("SELECT COUNT(*) FROM cases")
    stats['total_cases'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'neu'")
    stats['new_cases'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM watched_articles WHERE is_active = TRUE")
    stats['watched_articles'] = cursor.fetchone()[0]
    
    # Nach Schweregrad
    cursor.execute("""
        SELECT severity, COUNT(*) as count 
        FROM cases 
        GROUP BY severity 
        ORDER BY severity DESC
    """)
    stats['by_severity'] = {row['severity']: row['count'] for row in cursor.fetchall()}
    
    # Nach Typ
    cursor.execute("""
        SELECT case_type, COUNT(*) as count 
        FROM cases 
        GROUP BY case_type 
        ORDER BY count DESC
    """)
    stats['by_type'] = {row['case_type']: row['count'] for row in cursor.fetchall()}
    
    # Nach Sprache
    cursor.execute("""
        SELECT wiki_lang, COUNT(*) as count 
        FROM cases 
        GROUP BY wiki_lang
    """)
    stats['by_language'] = {row['wiki_lang']: row['count'] for row in cursor.fetchall()}
    
    # Top-Artikel mit meisten Fällen
    cursor.execute("""
        SELECT article_title, wiki_lang, COUNT(*) as case_count, MAX(severity) as max_severity
        FROM cases 
        GROUP BY article_title, wiki_lang 
        ORDER BY case_count DESC 
        LIMIT 10
    """)
    stats['top_articles'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return stats


# Datenbank beim Import initialisieren
if __name__ == "__main__":
    init_database()
