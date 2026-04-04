import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
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
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    for cid in subs:
        try:
            if is_poll:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        except Exception as e: print(f"DEBUG: שגיאת טלגרם: {e}")

def get_ai_summary(title):
    if not GEMINI_API_KEY: return None
    # המתנה ארוכה יותר למניעת 429 בגרסה החינמית
    print("LOG: ממתין 30 שניות לפני פנייה ל-AI כדי למנוע חסימת מכסה...")
    time.sleep(30)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Summarize for Hapoel Petah Tikva fans in 3 Hebrew sentences: {title}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"LOG: AI נכשל. סטטוס: {response.status_code}. תגובה: {response.text[:200]}")
    except: pass
    return None

def check_match_status():
    today = get_israel_time().strftime('%Y-%m-%d')
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    
    print(f"LOG: בודק API לכדורגל (מפתח: {RAPIDAPI_KEY[:5]}***)...")
    try:
        # ניסיון 1: בדיקת המשחקים הקרובים של הקבוצה
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "next": "5"}, timeout=15)
        
        print(f"LOG: תשובת API כדורגל (סטטוס {res.status_code})")
        data = res.json()
        
        if not data.get('response'):
            print(f"LOG: לא נמצאו משחקים ל-ID {TEAM_ID}. תשובה מלאה: {data}")
            return None

        for m in data['response']:
            match_date = m['fixture']['date'][:10]
            if match_date == today:
                is_home = str(m['teams']['home']['id']) == TEAM_ID
                opp = m['teams']['away']['name'] if is_home else m['teams']['home']['name']
                return {
                    "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
                    "opp_name": opp, "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                    "opp_score": m['goals']['away'] if is_home else m['goals']['home']
                }
    except Exception as e: print(f"LOG ERROR: {e}")
    return None

def main():
    now = get_israel_time()
    today_key = now.strftime('%Y-%m-%d')
    print(f"🚀 ריצה התחילה: {now.strftime('%H:%M:%S')}")

    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())

    # 1. RSS
    print("📰 סורק כתבות...")
    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    hapoel_keys = ["הפועל פ״ת", "פתח-תקוה", "פתח תקווה", "פתח-תקווה", "כחולים", "מבנה"]
    
    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in hapoel_keys):
                print(f"🎯 נמצאה כתבה: {entry.title}")
                summary = get_ai_summary(entry.title)
                text = summary if summary else entry.title
                send_to_all(f"**עדכון חדש על הפועל 💙**\n\n{text}\n\n🔗 [לכתבה המלאה]({entry.link})")
                with open(db_file, 'a') as f: f.write(entry.link + "\n")
                history.add(entry.link)

    # 2. Match Day
    match = check_match_status()
    task_log = "task_log.txt"
    if not os.path.exists(task_log): open(task_log, 'w').close()
    with open(task_log, 'r') as f: tasks_done = set(f.read().splitlines())

    if match:
        print(f"✅ משחק זוהה ב-API נגד {match['opp_name']}")
        if f"match_v3_{today_key}" not in tasks_done:
            clean_opp = urllib.parse.quote(match['opp_name'])
            img_url = f"https://pollinations.ai/p/football%20match%20Hapoel%20Petah%20Tikva%20blue%20vs%20{clean_opp}"
            send_to_all(f"MATCH DAY! 💙\n\nהפועל מול {match['opp_name']}\nמביאים 3 נקודות בעזרת השם! ⚽️", photo_url=img_url)
            
            poll = {"question": f"מה ההימור למשחק מול {match['opp_name']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_all("", is_poll=True, poll_data=poll)
            with open(task_log, 'a') as f: f.write(f"match_v3_{today_key}\n")
    else:
        # מצב חירום למשחק הערב בלבד (בגלל שה-API לא מזהה)
        if f"forced_bs_{today_key}" not in tasks_done:
            print("⚠️ API לא זיהה, מפעיל שליחה ידנית למשחק מול באר שבע")
            send_to_all("MATCH DAY! 💙\n\nהפועל מול באר שבע (טרנר)\nיוצאים למלחמה! מביאים 3 נקודות בעזרת השם! ⚽️", photo_url="https://pollinations.ai/p/football%20match%20Hapoel%20Petah%20Tikva%20blue%20vs%20Beer%20Sheva")
            poll = {"question": "מה ההימור למשחק מול באר שבע?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_all("", is_poll=True, poll_data=poll)
            with open(task_log, 'a') as f: f.write(f"forced_bs_{today_key}\n")

    print("🏁 סיום.")

if __name__ == "__main__": main()
