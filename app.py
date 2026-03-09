"""
Flask Web-Interface für den Wikipedia Edit-War Scanner
Mit Turso-Datenbank und Update-Logik
"""

import os
from flask import Flask, render_template_string, request, Response, redirect, url_for
from database import init_database, add_or_update_article, get_all_articles, get_scan_history, delete_article, log_scan
from scanner import get_recent_changes, search_article
from analyzer import analyze_article
from exporter import export_to_excel_compatible_csv
from config import SCAN_LIMIT
import time

app = Flask(__name__)

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wikipedia Edit-War Scanner</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .btn {
            display: inline-block;
            padding: 10px 20px;
            background: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            border: none;
            cursor: pointer;
            font-size: 14px;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        .btn:hover { background: #0055aa; }
        .btn-danger { background: #cc0000; }
        .btn-danger:hover { background: #aa0000; }
        .btn-success { background: #00aa00; }
        .btn-success:hover { background: #008800; }
        input[type="text"] {
            padding: 10px;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 300px;
            margin-right: 10px;
        }
        select {
            padding: 10px;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th { background: #f8f8f8; font-weight: 600; }
        tr:hover { background: #f8f8f8; }
        .score {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
        }
        .score-low { background: #4caf50; }
        .score-medium { background: #ff9800; }
        .score-high { background: #f44336; }
        .message {
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .message-success { background: #d4edda; color: #155724; }
        .message-error { background: #f8d7da; color: #721c24; }
        .message-info { background: #d1ecf1; color: #0c5460; }
        .stats { display: flex; gap: 20px; flex-wrap: wrap; }
        .stat {
            background: #e3f2fd;
            padding: 15px 25px;
            border-radius: 8px;
        }
        .stat-number { font-size: 24px; font-weight: bold; color: #1976d2; }
        .stat-label { font-size: 12px; color: #666; }
        a { color: #0066cc; }
        .loading { opacity: 0.6; pointer-events: none; }
    </style>
</head>
<body>
    <h1>Wikipedia Edit-War Scanner</h1>
    
    {% if message %}
    <div class="message message-{{ message_type }}">{{ message }}</div>
    {% endif %}
    
    <div class="card">
        <h2>Uebersicht</h2>
        <div class="stats">
            <div class="stat">
                <div class="stat-number">{{ stats.total_articles }}</div>
                <div class="stat-label">Artikel in DB</div>
            </div>
            <div class="stat">
                <div class="stat-number">{{ stats.high_conflict }}</div>
                <div class="stat-label">Hoher Konflikt (8-10)</div>
            </div>
            <div class="stat">
                <div class="stat-number">{{ stats.last_scan }}</div>
                <div class="stat-label">Letzter Scan</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h2>Automatischer Scan</h2>
        <p>Scannt die letzten 48 Stunden nach Artikeln mit hoher Bearbeitungsaktivitaet.</p>
        <form method="post" action="/scan" onsubmit="this.classList.add('loading')">
            <select name="wiki_lang">
                <option value="both">Beide (DE + EN)</option>
                <option value="de">Nur Deutsch</option>
                <option value="en">Nur Englisch</option>
            </select>
            <button type="submit" class="btn">Scan starten ({{ scan_limit }} Artikel)</button>
        </form>
        <p><small>Der Scan kann 1-2 Minuten dauern. Bestehende Artikel werden bei Aenderungen aktualisiert.</small></p>
    </div>
    
    <div class="card">
        <h2>Manuelle Suche</h2>
        <p>Suche nach einem bestimmten Artikel oder Thema zur Analyse.</p>
        <form method="post" action="/search" onsubmit="this.classList.add('loading')">
            <input type="text" name="search_term" placeholder="Artikelname oder Thema..." required>
            <select name="wiki_lang">
                <option value="de">Deutsch</option>
                <option value="en">Englisch</option>
            </select>
            <button type="submit" class="btn">Suchen und Analysieren</button>
        </form>
    </div>
    
    <div class="card">
        <h2>Gefundene Artikel</h2>
        <a href="/export" class="btn btn-success">Excel-Export (CSV)</a>
        
        {% if articles %}
        <table>
            <thead>
                <tr>
                    <th>Artikel</th>
                    <th>Wiki</th>
                    <th>Thema</th>
                    <th>Edits</th>
                    <th>Reverts</th>
                    <th>Editoren</th>
                    <th>Konflikt-Score</th>
                    <th>Zuletzt aktualisiert</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {% for article in articles %}
                <tr>
                    <td><a href="{{ article.url }}" target="_blank">{{ article.title }}</a></td>
                    <td>{{ article.wiki_lang|upper }}</td>
                    <td>{{ article.topic[:50] }}{% if article.topic|length > 50 %}...{% endif %}</td>
                    <td>{{ article.revision_count }}</td>
                    <td>{{ article.revert_count }}</td>
                    <td>{{ article.editor_count }}</td>
                    <td>
                        <span class="score {% if article.conflict_score|int >= 8 %}score-high{% elif article.conflict_score|int >= 5 %}score-medium{% else %}score-low{% endif %}">
                            {{ article.conflict_score }}/10
                        </span>
                    </td>
                    <td>{{ article.last_updated[:16] if article.last_updated else '' }}</td>
                    <td>
                        <form method="post" action="/delete/{{ article.id }}" style="display:inline;">
                            <button type="submit" class="btn btn-danger" style="padding:5px 10px;">X</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>Noch keine Artikel in der Datenbank. Starte einen Scan!</p>
        {% endif %}
    </div>
    
    <div class="card">
        <h2>Scan-Historie</h2>
        {% if scan_history %}
        <table>
            <thead>
                <tr>
                    <th>Zeitpunkt</th>
                    <th>Typ</th>
                    <th>Wiki</th>
                    <th>Gescannt</th>
                    <th>Neu</th>
                    <th>Aktualisiert</th>
                </tr>
            </thead>
            <tbody>
                {% for scan in scan_history %}
                <tr>
                    <td>{{ scan.timestamp }}</td>
                    <td>{{ scan.scan_type }}</td>
                    <td>{{ scan.wiki_lang|upper if scan.wiki_lang else '-' }}</td>
                    <td>{{ scan.articles_scanned }}</td>
                    <td>{{ scan.articles_added }}</td>
                    <td>{{ scan.articles_updated }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>Noch keine Scans durchgefuehrt.</p>
        {% endif %}
    </div>
    
</body>
</html>
'''


def get_stats():
    """Berechnet Statistiken fuer das Dashboard."""
    articles = get_all_articles()
    history = get_scan_history(1)
    
    return {
        'total_articles': len(articles),
        'high_conflict': len([a for a in articles if int(a['conflict_score'] or 0) >= 8]),
        'last_scan': history[0]['timestamp'][:16] if history else 'Noch nie'
    }


@app.route('/')
def index():
    """Hauptseite mit Dashboard."""
    init_database()
    
    articles = get_all_articles()
    scan_history = get_scan_history(10)
    stats = get_stats()
    
    message = request.args.get('message')
    message_type = request.args.get('type', 'info')
    
    return render_template_string(
        HTML_TEMPLATE,
        articles=articles,
        scan_history=scan_history,
        stats=stats,
        scan_limit=SCAN_LIMIT,
        message=message,
        message_type=message_type
    )


@app.route('/scan', methods=['POST'])
def run_scan():
    """Fuehrt einen manuellen Scan durch."""
    wiki_lang = request.form.get('wiki_lang', 'both')
    
    languages = ['de', 'en'] if wiki_lang == 'both' else [wiki_lang]
    total_scanned = 0
    total_added = 0
    total_updated = 0
    
    for lang in languages:
        articles_per_lang = SCAN_LIMIT // len(languages)
        active_articles = get_recent_changes(lang, limit=articles_per_lang)
        
        scanned = 0
        added = 0
        updated = 0
        
        for title, edit_data in active_articles:
            scanned += 1
            
            analysis = analyze_article(lang, title, edit_data)
            
            if analysis and analysis['conflict_score'] >= 3:
                result = add_or_update_article(analysis)
                if result == 'added':
                    added += 1
                elif result == 'updated':
                    updated += 1
            
            time.sleep(0.3)
        
        log_scan('manual', lang, scanned, added, updated)
        total_scanned += scanned
        total_added += added
        total_updated += updated
    
    message = f"Scan abgeschlossen: {total_scanned} Artikel gescannt, {total_added} neue, {total_updated} aktualisiert."
    return redirect(url_for('index', message=message, type='success'))


@app.route('/search', methods=['POST'])
def search():
    """Sucht und analysiert einen bestimmten Artikel."""
    search_term = request.form.get('search_term', '').strip()
    wiki_lang = request.form.get('wiki_lang', 'de')
    
    if not search_term:
        return redirect(url_for('index', message='Bitte Suchbegriff eingeben.', type='error'))
    
    results = search_article(wiki_lang, search_term)
    
    if not results:
        return redirect(url_for('index', message=f'Keine Artikel gefunden fuer "{search_term}".', type='error'))
    
    added = 0
    updated = 0
    analyzed = 0
    
    for title in results[:5]:
        analysis = analyze_article(wiki_lang, title)
        analyzed += 1
        
        if analysis:
            result = add_or_update_article(analysis)
            if result == 'added':
                added += 1
            elif result == 'updated':
                updated += 1
        
        time.sleep(0.3)
    
    log_scan('search', wiki_lang, analyzed, added, updated)
    
    message = f'Suche abgeschlossen: {analyzed} Artikel analysiert, {added} neue, {updated} aktualisiert.'
    return redirect(url_for('index', message=message, type='success'))


@app.route('/export')
def export():
    """Exportiert die Datenbank als CSV."""
    csv_content = export_to_excel_compatible_csv()
    
    if not csv_content:
        return redirect(url_for('index', message='Keine Daten zum Exportieren.', type='error'))
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=editwar_export.csv'}
    )


@app.route('/delete/<int:article_id>', methods=['POST'])
def delete(article_id):
    """Loescht einen Artikel aus der Datenbank."""
    delete_article(article_id)
    return redirect(url_for('index', message='Artikel geloescht.', type='info'))


@app.route('/cron/scan')
def cron_scan():
    """Wird vom Render Cron-Job aufgerufen."""
    secret = request.args.get('secret')
    expected_secret = os.environ.get('CRON_SECRET', 'default-secret')
    
    if secret != expected_secret:
        return 'Unauthorized', 401
    
    init_database()
    total_added = 0
    total_updated = 0
    
    for lang in ['de', 'en']:
        articles_per_lang = SCAN_LIMIT // 2
        active_articles = get_recent_changes(lang, limit=articles_per_lang)
        
        added = 0
        updated = 0
        
        for title, edit_data in active_articles:
            analysis = analyze_article(lang, title, edit_data)
            
            if analysis and analysis['conflict_score'] >= 3:
                result = add_or_update_article(analysis)
                if result == 'added':
                    added += 1
                elif result == 'updated':
                    updated += 1
            
            time.sleep(0.3)
        
        log_scan('scheduled', lang, len(active_articles), added, updated)
        total_added += added
        total_updated += updated
    
    return f'Scan completed. {total_added} added, {total_updated} updated.', 200


if __name__ == '__main__':
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
