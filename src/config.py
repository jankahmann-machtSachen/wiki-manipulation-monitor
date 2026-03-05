"""
Konfiguration für den Wikipedia Manipulation Monitor
=====================================================
OPTIMIERTE VERSION - Schnellere Scans
"""

import os
from dataclasses import dataclass
from typing import List

@dataclass
class Config:
    """Zentrale Konfiguration - OPTIMIERT für schnelle Scans"""
    
    # ========== DATENBANK ==========
    DB_PATH: str = "data/wiki_monitor.db"
    
    # ========== WIKIPEDIA APIs ==========
    WIKI_APIS: dict = None
    USER_AGENT: str = "WikiManipulationMonitor/1.0 (Educational Research)"
    
    # Aktivierte Sprachen
    ENABLED_LANGUAGES: List[str] = None
    
    # ========== HUGGING FACE KI ==========
    HF_API_TOKEN: str = None
    HF_MODEL: str = "facebook/bart-large-mnli"
    
    # ========== ERKENNUNGS-SCHWELLENWERTE ==========
    REVERT_THRESHOLD: int = 3
    REVERT_WINDOW_HOURS: int = 48
    HISTORY_YEARS: int = 5
    COORDINATION_WINDOW_MINUTES: int = 15
    COORDINATION_MIN_USERS: int = 3
    SPA_RATIO: float = 0.75
    SPA_MIN_EDITS: int = 10
    LARGE_DELETION_CHARS: int = 2000
    ADMIN_BLOCK_THRESHOLD: int = 3
    
    # ========== OPTIMIERTE LIMITS ==========
    MAX_ARTICLES: int = 100          # Reduziert von 500
    ARTICLES_PER_RUN: int = 20       # Reduziert von 50
    MAX_REVISIONS_PER_ARTICLE: int = 200  # NEU: Limit für Revisionen
    API_DELAY_SECONDS: float = 0.5   # NEU: Pause zwischen API-Calls
    
    # ========== SCHWEREGRAD-DEFINITIONEN ==========
    SEVERITY_LEVELS: dict = None
    
    def __post_init__(self):
        """Initialisiert komplexe Standardwerte"""
        
        self.WIKI_APIS = {
            'de': 'https://de.wikipedia.org/w/api.php',
            'en': 'https://en.wikipedia.org/w/api.php',
        }
        
        if self.ENABLED_LANGUAGES is None:
            self.ENABLED_LANGUAGES = ['de', 'en']
        
        if self.HF_API_TOKEN is None:
            self.HF_API_TOKEN = os.environ.get('HF_API_TOKEN', '')
        
        self.SEVERITY_LEVELS = {
            1: {'label': 'minimal', 'color': '#90EE90'},
            2: {'label': 'minimal', 'color': '#90EE90'},
            3: {'label': 'niedrig', 'color': '#FFFF00'},
            4: {'label': 'niedrig', 'color': '#FFFF00'},
            5: {'label': 'mittel', 'color': '#FFA500'},
            6: {'label': 'mittel', 'color': '#FFA500'},
            7: {'label': 'hoch', 'color': '#FF4500'},
            8: {'label': 'hoch', 'color': '#FF4500'},
            9: {'label': 'kritisch', 'color': '#FF0000'},
            10: {'label': 'kritisch', 'color': '#8B0000'},
        }


config = Config()
