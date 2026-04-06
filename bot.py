import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
import json
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים של GitHub
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/liga.aspx?FolderID=44"
FALLBACK_POSTER = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# --- מילון תרגום קבוצות ליגת העל 2026 ---
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Hapoel Haifa": "הפועל חיפה", "Hapoel Jerusalem": "הפועל ירושלים",
    "Maccabi Netanya": "מכבי נתניה", "Maccabi Bnei Reineh": "מכבי בני ריינה",
    "F.C. Ashdod": "מ.ס. אשדוד", "Hapoel Hadera": "הפועל חדרה",
    "Maccabi Petach Tikva": "מכבי פתח תקווה", "Bnei Sakhnin": "בני סכנין",
    "Hapoel Tel Aviv": "הפועל תל אביב", "Ironi Kiryat Shmona": "עירוני קרית שמונה",
    "Ironi Tiberias": "עירוני טבריה", "Maccabi Bnei Raina": "מכבי בני ריינה"
}

# --- שירי ניצחון ---
WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

# --- סגל שחקנים (סלקציה ל-MVP) ---
PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

# --- אירועים היסטוריים (ימי רביעי) ---
HISTORICAL_EVENTS = [
    "ב-1955 הפועל פ\"ת זכתה באליפות הראשונה בתולדותיה! 🏆",
    "נחום סטלמך כבש את השער המפורסם מול ברית המועצות ב-1956. ⚽",
    "הפועל פ\"ת מחזיקה בשיא של 5 אליפויות רצופות (1959-1963)! 💙",
    "הזכייה האחרונה בגביע המדינה הייתה ב-1992. 🏆",
    "האצטדיון המיתולוגי של הקבוצה היה 'האורווה'. 🏟️"
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

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, is_poll=False, poll_data=None, photo_url=None, with_table=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    payload = {"chat_id": ADMIN_ID}
    
    if with_table:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]})

    if photo_url:
        method = "sendPhoto"
        payload.update({"photo": photo_url, "caption": text, "parse_mode": "Markdown"})
    elif is_poll:
        method = "sendPoll"
        payload.update(poll_data)
    else:
        method = "sendMessage"
        payload.update({"text": text, "parse_mode": "Markdown"})
    
    try:
        r = requests.post(url + method, data=payload, timeout=15)
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
        "1. Write a 3-sentence summary in Hebrew. Tone: Professional Sport Journalist, loyal to Hapoel Petah Tikva.\n"
        "2. NICKNAMES: Use 'הפועל', 'הכחולים'. STRICTLY FORBIDDEN: 'לוזונים'.\n"
        "3. CONTEXT: Focus on how this news affects Hapoel Petah Tikva specifically.\n"
        f"### ARTICLE TITLE: {title} ###\n### TEXT ###\n{text[:2500]}"
    )
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.status_code == 200:
                out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                return out if "SKIP" not in out.upper() else None
        except: continue
    return None

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- {now_il.strftime('%H:%M:%S')} (Israel Time) ריצה ---")
    
    # טעינת קבצים
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. הודעות מתוזמנות
    if now_il.hour == 15 and f"betting_{today_str}" not in tasks:
        if send_telegram("💰 *זמן הימורים!* מה תהיה התוצאה היום? כתבו בתגובות! 👇"):
            with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")

    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        events = random.sample(HISTORICAL_EVENTS, 3)
        msg = "📜 *פינת ההיסטוריה הכחולה:*\n\n" + "\n".join([f"🔹 {e}" for e in events])
        if send_telegram(msg):
            with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול משחקים (RapidAPI)
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        
        # Match Day
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_time_il = datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)
            if ev_time_il.strftime('%Y-%m-%d') == today_str and f"matchday_{today_str}" not in tasks:
                is_home = str(next_ev['homeTeam']['id']) == TEAM_ID
                opp = next_ev['awayTeam']['name'] if is_home else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                msg = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
                if send_telegram(msg, photo_url=FALLBACK_POSTER):
                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")

        # סיום משחק
        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers, timeout=10).json()
        if r_last.get('events'):
            last_ev = r_last['events'][0]
            l_time_il = datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)
            if l_time_il.strftime('%Y-%m-%d') == today_str and last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                if f"final_{today_str}" not in tasks:
                    is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                    my = last_ev['homeScore']['display'] if is_h else last_ev['awayScore']['display']
                    opp = last_ev['awayScore']['display'] if is_h else last_ev['homeScore']['display']
                    opp_name = last_ev['awayTeam']['name'] if is_h else last_ev['homeTeam']['name']
                    opp_heb = TEAM_TRANSLATION.get(opp_name, opp_name)
                    
                    if my > opp:
                        txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb}\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
                    elif my == opp:
                        txt = f"תיקו בסיום המשחק של הפועל ({my}-{opp}), ממשיכים הלאה בכל הכוח. יאללה הפועלללל 💙"
                    else:
                        txt = f"הפסד בסיום המשחק ({my}-{opp}), לא נורא מרימים את הראש וממשיכים הלאה בכל הכוחח.\n\nיאלה הפועל מלחמההה 💙"
                    
                    if send_telegram(txt, with_table=True):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}:{now_il.strftime('%H:%M')}\n")
                        tasks.add(f"final_{today_str}:{now_il.strftime('%H:%M')}")

                # סקר MVP (10 דקות אחרי)
                final_entry = [t for t in tasks if t.startswith(f"final_{today_str}:")]
                if final_entry and f"mvp_{today_str}" not in tasks:
                    f_time_str = final_entry[0].split(":")[-2:]
                    f_time = now_il.replace(hour=int(f_time_str[0]), minute=int(f_time_str[1]))
                    if now_il >= f_time + timedelta(minutes=10):
                        try:
                            l_res = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/event/{last_ev['id']}/lineups", headers=headers, timeout=10).json()
                            side = 'home' if str(l_res['home']['team']['id']) == TEAM_ID else 'away'
                            players = [PLAYER_MAP.get(p['player']['name'], p['player']['name']) for p in l_res[side]['lineup']]
                        except: players = list(PLAYER_MAP.values())
                        if send_telegram("", is_poll=True, poll_data={"question": "מי המצטיין שלכם היום? ⚽️", "options": players[:10], "is_anonymous": False}):
                            with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"mvp_{today_str}\n")
    except: pass

    # 3. סריקת כתבות (ללא כפילויות)
    models = get_available_models()
    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                title = entry.title
                if link in history or any(title[:25] in h for h in history): continue
                
                try:
                    res_art = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res_art.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                if any(k.lower() in (title + content).lower() for k in HAPOEL_KEYS):
                    summary = get_ai_summary(content, models, title)
                    if summary == "SKIP": continue
                    summary_final = summary if summary else "הכתבה ללא תקציר 🙏"
                    msg = f"*יש עדכון חדש על הפועל 💙*\n\n{html.escape(summary_final)}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(f"{link} | {title}\n")
                        history.add(link)
                        time.sleep(5)
        except: continue

if __name__ == "__main__": main()
