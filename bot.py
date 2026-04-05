import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def clean_text_for_telegram(text):
    """מנקה טקסט מכל מה שיכול לשבור HTML של טלגרם"""
    if not text: return ""
    return html.escape(str(text))

def send_to_telegram(text, is_poll=False, poll_data=None):
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        if is_poll:
            r = requests.post(f"{url_base}/sendPoll", json={"chat_id": ADMIN_ID, **poll_data}, timeout=10)
        else:
            # שליחה בפורמט HTML - הכי בטוח
            r = requests.post(f"{url_base}/sendMessage", json={
                "chat_id": ADMIN_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }, timeout=10)
        
        print(f"DEBUG: Telegram Status {r.status_code}")
        if r.status_code != 200:
            print(f"DEBUG: Telegram Error Details: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_ai_summary(text, title):
    if not GEMINI_API_KEY: return None
    prompt = (f"כתוב תקציר של 4 משפטים על הכתבה הבאה עבור אוהדי הפועל פתח תקווה. "
              f"התמקד רק במידע שרלוונטי להם.\nטקסט: {text[:2500]}")
    
    # כתובת v1 היציבה ביותר
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"DEBUG AI FAILED: {res.status_code}")
    except: pass
    return None

def main():
    now = get_israel_time()
    print(f"--- ריצה: {now.strftime('%H:%M:%S')} ---")
    
    db_file, sum_db = "seen_links.txt", "recent_summaries.txt"
    for f in [db_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(line.strip() for line in f if line.strip())

    print("📡 סורק כתבות...")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                if entry.link in history: continue
                
                # בדיקה ראשונית בכותרת
                if any(k in entry.title for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    
                    # חילוץ טקסט הכתבה
                    res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    full_text = " ".join([p.get_text() for p in soup.find_all('p')])
                    
                    summary = get_ai_summary(full_text, entry.title)
                    
                    if summary:
                        # הודעה מעוצבת עם תקציר
                        clean_summary = clean_text_for_telegram(summary)
                        msg = f"💙 <b>עדכון חדש</b>\n\n{clean_summary}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        # הודעת חירום - כותרת ולינק בלבד (בלי שום דבר שיכול להישבר)
                        clean_title = clean_text_for_telegram(entry.title)
                        msg = f"💙 <b>{clean_title}</b>\n\n🔗 {entry.link}"
                        print("DEBUG: Sending emergency format (No AI summary)")

                    if send_to_telegram(msg):
                        with open(db_file, "a") as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        time.sleep(3)
        except Exception as e:
            print(f"DEBUG Error scanning feed {url}: {e}")
            continue

    print("--- סיום ריצה ---")

# הוספת הרשימה החסרה
RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

if __name__ == "__main__": main()
