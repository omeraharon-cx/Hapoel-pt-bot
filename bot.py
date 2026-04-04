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

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני המועדון ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה",
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Tel Aviv": "הפועל תל אביב"
}

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש*אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם! 💙"
]

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
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}, timeout=15)
                if res.status_code != 200:
                    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            else:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
            if r.status_code == 200: success = True
        except: pass
    return success

def get_ai_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        time.sleep(2)
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def get_match_players(event_id):
    url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        players = []
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        for p in res.get(side, {}).get('lineup', []):
            players.append(p['player']['name'])
        return players[:10]
    except: return ["רועי דוד", "עומר כץ", "מתן גושה", "רם לוי", "דרור ניר"]

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- ריצה תשתיתית: {now.strftime('%H:%M:%S')} ---")

    # ניהול קבצים
    db_file, sum_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, sum_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-10:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    # 1. יום רביעי היסטורי
    if now.weekday() == 2 and 10 <= now.hour <= 12:
        if f"hist_stable_{today_str}" not in tasks_done:
            prompt = "ספר לאוהדי הפועל פתח תקווה על אירוע היסטורי מהעבר של המועדון. כתוב ב-4 משפטים, טון חברי ומרגש."
            txt = get_ai_response(prompt)
            if txt:
                send_to_telegram(f"📜 **רביעי היסטורי**\n\n{txt}")
                with open(task_file, 'a') as f: f.write(f"hist_stable_{today_str}\n")

    # 2. יום משחק (SportAPI7)
    url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        for event in res.get('events', []):
            ev_date = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
            if ev_date == today_str:
                home_raw = event['homeTeam']['name']
                away_raw = event['awayTeam']['name']
                opp = TEAM_TRANSLATIONS.get(away_raw, away_raw) if str(event['homeTeam']['id']) == TEAM_ID else TEAM_TRANSLATIONS.get(home_raw, home_raw)
                status = event.get('status', {}).get('type')

                # הודעת Match Day - פעם אחת ביום!
                if f"matchday_stable_{today_str}" not in tasks_done:
                    msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {opp}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
                    poster = f"https://pollinations.ai/p/Action_shot_football_stadium_blue_Hapoel_Petah_Tikva_fans_cinematic"
                    send_to_telegram(msg, photo_url=poster)
                    poll = {"question": f"איך יסתיים המשחק מול {opp}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
                    send_to_telegram("", is_poll=True, poll_data=poll)
                    with open(task_file, 'a') as f: f.write(f"matchday_stable_{today_str}\n")

                # הודעת סיום משחק
                if status == 'finished' and f"final_stable_{today_str}" not in tasks_done:
                    h_score = event.get('homeScore', {}).get('display', 0)
                    a_score = event.get('awayScore', {}).get('display', 0)
                    my_score = h_score if str(event['homeTeam']['id']) == TEAM_ID else a_score
                    opp_score = a_score if str(event['homeTeam']['id']) == TEAM_ID else h_score
                    
                    if my_score > opp_score:
                        res_msg = f"{random.choice(WIN_CHANTS)}\n\nניצחון ענק! {my_score}-{opp_score} להפועל! 💙"
                    elif my_score == opp_score:
                        res_msg = f"תיקו {my_score}-{opp_score}. ממשיכים להילחם בכל מצב! 💙"
                    else:
                        res_msg = f"סיום בטרנר. {opp_score}-{my_score} לבאר שבע. מרימים את הראש, יאללה הפועל! 💙"
                    
                    send_to_telegram(res_msg)
                    players = get_match_players(event['id'])
                    mvp_poll = {"question": "מי השחקן המצטיין שלכם הערב? ⚽️", "options": players, "is_anonymous": False}
                    send_to_telegram("", is_poll=True, poll_data=mvp_poll)
                    with open(task_file, 'a') as f: f.write(f"final_stable_{today_str}\n")
    except: pass

    # 3. כתבות RSS
    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    keywords = ["הפועל", "פתח", "מבנה", "כחולים", "מלאבס"]
    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in keywords):
                prompt = (
                    f"כתוב תקציר של 4-5 משפטים על הכתבה הבאה. "
                    f"טון: חברי ובגובה העיניים. התמקד רק במה שקשור להפועל פתח תקווה. "
                    f"מנע כפילות עם: {recent}. \nטקסט: {entry.title}"
                )
                summary = get_ai_response(prompt)
                display = summary if summary else entry.title
                msg = f"💙 **עדכון חדש**\n\n{display}\n\n🔗 [לכתבה המלאה]({entry.link})"
                if send_to_telegram(msg):
                    with open(db_file, 'a') as f: f.write(entry.link + "\n")
                    if summary:
                        with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
