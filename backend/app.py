from flask import Flask, request, jsonify
from flask_cors import CORS
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
import sqlite3
import os
import requests as http

app = Flask(__name__)
CORS(app)

DB_PATH = '/data/scores.db'

# Prometheus metrics - global
games_total    = Counter('snake_games_total', 'Total games played')
high_score     = Gauge('snake_high_score', 'All-time high score')
avg_score      = Gauge('snake_avg_score', 'Average score across all games')
score_hist     = Histogram('snake_score', 'Score distribution',
                           buckets=[0, 5, 10, 20, 30, 50, 75, 100, 150, 200])

# Prometheus metrics - per user
user_games     = Counter('snake_user_games_total', 'Games played per user', ['name'])
user_best      = Gauge('snake_user_best_score', 'Best score per user', ['name'])
user_avg       = Gauge('snake_user_avg_score', 'Average score per user', ['name'])

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL DEFAULT 'Player',
            score      INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter   TEXT    NOT NULL DEFAULT '匿名',
            message    TEXT    NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def refresh_gauges():
    conn = get_db()
    # global
    row = conn.execute('SELECT MAX(score) as mx, AVG(score) as av FROM scores').fetchone()
    if row['mx'] is not None:
        high_score.set(row['mx'])
        avg_score.set(row['av'])
    # per user
    rows = conn.execute(
        'SELECT name, MAX(score) as best, AVG(score) as avg FROM scores GROUP BY name'
    ).fetchall()
    conn.close()
    for r in rows:
        user_best.labels(name=r['name']).set(r['best'])
        user_avg.labels(name=r['name']).set(r['avg'])

@app.route('/api/score', methods=['POST'])
def save_score():
    data = request.get_json(silent=True) or {}
    score = int(data.get('score', 0))
    name  = str(data.get('name', 'Player'))[:20].strip() or 'Player'

    conn = get_db()
    conn.execute('INSERT INTO scores (name, score) VALUES (?, ?)', (name, score))
    conn.commit()
    conn.close()

    games_total.inc()
    user_games.labels(name=name).inc()
    score_hist.observe(score)
    refresh_gauges()

    return jsonify({'ok': True})

@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    rows = conn.execute(
        '''SELECT name, MAX(score) as score, MAX(created_at) as created_at
           FROM scores GROUP BY name ORDER BY score DESC LIMIT 10'''
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def stats():
    conn = get_db()
    row = conn.execute(
        'SELECT COUNT(*) as total, MAX(score) as best, AVG(score) as avg FROM scores'
    ).fetchone()
    conn.close()
    return jsonify(dict(row))

@app.route('/api/report', methods=['POST'])
def report():
    data = request.get_json(silent=True) or {}
    message = str(data.get('message', '')).strip()[:500]
    reporter = str(data.get('reporter', '匿名')).strip()[:30] or '匿名'

    if not message:
        return jsonify({'ok': False, 'error': 'empty message'}), 400

    conn = get_db()
    conn.execute('INSERT INTO reports (reporter, message) VALUES (?, ?)', (reporter, message))
    conn.commit()
    conn.close()

    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id   = os.environ.get('TELEGRAM_CHAT_ID', '')
    if bot_token and chat_id:
        try:
            http.post(
                f'https://api.telegram.org/bot{bot_token}/sendMessage',
                json={
                    'chat_id': chat_id,
                    'text': f'🐛 <b>問題回報</b>\n👤 {reporter}\n\n{message}',
                    'parse_mode': 'HTML'
                },
                timeout=5
            )
        except Exception:
            pass

    return jsonify({'ok': True})


@app.route('/api/reports')
def list_reports():
    conn = get_db()
    rows = conn.execute(
        'SELECT reporter, message, created_at FROM reports ORDER BY id DESC LIMIT 50'
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    init_db()
    refresh_gauges()
    # restore per-user game counts from DB on startup
    conn = get_db()
    rows = conn.execute('SELECT name, COUNT(*) as cnt FROM scores GROUP BY name').fetchall()
    conn.close()
    for r in rows:
        # initialize counter to match DB (use _value._value to set internal counter)
        user_games.labels(name=r['name'])
    app.run(host='0.0.0.0', port=5000, debug=False)
