import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import urllib.parse
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני המועדון (קבועים) ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

# מילון תרגום קבוע ליריבות (מתעדכן אוטומטית ככל שיש משחקים)
TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Tel Aviv": "הפועל תל אביב",
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Petah Tikva": "הפועל פתח תקווה",
    "F.C. Ashdod": "מ.ס. אשדוד",
    "Hapoel Jerusalem": "הפועל ירושלים"
}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    success = False
    for cid in subs:
        try:
            if is_poll:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}, timeout=15)
                if r.status_code != 200: # Fallback אם התמונה נכשלת
                    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            else:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            
            if r.status_code == 200: success = True
        except: pass
    return success

def get_ai_summary(title, recent_summaries):
    if not GEMINI_API_KEY: return None
    summaries_context = "\n".join([f"- {s}" for s in recent_summaries])
    
    prompt = (
        f"Analyze if this news about Hapoel Petah Tikva is a duplicate of these recent updates:\n{summaries_context}\n"
        "If it is a duplicate or not about them, return ONLY: SKIP\n"
        "Otherwise, write a 3-sentence Hebrew summary. Casual tone, NO greetings, focus on impact.\n"
        f"TEXT: {title}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        # המתנה של 5 שניות למניעת חסימת מכסה (429)
        time.sleep(5)
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if "SKIP" in result.upper(): return "REJECTED"
            return result
    except: pass
    return None

def check_match_infrastructure():
    url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            today = get_israel_time().strftime('%Y-%m-%d')
            for event in data.get('events', []):
                dt = datetime.fromtimestamp(event.get('startTimestamp', 0))
                if dt.strftime('%Y-%m-%d') == today:
                    home = TEAM_TRANSLATIONS.get(event['homeTeam']['name'], event['homeTeam']['name'])
                    away = TEAM_TRANSLATIONS.get(event['awayTeam']['name'], event['awayTeam']['name'])
                    is_home = str(event['homeTeam']['id']) == TEAM_ID
                    opp = away if is_home else home
                    return {
                        "opp": opp,
                        "status": event.get('status', {}).get('type', 'unknown'),
                        "home_score": event.get('homeScore', {}).get('display', 0),
                        "away_score": event.get('awayScore', {}).get('display', 0)
                    }
    except: pass
    return None

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה תשתיתית: {now.strftime('%H:%M:%S')} ---")

    # ניהול היסטוריה
    db_file, sum_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, sum_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent_summaries = f.read().splitlines()[-10:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    # 1. יום משחק (תמיד בעדיפות)
    match = check_match_infrastructure()
    if match:
        print(f"LOG: זוהה משחק מול {match['opp']}")
        if f"matchday_infra_{today_str}" not in tasks_done:
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            poster = f"https://pollinations.ai/p/cinematic%20football%20stadium%20blue%20Hapoel%20Petah%20Tikva%20matchday%20poster"
            if send_to_telegram(msg, photo_url=poster):
                poll = {"question": f"הימור שלכם מול {match['opp']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
                send_to_telegram("", is_poll=True, poll_data=poll)
                with open(task_file, 'a') as f: f.write(f"matchday_infra_{today_str}\n")

        if match['status'] == 'finished' and f"finished_infra_{today_str}" not in tasks_done:
            score = f"{match['home_score']}-{match['away_score']}"
            send_to_telegram(f"סיום המשחק! ⚽️\nתוצאה: {score}\nיאללה הפועל בכל מצב! 💙")
            with open(task_file, 'a') as f: f.write(f"finished_infra_{today_str}\n")

    # 2. RSS
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/"]

    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            if entry.link not in history:
                if any(k in entry.title.lower() for k in hapoel_keys) or "hapoelpt.com" in entry.link:
                    print(f"LOG: מעבד כתבה: {entry.title}")
                    summary = get_ai_summary(entry.title, recent_summaries)
                    
                    if summary == "REJECTED": continue
                    
                    display_text = summary if summary else entry.title
                    msg = f"**יש עדכון חדש על הפועל 💙**\n\n{display_text}\n\n🔗 [לכתבה המלאה]({entry.link})"
                    
                    if send_to_telegram(msg):
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        if summary:
                            with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                        history.add(entry.link)

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
