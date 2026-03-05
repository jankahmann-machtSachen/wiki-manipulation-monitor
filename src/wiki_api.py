"""
Wikipedia API Client
====================
Kommuniziert mit der Wikipedia API für verschiedene Sprachversionen.
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .config import config


class WikipediaAPI:
    """Client für Wikipedia API Anfragen"""
    
    def __init__(self, lang: str = 'de'):
        self.lang = lang
        self.api_url = config.WIKI_APIS.get(lang, config.WIKI_APIS['de'])
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })
        self._last_request = 0
    
    def _rate_limit(self):
        """Einfaches Rate-Limiting: Max 1 Request pro Sekunde"""
        elapsed = time.time() - self._last_request
        if elapsed < 1:
            time.sleep(1 - elapsed)
        self._last_request = time.time()
    
    def _make_request(self, params: dict) -> dict:
        """Führt eine API-Anfrage durch"""
        self._rate_limit()
        params['format'] = 'json'
        
        try:
            response = self.session.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"API-Fehler: {e}")
            return {}
    
    # ==========================================
    # Artikel-Informationen
    # ==========================================
    
    def get_article_info(self, title: str) -> Optional[Dict]:
        """Holt Basis-Informationen über einen Artikel"""
        
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'info|pageprops',
            'inprop': 'protection|watchers'
        }
        
        data = self._make_request(params)
        pages = data.get('query', {}).get('pages', {})
        
        for page_id, page_data in pages.items():
            if page_id != '-1':
                return {
                    'page_id': int(page_id),
                    'title': page_data.get('title'),
                    'protection': page_data.get('protection', []),
                    'watchers': page_data.get('watchers', 0),
                    'is_protected': len(page_data.get('protection', [])) > 0
                }
        return None
    
    # ==========================================
    # Versionsgeschichte
    # ==========================================
    
    def get_revisions(
        self, 
        title: str, 
        limit: int = 500,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict]:
        """
        Holt die Versionsgeschichte eines Artikels.
        Für historische Analyse: start_date und end_date setzen.
        """
        
        all_revisions = []
        continue_token = None
        
        # Standard: Letzte 5 Jahre
        if start_date is None:
            start_date = datetime.now() - timedelta(days=365 * config.HISTORY_YEARS)
        
        while len(all_revisions) < limit:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'revisions',
                'rvprop': 'ids|timestamp|user|userid|comment|size|tags|flags',
                'rvlimit': min(500, limit - len(all_revisions)),  # Max 500 pro Request
                'rvdir': 'older'  # Neueste zuerst
            }
            
            if start_date:
                params['rvstart'] = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            if end_date:
                params['rvend'] = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            if continue_token:
                params['rvcontinue'] = continue_token
            
            data = self._make_request(params)
            
            pages = data.get('query', {}).get('pages', {})
            for page_id, page_data in pages.items():
                if page_id != '-1':
                    revisions = page_data.get('revisions', [])
                    all_revisions.extend(revisions)
            
            # Prüfe auf Fortsetzung
            if 'continue' in data:
                continue_token = data['continue'].get('rvcontinue')
            else:
                break
        
        # Berechne size_diff für jede Revision
        for i, rev in enumerate(all_revisions):
            rev['timestamp_parsed'] = datetime.strptime(
                rev['timestamp'], '%Y-%m-%dT%H:%M:%SZ'
            )
            if i < len(all_revisions) - 1:
                prev_size = all_revisions[i + 1].get('size', 0)
                rev['size_diff'] = rev.get('size', 0) - prev_size
            else:
                rev['size_diff'] = 0
            
            # Revert-Erkennung
            comment = rev.get('comment', '').lower()
            tags = rev.get('tags', [])
            rev['is_revert'] = (
                'mw-reverted' in tags or
                'mw-undo' in tags or
                'revert' in comment or
                'rückgängig' in comment or
                'zurückgesetzt' in comment or
                'rv ' in comment or
                'rvv' in comment
            )
        
        return all_revisions
    
    # ==========================================
    # Diskussionsseite (Talk Page)
    # ==========================================
    
    def get_talk_page_content(self, title: str) -> Optional[str]:
        """Holt den Inhalt der Diskussionsseite"""
        
        talk_title = f"Diskussion:{title}" if self.lang == 'de' else f"Talk:{title}"
        
        params = {
            'action': 'query',
            'titles': talk_title,
            'prop': 'revisions',
            'rvprop': 'content',
            'rvlimit': 1
        }
        
        data = self._make_request(params)
        pages = data.get('query', {}).get('pages', {})
        
        for page_id, page_data in pages.items():
            if page_id != '-1':
                revisions = page_data.get('revisions', [])
                if revisions:
                    return revisions[0].get('*', '')
        return None
    
    def get_talk_page_sections(self, title: str) -> List[Dict]:
        """Holt die Abschnitte der Diskussionsseite"""
        
        talk_title = f"Diskussion:{title}" if self.lang == 'de' else f"Talk:{title}"
        
        params = {
            'action': 'parse',
            'page': talk_title,
            'prop': 'sections'
        }
        
        data = self._make_request(params)
        return data.get('parse', {}).get('sections', [])
    
    # ==========================================
    # Nutzer-Informationen
    # ==========================================
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Holt Informationen über einen Benutzer"""
        
        params = {
            'action': 'query',
            'list': 'users',
            'ususers': username,
            'usprop': 'editcount|registration|groups|blockinfo'
        }
        
        data = self._make_request(params)
        users = data.get('query', {}).get('users', [])
        
        if users and 'missing' not in users[0]:
            user = users[0]
            return {
                'username': user.get('name'),
                'user_id': user.get('userid'),
                'edit_count': user.get('editcount', 0),
                'registration': user.get('registration'),
                'groups': user.get('groups', []),
                'is_admin': 'sysop' in user.get('groups', []),
                'is_blocked': 'blockid' in user
            }
        return None
    
    def get_user_contributions(
        self, 
        username: str, 
        limit: int = 500,
        namespace: int = None
    ) -> List[Dict]:
        """Holt die Beiträge eines Nutzers"""
        
        params = {
            'action': 'query',
            'list': 'usercontribs',
            'ucuser': username,
            'uclimit': min(500, limit),
            'ucprop': 'ids|title|timestamp|comment|size|tags'
        }
        
        if namespace is not None:
            params['ucnamespace'] = namespace
        
        data = self._make_request(params)
        return data.get('query', {}).get('usercontribs', [])
    
    # ==========================================
    # Kategorien und Listen
    # ==========================================
    
    def get_category_members(
        self, 
        category: str, 
        limit: int = 500,
        member_type: str = 'page'
    ) -> List[str]:
        """Holt alle Artikel einer Kategorie"""
        
        all_members = []
        continue_token = None
        
        # Kategorie-Präfix hinzufügen falls nötig
        if not category.startswith('Kategorie:') and not category.startswith('Category:'):
            category = f"Kategorie:{category}" if self.lang == 'de' else f"Category:{category}"
        
        while len(all_members) < limit:
            params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': category,
                'cmlimit': min(500, limit - len(all_members)),
                'cmtype': member_type
            }
            
            if continue_token:
                params['cmcontinue'] = continue_token
            
            data = self._make_request(params)
            members = data.get('query', {}).get('categorymembers', [])
            all_members.extend([m['title'] for m in members])
            
            if 'continue' in data:
                continue_token = data['continue'].get('cmcontinue')
            else:
                break
        
        return all_members[:limit]
    
    # ==========================================
    # Recent Changes (für Echtzeit-Erkennung)
    # ==========================================
    
    def get_recent_changes(
        self, 
        limit: int = 500,
        hours_back: int = 24,
        only_reverts: bool = False
    ) -> List[Dict]:
        """Holt kürzliche Änderungen"""
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        params = {
            'action': 'query',
            'list': 'recentchanges',
            'rcstart': end_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'rcend': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'rclimit': min(500, limit),
            'rcprop': 'title|ids|timestamp|user|comment|sizes|tags',
            'rcnamespace': 0,  # Nur Artikel
            'rctype': 'edit'
        }
        
        if only_reverts:
            params['rctag'] = 'mw-reverted'
        
        data = self._make_request(params)
        return data.get('query', {}).get('recentchanges', [])
    
    # ==========================================
    # Wikipedia-Listen abrufen
    # ==========================================
    
    def get_protected_pages(self, limit: int = 200) -> List[str]:
        """Holt Liste der geschützten Seiten"""
        
        params = {
            'action': 'query',
            'list': 'protectedtitles',
            'ptlimit': min(500, limit),
            'ptnamespace': 0
        }
        
        data = self._make_request(params)
        pages = data.get('query', {}).get('protectedtitles', [])
        return [p['title'] for p in pages]
    
    def search_articles(self, query: str, limit: int = 50) -> List[str]:
        """Sucht nach Artikeln"""
        
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'srlimit': min(500, limit),
            'srnamespace': 0
        }
        
        data = self._make_request(params)
        results = data.get('query', {}).get('search', [])
        return [r['title'] for r in results]


# Factory-Funktion für verschiedene Sprachen
def get_wiki_api(lang: str = 'de') -> WikipediaAPI:
    """Erstellt einen Wikipedia API Client für die angegebene Sprache"""
    return WikipediaAPI(lang)
