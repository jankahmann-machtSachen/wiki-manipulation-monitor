# wiki-manipulation-monitor
Automatisierte Erkennung von Manipulation und Machtmissbrauch in Wikipedia
# 🔍 Wikipedia Manipulation Monitor

Automatisierte Erkennung von Manipulation, Edit-Wars und Machtmissbrauch in Wikipedia.

## ✨ Features

- **Automatische Erkennung** von Edit-Wars, koordinierten Bearbeitungen, Single-Purpose-Accounts
- **Historische Analyse** - scannt 5 Jahre zurück
- **KI-gestützte Bewertung** der Schwere jedes Falls
- **Web-Dashboard** zur Übersicht und manuellen Prüfung
- **Mehrsprachig** - Deutsche und englische Wikipedia
- **100% kostenlos** - läuft auf GitHub Actions & Streamlit Cloud

## 🚀 Quick Start

### 1. Repository forken/klonen

```bash
git clone https://github.com/DEIN-USERNAME/wiki-manipulation-monitor.git
```

### 2. Hugging Face Token einrichten

1. Erstelle einen Account auf [huggingface.co](https://huggingface.co)
2. Gehe zu Settings → Access Tokens
3. Erstelle einen Token (Read)
4. Füge ihn als GitHub Secret hinzu:
   - Repository → Settings → Secrets → Actions
   - Name: `HF_API_TOKEN`
   - Value: Dein Token

### 3. GitHub Actions aktivieren

Der Scan läuft automatisch täglich um 6:00 UTC.

Manuell starten: Actions → Daily Wikipedia Scan → Run workflow

### 4. Dashboard auf Streamlit Cloud deployen

1. Gehe zu [streamlit.io/cloud](https://streamlit.io/cloud)
2. "New app" → Wähle dein Repository
3. Main file: `app.py`
4. Deploy!

## 📊 Was wird erkannt?

| Typ | Beschreibung | Schweregrad |
|-----|--------------|-------------|
| `edit_war` | Wiederholte Reverts zwischen Nutzern | 3-10 |
| `coordinated_editing` | Mehrere Accounts bearbeiten gleichzeitig | 5-10 |
| `single_purpose_account` | Account editiert nur einen Artikel | 4-8 |
| `large_unexplained_deletion` | Große Löschungen ohne Begründung | 3-7 |
| `suspicious_admin_activity` | Auffälliges Admin-Verhalten | 5-10 |

## 🗂️ Projektstruktur

```
wiki-manipulation-monitor/
├── .github/workflows/
│   └── daily_scan.yml      # Automatische Ausführung
├── data/
│   └── wiki_monitor.db     # SQLite Datenbank
├── src/
│   ├── config.py           # Konfiguration
│   ├── database.py         # Datenbank-Funktionen
│   ├── wiki_api.py         # Wikipedia API Client
│   ├── detectors.py        # Erkennungsalgorithmen
│   ├── ai_analyzer.py      # KI-Analyse
│   └── article_finder.py   # Artikel-Suche
├── app.py                  # Streamlit Dashboard
├── main.py                 # Hauptskript
└── requirements.txt        # Python-Abhängigkeiten
```

## ⚙️ Konfiguration anpassen

Bearbeite `src/config.py`:

```python
# Erkennungs-Schwellenwerte
REVERT_THRESHOLD: int = 3       # Min. Reverts für Edit-War
HISTORY_YEARS: int = 5          # Jahre zurück analysieren
MAX_ARTICLES: int = 500         # Max. überwachte Artikel

# Sprachen
ENABLED_LANGUAGES: List[str] = ['de', 'en']
```

## 🖥️ Lokale Entwicklung

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Datenbank initialisieren
python main.py init

# Scan durchführen
python main.py scan

# Dashboard starten
streamlit run app.py
```

## 📝 Lizenz

MIT License - Frei verwendbar für Forschung und Transparenz.

## 🤝 Beitragen

Pull Requests sind willkommen! Besonders für:
- Neue Erkennungsalgorithmen
- Weitere Sprachen
- Dashboard-Verbesserungen
