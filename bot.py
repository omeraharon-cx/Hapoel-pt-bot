import feedparser
import requests
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית של לוגים בעברית
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני הפועל פתח תקווה ב-SportAPI ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    for cid in subs:
        try:
            if is_poll:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}, timeout=15)
                if res.status_code != 200:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            else:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"LOG: שגיאה בשליחה ל-{cid}: {e}")

def get_ai_summary(title):
    if not GEMINI_API_KEY: return title
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        time.sleep(2)
        res = requests.post(url, json={"contents": [{"parts": [{"text": f"סכם ב-2 משפטים לאוהדי הפועל פתח תקווה: {title}"}]}]}, timeout=10)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: pass
    return title

def check_for_match():
    # משתמשים ב-next/0 כדי לראות את המשחקים הבאים/הנוכחיים
    url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    
    print(f"INFRA: בודק לוח משחקים ב-{RAPIDAPI_HOST}...")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"INFRA ERROR: API החזיר סטטוס {response.status_code}")
            return None
        
        data = response.json()
        events = data.get('events', [])
        today = get_israel_time().strftime('%Y-%m-%d')
        
        for event in events:
            dt = datetime.fromtimestamp(event.get('startTimestamp', 0))
            if dt.strftime('%Y-%m-%d') == today:
                home = event['homeTeam']['name']
                away = event['awayTeam']['name']
                is_home = str(event['homeTeam']['id']) == TEAM_ID
                opp = away if is_home else home
                status = event.get('status', {}).get('type', 'unknown')
                
                print(f"INFRA: נמצא משחק להיום! {home} נגד {away} (סטטוס: {status})")
                return {
                    "opp": opp,
                    "status": status,
                    "home_score": event.get('homeScore', {}).get('display', 0),
                    "away_score": event.get('awayScore', {}).get('display', 0)
                }
    except Exception as e:
        print(f"INFRA ERROR: {e}")
    return None

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now.strftime('%H:%M:%S')} ---")

    # 1. RSS
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())

    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    keywords = ["הפועל פ״ת", "פתח-תקוה", "פתח תקווה", "מבנה", "באר שבע"]
    
    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in keywords):
                print(f"RSS: מעבד כתבה חדשה: {entry.title}")
                summary = get_ai_summary(entry.title)
                send_to_telegram(f"**חדשות הפועל** 💙\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})")
                with open(db_file, 'a') as f: f.write(entry.link + "\n")
                history.add(entry.link)

    # 2. Match Day
    match = check_for_match()
    task_file = "task_log.txt"
    if not os.path.exists(task_file): open(task_file, 'w').close()
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    if match:
        if f"matchday_v4_{today_str}" not in tasks_done:
            print("MATCH: שולח הודעת יום משחק")
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            poster = f"https://pollinations.ai/p/football%20stadium%20blue%20Hapoel%20Petah%20Tikva%20vs%20{urllib.parse.quote(match['opp'])}"
            send_to_telegram(msg, photo_url=poster)
            
            poll = {"question": f"איך יסתיים המשחק מול {match['opp']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_telegram("", is_poll=True, poll_data=poll)
            
            with open(task_file, 'a') as f: f.write(f"matchday_v4_{today_str}\n")

        if match['status'] == 'finished' and f"finished_v4_{today_str}" not in tasks_done:
            print("MATCH: המשחק הסתיים")
            score = f"{match['home_score']}-{match['away_score']}"
            res_msg = f"סיום המשחק! ⚽️\nתוצאה: {score}\nיאללה הפועל בכל מצב! 💙"
            send_to_telegram(res_msg)
            with open(task_file, 'a') as f: f.write(f"finished_v4_{today_str}\n")
    else:
        print("MATCH: לא זוהה משחק להיום בלוח האירועים.")

    print("--- סיום ריצה ---")

if __name__ == "__main__":
    main()
