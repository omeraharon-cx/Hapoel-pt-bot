import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
from datetime import datetime, timedelta
import calendar

# מוודא שההדפסות יופיעו מיד בלוג
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מזהים (RapidAPI) ---
TEAM_ID = "5199" 
LEAGUE_ID = "877"

# --- הגדרות מערכת (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_subscribers():
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f:
        return list(set(line.strip() for line in f if line.strip()))

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll and poll_data:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll"
                payload = {"chat_id": cid, **poll_data}
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
                if reply_markup: payload["reply_markup"] = reply_markup
            requests.post(url, json=payload, timeout=10)
        except: pass

def get_match_players(fixture_id):
    """שואב את רשימת השחקנים ששיחקו במשחק ספציפי מ-RapidAPI"""
    url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players_data = res['response'][0]['players']
        # לוקחים שחקנים ששיחקו (דקות > 0) וממיינים לפי ציון אם קיים
        played_players = [p for p in players_data if p['statistics'][0]['games']['minutes'] or 0 > 0]
        names = [p['player']['name'] for p in played_players[:10]] # מקסימום 10 לסקר
        return names if names else ["שחקן אחר"]
    except:
        return ["עומר כץ", "רם לוי", "דרור ניר", "רוי נאווי", "מתן פלג"] # ברירת מחדל אם נכשל

def check_match_status():
    """בודק תוצאה וסטטוס משחק מ-RapidAPI"""
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    today = datetime.now().strftime('%Y-%m-%d')
    params = {"team": TEAM_ID, "date": today}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            status = m['fixture']['status']['short']
            fixture_id = m['fixture']['id']
            home_score = m['goals']['home']
            away_score = m['goals']['away']
            is_home = str(m['teams']['home']['id']) == TEAM_ID
            
            my_score = home_score if is_home else away_score
            opp_score = away_score if is_home else home_score
            opp_name = m['teams']['away']['name'] if is_home else m['teams']['home']['name']
            
            return {
                "id": fixture_id,
                "status": status,
                "my_score": my_score,
                "opp_score": opp_score,
                "opp_name": opp_name,
                "venue": m['fixture']['venue']['name']
            }
    except: return None
    return None

def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}", flush=True)
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    
    task_file = "task_log.txt"
    if not os.path.exists(task_file): open(task_file, 'w').close()
    with open(task_file, 'r') as f: tasks_done = f.read().splitlines()

    # 1. בדיקת סטטוס משחק (הימורים, פוסטר, וסיום)
    match = check_match_status()
    
    if match:
        # בוקר המשחק (15:00)
        if now.hour == 15 and f"match_start_{today_key}" not in tasks_done:
            msg = f"⚽️ **יום משחק! MATCH DAY** ⚽️\nהיום נגד {match['opp_name']}\n🏟 {match['venue']}\n\nיאלההה הפועל! 💙"
            send_to_all(msg)
            send_to_all("", is_poll=True, poll_data={
                "question": f"איך יסתיים המשחק היום מול {match['opp_name']}?",
                "options": ["ניצחון כחול 💙", "תיקו", "הפסד (חס וחלילה)"],
                "is_anonymous": False
            })
            with open(task_file, 'a') as f: f.write(f"match_start_{today_key}\n")

        # סיום המשחק (FT)
        if match['status'] == 'FT' and f"match_end_{today_key}" not in tasks_done:
            result_text = f"🏁 **שריקת הסיום!**\nהפועל {match['my_score']} - {match['opp_score']} {match['opp_name']}"
            
            if match['my_score'] > match['opp_score']:
                result_text += "\n\nכחול זה הצבע, כחול זה בלב\nכחול זה הפועלללל - אותך רק אוהב\nאיזה נצחוןןן של הפועל שלנו\nיאלההה הפועל 💙"
            elif match['my_score'] == match['opp_score']:
                result_text += "\n\nנגמר בתיקו. ממשיכים קדימה בכל הכוח! 💪"
            else:
                result_text += "\n\nהפסד כואב, אבל הראש תמיד למעלה. נחזור חזקים יותר. 💙"
            
            # כפתור טבלה רק כאן!
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": "https://www.football.co.il/leagues/israeli-premier-league/table"}]]}
            send_to_all(result_text, reply_markup=markup)
            
            # סקר שחקנים דינמי אחרי 10 דקות (במקרה שלנו בריצה הבאה או delay)
            players = get_match_players(match['id'])
            send_to_all("", is_poll=True, poll_data={
                "question": "מי השחקן המצטיין שלכם היום? ⚽️",
                "options": players,
                "is_anonymous": False
            })
            
            with open(task_file, 'a') as f: f.write(f"match_end_{today_key}\n")

    # 2. פינת היסטוריה (רביעי ב-12:00) כרגיל...
    # (המשך הקוד של RSS_FEEDS נשאר זהה לגרסה הקודמת ללא כפתור הטבלה)

    print("🏁 סיום.")

if __name__ == "__main__":
    main()
