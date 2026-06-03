"""
額外功能模組：天氣預報、學習統計、AI 新聞
"""
import json
import os
import urllib.request
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date

STUDY_LOG = '/app/study_log.json'
WEATHER_CACHE = {}
NEWS_CACHE = {'articles': [], 'updated_at': ''}
_weather_city = 'Taoyuan'

# ══════════════════════════════
# 🌤️ 天氣預報 (wttr.in，免費免 API Key)
# ══════════════════════════════

def get_weather_city():
    return _weather_city

def set_weather_city(city):
    global _weather_city
    _weather_city = city
    _fetch_weather()

def _fetch_weather():
    global WEATHER_CACHE
    city = _weather_city
    if not city:
        return
    try:
        url = f'https://wttr.in/{city}?format=j1&lang=zh-tw'
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        current = data.get('current_condition', [{}])[0]
        hourly = data.get('weather', [{}])[0].get('hourly', [])

        # 降雨機率：取今天所有時段最高值
        rain_chances = [int(h.get('chanceofrain', 0)) for h in hourly]
        max_rain = max(rain_chances) if rain_chances else 0

        forecast = []
        for h in hourly[:6]:
            hour = int(h.get('time', '0')) // 100
            forecast.append({
                'time': f'{hour:02d}:00',
                'temp': h.get('tempC', '--'),
                'desc': h.get('lang_zh-tw', [{}])[0].get('value', '') if h.get('lang_zh-tw') else h.get('weatherDesc', [{}])[0].get('value', ''),
                'rain': h.get('chanceofrain', '0')
            })

        desc_list = current.get('lang_zh-tw', [])
        condition = desc_list[0].get('value', '') if desc_list else current.get('weatherDesc', [{}])[0].get('value', '')

        WEATHER_CACHE = {
            'city': city,
            'temp_c': current.get('temp_C', '--'),
            'condition': condition,
            'humidity': current.get('humidity', '--'),
            'rain_chance': str(max_rain),
            'wind_speed': current.get('windspeedKmph', '--'),
            'forecast': forecast,
            'updated_at': datetime.now().strftime('%H:%M')
        }
        print(f'[天氣] {city}: {WEATHER_CACHE["temp_c"]}°C, {condition}')
    except Exception as e:
        print(f'[天氣] 錯誤: {e}')

def get_weather_data():
    return WEATHER_CACHE

def _weather_thread():
    time.sleep(2)
    _fetch_weather()
    while True:
        time.sleep(1800)  # 每 30 分鐘
        _fetch_weather()

threading.Thread(target=_weather_thread, daemon=True).start()

# ══════════════════════════════
# 📊 學習時間統計
# ══════════════════════════════

def _load_study_log():
    if not os.path.exists(STUDY_LOG):
        return {}
    try:
        with open(STUDY_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def _save_study_log(data):
    with open(STUDY_LOG, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def record_pomodoro(work_minutes=25):
    """記錄一個番茄鐘完成"""
    log = _load_study_log()
    today = date.today().isoformat()
    if today not in log:
        log[today] = {'count': 0, 'minutes': 0}
    log[today]['count'] += 1
    log[today]['minutes'] += work_minutes
    _save_study_log(log)
    return log[today]

def get_study_stats():
    """取得學習統計"""
    log = _load_study_log()
    today = date.today().isoformat()
    today_data = log.get(today, {'count': 0, 'minutes': 0})

    # 最近 7 天
    from datetime import timedelta
    week_data = []
    total_week = 0
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        day_info = log.get(d, {'count': 0, 'minutes': 0})
        week_data.append({
            'date': d,
            'count': day_info['count'],
            'minutes': day_info['minutes']
        })
        total_week += day_info['count']

    return {
        'today_count': today_data['count'],
        'today_minutes': today_data['minutes'],
        'week_total': total_week,
        'week_data': week_data
    }

def generate_study_metrics():
    """產生 Prometheus 指標"""
    stats = get_study_stats()
    lines = []
    lines.append('# HELP pomodoro_today_count 今日完成番茄鐘數')
    lines.append('# TYPE pomodoro_today_count gauge')
    lines.append(f'pomodoro_today_count {stats["today_count"]}')

    lines.append('# HELP pomodoro_today_minutes 今日學習分鐘數')
    lines.append('# TYPE pomodoro_today_minutes gauge')
    lines.append(f'pomodoro_today_minutes {stats["today_minutes"]}')

    lines.append('# HELP pomodoro_week_total 本週完成番茄鐘數')
    lines.append('# TYPE pomodoro_week_total gauge')
    lines.append(f'pomodoro_week_total {stats["week_total"]}')

    return '\n'.join(lines)

# ══════════════════════════════
# 📰 AI 新聞 (RSS)
# ══════════════════════════════

RSS_FEEDS = [
    ('Google AI News', 'https://news.google.com/rss/search?q=artificial+intelligence&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'),
    ('TechCrunch AI', 'https://techcrunch.com/category/artificial-intelligence/feed/'),
]

def _parse_rss(url, source_name):
    articles = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)

        for item in root.iter('item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            pub = item.findtext('pubDate', '')
            desc = item.findtext('description', '')
            # 清理 HTML
            if '<' in desc:
                desc = desc.split('<')[0]
            if len(desc) > 200:
                desc = desc[:200] + '...'
            articles.append({
                'title': title,
                'link': link,
                'published': pub[:16] if pub else '',
                'summary': desc,
                'source': source_name
            })
    except Exception as e:
        print(f'[新聞] {source_name} 錯誤: {e}')
    return articles

def _fetch_news():
    global NEWS_CACHE
    all_articles = []
    for name, url in RSS_FEEDS:
        articles = _parse_rss(url, name)
        all_articles.extend(articles)

    # 去重，取前 15 筆
    seen = set()
    unique = []
    for a in all_articles:
        if a['title'] not in seen:
            seen.add(a['title'])
            unique.append(a)
    unique = unique[:15]

    NEWS_CACHE = {
        'articles': unique,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    print(f'[新聞] 取得 {len(unique)} 筆 AI 新聞')

def get_news():
    return NEWS_CACHE

def format_news_telegram():
    """格式化新聞給 Telegram"""
    articles = NEWS_CACHE.get('articles', [])[:5]
    if not articles:
        return None
    lines = ['📰 <b>AI 新聞摘要</b>\n']
    for i, a in enumerate(articles, 1):
        lines.append(f'{i}. <a href="{a["link"]}">{a["title"]}</a>')
        if a.get('summary'):
            lines.append(f'   {a["summary"][:80]}')
        lines.append('')
    lines.append(f'更新時間：{NEWS_CACHE.get("updated_at", "")}')
    return '\n'.join(lines)

def _news_thread():
    time.sleep(5)
    _fetch_news()
    while True:
        time.sleep(7200)  # 每 2 小時
        _fetch_news()

threading.Thread(target=_news_thread, daemon=True).start()
