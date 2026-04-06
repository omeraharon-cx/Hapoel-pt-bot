import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

# --- תרגום קבוצות (יריבות) ---
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Hapoel Haifa": "הפועל חיפה", "Hapoel Jerusalem": "הפועל ירושלים",
    "Maccabi Netanya": "מכבי נתניה", "Maccabi Bnei Reineh": "מכבי בני ריינה",
    "F.C. Ashdod": "מ.ס אשדוד", "Hapoel Hadera": "הפועל חדרה",
    "Maccabi Petach Tikva": "מכבי פתח תקווה", "Bnei Sakhnin": "בני סכנין",
    "Hapoel Tel Aviv": "הפועל תל אביב", "Ironi Kiryat Shmona": "עירוני קרית שמונה"
}

# --- אירועים היסטוריים (ימי רביעי) ---
HISTORICAL_EVENTS = [
    "ב-1955 הפועל פ\"ת זכתה באליפות הראשונה בתולדותיה! 🏆",
    "סטלמך כבש את השער המפורסם מול ברית המועצות ב-1956. ⚽",
    "הפועל פ\"ת מחזיקה בשיא של 5 אליפויות רצופות (1959-1963)! 💙",
    "הזכייה האחרונה בגביע המדינה הייתה ב-1992, עם שער של וואליד באדיר. 🏆"
]

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "עומר פרץ", "הפועל מבנה"]

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Orel Dgani": "אוראל דגני", "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", "Roee David": "רועי דוד", "Itay Rotman": "איתי רוטמן"
}
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "איתי רוטמן", "דרור ניר", "עידן כהן", "שחר רוזן"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, is_poll=False, poll_data=None, photo_url=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    if photo_url:
        method = "sendPhoto"
        payload = {"chat_id": ADMIN_ID, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}
    elif is_poll:
        method = "sendPoll"
        payload = {"chat_id": ADMIN_ID, **poll_data}
    else:
        method = "sendMessage"
        payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    
    try:
        r = requests.post(url + method, json=payload, timeout=15)
        return r.status_code == 200
    except: return False

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=10).json()
        models = [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, title):
    if not text or len(text) < 100: return None
    prompt = (
        "אתה עיתונאי ספורט ואוהד הפועל פתח תקווה. כתוב תקציר של 3 משפטים בטון ענייני אך אוהד. "
        "התייחס לקבוצה כ'הפועל'. בלי 'לוזונים'. אם לא רלוונטי החזר SKIP.\n\n"
        f"טקסט: {text[:3000]}"
    )
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.status_code == 200:
                out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                return out if "SKIP" not in out.upper() else "SKIP"
        except: continue
    return None

def main():
    now_il = get_israel_time()
    print(f"--- {now_il.strftime('%H:%M:%S')} ריצה מלאה ---")
    
    # טעינת זיכרון
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. הודעות מתוזמנות (הימורים והיסטוריה)
    if now_il.hour == 15 and f"betting_{now_il.date()}" not in tasks:
        if send_telegram("💰 *זמן הימורים!* מה תהיה התוצאה היום? כתבו בתגובות! 👇"):
            with open("task_log.txt", 'a') as f: f.write(f"betting_{now_il.date()}\n")

    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{now_il.date()}" not in tasks:
        events = random.sample(HISTORICAL_EVENTS, 3)
        msg = "📜 *פינת ההיסטוריה הכחולה:*\n\n" + "\n".join([f"🔹 {e}" for e in events])
        if send_telegram(msg):
            with open("task_log.txt", 'a') as f: f.write(f"history_{now_il.date()}\n")

    # 2. ניהול יום משחק (Match Day וסיום)
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        next_ev = r.get('events', [{}])[0]
        ev_date = datetime.fromtimestamp(next_ev['startTimestamp']).strftime('%Y-%m-%d')
        
        if ev_date == now_il.strftime('%Y-%m-%d') and f"matchday_{ev_date}" not in tasks:
            opp_name = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
            opp_heb = TEAM_TRANSLATION.get(opp_name, opp_name)
            msg = f"⚽ *MATCH DAY!* הפועל נגד {opp_heb}\nיאללה הפועל! 💙"
            if send_telegram(msg, photo_url="https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"):
                with open("task_log.txt", 'a') as f: f.write(f"matchday_{ev_date}\n")

        # סיום משחק
        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers, timeout=10).json()
        last_ev = r_last.get('events', [{}])[0]
        l_date = datetime.fromtimestamp(last_ev['startTimestamp']).strftime('%Y-%m-%d')
        
        if l_date == now_il.strftime('%Y-%m-%d') and last_ev.get('status', {}).get('type') == 'finished':
            if f"final_{l_date}" not in tasks:
                is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                my = last_ev['homeScore']['display'] if is_h else last_ev['awayScore']['display']
                opp = last_ev['awayScore']['display'] if is_h else last_ev['homeScore']['display']
                if my > opp:
                    txt = f"🥳 *ניצחון כחול!* {my}-{opp}\n\nאלך אחריך גם עד סוף העולם! 💙"
                else:
                    txt = f"🏁 סיום המשחק: {my}-{opp}. תמיד איתך הפועל! 💙"
                if send_telegram(txt):
                    with open("task_log.txt", 'a') as f: f.write(f"final_{l_date}:{now_il.strftime('%H:%M')}\n")

            # סקר MVP (10 דקות אחרי)
            final_task = [t for t in tasks if t.startswith(f"final_{l_date}:")]
            if final_task and f"mvp_{l_date}" not in tasks:
                t_min = int(final_task[0].split(":")[-1])
                if now_il.minute >= t_min + 10:
                    poll = {"question": "מי המצטיין?", "options": DEFAULT_PLAYERS[:10], "is_anonymous": False}
                    if send_telegram("", is_poll=True, poll_data=poll):
                        with open("task_log.txt", 'a') as f: f.write(f"mvp_{l_date}\n")
    except: pass

    # 3. סריקת כתבות (עם מודל גמיש)
    models = get_available_models()
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15).content)
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0]
                if link in history: continue
                # (כאן מגיעה לוגיקת סריקת הכתבות וה-AI שכבר עובדת לך...)
        except: continue

if __name__ == "__main__": main()
