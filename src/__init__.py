"""
Wikipedia Manipulation Monitor
==============================
Automatisierte Erkennung von Manipulation und Machtmissbrauch in Wikipedia.
"""

from .config import config
from .database import init_database, get_db_connection, insert_case, get_cases
from .wiki_api import WikipediaAPI, get_wiki_api
from .detectors import ManipulationDetector, run_detection, DetectionResult
from .ai_analyzer import AIAnalyzer, analyze_case_with_ai
from .article_finder import ArticleFinder, populate_watchlist

__version__ = "1.0.0"
__all__ = [
    'config',
    'init_database',
    'get_db_connection', 
    'insert_case',
    'get_cases',
    'WikipediaAPI',
    'get_wiki_api',
    'ManipulationDetector',
    'run_detection',
    'DetectionResult',
    'AIAnalyzer',
    'analyze_case_with_ai',
    'ArticleFinder',
    'populate_watchlist',
]
