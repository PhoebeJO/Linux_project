#!/usr/bin/env python3
"""
Student Life Metrics Exporter
作業截止 Prometheus 指標 + 番茄鐘 + 作業管理 + 深夜提醒 + 股價監控
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import yaml
import json
import os
import urllib.request
import threading
import time
from datetime import datetime

DEADLINES_FILE    = '/app/deadlines.yml'
SETTINGS_FILE     = '/app/settings.yml'
STOCKS_FILE       = '/app/stocks.yml'
POMODORO_HTML     = '/app/pomodoro.html'
ADMIN_HTML        = '/app/admin.html'
STOCKS_HTML       = '/app/stocks.html'
WEATHER_HTML      = '/app/weather.html'
NEWS_HTML         = '/app/news.html'
LATE_NIGHT_JS     = '/app/late-night-alert.js'

from features import (
    get_weather_data, set_weather_city, get_weather_city,
    record_pomodoro, get_study_stats, generate_study_metrics,
    get_news, format_news_telegram,
    get_news_config, save_news_config, _fetch_news
)
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

    # ── 股價指標 ──
    with _stock_lock:
        cache = dict(_stock_cache)
    if cache:
        lines.append('')
        lines.append('# HELP stock_price 股票現價')
        lines.append('# TYPE stock_price gauge')
        for sym, d in cache.items():
            if d.get('price'):
                lines.append(f'stock_price{{symbol="{sym}",name="{d["name"]}"}} {d["price"]}')

        lines.append('# HELP stock_change_pct 股票當日漲跌幅(%)')
        lines.append('# TYPE stock_change_pct gauge')
        for sym, d in cache.items():
            if d.get('change_pct') is not None:
                lines.append(f'stock_change_pct{{symbol="{sym}",name="{d["name"]}"}} {d["change_pct"]:.4f}')

    # ── 學習統計指標 ──
    lines.append('')
    lines.append(generate_study_metrics())

    return '\n'.join(lines) + '\n'

# ── 股價 ──

_stock_cache: dict = {}
_stock_lock = threading.Lock()
_stock_prev_prices: dict = {}  # symbol → 上一次 fetch 的價格
_stock_alerted: dict = {}  # symbol → 最後告警的價格，避免同方向重複告警

def _load_stocks_config():
    default = {'stocks': [], 'alert_drop_pct': 3.0, 'alert_rise_pct': 5.0}
    if not os.path.exists(STOCKS_FILE):
        return default
    try:
        with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data if data else default
    except:
        return default

def _save_stocks_config(data):
    with open(STOCKS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def _fetch_stocks():
    try:
        import yfinance as yf
    except ImportError:
        print('[股價] yfinance 未安裝')
        return

    cfg = _load_stocks_config()
    stocks = cfg.get('stocks', [])
    if not stocks:
        return

    symbols = [s['symbol'] for s in stocks]
    name_map = {s['symbol']: s.get('name', s['symbol']) for s in stocks}

    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            hist = t.history(period='5d')
            if hist.empty:
                print(f'[股價] {sym} 無資料')
                continue
            price = float(hist['Close'].iloc[-1])
            if len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
            else:
                prev_close = price
            daily_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

            prev_fetch = _stock_prev_prices.get(sym)
            if prev_fetch is not None and prev_fetch != 0:
                fetch_pct = ((price - prev_fetch) / prev_fetch * 100)
            else:
                fetch_pct = 0.0
            _stock_prev_prices[sym] = price

            with _stock_lock:
                _stock_cache[sym] = {
                    'name': name_map[sym],
                    'price': round(price, 2),
                    'prev_close': round(prev_close, 2),
                    'change_pct': round(daily_pct, 4),
                    'fetch_change_pct': round(fetch_pct, 4),
                    'prev_fetch_price': round(prev_fetch, 2) if prev_fetch else None,
                    'updated_at': datetime.now().strftime('%H:%M:%S'),
                    'stale': False
                }
            print(f'[股價] {sym} = {price:.2f} (日:{daily_pct:+.2f}% 即時:{fetch_pct:+.2f}%)')
        except Exception as e:
            print(f'[股價] {sym} 錯誤: {e}')
            with _stock_lock:
                if sym in _stock_cache:
                    _stock_cache[sym]['stale'] = True

    _check_stock_alerts(cfg)

def _check_stock_alerts(cfg):
    global_drop = cfg.get('alert_drop_pct', 3.0)
    global_rise = cfg.get('alert_rise_pct', 5.0)
    stock_configs = {s['symbol']: s for s in cfg.get('stocks', [])}

    with _stock_lock:
        cache = dict(_stock_cache)

    for sym, d in cache.items():
        fetch_pct = d.get('fetch_change_pct')
        if fetch_pct is None or fetch_pct == 0:
            continue

        last_alerted = _stock_alerted.get(sym)
        price = d.get('price', 0)

        sc = stock_configs.get(sym, {})
        drop_pct = sc.get('alert_drop_pct', global_drop)
        rise_pct = sc.get('alert_rise_pct', global_rise)
        name = d.get('name', sym)
        prev = d.get('prev_fetch_price', '?')
        daily_pct = d.get('change_pct', 0)

        if fetch_pct <= -drop_pct:
            if last_alerted == f'drop:{price}':
                continue
            msg = (f'📉 <b>股價即時下跌</b>\n'
                   f'{name}（{sym}）\n'
                   f'現價：{price}　前次：{prev}\n'
                   f'即時跌幅：{fetch_pct:.2f}%（門檻 -{drop_pct}%）\n'
                   f'當日累計：{daily_pct:+.2f}%')
            if send_telegram(msg):
                _stock_alerted[sym] = f'drop:{price}'
                print(f'[即時告警] {sym} 跌 {fetch_pct:.2f}% → 已通知')
        elif fetch_pct >= rise_pct:
            if last_alerted == f'rise:{price}':
                continue
            msg = (f'📈 <b>股價即時上漲</b>\n'
                   f'{name}（{sym}）\n'
                   f'現價：{price}　前次：{prev}\n'
                   f'即時漲幅：+{fetch_pct:.2f}%（門檻 +{rise_pct}%）\n'
                   f'當日累計：{daily_pct:+.2f}%')
            if send_telegram(msg):
                _stock_alerted[sym] = f'rise:{price}'
                print(f'[即時告警] {sym} 漲 {fetch_pct:.2f}% → 已通知')

def _stock_thread():
    while True:
        _fetch_stocks()
        time.sleep(60)  # 每 1 分鐘更新

threading.Thread(target=_stock_thread, daemon=True).start()

# ── 每日作業提醒 ──

_deadline_reminded_date: str = ''

def _send_daily_deadline_reminder():
    deadlines = load_deadlines()
    now = datetime.now()
    upcoming = []
    for item in deadlines:
        try:
            dl = datetime.fromisoformat(item['deadline'])
            days_left = (dl - now).total_seconds() / 86400
            if days_left < 0:
                continue
            upcoming.append((item, days_left))
        except:
            pass
    if not upcoming:
        return
    upcoming.sort(key=lambda x: x[1])
    lines = ['📋 <b>每日作業提醒</b>\n']
    for item, days in upcoming:
        name = item['name']
        course = item.get('course', '')
        dl_str = item['deadline'][:10]
        if days < 1:
            hours = int(days * 24)
            tag = f'⚠️ 剩不到 {hours} 小時！'
        elif days < 3:
            tag = f'🔴 剩 {days:.1f} 天'
        elif days < 7:
            tag = f'🟡 剩 {days:.0f} 天'
        else:
            tag = f'🟢 剩 {int(days)} 天'
        lines.append(f'• <b>{name}</b>（{course}）\n  截止：{dl_str}　{tag}')
    lines.append(f'\n共 {len(upcoming)} 項作業待完成，加油！💪')
    send_telegram('\n'.join(lines))

def _deadline_reminder_thread():
    global _deadline_reminded_date
    while True:
        time.sleep(60)
        now = datetime.now()
        settings = load_settings()
        reminder_hour = settings.get('deadline_reminder_hour', 9)
        today = now.strftime('%Y-%m-%d')
        if now.hour == reminder_hour and _deadline_reminded_date != today:
            _deadline_reminded_date = today
            _send_daily_deadline_reminder()
            print(f'[作業提醒] {today} {reminder_hour}:00 已發送')

threading.Thread(target=_deadline_reminder_thread, daemon=True).start()

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
        elif self.path == '/stocks':
            self._send_html(STOCKS_HTML)
        elif self.path == '/weather':
            self._send_html(WEATHER_HTML)
        elif self.path == '/news':
            self._send_html(NEWS_HTML)
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
        elif self.path == '/api/weather':
            self._send_json(get_weather_data())
        elif self.path == '/api/news':
            self._send_json(get_news())
        elif self.path == '/api/news/config':
            self._send_json(get_news_config())
        elif self.path == '/api/study':
            self._send_json(get_study_stats())
        elif self.path == '/api/stocks':
            cfg = _load_stocks_config()
            with _stock_lock:
                cache = dict(_stock_cache)
            result = []
            for s in cfg.get('stocks', []):
                sym = s['symbol']
                d = cache.get(sym, {})
                item = {
                    'symbol': sym,
                    'name': s.get('name', sym),
                    'price': d.get('price'),
                    'change_pct': d.get('change_pct'),
                    'updated_at': d.get('updated_at'),
                    'stale': d.get('stale', False),
                }
                if 'alert_drop_pct' in s:
                    item['alert_drop_pct'] = s['alert_drop_pct']
                if 'alert_rise_pct' in s:
                    item['alert_rise_pct'] = s['alert_rise_pct']
                result.append(item)
            self._send_json({'stocks': result, 'config': {
                'alert_drop_pct': cfg.get('alert_drop_pct', 3.0),
                'alert_rise_pct': cfg.get('alert_rise_pct', 5.0)
            }})
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
        elif self.path == '/api/pomodoro/complete':
            try:
                data = self._read_body()
                minutes = data.get('minutes', 25)
                result = record_pomodoro(minutes)
                self._send_json({'ok': True, 'today': result})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/news/push':
            try:
                msg = format_news_telegram()
                if msg:
                    ok = send_telegram(msg)
                    self._send_json({'ok': ok})
                else:
                    self._send_json({'ok': False, 'error': '暫無新聞'})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/news/config':
            try:
                data = self._read_body()
                query = data.get('query', '').strip()
                if not query:
                    self._send_json({'ok': False, 'error': '請輸入搜尋主題'}, 400)
                    return
                save_news_config({'query': query})
                threading.Thread(target=_fetch_news, daemon=True).start()
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/stocks/refresh':
            threading.Thread(target=_fetch_stocks, daemon=True).start()
            self._send_json({'ok': True})
        elif self.path == '/api/stocks':
            try:
                data = self._read_body()
                cfg = _load_stocks_config()
                stocks = cfg.get('stocks', [])
                sym = data.get('symbol', '').strip().upper()
                name = data.get('name', '').strip()
                if not sym or not name:
                    self._send_json({'ok': False, 'error': '缺少代號或名稱'}, 400)
                    return
                if any(s['symbol'] == sym for s in stocks):
                    self._send_json({'ok': False, 'error': '此股票已在監控清單'}, 400)
                    return
                new_stock = {'symbol': sym, 'name': name}
                custom_drop = data.get('alert_drop_pct')
                custom_rise = data.get('alert_rise_pct')
                if custom_drop is not None:
                    new_stock['alert_drop_pct'] = float(custom_drop)
                if custom_rise is not None:
                    new_stock['alert_rise_pct'] = float(custom_rise)
                stocks.append(new_stock)
                cfg['stocks'] = stocks
                _save_stocks_config(cfg)
                threading.Thread(target=_fetch_stocks, daemon=True).start()
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
        elif self.path == '/api/weather/city':
            try:
                data = self._read_body()
                city = data.get('city', '').strip()
                if city:
                    set_weather_city(city)
                    self._send_json({'ok': True})
                else:
                    self._send_json({'ok': False, 'error': '請填城市名'}, 400)
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path == '/api/stocks/settings':
            try:
                data = self._read_body()
                cfg = _load_stocks_config()
                cfg['alert_drop_pct'] = data.get('alert_drop_pct', 3.0)
                cfg['alert_rise_pct'] = data.get('alert_rise_pct', 5.0)
                _save_stocks_config(cfg)
                _stock_alerted.clear()
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path.startswith('/api/stocks/') and self.path[len('/api/stocks/'):].isdigit():
            try:
                index = int(self.path.split('/')[-1])
                data = self._read_body()
                cfg = _load_stocks_config()
                stocks = cfg.get('stocks', [])
                if index < 0 or index >= len(stocks):
                    self._send_json({'ok': False, 'error': '索引超出範圍'}, 400)
                    return
                if 'alert_drop_pct' in data:
                    if data['alert_drop_pct'] is None:
                        stocks[index].pop('alert_drop_pct', None)
                    else:
                        stocks[index]['alert_drop_pct'] = float(data['alert_drop_pct'])
                if 'alert_rise_pct' in data:
                    if data['alert_rise_pct'] is None:
                        stocks[index].pop('alert_rise_pct', None)
                    else:
                        stocks[index]['alert_rise_pct'] = float(data['alert_rise_pct'])
                if 'name' in data:
                    stocks[index]['name'] = data['name'].strip()
                cfg['stocks'] = stocks
                _save_stocks_config(cfg)
                sym = stocks[index]['symbol']
                _stock_alerted.pop(sym, None)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith('/api/stocks/') and not self.path.startswith('/api/stocks/settings'):
            try:
                index = int(self.path.split('/')[-1])
                cfg = _load_stocks_config()
                stocks = cfg.get('stocks', [])
                if index < 0 or index >= len(stocks):
                    self._send_json({'ok': False, 'error': '索引超出範圍'}, 400)
                    return
                removed = stocks.pop(index)
                cfg['stocks'] = stocks
                _save_stocks_config(cfg)
                with _stock_lock:
                    _stock_cache.pop(removed['symbol'], None)
                self._send_json({'ok': True})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
        elif self.path.startswith('/api/deadlines/'):
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
