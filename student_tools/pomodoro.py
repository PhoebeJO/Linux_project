#!/usr/bin/env python3
"""
🍅 番茄鐘計時器
透過 Telegram 發送提醒通知

使用方式：
  python pomodoro.py          → 標準番茄鐘（25/5/15分鐘）
  python pomodoro.py --short  → 測試模式（1/0.5分鐘）
"""
import time
import requests
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')

# 測試模式：python pomodoro.py --short
TEST_MODE = '--short' in sys.argv

WORK_MIN        = 1   if TEST_MODE else 25
SHORT_BREAK_MIN = 0.5 if TEST_MODE else 5
LONG_BREAK_MIN  = 1   if TEST_MODE else 15
SESSIONS_BEFORE_LONG = 4

def send_telegram(message: str):
    """發送 Telegram 通知"""
    if not BOT_TOKEN or not CHAT_ID:
        print(f'[Telegram 未設定] {message}')
        return
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        resp = requests.post(url, json={
            'chat_id': int(CHAT_ID),
            'text': message,
            'parse_mode': 'HTML'
        }, timeout=10)
        if not resp.ok:
            print(f'[Telegram 錯誤] {resp.text}')
    except Exception as e:
        print(f'[Telegram 發送失敗] {e}')

def countdown(minutes: float, label: str):
    """倒數計時，顯示剩餘時間"""
    total = int(minutes * 60)
    print(f'\n⏱  {label}（{minutes:.0f} 分鐘）開始')
    start = time.time()
    while True:
        elapsed = time.time() - start
        remaining = total - elapsed
        if remaining <= 0:
            break
        m, s = divmod(int(remaining), 60)
        print(f'\r   剩餘 {m:02d}:{s:02d}', end='', flush=True)
        time.sleep(0.5)
    print('\r   ✅ 時間到！        ')

def main():
    mode_str = '【測試模式】' if TEST_MODE else ''
    print(f'🍅 番茄鐘啟動 {mode_str}')
    print(f'   工作：{WORK_MIN} 分鐘 | 短休息：{SHORT_BREAK_MIN} 分鐘 | 長休息：{LONG_BREAK_MIN} 分鐘')
    print('   按 Ctrl+C 隨時中止\n')

    send_telegram(
        f'🍅 <b>番茄鐘開始！</b> {mode_str}\n'
        f'專注學習 {WORK_MIN:.0f} 分鐘 💪\n'
        f'開始時間：{datetime.now().strftime("%H:%M")}'
    )

    session = 0
    try:
        while True:
            session += 1
            print(f'\n{"="*35}')
            print(f'🍅 第 {session} 個番茄')

            # ── 工作階段 ──
            countdown(WORK_MIN, f'第 {session} 個番茄 — 專注中')

            if session % SESSIONS_BEFORE_LONG == 0:
                # 長休息
                send_telegram(
                    f'🎉 <b>完成 {session} 個番茄！</b>\n'
                    f'長休息 {LONG_BREAK_MIN:.0f} 分鐘，喝水、伸展一下 🚶\n'
                    f'時間：{datetime.now().strftime("%H:%M")}'
                )
                countdown(LONG_BREAK_MIN, '長休息')
                send_telegram(f'🍅 <b>長休息結束！</b>\n繼續下一輪，加油！💪')
            else:
                # 短休息
                send_telegram(
                    f'✅ <b>第 {session} 個番茄完成！</b>\n'
                    f'短休息 {SHORT_BREAK_MIN:.0f} 分鐘，放鬆眼睛 👀\n'
                    f'時間：{datetime.now().strftime("%H:%M")}'
                )
                countdown(SHORT_BREAK_MIN, '短休息')
                send_telegram(f'🍅 <b>準備第 {session+1} 個番茄！</b>\n保持專注 💪')

    except KeyboardInterrupt:
        send_telegram(
            f'⏹ <b>番茄鐘結束</b>\n'
            f'今天完成了 <b>{session}</b> 個番茄，辛苦了！🎓\n'
            f'結束時間：{datetime.now().strftime("%H:%M")}'
        )
        print(f'\n\n已完成 {session} 個番茄鐘，辛苦了！')

if __name__ == '__main__':
    main()
