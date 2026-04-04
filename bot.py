import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264423"
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

TEAM_TRANSLATIONS = {"Hapoel Be'er Sheva": "הפועל באר שבע", "Hapoel Petah Tikva": "הפועל פתח תקווה"}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    try:
        payload = {"chat_id": ADMIN_ID, "parse_mode": "Markdown"}
        if is_poll:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={**payload, **poll_data}, timeout=10)
        elif photo_url:
            payload.update({"photo": photo_url, "caption": text, "reply_markup": reply_markup})
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json=payload, timeout=15)
        else:
            payload.update({"text": text, "reply_markup": reply_markup})
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
        print(f"DEBUG: Telegram status {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_ai_summary(url, title, recent_summaries):
    print(f"DEBUG: שולח ל-AI סיכום עבור: {title}")
    # (כאן הקוד של ה-Scraping והפרומפט נשאר אותו דבר, רק הוספתי הדפסה בסוף)
    # ... (קוד ה-AI שלך)
    # נניח שחזר סיכום:
    # return summary

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now.strftime('%H:%M:%S')} ---")

    # ניהול קבצים
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("task_log.txt", "r") as f: tasks = set(f.read().splitlines())
    print(f"DEBUG: משימות שכבר בוצעו היום: {tasks}")

    # 1. בדיקת משחק
    print("DEBUG: בודק נתוני משחק ב-API...")
    # (כאן קוד ה-API)
    # דוגמה למניעת כפילות:
    if f"matchday_{today_str}" in tasks:
        print(f"DEBUG: הודעת יום משחק ל-{today_str} כבר נשלחה. מדלג.")
    else:
        # שליחה ורישום...
        pass

    # 2. RSS
    print(f"DEBUG: מתחיל לסרוק {len(RSS_FEEDS)} פידים של RSS...")
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פ\"ת", "מלאבס"]
    
    for url in RSS_FEEDS:
        print(f"DEBUG: סורק פיד: {url}")
        feed = feedparser.parse(url)
        print(f"DEBUG: נמצאו {len(feed.entries)} כתבות בפיד.")
        for entry in feed.entries[:10]:
            if entry.link in history:
                continue # כבר ראינו, שקט
            
            match = any(k in entry.title.lower() for k in hapoel_keys)
            if match or "hapoelpt.com" in entry.link:
                print(f"🎯 נמצאה כתבה רלוונטית: {entry.title}")
                # AI וסיכום...
            else:
                # הדפסה קטנה כדי לדעת למה דילגנו
                # print(f"DEBUG: מדלג על כתבה לא רלוונטית: {entry.title}")
                pass

    print("--- סיום ריצה ---")
