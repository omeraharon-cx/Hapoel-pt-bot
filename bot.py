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

# פונקציית עזר לבדיקת תקינות מפתחות בלוג
def check_keys():
    print(f"--- אבחון מפתחות ---")
    print(f"Gemini Key: {GEMINI_API_KEY[:5]}***" if GEMINI_API_KEY else "Gemini Key: MISSING ❌")
    print(f"Telegram Token: {TELEGRAM_TOKEN[:5]}***" if TELEGRAM_TOKEN else "Telegram Token: MISSING ❌")
    print(f"RapidAPI Key: {RAPIDAPI_KEY[:5]}***" if RAPIDAPI_KEY else "RapidAPI Key: MISSING ❌")
    print(f"-------------------")

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = list(set(line.strip() for line in open("subscribers.txt", 'r') if line.strip())) if os.path.exists("subscribers.txt") else [ADMIN_ID]
    print(f"DEBUG: מנסה לשלוח ל-{len(subs)} מנויים: {subs}")
    for cid in subs:
        try:
            if is_poll:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
            
            print(f"DEBUG: תשובת טלגרם ל-{cid}: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"DEBUG: שגיאה פיזית בשליחה ל-{cid}: {e}")

def get_ai_summary(text, recent_summaries):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Summarize in 3 Hebrew sentences for Hapoel PT fans. Casual tone. TEXT: {text[:2000]}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if response.status_code == 429:
            print(f"DEBUG: AI Quota Exceeded (429). Response: {response.text}")
            return "QUOTA_EXCEEDED"
        return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def check_match_status():
    today = get_israel_time().strftime('%Y-%m-%d')
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    
    print(f"DEBUG: סורק משחקים להיום ({today})...")
    # חיפוש רחב יותר - כל המשחקים בליגה הישראלית (ID 281 בדרך כלל) או לפי קבוצה
    try:
        url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
        # ניסיון לפי TEAM_ID
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "last": "1"}, timeout=15).json()
        if res.get('response'):
            m = res['response'][0]
            print(f"DEBUG: משחק אחרון שנמצא: {m['fixture']['date']} - {m['teams']['home']['name']} vs {m['teams']['away']['name']}")
            if m['fixture']['date'].startswith(today):
                return parse_match(m)
        
        # ניסיון נוסף: המשחק הבא
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "next": "1"}, timeout=15).json()
        if res.get('response'):
            m = res['response'][0]
            print(f"DEBUG: משחק הבא שנמצא: {m['fixture']['date']} - {m['teams']['home']['name']} vs {m['teams']['away']['name']}")
            if m['fixture']['date'].startswith(today):
                return parse_match(m)
    except Exception as e:
        print(f"DEBUG: תקלה בחיפוש משחק: {e}")
    return None

def parse_match(m):
    is_home = str(m['teams']['home']['id']) == TEAM_ID
    return {
        "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
        "my_score": m['goals']['home'] if is_home else m['goals']['away'],
        "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
        "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name']
    }

def main():
    check_keys()
    now = get_israel_time()
    today_key = now.strftime('%Y-%m-%d')
    
    if not os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "w") as f: f.write(ADMIN_ID + "\n")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    
    hapoel_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל ״מבנה״ פתח-תקוה", "הכחולים"]

    # RSS
    print("--- שלב 1: כתבות ---")
    rss_url = "https://www.hapoelpt.com/blog-feed.xml"
    feed = feedparser.parse(rss_url)
    for entry in feed.entries[:3]:
        if entry.link not in history:
            print(f"DEBUG: מעבד כתבה מהאתר הרשמי: {entry.title}")
            summary = get_ai_summary(entry.title, [])
            msg = f"**עדכון חדש**\n\n{entry.title}\n\n🔗 [לכתבה המלאה]({entry.link})"
            send_to_all(msg)
            with open(db_file, 'a') as f: f.write(entry.link + "\n")
            history.add(entry.link)

    # Match Day
    print("--- שלב 2: יום משחק ---")
    match = check_match_status()
    if match:
        print(f"✅ משחק זוהה: מול {match['opp_name']}")
        task_log = "task_log.txt"
        if not os.path.exists(task_log): open(task_log, 'w').close()
        with open(task_log, 'r') as f: done = f.read().splitlines()
        
        if f"poster_{today_key}" not in done:
            send_to_all(f"Match Day! 💙\nהפועל נגד {match['opp_name']}\nמביאים 3 נקודות!")
            with open(task_log, 'a') as f: f.write(f"poster_{today_key}\n")
    else:
        print("❌ לא נמצא משחק להיום בלוח המשחקים.")

    print("🏁 סיום.")

if __name__ == "__main__": main()
