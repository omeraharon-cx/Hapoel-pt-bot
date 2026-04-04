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
    # טעינת מנויים
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
        except Exception as e:
            print(f"DEBUG: שגיאת טלגרם ל-{cid}: {e}")

def get_ai_summary(title, content=""):
    if not GEMINI_API_KEY: return title
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Summarize this for Hapoel Petah Tikva fans in 3 Hebrew sentences: {title}. {content[:1000]}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"DEBUG: AI חסום (סטטוס {response.status_code}), משתמש בכותרת.")
        return title
    except: return title

def find_today_match():
    today = get_israel_time().strftime('%Y-%m-%d')
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    
    print(f"DEBUG: מחפש משחק לתאריך {today}...")
    try:
        # בודק את 5 המשחקים הבאים של הקבוצה
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "next": "5"}, timeout=15).json()
        for m in res.get('response', []):
            match_date = m['fixture']['date'][:10]
            if match_date == today:
                print(f"✅ נמצא משחק ב-API: {m['teams']['home']['name']} נגד {m['teams']['away']['name']}")
                is_home = str(m['teams']['home']['id']) == TEAM_ID
                return {
                    "id": m['fixture']['id'],
                    "status": m['fixture']['status']['short'],
                    "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                    "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
                    "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name']
                }
    except Exception as e:
        print(f"DEBUG: שגיאת API: {e}")
    return None

def main():
    now = get_israel_time()
    today_key = now.strftime('%Y-%m-%d')
    print(f"🚀 סריקה התחילה: {now.strftime('%H:%M')} (ישראל)")

    # שלב 1: כתבות RSS
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())

    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    hapoel_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הכחולים"]

    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in hapoel_keys):
                print(f"🎯 מעבד כתבה: {entry.title}")
                summary = get_ai_summary(entry.title)
                send_to_all(f"**עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})")
                with open(db_file, 'a') as f: f.write(entry.link + "\n")
                history.add(entry.link)
                time.sleep(2)

    # שלב 2: יום משחק
    match = find_today_match()
    task_log = "task_log.txt"
    if not os.path.exists(task_log): open(task_log, 'w').close()
    with open(task_log, 'r') as f: tasks_done = f.read().splitlines()

    if match:
        # פוסטר וסקר
        if f"poster_{today_key}" not in tasks_done:
            img_desc = f"cinematic%20football%20poster%20Hapoel%20Petah%20Tikva%20blue%20vs%20{match['opp_name']}"
            img_url = f"https://pollinations.ai/p/{img_desc}"
            
            send_to_all(f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp_name']}\nיוצאים למלחמה! מביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️", photo_url=img_url)
            
            # סקר הימורים
            poll_data = {"question": f"איך יסתיים המשחק מול {match['opp_name']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_all("", is_poll=True, poll_data=poll_data)
            
            with open(task_log, 'a') as f: f.write(f"poster_{today_key}\n")

        # סיום משחק (אם הסטטוס הוא FT)
        if match['status'] == 'FT' and f"end_{today_key}" not in tasks_done:
            msg = f"סיום המשחק! {match['my_score']}:{match['opp_score']} להפועל מול {match['opp_name']}. יאללה הפועל! 💙"
            send_to_all(msg)
            with open(task_log, 'a') as f: f.write(f"end_{today_key}\n")
    else:
        print("❌ לא זוהה משחק להיום ב-API.")

    print("🏁 סיום.")

if __name__ == "__main__": main()
