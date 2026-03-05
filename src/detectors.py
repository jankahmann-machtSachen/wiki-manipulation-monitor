"""
Detektoren für verschiedene Arten von Manipulation
===================================================
Erkennt Edit Wars, Sockpuppets, Admin-Missbrauch, etc.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

from .config import config
from .wiki_api import WikipediaAPI


@dataclass
class DetectionResult:
    """Ergebnis einer Erkennung"""
    detected: bool
    case_type: str
    severity: int  # 1-10
    confidence: float  # 0-1
    title: str
    description: str
    involved_users: List[str]
    evidence: Dict[str, Any]
    incident_start: Optional[datetime] = None
    incident_end: Optional[datetime] = None
    admin_involved: Optional[str] = None


class ManipulationDetector:
    """Hauptklasse für alle Erkennungsalgorithmen"""
    
    def __init__(self, wiki_api: WikipediaAPI):
        self.api = wiki_api
    
    def analyze_article(self, title: str) -> List[DetectionResult]:
        """
        Führt alle Erkennungsalgorithmen auf einem Artikel aus.
        Gibt eine Liste aller gefundenen Probleme zurück.
        """
        results = []
        
        # Hole Versionsgeschichte
        revisions = self.api.get_revisions(title, limit=1000)
        
        if not revisions:
            return results
        
        # 1. Edit Wars erkennen
        edit_wars = self.detect_edit_wars(title, revisions)
        results.extend(edit_wars)
        
        # 2. Koordinierte Bearbeitungen erkennen
        coordination = self.detect_coordinated_editing(title, revisions)
        if coordination.detected:
            results.append(coordination)
        
        # 3. Große unerklärte Löschungen
        deletions = self.detect_large_deletions(title, revisions)
        results.extend(deletions)
        
        # 4. Single Purpose Accounts
        spa_results = self.detect_single_purpose_accounts(title, revisions)
        results.extend(spa_results)
        
        # 5. Admin-Eingriffe analysieren
        admin_analysis = self.detect_admin_actions(title, revisions)
        if admin_analysis.detected:
            results.append(admin_analysis)
        
        return results
    
    # ==========================================
    # DETEKTOR 1: Edit Wars
    # ==========================================
    
    def detect_edit_wars(
        self, 
        title: str, 
        revisions: List[Dict]
    ) -> List[DetectionResult]:
        """
        Erkennt Edit Wars (wiederholte Reverts zwischen Nutzern).
        Scannt die gesamte Historie und findet alle Edit-War-Perioden.
        """
        results = []
        
        if len(revisions) < 5:
            return results
        
        # Gruppiere Reverts in Zeitfenster
        window_hours = config.REVERT_WINDOW_HOURS
        revert_revisions = [r for r in revisions if r.get('is_revert')]
        
        if len(revert_revisions) < config.REVERT_THRESHOLD:
            return results
        
        # Finde Cluster von Reverts
        clusters = []
        current_cluster = []
        
        for rev in revert_revisions:
            if not current_cluster:
                current_cluster = [rev]
            else:
                time_diff = (
                    current_cluster[0]['timestamp_parsed'] - 
                    rev['timestamp_parsed']
                )
                if time_diff <= timedelta(hours=window_hours):
                    current_cluster.append(rev)
                else:
                    if len(current_cluster) >= config.REVERT_THRESHOLD:
                        clusters.append(current_cluster)
                    current_cluster = [rev]
        
        # Letzten Cluster prüfen
        if len(current_cluster) >= config.REVERT_THRESHOLD:
            clusters.append(current_cluster)
        
        # Für jeden Cluster einen Fall erstellen
        for cluster in clusters:
            users = list(set(r.get('user', 'Anonym') for r in cluster))
            revert_count = len(cluster)
            
            # Schweregrad berechnen
            severity = min(10, 3 + (revert_count // 3) + (len(users) - 1))
            
            # Zeitraum
            incident_start = min(r['timestamp_parsed'] for r in cluster)
            incident_end = max(r['timestamp_parsed'] for r in cluster)
            
            results.append(DetectionResult(
                detected=True,
                case_type='edit_war',
                severity=severity,
                confidence=0.9 if revert_count > 5 else 0.7,
                title=f"Edit War: {revert_count} Reverts",
                description=(
                    f"Edit War mit {revert_count} Reverts zwischen "
                    f"{len(users)} Nutzern im Zeitraum "
                    f"{incident_start.strftime('%d.%m.%Y')} bis "
                    f"{incident_end.strftime('%d.%m.%Y')}."
                ),
                involved_users=users,
                evidence={
                    'revert_count': revert_count,
                    'user_count': len(users),
                    'duration_hours': (incident_end - incident_start).total_seconds() / 3600,
                    'reverts': [
                        {
                            'user': r.get('user'),
                            'timestamp': r.get('timestamp'),
                            'comment': r.get('comment', '')[:100]
                        }
                        for r in cluster[:20]  # Max 20 als Beispiel
                    ]
                },
                incident_start=incident_start,
                incident_end=incident_end
            ))
        
        return results
    
    # ==========================================
    # DETEKTOR 2: Koordinierte Bearbeitung
    # ==========================================
    
    def detect_coordinated_editing(
        self, 
        title: str, 
        revisions: List[Dict]
    ) -> DetectionResult:
        """
        Erkennt koordinierte Bearbeitungen (mögliche Sockpuppets).
        Mehrere verschiedene Accounts bearbeiten fast gleichzeitig.
        """
        window_minutes = config.COORDINATION_WINDOW_MINUTES
        min_users = config.COORDINATION_MIN_USERS
        
        # Gruppiere Edits nach Zeitfenster
        time_clusters = defaultdict(list)
        
        for rev in revisions:
            ts = rev['timestamp_parsed']
            # Runde auf Zeitfenster
            cluster_key = ts.replace(
                minute=(ts.minute // window_minutes) * window_minutes,
                second=0, microsecond=0
            )
            time_clusters[cluster_key].append(rev)
        
        # Finde verdächtige Cluster
        suspicious_clusters = []
        for cluster_time, edits in time_clusters.items():
            unique_users = set(e.get('user', 'Anonym') for e in edits)
            if len(unique_users) >= min_users:
                suspicious_clusters.append({
                    'time': cluster_time,
                    'users': list(unique_users),
                    'edit_count': len(edits)
                })
        
        if not suspicious_clusters:
            return DetectionResult(
                detected=False, case_type='coordinated_editing',
                severity=0, confidence=0, title='', description='',
                involved_users=[], evidence={}
            )
        
        # Alle beteiligten Nutzer sammeln
        all_users = set()
        for cluster in suspicious_clusters:
            all_users.update(cluster['users'])
        
        severity = min(10, 4 + len(suspicious_clusters) + len(all_users) // 2)
        
        return DetectionResult(
            detected=True,
            case_type='coordinated_editing',
            severity=severity,
            confidence=0.6 + (0.05 * len(suspicious_clusters)),
            title=f"Koordinierte Bearbeitung: {len(all_users)} Accounts",
            description=(
                f"{len(suspicious_clusters)} Fälle von koordinierten Bearbeitungen "
                f"durch {len(all_users)} verschiedene Accounts innerhalb von "
                f"{window_minutes}-Minuten-Fenstern. Mögliche Sockpuppets."
            ),
            involved_users=list(all_users),
            evidence={
                'suspicious_clusters': suspicious_clusters[:10],
                'total_clusters': len(suspicious_clusters),
                'unique_users': len(all_users)
            }
        )
    
    # ==========================================
    # DETEKTOR 3: Große Löschungen
    # ==========================================
    
    def detect_large_deletions(
        self, 
        title: str, 
        revisions: List[Dict]
    ) -> List[DetectionResult]:
        """
        Erkennt große Inhaltslöschungen ohne angemessene Begründung.
        """
        results = []
        threshold = config.LARGE_DELETION_CHARS
        
        for rev in revisions:
            size_diff = rev.get('size_diff', 0)
            
            if size_diff < -threshold:
                comment = rev.get('comment', '')
                
                # Prüfe ob Begründung vorhanden
                has_explanation = len(comment) > 20
                is_revert = rev.get('is_revert', False)
                
                if not has_explanation and not is_revert:
                    severity = min(10, 3 + abs(size_diff) // 2000)
                    
                    results.append(DetectionResult(
                        detected=True,
                        case_type='large_unexplained_deletion',
                        severity=severity,
                        confidence=0.7,
                        title=f"Große Löschung: {abs(size_diff)} Zeichen",
                        description=(
                            f"Nutzer '{rev.get('user', 'Anonym')}' hat {abs(size_diff)} "
                            f"Zeichen gelöscht ohne ausreichende Begründung."
                        ),
                        involved_users=[rev.get('user', 'Anonym')],
                        evidence={
                            'chars_deleted': abs(size_diff),
                            'comment': comment,
                            'revision_id': rev.get('revid'),
                            'timestamp': rev.get('timestamp')
                        },
                        incident_start=rev['timestamp_parsed'],
                        incident_end=rev['timestamp_parsed']
                    ))
        
        return results
    
    # ==========================================
    # DETEKTOR 4: Single Purpose Accounts
    # ==========================================
    
    def detect_single_purpose_accounts(
        self, 
        title: str, 
        revisions: List[Dict]
    ) -> List[DetectionResult]:
        """
        Erkennt Single Purpose Accounts (SPAs), die fast nur
        einen Artikel bearbeiten - oft Zeichen von bezahlter Bearbeitung.
        """
        results = []
        
        # Sammle alle Nutzer und ihre Edit-Counts auf diesem Artikel
        user_edits = defaultdict(int)
        for rev in revisions:
            user = rev.get('user', 'Anonym')
            if user != 'Anonym':
                user_edits[user] += 1
        
        # Prüfe jeden Nutzer mit genug Edits
        for user, edit_count in user_edits.items():
            if edit_count < config.SPA_MIN_EDITS:
                continue
            
            # Hole die Contributions des Nutzers
            contributions = self.api.get_user_contributions(user, limit=200)
            
            if len(contributions) < config.SPA_MIN_EDITS:
                continue
            
            # Berechne Konzentration
            article_counts = defaultdict(int)
            for contrib in contributions:
                article_counts[contrib['title']] += 1
            
            total_edits = len(contributions)
            edits_on_this = article_counts.get(title, 0)
            concentration = edits_on_this / total_edits if total_edits > 0 else 0
            
            if concentration >= config.SPA_RATIO:
                severity = min(10, 4 + int(concentration * 5))
                
                results.append(DetectionResult(
                    detected=True,
                    case_type='single_purpose_account',
                    severity=severity,
                    confidence=0.7 + (concentration - 0.75) * 2,
                    title=f"Single Purpose Account: {user}",
                    description=(
                        f"Account '{user}' hat {concentration*100:.1f}% seiner Edits "
                        f"({edits_on_this} von {total_edits}) auf diesem Artikel gemacht. "
                        f"Mögliche bezahlte oder interessengeleitete Bearbeitung."
                    ),
                    involved_users=[user],
                    evidence={
                        'username': user,
                        'concentration_percent': round(concentration * 100, 1),
                        'edits_on_article': edits_on_this,
                        'total_edits': total_edits,
                        'other_articles': len(article_counts) - 1
                    }
                ))
        
        return results
    
    # ==========================================
    # DETEKTOR 5: Admin-Aktionen
    # ==========================================
    
    def detect_admin_actions(
        self, 
        title: str, 
        revisions: List[Dict]
    ) -> DetectionResult:
        """
        Analysiert Admin-Eingriffe auf möglichen Missbrauch.
        Z.B. einseitige Sperrungen, wiederholte Eingriffe zugunsten einer Partei.
        """
        # Finde alle Admin-Nutzer in den Revisions
        admin_actions = defaultdict(list)
        
        for rev in revisions:
            user = rev.get('user', '')
            # Prüfe ob Nutzer Admin ist
            user_info = self.api.get_user_info(user)
            if user_info and user_info.get('is_admin'):
                admin_actions[user].append(rev)
        
        if not admin_actions:
            return DetectionResult(
                detected=False, case_type='admin_involvement',
                severity=0, confidence=0, title='', description='',
                involved_users=[], evidence={}
            )
        
        # Analysiere Admin-Verhalten
        suspicious_admins = []
        
        for admin, actions in admin_actions.items():
            revert_count = sum(1 for a in actions if a.get('is_revert'))
            
            if revert_count >= config.ADMIN_BLOCK_THRESHOLD:
                suspicious_admins.append({
                    'admin': admin,
                    'total_actions': len(actions),
                    'reverts': revert_count
                })
        
        if not suspicious_admins:
            return DetectionResult(
                detected=True,
                case_type='admin_involvement',
                severity=3,  # Niedrig - nur Info
                confidence=1.0,
                title=f"Admin-Beteiligung: {len(admin_actions)} Admins",
                description=(
                    f"{len(admin_actions)} Admin(s) haben auf diesem Artikel editiert. "
                    f"Keine offensichtlichen Unregelmäßigkeiten erkannt."
                ),
                involved_users=list(admin_actions.keys()),
                evidence={'admin_actions': dict(admin_actions)},
                admin_involved=list(admin_actions.keys())[0] if admin_actions else None
            )
        
        # Verdächtige Admin-Aktivität gefunden
        severity = min(10, 5 + len(suspicious_admins) * 2)
        
        return DetectionResult(
            detected=True,
            case_type='suspicious_admin_activity',
            severity=severity,
            confidence=0.6,
            title=f"Verdächtige Admin-Aktivität",
            description=(
                f"{len(suspicious_admins)} Admin(s) mit auffällig vielen Reverts. "
                f"Möglicher Machtmissbrauch - manuelle Prüfung empfohlen."
            ),
            involved_users=[a['admin'] for a in suspicious_admins],
            evidence={'suspicious_admins': suspicious_admins},
            admin_involved=suspicious_admins[0]['admin']
        )


def run_detection(article_title: str, wiki_lang: str = 'de') -> List[DetectionResult]:
    """Convenience-Funktion zum Ausführen aller Detektoren"""
    api = WikipediaAPI(wiki_lang)
    detector = ManipulationDetector(api)
    return detector.analyze_article(article_title)
