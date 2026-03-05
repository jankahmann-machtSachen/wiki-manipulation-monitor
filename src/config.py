"""
Konfiguration für den Wikipedia Manipulation Monitor
=====================================================
"""

import os
from dataclasses import dataclass
from typing import List

@dataclass
class Config:
    """Zentrale Konfiguration - hier kannst du alles anpassen"""
    
    # ========== DATENBANK ==========
    DB_PATH: str = "data/wiki_monitor.db"
    
    # ========== WIKIPEDIA APIs ==========
    WIKI_APIS: dict = None  # Wird in __post_init__ gesetzt
    USER_AGENT: str = "WikiManipulationMonitor/1.0 (Educational Research; Contact: github.com/dein-username)"
    
    # Aktivierte Sprachen
    ENABLED_LANGUAGES: List[str] = None
    
    # ========== HUGGING FACE KI ==========
    HF_API_TOKEN: str = None  # Wird aus Umgebungsvariable geladen
    HF_MODEL: str = "facebook/bart-large-mnli"  # Kostenlos, gut für Klassifikation
    
    # ========== ERKENNUNGS-SCHWELLENWERTE ==========
    
    # Edit War Erkennung
    REVERT_THRESHOLD: int = 3           # Min. Reverts für Edit-War
    REVERT_WINDOW_HOURS: int = 48       # Zeitfenster für Revert-Zählung
    
    # Historische Analyse
    HISTORY_YEARS: int = 5              # Wie weit zurück analysieren
    
    # Koordinierte Bearbeitung (Sockpuppet-Verdacht)
    COORDINATION_WINDOW_MINUTES: int = 15
    COORDINATION_MIN_USERS: int = 3
    
    # Single Purpose Account
    SPA_RATIO: float = 0.75             # 75%+ Edits auf einem Artikel = verdächtig
    SPA_MIN_EDITS: int = 10             # Mindestens 10 Edits für SPA-Check
    
    # Große Löschungen
    LARGE_DELETION_CHARS: int = 2000    # Zeichen
    
    # Admin-Missbrauch
    ADMIN_BLOCK_THRESHOLD: int = 3      # Admin blockt 3+ User im selben Konflikt
    
    # ========== ARTIKEL-LIMITS ==========
    MAX_ARTICLES: int = 500             # Maximale Artikel-Anzahl
    ARTICLES_PER_RUN: int = 50          # Pro Durchlauf analysieren
    
    # ========== SCHWEREGRAD-DEFINITIONEN ==========
    SEVERITY_LEVELS: dict = None  # Wird in __post_init__ gesetzt
    
    def __post_init__(self):
        """Initialisiert komplexe Standardwerte"""
        
        # Wikipedia APIs für verschiedene Sprachen
        self.WIKI_APIS = {
            'de': 'https://de.wikipedia.org/w/api.php',
            'en': 'https://en.wikipedia.org/w/api.php',
        }
        
        # Aktivierte Sprachen
        if self.ENABLED_LANGUAGES is None:
            self.ENABLED_LANGUAGES = ['de', 'en']
        
        # API Token aus Umgebungsvariable
        if self.HF_API_TOKEN is None:
            self.HF_API_TOKEN = os.environ.get('HF_API_TOKEN', '')
        
        # Schweregrad-Definitionen
        self.SEVERITY_LEVELS = {
            1: {'label': 'minimal', 'color': '#90EE90', 'description': 'Kaum relevant'},
            2: {'label': 'minimal', 'color': '#90EE90', 'description': 'Sehr geringfügig'},
            3: {'label': 'niedrig', 'color': '#FFFF00', 'description': 'Geringfügiger Konflikt'},
            4: {'label': 'niedrig', 'color': '#FFFF00', 'description': 'Kleiner Konflikt'},
            5: {'label': 'mittel', 'color': '#FFA500', 'description': 'Moderater Konflikt'},
            6: {'label': 'mittel', 'color': '#FFA500', 'description': 'Deutlicher Konflikt'},
            7: {'label': 'hoch', 'color': '#FF4500', 'description': 'Ernsthafter Konflikt'},
            8: {'label': 'hoch', 'color': '#FF4500', 'description': 'Schwerer Konflikt'},
            9: {'label': 'kritisch', 'color': '#FF0000', 'description': 'Sehr schwerer Fall'},
            10: {'label': 'kritisch', 'color': '#8B0000', 'description': 'Extremer Missbrauch'},
        }


# Globale Instanz
config = Config()
