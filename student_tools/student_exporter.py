#!/usr/bin/env python3
"""
Student Life Metrics Exporter
作業截止 Prometheus 指標 + 番茄鐘 + 作業管理 + 深夜提醒設定
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import yaml
import json
import os
import urllib.request
from datetime import datetime

DEADLINES_FILE    = '/app/deadlines.yml'
SETTINGS_FILE     = '/app/settings.yml'
POMODORO_HTML     = '/app/pomodoro.html'
ADMIN_HTML        = '/app/admin.html'
LATE_NIGHT_JS     = '/app/late-night-alert.js'
PORT = 8001

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TELEGRAM_CHAT_ID', '')

# ── 設定檔 ──

def load_settings():
    defaults = {'late_night': {'start_hour': 1, 'end_hour': 6, 'message': '該睡覺了！'}}
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data if data else defaults
    except:
        return defaults

def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

# ── 作業資料 CRUD ──

def load_deadlines():
    if not os.path.exists(DEADLINES_FILE):
        return []
    with open(DEADLINES_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('deadlines', []) if data else []

def save_deadlines(deadlines):
    data = {'deadlines': deadlines}
    with open(DEADLINES_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def deadlines_with_hours(deadlines):
    result = []
    now = datetime.now()
    for item in deadlines:
        try:
            dl = datetime.fromisoformat(item['deadline'])
            hours = max(0, (dl - now).total_seconds() / 3600)
            result.append({
                'name': item['name'],
                'course': item.get('course', ''),
                'deadline': item['deadline'],
                'hours_remaining': round(hours, 1)
            })
        except:
            pass
    return result

# ── Prometheus Metrics ──

def generate_metrics():
    lines = []
    now = datetime.now()

    # 作業截止指標
    deadlines = load_deadlines()
    lines.append('# HELP homework_deadline_hours_remaining 距離作業截止剩餘小時數')
    lines.append('# TYPE homework_deadline_hours_remaining gauge')
    for item in deadlines:
        name = item['name']
        course = item.get('course', 'unknown')
        try:
            dl = datetime.fromisoformat(item['deadline'])
            hours_left = max(0, (dl - now).total_seconds() / 3600)
            lines.append(
                f'homework_deadline_hours_remaining{{task="{name}",course="{course}"}} {hours_left:.2f}'
            )
        except Exception as e:
            print(f'[ERROR] {name}: {e}')

    # 深夜提醒指標
    settings = load_settings()
    ln = settings.get('late_night', {})
    start_h = ln.get('start_hour', 1)
    end_h = ln.get('end_hour', 6)
    current_hour = now.hour

    if start_h <= end_h:
        is_late = start_h <= current_hour < end_h
    else:  # 跨午夜，例如 23 ~ 6
        is_late = current_hour >= start_h or current_hour < end_h

    lines.append('')
    lines.append('# HELP late_night_active 是否在深夜時段 (1=深夜, 0=正常)')
    lines.append('# TYPE late_night_active gauge')
    lines.append(f'late_night_active {1 if is_late else 0}')

    lines.append('# HELP late_night_start_hour 深夜提醒開始時間')
    lines.append('# TYPE late_night_start_hour gauge')
    lines.append(f'late_night_start_hour {start_h}')

    lines.append('# HELP late_night_end_hour 深夜提醒結束時間')
    lines.append('# TYPE late_night_end_hour gauge')
    lines.append(f'late_night_end_hour {end_h}')

    return '\n'.join(lines) + '\n'

# ── Telegram ──

def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print(f'[Telegram 未設定] {message}')
        return False
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        data = json.dumps({
            'chat_id': int(CHAT_ID),
            'text': message,
            'parse_mode': 'HTML'
        }).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f'[Telegram 錯誤] {e}')
        return False

# ── HTTP Handler ──

class Handler(BaseHTTPRequestHandler):

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                html = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'File not found')

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        if self.path == '/metrics':
            content = generate_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        elif self.path == '/' or self.path == '/pomodoro':
            self._send_html(POMODORO_HTML)
        elif self.path == '/admin':
            self._send_html(ADMIN_HTML)
        elif self.path == '/late-night-alert.js':
            try:
                with open(LATE_NIGHT_JS, 'r', encoding='utf-8') as f:
                    js = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.end_headers()
                self.wfile.write(js.encode('utf-8'))
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
        elif self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        elif self.path == '/api/deadlines':
            self._send_json(deadlines_with_hours(load_deadlines()))
        elif self.path == '/api/settings':
            self._send_json(load_settings())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/pomodoro/notify':
            try:
                data = self._read_body()
                ok = send_telegram(data.get('message', ''))
                self._send_json({'ok': ok})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/deadlines':
            try:
                data = self._read_body()
                name = data.get('name', '').strip()
                course = data.get('course', '').strip()
                deadline = data.get('deadline', '').strip()
                if not name or not course or not deadline:
                    self._send_json({'ok': False, 'error': '缺少必填欄位'}, 400)
                    return
                deadlines = load_deadlines()
                deadlines.append({'name': name, 'course': course, 'deadline': deadline})
                save_deadlines(deadlines)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith('/api/deadlines/'):
            try:
                index = int(self.path.split('/')[-1])
                data = self._read_body()
                deadlines = load_deadlines()
                if index < 0 or index >= len(deadlines):
                    self._send_json({'ok': False, 'error': '索引超出範圍'}, 400)
                    return
                deadlines[index] = {
                    'name': data.get('name', '').strip(),
                    'course': data.get('course', '').strip(),
                    'deadline': data.get('deadline', '').strip()
                }
                save_deadlines(deadlines)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/settings':
            try:
                data = self._read_body()
                save_settings(data)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith('/api/deadlines/'):
            try:
                index = int(self.path.split('/')[-1])
                deadlines = load_deadlines()
                if index < 0 or index >= len(deadlines):
                    self._send_json({'ok': False, 'error': '索引超出範圍'}, 400)
                    return
                removed = deadlines.pop(index)
                save_deadlines(deadlines)
                self._send_json({'ok': True, 'removed': removed['name']})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    print(f'Student Exporter 啟動，監聽 port {PORT}...')
    print(f'  番茄鐘：http://localhost:{PORT}/pomodoro')
    print(f'  作業管理：http://localhost:{PORT}/admin')
    print(f'  Metrics：http://localhost:{PORT}/metrics')
    print(f'  Telegram: {"已設定" if BOT_TOKEN else "未設定"}')
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
