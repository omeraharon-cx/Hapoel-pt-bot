import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import urllib.parse
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
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
        except: pass

def get_ai_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None
    return None

def get_match_players(event_id):
    """מושך את שמות השחקנים מהמשחק לסקר MVP"""
    url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        players = []
        # מחפש את הקבוצה שלנו בהרכבים
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        for p in res.get(side, {}).get('lineup', []):
            players.append(p['player']['name'])
        return players[:10] # 10 ראשונים לסקר
    except: return ["רועי דוד", "עומר כץ", "איתי שכטר", "רם לוי", "עידן ורד"]

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    
    # --- 1. היסטוריה של יום רביעי ---
    if now.weekday() == 2 and 10 <= now.hour <= 12:
        task_file = "task_log.txt"
        if not os.path.exists(task_file): open(task_file, 'w').close()
        with open(task_file, 'r') as f: tasks = f.read().splitlines()
        
        if f"history_{today_str}" not in tasks:
            prompt = "ספר לאוהדי הפועל פתח תקווה על אירוע היסטורי מרגש מהעבר של המועדון (אליפויות, שחקני עבר, משחקים מפורסמים). כתוב ב-4 משפטים, טון חברי ומרגש."
            hist_msg = get_ai_response(prompt)
            if hist_msg:
                send_to_telegram(f"📜 **רביעי היסטורי**\n\n{hist_msg}")
                with open(task_file, 'a') as f: f.write(f"history_{today_str}\n")

    # --- 2. כתבות RSS ---
    db_file = "seen_links.txt"
    sum_db = "recent_summaries.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    if not os.path.exists(sum_db): open(sum_db, 'w').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-10:]

    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    for entry in feed.entries[:5]:
        if entry.link not in history:
            print(f"מעבד כתבה: {entry.title}")
            prompt = (
                f"כתוב תקציר של 4-5 משפטים על הכתבה הבאה. "
                f"דגשים: טון חברי ובגובה העיניים (לא רשמי), התמקד רק בחלק שקשור להפועל פתח תקווה. "
                f"מנע כפילות עם תקצירים קודמים: {recent}. \nטקסט: {entry.title}"
            )
            summary = get_ai_response(prompt)
            if summary and "SKIP" not in summary.upper():
                msg = f"💙 **עדכון חדש מהשטח**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                send_to_telegram(msg)
                with open(db_file, 'a') as f: f.write(entry.link + "\n")
                with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")

    # --- 3. לוגיקת משחק (SportAPI7) ---
    url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        for event in res.get('events', []):
            ev_date = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
            if ev_date == today_str:
                opp = TEAM_TRANSLATIONS.get(event['awayTeam']['name'], event['awayTeam']['name'])
                status = event.get('status', {}).get('type')
                
                # Match Day
                task_file = "task_log.txt"
                with open(task_file, 'r') as f: tasks = f.read().splitlines()
                if f"matchday_v6_{today_str}" not in tasks:
                    msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {opp}\nמביאים 3 נקודות בעזרת השם!\n\nיאללה הפועל! ⚽️"
                    # פוסטר משופר
                    poster = f"https://pollinations.ai/p/Action_shot_of_blue_football_stadium_with_crowd_Hapoel_Petah_Tikva_theme_cinematic_lighting_hyper_realistic"
                    send_to_telegram(msg, photo_url=poster)
                    poll = {"question": f"מה ההימור למשחק מול {opp}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
                    send_to_telegram("", is_poll=True, poll_data=poll)
                    with open(task_file, 'a') as f: f.write(f"matchday_v6_{today_str}\n")

                # End Match
                if status == 'finished' and f"finish_v6_{today_str}" not in tasks:
                    h_score = event['homeScore']['display']
                    a_score = event['awayScore']['display']
                    my_score = h_score if str(event['homeTeam']['id']) == TEAM_ID else a_score
                    opp_score = a_score if str(event['homeTeam']['id']) == TEAM_ID else h_score
                    
                    if my_score > opp_score:
                        result_msg = f"{random.choice(WIN_CHANTS)}\n\nניצחון ענק! {my_score}-{opp_score} להפועל! 💙"
                    elif my_score == opp_score:
                        result_msg = f"תיקו {my_score}-{my_score}. ממשיכים להילחם! 💙"
                    else:
                        result_msg = f"הפסד {opp_score}-{my_score}. מרימים את הראש, יאללה הפועל בכל מצב! 💙"
                    
                    send_to_all(result_msg)
                    players = get_match_players(event['id'])
                    mvp_poll = {"question": "מי השחקן המצטיין שלכם הערב? ⚽️", "options": players, "is_anonymous": False}
                    send_to_telegram("", is_poll=True, poll_data=mvp_poll)
                    with open(task_file, 'a') as f: f.write(f"finish_v6_{today_str}\n")
    except: pass

if __name__ == "__main__": main()
