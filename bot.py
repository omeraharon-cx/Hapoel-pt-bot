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

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/liga.aspx?FolderID=44"

# --- תרגום קבוצות מדויק (לפי טבלת ליגת העל 2026) ---
TEAM_TRANSLATION = {
    "Hapoel Be'er Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Tel Aviv": "מכבי תל אביב", "Hapoel Tel Aviv": "הפועל תל אביב",
    "Maccabi Haifa": "מכבי חיפה", "Hapoel Petah Tikva": "הפועל פתח תקווה",
    "Maccabi Netanya": "מכבי נתניה", "Bnei Sakhnin": "בני סכנין",
    "Hapoel Kiryat Shmona": "הפועל קרית שמונה", "Hapoel Haifa": "הפועל חיפה",
    "M.S. Ashdod": "מ.ס. אשדוד", "Hapoel Jerusalem": "הפועל ירושלים",
    "Ironi Tiberias": "עירוני טבריה", "Maccabi Bnei Reineh": "מכבי בני ריינה"
}

# --- שירים ועידוד (לפי בקשתך) ---
WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙",
    "הפועל פתח תקווה, לעולם ועד! 💙"
]

# --- סגל שחקנים מורחב ---
PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}
DEFAULT_PLAYERS = list(PLAYER_MAP.values())

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

def send_telegram(text, is_poll=False, poll_data=None, photo_url=None, with_table_button=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    payload = {"chat_id": ADMIN_ID, "parse_mode": "Markdown"}
    
    if with_table_button:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]
        })

    if photo_url:
        method = "sendPhoto"
        payload.update({"photo": photo_url, "caption": text})
    elif is_poll:
        method = "sendPoll"
        payload.update(poll_data)
    else:
        method = "sendMessage"
        payload.update({"text": text})
    
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
        return models
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, title):
    if not text or len(text) < 100: return None
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Write a 3-sentence summary in Hebrew. Tone: Professional Sport Journalist, passionate for Hapoel Petah Tikva.\n"
        "2. NICKNAMES: Use 'הפועל', 'הכחולים' or 'המלאבסים'.\n"
        "3. STRICTLY FORBIDDEN: Do not use the word 'לוזונים' unless specifically mentioned in the context of a chant.\n"
        "4. CONTEXT: Always focus on the impact on Hapoel Petah Tikva.\n"
        f"### ARTICLE TEXT ###\n{text[:3000]}"
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
    print(f"--- {now_il.strftime('%H:%M:%S')} ריצה מלאה ---")
    
    # טעינת זיכרון
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. הודעת הימורים (15:00)
    if now_il.hour == 15 and f"betting_{now_il.date()}" not in tasks:
        if send_telegram("💰 *זמן הימורים!* מה תהיה התוצאה היום? כתבו בתגובות! 👇"):
            with open("task_log.txt", 'a') as f: f.write(f"betting_{now_il.date()}\n")

    # 2. ניהול יום משחק
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        # בדיקת משחק קרוב (Match Day)
        r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        if r.get('events'):
            next_ev = r['events'][0]
            ev_date = datetime.fromtimestamp(next_ev['startTimestamp']).strftime('%Y-%m-%d')
            if ev_date == now_il.strftime('%Y-%m-%d') and f"matchday_{ev_date}" not in tasks:
                opp_name = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp_name, opp_name)
                msg = f"⚽ *MATCH DAY!* הפועל נגד {opp_heb}\nיאללה הפועל! 💙"
                if send_telegram(msg, photo_url="https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"):
                    with open("task_log.txt", 'a') as f: f.write(f"matchday_{ev_date}\n")

        # בדיקת סיום משחק
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
                        txt = f"{random.choice(WIN_CHANTS)}\n\n*ניצחון כחול!* {my}-{opp} להפועל! 💙"
                    elif my == opp:
                        txt = f"🤝 תיקו {my}-{my}. ממשיכים להילחם על כל נקודה, יאללה הפועל! 💙"
                    else:
                        txt = f"🏁 סיום המשחק: {my}-{opp}. הראש למעלה, תמיד איתך הפועל! 💙"
                    if send_telegram(txt, with_table_button=True):
                        with open("task_log.txt", 'a') as f: f.write(f"final_{l_date}:{now_il.strftime('%H:%M')}\n")
                        tasks.add(f"final_{l_date}:{now_il.strftime('%H:%M')}")

                # סקר MVP (10 דקות אחרי)
                final_task = [t for t in tasks if t.startswith(f"final_{l_date}:")]
                if final_task and f"mvp_{l_date}" not in tasks:
                    t_min = int(final_task[0].split(":")[-1])
                    if now_il.minute >= t_min + 10:
                        try:
                            l_url = f"https://{RAPIDAPI_HOST}/api/v1/event/{last_ev['id']}/lineups"
                            l_res = requests.get(l_url, headers=headers, timeout=10).json()
                            side = 'home' if str(l_res['home']['team']['id']) == TEAM_ID else 'away'
                            players = [PLAYER_MAP.get(p['player']['name'], p['player']['name']) for p in l_res[side]['lineup']]
                        except: players = DEFAULT_PLAYERS
                        
                        poll_data = {"question": "מי המצטיין שלכם היום? ⚽️", "options": players[:10], "is_anonymous": False}
                        if send_telegram("", is_poll=True, poll_data=poll_data):
                            with open("task_log.txt", 'a') as f: f.write(f"mvp_{l_date}\n")
    except: print("DEBUG: Match system skip.")

    # 3. סריקת כתבות
    models = get_available_models()
    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:30]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue
                
                # פילטר זמן 72 שעות
                pub = entry.get('published_parsed')
                if pub and now_il - (datetime(*pub[:6]) + timedelta(hours=3)) > timedelta(hours=72): continue

                try:
                    res_art = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res_art.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                if any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    summary = get_ai_summary(content, models, entry.title)
                    header = "*יש עדכון חדש על הפועל 💙*"
                    summary_final = summary if summary else "הכתבה ללא תקציר 🙏"
                    msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        history.add(link)
                        time.sleep(5)
        except: continue

if __name__ == "__main__": main()
