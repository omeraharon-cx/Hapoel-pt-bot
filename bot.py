import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
import html
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264423"
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

# מפת תרגום שחקנים מעודכנת
PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "תומר אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "ממאדי דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

# רשימת הגיבוי שביקשת
DEFAULT_PLAYERS = [
    "עומר כץ", "אוראל דגני", "איתי רוטמן", "דרור ניר", "עידן כהן", 
    "נדב נידם", "רועי דוד", "יונתן כהן", "מארק קוסטה", "שביט מזל", "קליי"
]

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש-אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def escape_html(text):
    if not text: return ""
    return html.escape(text)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        payload = {"chat_id": ADMIN_ID, "parse_mode": "HTML"}
        if is_poll:
            r = requests.post(f"{url_base}/sendPoll", json={**payload, **poll_data}, timeout=10)
        elif photo_url:
            payload.update({"photo": photo_url, "caption": text, "reply_markup": reply_markup})
            r = requests.post(f"{url_base}/sendPhoto", json=payload, timeout=15)
        else:
            payload.update({"text": text, "reply_markup": reply_markup})
            r = requests.post(f"{url_base}/sendMessage", json=payload, timeout=10)
        print(f"DEBUG: Telegram Status {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_ai_summary(text, title, recent_summaries):
    if not GEMINI_API_KEY: return None
    context = "\n".join(recent_summaries)
    prompt = (
        f"אתה עיתונאי ספורט עבור אוהדי הפועל פתח תקווה. "
        f"כתוב תקציר של 4-5 משפטים על הכתבה הבאה. התמקד רק במידע שרלוונטי להפועל פתח תקווה. "
        f"אל תחזור על מידע מהעדכונים האלו: {context}. "
        f"אם הכתבה לא קשורה להפועל פתח תקווה, כתוב רק: SKIP\n"
        f"טקסט: {text[:3500]}"
    )
    try:
        # חזרה ל-v1beta עם שם מודל מפורש - זה השילוב הכי יציב
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return result if "SKIP" not in result.upper() else None
        else:
            print(f"DEBUG Gemini API Error {res.status_code}")
            print(f"DEBUG Gemini Error Body: {res.text}") # זה יעזור לנו להבין בדיוק למה 404
    except: pass
    return None

def get_match_data():
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    now_il = get_israel_time()
    dates = [now_il.strftime('%Y-%m-%d'), (now_il - timedelta(days=1)).strftime('%Y-%m-%d')]
    for endpoint in ["next", "last"]:
        try:
            url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/{endpoint}/0"
            res = requests.get(url, headers=headers, timeout=10).json()
            for event in res.get('events', []):
                dt = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
                if dt in dates:
                    is_h = str(event['homeTeam']['id']) == TEAM_ID
                    return {
                        "id": event['id'], "status": event.get('status', {}).get('type'), "date": dt,
                        "my_score": event.get('homeScore', {}).get('display', 0) if is_h else event.get('awayScore', {}).get('display', 0),
                        "opp_score": event.get('awayScore', {}).get('display', 0) if is_h else event.get('homeScore', {}).get('display', 0)
                    }
        except: continue
    return None

def get_mvp_players(event_id):
    try:
        url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
        res = requests.get(url, headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}, timeout=10).json()
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        lineup = [p['player']['name'] for p in res[side].get('lineup', [])]
        lineup += [p['player']['name'] for p in res[side].get('substitutes', []) if p.get('statistics', {}).get('minutesPlayed', 0) > 0]
        translated = [PLAYER_MAP.get(n, n) for n in lineup]
        if translated: return list(dict.fromkeys(translated))[:10]
    except: pass
    return DEFAULT_PLAYERS

def main():
    now = get_israel_time()
    print(f"--- ריצה: {now.strftime('%H:%M:%S')} ---")
    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(line.strip() for line in f if line.strip())
    with open(db_file, 'r') as f: history = set(line.strip() for line in f if line.strip())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-15:]

    match = get_match_data()
    if match and match['status'] in ['finished', 'FT']:
        m_date = match['date']
        if f"final_msg_{m_date}" not in tasks:
            if match['my_score'] > match['opp_score']:
                txt = f"{random.choice(WIN_CHANTS)}\n\n<b>ניצחון ענק!</b> {match['my_score']}-{match['opp_score']} להפועל! 💙"
            elif match['my_score'] == match['opp_score']:
                txt = f"תיקו בסיום המשחק. ⚽\nהתוצאה: {match['my_score']}-{match['opp_score']}.\n\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
            else:
                txt = f"סיום המשחק. התוצאה: {match['opp_score']}-{match['my_score']} ליריבה. מרימים את הראש! יאללה הפועל מלחמה! 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
            if send_to_telegram(txt, reply_markup=markup):
                with open(task_file, 'a') as f: f.write(f"final_msg_{m_date}:{now.strftime('%H:%M')}\n")
                tasks.add(f"final_msg_{m_date}:{now.strftime('%H:%M')}")

        final_task = [t for t in tasks if t.startswith(f"final_msg_{m_date}:")]
        if final_task and f"mvp_poll_{m_date}" not in tasks:
            t_parts = final_task[0].split(":")[-2:]
            if now.minute >= int(t_parts[1]) + 10 or now.hour > int(t_parts[0]):
                players = get_mvp_players(match['id'])
                poll = {"question": "מי המצטיין שלכם היום? ⚽️", "options": players, "is_anonymous": False}
                if send_to_telegram("", is_poll=True, poll_data=poll):
                    with open(task_file, 'a') as f: f.write(f"mvp_poll_{m_date}\n")

    print("📡 סורק כתבות...")
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            if entry.link in history: continue
            try:
                res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                text = " ".join([p.get_text() for p in soup.find_all('p')])
                if any(k in (entry.title + text) for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    summary = get_ai_summary(text, entry.title, recent)
                    if summary:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{escape_html(summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                        if send_to_telegram(msg):
                            with open(db_file, "a") as f: f.write(entry.link + "\n")
                            with open(sum_db, "a", encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                            history.add(entry.link)
                    else: print(f"DEBUG: AI skipped summary for {entry.title}")
            except Exception as e: 
                print(f"DEBUG Error scanning {entry.link}: {e}")
    print("--- סיום ---")

if __name__ == "__main__": main()
