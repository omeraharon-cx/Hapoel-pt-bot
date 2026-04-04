import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים של GitHub
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199" # הפועל פתח תקווה

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    print(f"LOG: שולח ל-{len(subs)} מנויים...")
    for cid in subs:
        try:
            if is_poll:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        except Exception as e:
            print(f"LOG ERROR: תקלה בשליחה ל-{cid}: {e}")

def get_ai_summary(title, content=""):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Summarize for Hapoel Petah Tikva fans in 3 Hebrew sentences. Casual tone. TEXT: {title}. {content[:1000]}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"LOG: AI נכשל (סטטוס {response.status_code}). תגובה: {response.text[:100]}")
    except Exception as e:
        print(f"LOG: תקלה בפנייה ל-AI: {e}")
    return None

def check_match_status():
    today = get_israel_time().strftime('%Y-%m-%d')
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    
    print(f"LOG: בודק לוח משחקים עבור הפועל פתח תקווה (ID: {TEAM_ID})...")
    try:
        # מושכים את 10 המשחקים הקרובים כדי לוודא שלא נפספס בגלל תאריך
        res = requests.get(url, headers=headers, params={"team": TEAM_ID, "next": "10"}, timeout=15).json()
        
        if not res.get('response'):
            print("LOG: ה-API לא החזיר משחקים קרובים.")
            return None

        for m in res['response']:
            match_date = m['fixture']['date'][:10]
            if match_date == today:
                is_home = str(m['teams']['home']['id']) == TEAM_ID
                opp = m['teams']['away']['name'] if is_home else m['teams']['home']['name']
                print(f"LOG: ✅ נמצא משחק להיום ב-API! נגד {opp}")
                return {
                    "id": m['fixture']['id'],
                    "status": m['fixture']['status']['short'],
                    "opp_name": opp,
                    "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                    "opp_score": m['goals']['away'] if is_home else m['goals']['home']
                }
        print(f"LOG: לא נמצא משחק ב-API שחל היום ({today}).")
    except Exception as e:
        print(f"LOG ERROR: תקלה ב-Football API: {e}")
    return None

def main():
    now = get_israel_time()
    today_key = now.strftime('%Y-%m-%d')
    print(f"🚀 ריצה התחילה: {now.strftime('%H:%M:%S')} (זמן ישראל)")

    # 1. RSS
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())

    hapoel_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הכחולים", "מבנה"]
    
    print("📰 סורק פידים...")
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/"]
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            if entry.link not in history:
                if any(k in entry.title.lower() for k in hapoel_keys):
                    print(f"LOG: מעבד כתבה רלוונטית: {entry.title}")
                    summary = get_ai_summary(entry.title)
                    display_text = summary if summary else entry.title # אם ה-AI נכשל, שמים את הכותרת
                    
                    send_to_all(f"**עדכון חדש על הפועל 💙**\n\n{display_text}\n\n🔗 [לכתבה המלאה]({entry.link})")
                    
                    # שומרים להיסטוריה רק אם ההודעה נשלחה (או לפחות ניסינו)
                    with open(db_file, 'a') as f: f.write(entry.link + "\n")
                    history.add(entry.link)
                    time.sleep(5)

    # 2. יום משחק
    match = check_match_status()
    task_log = "task_log.txt"
    if not os.path.exists(task_log): open(task_log, 'w').close()
    with open(task_log, 'r') as f: tasks_done = set(f.read().splitlines())

    if match:
        if f"match_v2_{today_key}" not in tasks_done:
            print(f"LOG: שולח פוסטר וסקר למשחק מול {match['opp_name']}")
            clean_opp = urllib.parse.quote(match['opp_name'])
            img_url = f"https://pollinations.ai/p/football%20poster%20Hapoel%20Petah%20Tikva%20blue%20vs%20{clean_opp}"
            
            send_to_all(f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp_name']}\nיוצאים למלחמה! מביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️", photo_url=img_url)
            
            poll_data = {"question": f"איך יסתיים המשחק מול {match['opp_name']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_all("", is_poll=True, poll_data=poll_data)
            
            with open(task_log, 'a') as f: f.write(f"match_v2_{today_key}\n")

        # עדכון סיום משחק
        if match['status'] == 'FT' and f"final_v2_{today_key}" not in tasks_done:
            res_msg = f"סיום המשחק! {match['my_score']}:{match['opp_score']} להפועל מול {match['opp_name']}. יאללה הפועל! 💙"
            send_to_all(res_msg)
            with open(task_log, 'a') as f: f.write(f"final_v2_{today_key}\n")

    print("🏁 סיום ריצה.")

if __name__ == "__main__": main()
