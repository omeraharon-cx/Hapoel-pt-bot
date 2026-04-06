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
ADMIN_ID = "425605110" # Chat ID של הערוץ
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
    "Hapoel Tel Aviv": "הפועל תל אביב", "Ironi Kiryat Shmona": "עירוני קרית שמונה",
    "Maccabi Bnei Raina": "מכבי בני ריינה", "Hapoel Nof HaGalil": "הפועל נוף הגליל"
}

# --- אירועים היסטוריים (ימי רביעי) ---
HISTORICAL_EVENTS = [
    "ב-1955 הפועל פ\"ת זכתה באליפות הראשונה בתולדותיה! 🏆",
    "נחום סטלמך כבש את השער המפורסם מול ברית המועצות ב-1956. ⚽",
    "הפועל פ\"ת מחזיקה בשיא של 5 אליפויות רצופות (1959-1963)! 💙",
    "הזכייה האחרונה בגביע המדינה הייתה ב-1992, עם שער של וואליד באדיר. 🏆",
    "האצטדיון המיתולוגי של הקבוצה היה 'האורווה', בו נכתבו סיפורים בלתי נשכחים. 🏟️",
    "הפועל פ\"ת הייתה הקבוצה הישראלית הראשונה ששיחקה במפעל אירופי רשמי. 🌍"
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
        return models if models else ["models/gemini-1.5-flash"]
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, title):
    if not text or len(text) < 100: return None
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Write a 3-sentence summary in Hebrew. Tone: Professional Sport Journalist, passionate but formal.\n"
        "2. NICKNAMES: Use 'הפועל', 'הכחולים' or 'המלאבסים'.\n"
        "3. STRICTLY FORBIDDEN: Do not use the word 'לוזונים'.\n"
        "4. CONTEXT: Always relate the content specifically to Hapoel Petah Tikva.\n"
        "5. If not relevant to the team, return ONLY: SKIP\n\n"
        f"### ARTICLE TEXT ###\n{text[:3000]}"
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
    print(f"--- {now_il.strftime('%H:%M:%S')} ריצה משולבת ---")
    
    # טעינת זיכרון
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. הודעות מתוזמנות (הימורים והיסטוריה)
    if now_il.hour == 15 and f"betting_{now_il.date()}" not in tasks:
        msg = "💰 *זמן הימורים!* מה תהיה התוצאה היום? כתבו בתגובות! 👇"
        if send_telegram(msg):
            with open("task_log.txt", 'a') as f: f.write(f"betting_{now_il.date()}\n")

    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{now_il.date()}" not in tasks:
        events = random.sample(HISTORICAL_EVENTS, 3)
        msg = "📜 *פינת ההיסטוריה הכחולה:*\n\n" + "\n".join([f"🔹 {e}" for e in events])
        if send_telegram(msg):
            with open("task_log.txt", 'a') as f: f.write(f"history_{now_il.date()}\n")

    # 2. ניהול יום משחק (Match Day וסיום)
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        # בדיקת משחק קרוב
        r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        if r.get('events'):
            next_ev = r['events'][0]
            ev_date = datetime.fromtimestamp(next_ev['startTimestamp']).strftime('%Y-%m-%d')
            if ev_date == now_il.strftime('%Y-%m-%d') and f"matchday_{ev_date}" not in tasks:
                is_home = str(next_ev['homeTeam']['id']) == TEAM_ID
                opp_name = next_ev['awayTeam']['name'] if is_home else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp_name, opp_name)
                msg = f"⚽ *MATCH DAY!* הפועל נגד {opp_heb}\nיאללה הפועל! 💙"
                if send_telegram(msg, photo_url="https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"):
                    with open("task_log.txt", 'a') as f: f.write(f"matchday_{ev_date}\n")

        # בדיקת משחק שהסתיים
        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers, timeout=10).json()
        if r_last.get('events'):
            last_ev = r_last['events'][0]
            l_date = datetime.fromtimestamp(last_ev['startTimestamp']).strftime('%Y-%m-%d')
            if l_date == now_il.strftime('%Y-%m-%d') and last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                if f"final_{l_date}" not in tasks:
                    is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                    my = last_ev['homeScore']['display'] if is_h else last_ev['awayScore']['display']
                    opp = last_ev['awayScore']['display'] if is_h else last_ev['homeScore']['display']
                    if my > opp:
                        txt = f"🥳 *ניצחון כחול!* {my}-{opp}\n\nאלך אחריך גם עד סוף העולם! 💙"
                    elif my == opp:
                        txt = f"🤝 תיקו {my}-{my}. ממשיכים קדימה, הפועל! 💙"
                    else:
                        txt = f"🏁 סיום המשחק: {my}-{opp}. הראש למעלה, תמיד איתך! 💙"
                    if send_telegram(txt):
                        with open("task_log.txt", 'a') as f: f.write(f"final_{l_date}:{now_il.strftime('%H:%M')}\n")
                        tasks.add(f"final_{l_date}:{now_il.strftime('%H:%M')}")

                # סקר MVP (10 דקות אחרי סיום)
                final_task = [t for t in tasks if t.startswith(f"final_{l_date}:")]
                if final_task and f"mvp_{l_date}" not in tasks:
                    t_min = int(final_task[0].split(":")[-1])
                    if now_il.minute >= t_min + 10:
                        # ניסיון להוציא הרכב
                        try:
                            l_url = f"https://{RAPIDAPI_HOST}/api/v1/event/{last_ev['id']}/lineups"
                            l_res = requests.get(l_url, headers=headers, timeout=10).json()
                            side = 'home' if str(l_res['home']['team']['id']) == TEAM_ID else 'away'
                            players = [PLAYER_MAP.get(p['player']['name'], p['player']['name']) for p in l_res[side]['lineup']]
                        except: players = DEFAULT_PLAYERS
                        
                        poll = {"question": "מי המצטיין שלכם היום? ⚽️", "options": players[:10], "is_anonymous": False}
                        if send_telegram("", is_poll=True, poll_data=poll):
                            with open("task_log.txt", 'a') as f: f.write(f"mvp_{l_date}\n")
    except: print("DEBUG: Match check error.")

    # 3. סריקת כתבות
    models = get_available_models()
    for feed_url in RSS_FEEDS:
        try:
            headers_rss = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(feed_url, headers=headers_rss, timeout=15)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue
                
                # פילטר זמן (72 שעות)
                pub = entry.get('published_parsed')
                if pub:
                    if now_il - (datetime(*pub[:6]) + timedelta(hours=3)) > timedelta(hours=72): continue

                try:
                    res_art = requests.get(entry.link, headers=headers_rss, timeout=10)
                    soup = BeautifulSoup(res_art.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                if any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    summary = get_ai_summary(content, models, entry.title)
                    if summary == "SKIP": continue
                    
                    header = "*יש עדכון חדש על הפועל 💙*"
                    summary_final = summary if summary else "הכתבה ללא תקציר 🙏"
                    msg_art = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg_art):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        history.add(link)
                        time.sleep(5)
        except: continue

if __name__ == "__main__": main()
