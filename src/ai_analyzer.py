"""
KI-Analyse-Modul
================
Nutzt Hugging Face API für Konflikt- und Manipulationsanalyse.
Komplett kostenlos über Hugging Face Inference API.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .config import config


@dataclass
class AIAnalysisResult:
    """Ergebnis der KI-Analyse"""
    conflict_score: float      # 0-10: Wie schwer ist der Konflikt?
    manipulation_score: float  # 0-10: Wie wahrscheinlich ist Manipulation?
    power_abuse_score: float   # 0-10: Wie wahrscheinlich ist Machtmissbrauch?
    summary: str               # Zusammenfassung
    reasoning: str             # Begründung
    recommended_severity: int  # Empfohlener Schweregrad 1-10
    confidence: float          # Konfidenz der Analyse


class AIAnalyzer:
    """
    KI-gestützte Analyse von Wikipedia-Konflikten.
    Nutzt Hugging Face's kostenlose Inference API.
    """
    
    def __init__(self):
        self.api_token = config.HF_API_TOKEN or os.environ.get('HF_API_TOKEN', '')
        self.api_url = "https://api-inference.huggingface.co/models/"
        
        # Modelle für verschiedene Aufgaben
        self.classification_model = "facebook/bart-large-mnli"  # Zero-shot Classification
        self.summarization_model = "facebook/bart-large-cnn"    # Zusammenfassung
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}"
        } if self.api_token else {}
    
    def _query_model(self, model: str, payload: dict) -> dict:
        """Sendet Anfrage an Hugging Face API"""
        
        if not self.api_token:
            return {"error": "Kein HF_API_TOKEN konfiguriert"}
        
        url = f"{self.api_url}{model}"
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def _classify_text(
        self, 
        text: str, 
        labels: List[str]
    ) -> Dict[str, float]:
        """Zero-Shot Klassifikation eines Textes"""
        
        payload = {
            "inputs": text,
            "parameters": {
                "candidate_labels": labels,
                "multi_label": True
            }
        }
        
        result = self._query_model(self.classification_model, payload)
        
        if "error" in result:
            return {label: 0.5 for label in labels}
        
        if "labels" in result and "scores" in result:
            return dict(zip(result["labels"], result["scores"]))
        
        return {label: 0.5 for label in labels}
    
    def analyze_conflict(
        self, 
        case_data: Dict[str, Any]
    ) -> AIAnalysisResult:
        """
        Analysiert einen erkannten Fall mit KI.
        
        Args:
            case_data: Dictionary mit Falldaten (case_type, description, evidence, etc.)
        
        Returns:
            AIAnalysisResult mit Scores und Zusammenfassung
        """
        
        # Beschreibung für KI vorbereiten
        description = self._prepare_description(case_data)
        
        # 1. Konflikt-Klassifikation
        conflict_labels = [
            "severe conflict requiring immediate attention",
            "moderate disagreement between editors",
            "minor editorial dispute",
            "normal collaborative editing"
        ]
        conflict_scores = self._classify_text(description, conflict_labels)
        
        # 2. Manipulations-Klassifikation
        manipulation_labels = [
            "deliberate manipulation of information",
            "biased editing with hidden agenda",
            "coordinated inauthentic behavior",
            "honest mistake or misunderstanding",
            "legitimate editorial work"
        ]
        manipulation_scores = self._classify_text(description, manipulation_labels)
        
        # 3. Machtmissbrauchs-Klassifikation
        power_labels = [
            "abuse of administrative powers",
            "unfair blocking or censorship",
            "neutral moderation",
            "appropriate use of authority"
        ]
        power_scores = self._classify_text(description, power_labels)
        
        # Scores berechnen (0-10 Skala)
        conflict_score = self._calculate_conflict_score(conflict_scores)
        manipulation_score = self._calculate_manipulation_score(manipulation_scores)
        power_abuse_score = self._calculate_power_abuse_score(power_scores)
        
        # Gesamtschweregrad
        recommended_severity = self._calculate_severity(
            conflict_score, manipulation_score, power_abuse_score, case_data
        )
        
        # Zusammenfassung und Begründung generieren
        summary, reasoning = self._generate_summary(
            case_data, conflict_score, manipulation_score, power_abuse_score
        )
        
        return AIAnalysisResult(
            conflict_score=round(conflict_score, 1),
            manipulation_score=round(manipulation_score, 1),
            power_abuse_score=round(power_abuse_score, 1),
            summary=summary,
            reasoning=reasoning,
            recommended_severity=recommended_severity,
            confidence=self._calculate_confidence(conflict_scores, manipulation_scores)
        )
    
    def _prepare_description(self, case_data: Dict[str, Any]) -> str:
        """Bereitet eine Beschreibung für die KI vor"""
        
        parts = [
            f"Case Type: {case_data.get('case_type', 'unknown')}",
            f"Description: {case_data.get('description', 'No description')}",
        ]
        
        evidence = case_data.get('evidence', {})
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except:
                evidence = {}
        
        if evidence.get('revert_count'):
            parts.append(f"Number of reverts: {evidence['revert_count']}")
        
        if evidence.get('user_count'):
            parts.append(f"Users involved: {evidence['user_count']}")
        
        involved_users = case_data.get('involved_users', [])
        if involved_users:
            if isinstance(involved_users, str):
                try:
                    involved_users = json.loads(involved_users)
                except:
                    involved_users = [involved_users]
            parts.append(f"Involved users: {', '.join(involved_users[:5])}")
        
        if case_data.get('admin_involved'):
            parts.append(f"Admin involved: {case_data['admin_involved']}")
        
        return " | ".join(parts)
    
    def _calculate_conflict_score(self, scores: Dict[str, float]) -> float:
        """Berechnet Konflikt-Score (0-10)"""
        
        severe = scores.get("severe conflict requiring immediate attention", 0)
        moderate = scores.get("moderate disagreement between editors", 0)
        minor = scores.get("minor editorial dispute", 0)
        normal = scores.get("normal collaborative editing", 0)
        
        # Gewichtete Berechnung
        score = (severe * 10 + moderate * 6 + minor * 3 + normal * 0) / max(
            severe + moderate + minor + normal, 0.01
        )
        
        return min(10, max(0, score))
    
    def _calculate_manipulation_score(self, scores: Dict[str, float]) -> float:
        """Berechnet Manipulations-Score (0-10)"""
        
        deliberate = scores.get("deliberate manipulation of information", 0)
        biased = scores.get("biased editing with hidden agenda", 0)
        coordinated = scores.get("coordinated inauthentic behavior", 0)
        mistake = scores.get("honest mistake or misunderstanding", 0)
        legitimate = scores.get("legitimate editorial work", 0)
        
        # Negative Indikatoren gewichten
        manipulation = (deliberate * 10 + biased * 8 + coordinated * 9)
        benign = (mistake * 2 + legitimate * 0)
        
        total = deliberate + biased + coordinated + mistake + legitimate
        if total > 0:
            score = (manipulation - benign) / total
        else:
            score = 5
        
        return min(10, max(0, score))
    
    def _calculate_power_abuse_score(self, scores: Dict[str, float]) -> float:
        """Berechnet Machtmissbrauchs-Score (0-10)"""
        
        abuse = scores.get("abuse of administrative powers", 0)
        unfair = scores.get("unfair blocking or censorship", 0)
        neutral = scores.get("neutral moderation", 0)
        appropriate = scores.get("appropriate use of authority", 0)
        
        abuse_total = abuse * 10 + unfair * 8
        benign_total = neutral * 2 + appropriate * 0
        
        total = abuse + unfair + neutral + appropriate
        if total > 0:
            score = (abuse_total - benign_total) / total
        else:
            score = 0
        
        return min(10, max(0, score))
    
    def _calculate_severity(
        self, 
        conflict: float, 
        manipulation: float, 
        power_abuse: float,
        case_data: Dict[str, Any]
    ) -> int:
        """Berechnet empfohlenen Schweregrad"""
        
        # Basis: Durchschnitt der Scores
        base_score = (conflict + manipulation * 1.2 + power_abuse * 1.5) / 3.7
        
        # Bonus für bestimmte Case-Types
        case_type = case_data.get('case_type', '')
        type_bonus = {
            'suspicious_admin_activity': 2,
            'coordinated_editing': 1.5,
            'edit_war': 1,
            'single_purpose_account': 0.5,
            'large_unexplained_deletion': 0.5
        }.get(case_type, 0)
        
        # Evidence-basierter Bonus
        evidence = case_data.get('evidence', {})
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except:
                evidence = {}
        
        evidence_bonus = 0
        if evidence.get('revert_count', 0) > 10:
            evidence_bonus += 1
        if evidence.get('user_count', 0) > 5:
            evidence_bonus += 0.5
        
        final_score = base_score + type_bonus + evidence_bonus
        
        return min(10, max(1, round(final_score)))
    
    def _generate_summary(
        self,
        case_data: Dict[str, Any],
        conflict: float,
        manipulation: float,
        power_abuse: float
    ) -> tuple:
        """Generiert Zusammenfassung und Begründung"""
        
        case_type = case_data.get('case_type', 'Unbekannt')
        article = case_data.get('article_title', 'Unbekannt')
        
        # Zusammenfassung basierend auf Scores
        severity_word = "kritischer" if (conflict + manipulation + power_abuse) / 3 > 6 else \
                       "moderater" if (conflict + manipulation + power_abuse) / 3 > 3 else "geringer"
        
        summary = f"{severity_word.capitalize()} Fall auf Artikel '{article}'"
        
        # Begründung
        reasons = []
        
        if conflict > 5:
            reasons.append(f"Hohe Konfliktintensität (Score: {conflict:.1f}/10)")
        
        if manipulation > 5:
            reasons.append(f"Verdacht auf Manipulation (Score: {manipulation:.1f}/10)")
        
        if power_abuse > 5:
            reasons.append(f"Hinweise auf Machtmissbrauch (Score: {power_abuse:.1f}/10)")
        
        if case_type == 'edit_war':
            reasons.append("Edit-War-Muster erkannt")
        elif case_type == 'coordinated_editing':
            reasons.append("Koordinierte Bearbeitung durch mehrere Accounts")
        elif case_type == 'single_purpose_account':
            reasons.append("Single-Purpose-Account identifiziert")
        elif case_type == 'suspicious_admin_activity':
            reasons.append("Auffällige Admin-Aktivität")
        
        reasoning = " | ".join(reasons) if reasons else "Keine besonderen Auffälligkeiten"
        
        return summary, reasoning
    
    def _calculate_confidence(
        self, 
        conflict_scores: Dict[str, float],
        manipulation_scores: Dict[str, float]
    ) -> float:
        """Berechnet Konfidenz der Analyse"""
        
        # Höhere Konfidenz wenn Scores eindeutig sind
        all_scores = list(conflict_scores.values()) + list(manipulation_scores.values())
        
        if not all_scores:
            return 0.5
        
        max_score = max(all_scores)
        avg_score = sum(all_scores) / len(all_scores)
        
        # Wenn ein Score deutlich dominiert = höhere Konfidenz
        if max_score > 0.7:
            return 0.8
        elif max_score > 0.5:
            return 0.6
        else:
            return 0.4


def analyze_case_with_ai(case_data: Dict[str, Any]) -> AIAnalysisResult:
    """Convenience-Funktion für KI-Analyse"""
    analyzer = AIAnalyzer()
    return analyzer.analyze_conflict(case_data)
