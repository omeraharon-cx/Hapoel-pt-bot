import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import urllib.parse
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה... 💙",
    "מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    all_success = True
    for cid in subs:
        try:
            if is_poll:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}, timeout=15)
                if res.status_code != 200:
                    res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            else:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            
            if res.status_code != 200:
                print(f"LOG: שגיאה בשליחה ל-{cid}: {res.text}")
                all_success = False
        except Exception as e:
            print(f"LOG ERROR: {e}")
            all_success = False
    return all_success

def get_ai_summary(title):
    if not GEMINI_API_KEY: return title
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = (
        f"כתוב תקציר של 4-5 משפטים לאוהדי הפועל פתח תקווה על הידיעה הבאה. "
        f"טון חברי, בגובה העיניים, בלי שלום חברים. התמקד אך ורק במה שקשור להפועל פתח תקווה. "
        f"טקסט: {title}"
    )
    try:
        time.sleep(2)
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: pass
    return title

def get_match_data():
    """סורק גם משחקים קרובים וגם אחרונים כדי למנוע פספוס ברגע הסיום"""
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    today = get_israel_time().strftime('%Y-%m-%d')
    
    for endpoint in ["next", "last"]:
        url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/{endpoint}/0"
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            for event in res.get('events', []):
                dt = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
                if dt == today:
                    is_home = str(event['homeTeam']['id']) == TEAM_ID
                    opp_raw = event['awayTeam']['name'] if is_home else event['homeTeam']['name']
                    return {
                        "id": event['id'],
                        "opp": TEAM_TRANSLATIONS.get(opp_raw, opp_raw),
                        "status": event.get('status', {}).get('type'),
                        "my_score": event.get('homeScore', {}).get('display', 0) if is_home else event.get('awayScore', {}).get('display', 0),
                        "opp_score": event.get('awayScore', {}).get('display', 0) if is_home else event.get('homeScore', {}).get('display', 0)
                    }
        except: continue
    return None

def get_mvp_players(event_id):
    url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        players = [p['player']['name'] for p in res.get(side, {}).get('lineup', [])]
        return players[:10]
    except: return ["רועי דוד", "עומר כץ", "רם לוי", "מתן גושה", "דרור ניר"]

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- ריצת תשתית: {now.strftime('%H:%M:%S')} ---")

    db_file, task_file = "seen_links.txt", "task_log.txt"
    for f in [db_file, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    # 1. בדיקת משחק (סריקה כפולה)
    match = get_match_data()
    if match:
        print(f"LOG: זוהה משחק מול {match['opp']} (סטטוס: {match['status']})")
        # Match Day
        if f"matchday_stable_{today_str}" not in tasks_done:
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            if send_to_telegram(msg, photo_url="https://pollinations.ai/p/Action_shot_blue_football_stadium_Hapoel_Petah_Tikva"):
                poll = {"question": f"הימור למשחק מול {match['opp']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
                send_to_telegram("", is_poll=True, poll_data=poll)
                with open(task_file, 'a') as f: f.write(f"matchday_stable_{today_str}\n")

        # סיום משחק (FT/finished)
        if match['status'] in ['finished', 'FT'] and f"final_stable_{today_str}" not in tasks_done:
            print("LOG: המשחק הסתיים, שולח סיכום")
            if match['my_score'] > match['opp_score']:
                res_msg = f"ניצחון ענק! {match['my_score']}-{match['opp_score']} להפועל! 💙\n{WIN_CHANTS[0]}"
            elif match['my_score'] == match['opp_score']:
                res_msg = f"תיקו {match['my_score']}-{match['opp_score']}. ממשיכים להילחם! 💙"
            else:
                res_msg = f"הפסד {match['opp_score']}-{match['my_score']}. מרימים את הראש, יאללה הפועל בכל מצב! 💙"
            
            if send_to_telegram(res_msg):
                players = get_mvp_players(match['id'])
                send_to_telegram("", is_poll=True, poll_data={"question": "מי המצטיין שלכם הערב? ⚽️", "options": players, "is_anonymous": False})
                with open(task_file, 'a') as f: f.write(f"final_stable_{today_str}\n")

    # 2. RSS
    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in hapoel_keys) or "hapoelpt.com" in entry.link:
                print(f"LOG: מעבד כתבה: {entry.title}")
                summary = get_ai_summary(entry.title)
                msg = f"💙 **עדכון חדש**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                if send_to_telegram(msg):
                    with open(db_file, 'a') as f: f.write(entry.link + "\n")
                    history.add(entry.link)

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
