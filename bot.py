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

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

DEFAULT_PLAYERS = ["עומר כץ", "שחר רוזן", "דרור ניר", "איתי רוטמן", "אוראל דגני", "מוסונדה", "עידן כהן", "נועם כהן", "אלטמן", "נדב נידם", "רועי דוד", "ארי כהן", "דיארה", "יונתן כהן", "קליי", "סונגה", "קוסטה", "שביט מזל", "בוני"]

WIN_CHANTS = ["אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש-אה! 💙", "מי שלא קופץ לוזון! 💙", "אלך אחריך גם עד סוף העולם! 💙"]

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
    prompt = (f"אתה עיתונאי ספורט עבור אוהדי הפועל פתח תקווה. "
              f"כתוב תקציר של 4-5 משפטים על הכתבה. התמקד רק במידע שרלוונטי להפועל פתח תקווה. "
              f"אל תחזור על: {context}.\nטקסט: {text[:3000]}")
    
    # ניסיון אחרון בכתובת הכי ישרה שיש
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"DEBUG AI FAILED: {res.status_code} - {res.text}")
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
                    return {"id": event['id'], "status": event.get('status', {}).get('type'), "date": dt,
                            "my": event.get('homeScore', {}).get('display', 0) if is_h else event.get('awayScore', {}).get('display', 0),
                            "opp": event.get('awayScore', {}).get('display', 0) if is_h else event.get('homeScore', {}).get('display', 0)}
        except: continue
    return None

def main():
    now = get_israel_time()
    print(f"--- ריצה: {now.strftime('%H:%M:%S')} ---")
    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(line.strip() for line in f if line.strip())
    with open(db_file, 'r') as f: history = set(line.strip() for line in f if line.strip())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-10:]

    # ניהול משחק (בדיקת מכסה)
    try:
        match = get_match_data()
        if match and match['status'] in ['finished', 'FT']:
            m_date = match['date']
            if f"final_msg_{m_date}" not in tasks:
                txt = f"<b>סיום המשחק!</b>\nהתוצאה: {match['my']}-{match['opp']} להפועל 💙"
                if send_to_telegram(txt):
                    with open(task_file, 'a') as f: f.write(f"final_msg_{m_date}:{now.strftime('%H:%M')}\n")
    except: print("DEBUG: RapidAPI Quota or Error")

    # סריקת כתבות
    print("📡 סורק כתבות...")
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            if entry.link in history: continue
            try:
                res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                full_text = " ".join([p.get_text() for p in soup.find_all('p')])
                if any(k in (entry.title + full_text) for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    summary = get_ai_summary(full_text, entry.title, recent)
                    
                    # מנגנון הגנה: אם ה-AI נכשל, שולח בלי תקציר
                    if summary:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{escape_html(summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{escape_html(entry.title)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                        print("DEBUG: Sending without summary due to AI failure.")

                    if send_to_telegram(msg):
                        with open(db_file, "a") as f: f.write(entry.link + "\n")
                        if summary:
                            with open(sum_db, "a", encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                        history.add(entry.link)
                        time.sleep(2)
            except: continue
    print("--- סיום ---")

if __name__ == "__main__": main()
