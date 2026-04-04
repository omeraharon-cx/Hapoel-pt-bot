import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199" 

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = [ADMIN_ID] # לצורך הבדיקה נשלח קודם כל אליך
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    print(f"DEBUG: מנסה לשלוח הודעה ל-{len(subs)} מנויים...")
    for cid in subs:
        try:
            if is_poll:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
            print(f"DEBUG: תשובת טלגרם עבור {cid}: {res.status_code}")
        except Exception as e:
            print(f"DEBUG: שגיאה בשליחה: {e}")

def get_ai_summary(text):
    if not GEMINI_API_KEY: return "תקציר לא זמין כרגע."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Summarize this for Hapoel PT fans in 3 Hebrew sentences. Casual tone. TEXT: {text[:2000]}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"DEBUG: AI חזר עם שגיאה {response.status_code}")
        return None
    except: return None

def check_match_status():
    # מנגנון עקיפת API ליום המשחק
    print("DEBUG: בודק API לכדורגל...")
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "next": "1"}, timeout=15).json()
        if res.get('response'):
            m = res['response'][0]
            print(f"DEBUG: נמצא משחק ב-API: {m['teams']['away']['name']}")
            return { "id": m['fixture']['id'], "opp_name": "הפועל באר שבע", "status": m['fixture']['status']['short'], "my_score": 0, "opp_score": 0 }
    except: pass
    
    # אם ה-API נכשל, אנחנו כופים את המשחק מול באר שבע כי אנחנו יודעים שהוא קורה!
    print("DEBUG: API לא מצא משחק, מפעיל 'מצב כפייה' לבאר שבע!")
    return { "id": "forced", "opp_name": "הפועל באר שבע", "status": "NS", "my_score": 0, "opp_score": 0 }

def main():
    now = get_israel_time()
    print(f"--- תחילת ריצת חירום: {now.strftime('%H:%M')} ---")
    
    # בדיקת טלגרם מיידית
    send_to_all("🚀 הבוט התעורר לסריקה לקראת המשחק!")

    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())

    # שלב 1: RSS - סריקה אגרסיבית
    print("--- שלב 1: כתבות ---")
    rss_urls = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/"]
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            print(f"DEBUG: בודק כתבה: {entry.title}")
            if entry.link not in history:
                print(f"🎯 נמצאה כתבה חדשה! מעבד...")
                summary = get_ai_summary(entry.title) or entry.title
                send_to_all(f"**עדכון חדש**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})")
                with open(db_file, 'a') as f: f.write(entry.link + "\n")
                history.add(entry.link)
                time.sleep(2)

    # שלב 2: יום משחק - כפוי
    print("--- שלב 2: יום משחק ---")
    match = check_match_status()
    today_key = now.strftime('%Y-%m-%d')
    task_log = "task_log.txt"
    if not os.path.exists(task_log): open(task_log, 'w').close()
    with open(task_log, 'r') as f: done = f.read().splitlines()

    if f"poster_{today_key}" not in done:
        # פוסטר
        img_url = f"https://pollinations.ai/p/cinematic%20football%20poster%20Hapoel%20Petah%20Tikva%20blue%20stadium%20vs%20Beer%20Sheva"
        send_to_all(f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp_name']}\nיוצאים למלחמה בטרנר! מביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️", photo_url=img_url)
        
        # סקר הימורים (שולחים מיד כי כבר 19:20)
        poll_data = {"question": "מה ההימור שלכם להערב?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
        send_to_all("", is_poll=True, poll_data=poll_data)
        
        with open(task_log, 'a') as f: f.write(f"poster_{today_key}\n")

    print("🏁 סיום ריצת חירום.")

if __name__ == "__main__": main()
