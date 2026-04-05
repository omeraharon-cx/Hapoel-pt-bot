import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
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

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

DEFAULT_PLAYERS = ["עומר כץ", "שחר רוזן", "דרור ניר", "איתי רוטמן", "אוראל דגני", "מוסונדה", "עידן כהן", "נועם כהן", "אלטמן", "נדב נידם", "רועי דוד", "ארי כהן", "דיארה", "יונתן כהן", "קליי", "סונגה", "קוסטה", "שביט מזל", "בוני"]

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש-אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def clean_html(text):
    if not text: return ""
    return html.escape(str(text))

def send_telegram(text, is_poll=False, poll_data=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    method = "sendPoll" if is_poll else "sendMessage"
    payload = {"chat_id": ADMIN_ID, **(poll_data if is_poll else {"text": text, "parse_mode": "HTML"})}
    try:
        r = requests.post(url + method, json=payload, timeout=10)
        print(f"DEBUG: Telegram {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def get_ai_summary(text, title):
    if not GEMINI_API_KEY: return None
    # שימוש בנתיב v1 היציב ביותר ל-2026
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"כתוב תקציר של 4 משפטים על הכתבה עבור אוהדי הפועל פתח תקווה:\n{text[:3000]}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: pass
    return None

def get_match_data():
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    now = get_israel_time()
    dates = [now.strftime('%Y-%m-%d'), (now - timedelta(days=1)).strftime('%Y-%m-%d')]
    for endpoint in ["next", "last"]:
        try:
            r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/{endpoint}/0", headers=headers, timeout=10).json()
            for ev in r.get('events', []):
                dt = datetime.fromtimestamp(ev['startTimestamp']).strftime('%Y-%m-%d')
                if dt in dates:
                    is_h = str(ev['homeTeam']['id']) == TEAM_ID
                    return {
                        "id": ev['id'], "status": ev.get('status', {}).get('type'), "date": dt,
                        "my": ev.get('homeScore', {}).get('display', 0) if is_h else ev.get('awayScore', {}).get('display', 0),
                        "opp": ev.get('awayScore', {}).get('display', 0) if is_h else ev.get('homeScore', {}).get('display', 0)
                    }
        except: continue
    return None

def get_lineup(ev_id):
    try:
        r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/event/{ev_id}/lineups", headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}, timeout=10).json()
        side = 'home' if str(r.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        names = [p['player']['name'] for p in r[side].get('lineup', [])]
        names += [p['player']['name'] for p in r[side].get('substitutes', []) if p.get('statistics', {}).get('minutesPlayed', 0) > 0]
        translated = [PLAYER_MAP.get(n, n) for n in names]
        return list(dict.fromkeys(translated))[:10]
    except: return DEFAULT_PLAYERS

def main():
    now = get_israel_time()
    print(f"--- {now.strftime('%H:%M:%S')} ריצה ---")
    
    # וודוא קבצים קיימים
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r') as f: tasks = set(line.strip() for line in f)

    # 1. ניהול משחק (תוצאה וסקר)
    match = get_match_data()
    if match and match['status'] in ['finished', 'FT']:
        m_date = match['date']
        # הודעת סיום
        if f"final_{m_date}" not in tasks:
            if match['my'] > match['opp']:
                txt = f"{random.choice(WIN_CHANTS)}\n\n<b>ניצחון ענק!</b> {match['my']}-{match['opp']} להפועל! 💙"
            else:
                txt = f"סיום המשחק. התוצאה: {match['my']}-{match['opp']}. יאללה הפועל! 💙"
            
            if send_telegram(txt):
                with open("task_log.txt", 'a') as f: f.write(f"final_{m_date}:{now.strftime('%H:%M')}\n")
                tasks.add(f"final_{m_date}:{now.strftime('%H:%M')}")

        # סקר MVP
        final_task = [t for t in tasks if t.startswith(f"final_{m_date}:")]
        if final_task and f"mvp_{m_date}" not in tasks:
            t_parts = final_task[0].split(":")[-2:]
            if now.minute >= int(t_parts[1]) + 10 or now.hour > int(t_parts[0]):
                players = get_lineup(match['id'])
                if send_telegram("", is_poll=True, poll_data={"question": "מי המצטיין שלכם היום? ⚽️", "options": players, "is_anonymous": False}):
                    with open("task_log.txt", 'a') as f: f.write(f"mvp_{m_date}\n")

    # 2. סריקת כתבות
    print("📡 סורק כתבות...")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:8]:
                if entry.link in history: continue
                
                # בדיקת מילות מפתח
                if any(k in (entry.title + entry.get('summary', '')) for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    
                    # חילוץ טקסט מלא לסנכרון עם ה-AI
                    try:
                        res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                        soup = BeautifulSoup(res.content, 'html.parser')
                        full_text = " ".join([p.get_text() for p in soup.find_all('p')])
                    except: full_text = entry.title

                    summary = get_ai_summary(full_text, entry.title)
                    
                    if summary:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{clean_html(summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        msg = f"💙 <b>{clean_html(entry.title)}</b>\n\n🔗 {entry.link}"

                    if send_telegram(msg):
                        with open("seen_links.txt", 'a') as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        time.sleep(2)
        except Exception as e:
            print(f"DEBUG RSS Error: {e}")

    print("--- סיום ריצה ---")

if __name__ == "__main__":
    main()
