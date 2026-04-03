import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta
import calendar

# מוודא שההדפסות יופיעו מיד בלוג
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מזהים (RapidAPI) ---
TEAM_ID = "5199" 
LEAGUE_ID = "877"

# --- מאגר שירים להגרלה בניצחון ---
WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ״ש*אה״\nאלך אחריך גם עד סוף העולם, אקפו אשתגע יאללה ביחד כולםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

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

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll and poll_data:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll"
                payload = {"chat_id": cid, **poll_data}
            elif photo_url:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                payload = {"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}
                if reply_markup: payload["reply_markup"] = reply_markup
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
                if reply_markup: payload["reply_markup"] = reply_markup
            requests.post(url, json=payload, timeout=10)
        except: pass

def get_ai_response(prompt):
    url_base = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    url = f"{url_base}?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, json=payload, timeout=20).json()
        return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def get_match_players(fixture_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players_data = res['response'][0]['players']
        played = [p['player']['name'] for p in players_data if (p['statistics'][0]['games']['minutes'] or 0) > 0]
        return played[:10]
    except:
        return ["עומר כץ", "רם לוי", "דרור ניר", "רוי נאווי", "מתן פלג", "אופק אושר", "מתן גושה", "שחקן אחר"]

def check_match_status():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    today = datetime.now().strftime('%Y-%m-%d')
    params = {"team": TEAM_ID, "date": today}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            is_home = str(m['teams']['home']['id']) == TEAM_ID
            return {
                "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
                "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
                "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name'],
                "venue": m['fixture']['venue']['name']
            }
    except: return None
    return None

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2', 'h3']) if len(t.get_text()) > 25])
    except: return ""

def get_ai_summary(text, recent_summaries):
    if not text or len(text) < 100: return None
    context = "\n".join([f"- {s}" for s in recent_summaries])
    prompt = f"Analyze this article about Hapoel Petah Tikva. Return SKIP if not primarily about them or DUPLICATE if it repeats: {context}. Otherwise, 3 Hebrew sentences summary. Casual tone. TEXT: {text[:3000]}"
    res = get_ai_response(prompt)
    if res and ("SKIP" in res.upper() or "DUPLICATE" in res.upper()): return "REJECTED"
    return res

def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}", flush=True)
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    task_file = "task_log.txt"
    if not os.path.exists(task_file): open(task_file, 'w').close()
    with open(task_file, 'r') as f: tasks_done = f.read().splitlines()

    match = check_match_status()
    
    if match:
        # 1. Match Day (עד 12:00)
        if now.hour < 12 and f"match_poster_{today_key}" not in tasks_done:
            poster_prompt = f"Cinematic football poster: Hapoel Petah Tikva vs {match['opp_name']}, blue and white colors, stadium atmosphere."
            img_prompt = get_ai_response(f"Translate to an image generation prompt: {poster_prompt}")
            url = f"https://pollinations.ai/p/{img_prompt.replace(' ', '%20')}" if img_prompt else "https://hapoelpt.com/static/media/logo.png"
            text = "Match Day 💙\n\nהפועל שלנו תעלה בעוד כמה שעות לכר הדשא\nיאללה הפועל לתת את הלב בשביל הסמל.\nמביאים 3 נקודות בע״ה\n\nקדימה הפועללל ⚽️"
            send_to_all(text, photo_url=url)
            with open(task_file, 'a') as f: f.write(f"match_poster_{today_key}\n")

        # 2. הימורים (15:00)
        if now.hour == 15 and f"match_bet_{today_key}" not in tasks_done:
            send_to_all("", is_poll=True, poll_data={
                "question": f"איך יסתיים המשחק היום מול {match['opp_name']}?",
                "options": ["ניצחון כחול 💙", "תיקו", "הפסד (חס וחלילה)"],
                "is_anonymous": False
            })
            with open(task_file, 'a') as f: f.write(f"match_bet_{today_key}\n")

        # 3. סיום משחק (FT)
        if match['status'] == 'FT' and f"match_end_{today_key}" not in tasks_done:
            if match['my_score'] > match['opp_score']:
                chant = random.choice(WIN_CHANTS)
                res_msg = f"{chant}\n\nיופי הפועללל, איזה נצחון גדול.\nהבאנו 3 נקודות חשובות.\nיאלללה הפועל 💙"
            elif match['my_score'] == match['opp_score']:
                res_msg = "תיקו בסיום המשחק של הפועל, ממשיכים הלאה בכל הכוח\nיאללה הפועללללל 💙"
            else:
                res_msg = "הפסד כואב של הפועל, לא נורא הפועל להרים את הראש.\nממשיכים הלאה חזק, קדימה הפועל מלחמההה 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": "https://www.football.co.il/leagues/israeli-premier-league/table"}]]}
            send_to_all(res_msg, reply_markup=markup)
            
            print("⏳ מחכה 10 דקות לסקר...", flush=True)
            time.sleep(600)
            players = get_match_players(match['id'])
            send_to_all("", is_poll=True, poll_data={"question": "מי השחקן המצטיין שלכם היום? ⚽️", "options": players, "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"match_end_{today_key}\n")

    # 4. פינת היסטוריה (רביעי ב-12:00)
    if now.weekday() == 2 and now.hour == 12 and f"hist_{today_key}" not in tasks_done:
        hist = get_ai_response("סכם 3 אירועים היסטוריים משמעותיים של הפועל פתח תקווה מהתאריך הנוכחי או השבוע הזה בעבר. עברית, מרגש.")
        if hist:
            send_to_all(f"📚 **פינת ההיסטוריה השבועית** 📚\n\n{hist}")
            with open(task_file, 'a') as f: f.write(f"hist_{today_key}\n")

    # 5. סריקת RSS רגילה
    db_file, sum_db = "seen_links.txt", "recent_summaries.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    if not os.path.exists(sum_db): open(sum_db, 'w', encoding='utf-8').close()
    with open(db_file, 'r') as f: history = f.read().splitlines()
    with open(sum_db, 'r', encoding='utf-8') as f: recent_sums = f.read().splitlines()[-15:]

    h_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if entry.link in history: continue
            content = get_full_article_text(entry.link)
            if "hapoelpt.com" in entry.link or any(k in (entry.title + content).lower() for k in h_keys):
                summary = get_ai_summary(content, recent_sums)
                if summary and summary != "REJECTED":
                    send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})")
                    with open(db_file, 'a') as f: f.write(entry.link + "\n")
                    with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    time.sleep(5)
    print("🏁 סיום.")

if __name__ == "__main__":
    main()
