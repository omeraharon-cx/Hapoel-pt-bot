import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime

# הגדרת לוגים לעברית
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות קבועות ---
TEAM_ID = "5199" 
LEAGUE_ID = "877"
ADMIN_ID = "425605110"

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ״ש*אה״\nאלך אחריך גם עד סוף העולם, אקפו אשתגע יאללה ביחד כולםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# --- ניהול מנויים ---
def get_subscribers():
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f:
        return list(set(line.strip() for line in f if line.strip()))

def update_subscribers():
    print("DEBUG: בודק אם יש מנויים חדשים (start/)...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("ok"):
            subs = get_subscribers()
            for up in res.get("result", []):
                msg = up.get("message", {})
                if msg.get("text") == "/start":
                    cid = str(msg["chat"]["id"])
                    if cid not in subs:
                        with open("subscribers.txt", "a") as f: f.write(cid + "\n")
                        print(f"✅ מנוי חדש התווסף: {cid}")
    except: pass

# --- פונקציות ליבה ---
def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        except: pass

def get_ai_response(prompt):
    # כתובת v1 היציבה ל-2026
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "safetySettings": safety}, timeout=25)
        data = res.json()
        if res.status_code == 200 and 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"⚠️ שגיאת AI: {data.get('error', {}).get('message', 'Unknown error')}")
        return None
    except: return None

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2', 'h3']) if len(t.get_text()) > 25])
    except: return ""

def get_match_players(fixture_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players = res['response'][0]['players']
        return [p['player']['name'] for p in players if (p['statistics'][0]['games']['minutes'] or 0) > 0][:10]
    except: 
        return ["שחקן מהסגל", "שחקן אחר"]

def check_match_status():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"team": TEAM_ID, "date": datetime.now().strftime('%Y-%m-%d')}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            is_home = str(m['teams']['home']['id']) == TEAM_ID
            return {
                "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
                "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
                "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name']
            }
    except: return None

# --- ריצה ראשית ---
def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}")
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    
    update_subscribers() 
    
    db_file, task_file = "seen_links.txt", "task_log.txt"
    for f in [db_file, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    # --- שלב 1: כתבות RSS - המילים המדויקות שלך ---
    h_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל ״מבנה״ פתח-תקוה", "הכחולים", "המלאבסים", "הפועל פת"]
    
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.link
            if link in history: continue
            if any(j in link.lower() for j in ["finance", "lifestyle", "shopping", "promoted"]): continue
            
            print(f"🔍 בודק לעומק: {entry.title}")
            full_text = get_full_article_text(link)
            combined_text = (entry.title + " " + full_text).lower()
            
            # בדיקה אם יש קשר להפועל (לפי המילים שלך)
            if any(k in combined_text for k in h_keys) or "hapoelpt.com" in link:
                print(f"🎯 נמצא קשר להפועל! מבקש סינון חכם מה-AI...")
                # ה-AI מקבל הוראה להבדיל בין הפועל למכבי
                prompt = (f"Analyze this article about Israeli football. "
                         f"If it is primarily about Hapoel Petah Tikva (the 'Blues') or mentions them as a key subject, summarize it in 3 Hebrew sentences. "
                         f"If it is primarily about Maccabi Petah Tikva or another team and Hapoel is only mentioned in passing, return 'SKIP'. "
                         f"TEXT: {full_text[:2500]}")
                
                summary = get_ai_response(prompt)
                
                if summary and "SKIP" not in summary.upper():
                    print(f"✅ שולח לטלגרם: {entry.title}")
                    send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})")
                    with open(db_file, 'a') as f: f.write(link + "\n")
                    history.add(link)
                    time.sleep(10) # המתנה למניעת חסימה

    # --- שלב 2: יום משחק ---
    match = check_match_status()
    if match:
        if now.hour < 12 and f"poster_{today_key}" not in tasks_done:
            img_desc = get_ai_response(f"Translate to English: פוסטר יום משחק כדורגל, הפועל פתח תקווה נגד {match['opp_name']}, אווירה של אצטדיון.")
            if img_desc:
                url = f"https://pollinations.ai/p/{img_desc.replace(' ', '%20')}"
                send_to_all("Match Day 💙\n\nהפועל שלנו תעלה בעוד כמה שעות לכר הדשא\nיאללה הפועל לתת את הלב בשביל הסמל.\nמביאים 3 נקודות בע״ה\n\nקדימה הפועללל ⚽️", photo_url=url)
                with open(task_file, 'a') as f: f.write(f"poster_{today_key}\n")

        if now.hour == 15 and f"bet_{today_key}" not in tasks_done:
            send_to_all("", is_poll=True, poll_data={"question": f"איך יסתיים המשחק מול {match['opp_name']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"bet_{today_key}\n")

        if match['status'] == 'FT' and f"end_{today_key}" not in tasks_done:
            if match['my_score'] > match['opp_score']:
                res_msg = f"{random.choice(WIN_CHANTS)}\n\nיופי הפועללל, איזה נצחון גדול! 💙"
            elif match['my_score'] == match['opp_score']:
                res_msg = "תיקו בסיום. ממשיכים הלאה בכל הכוח! 💙"
            else:
                res_msg = "הפסד כואב, מרימים את הראש וממשיכים מלחמה! 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": "https://www.football.co.il/leagues/israeli-premier-league/table"}]]}
            send_to_all(res_msg, reply_markup=markup)
            
            time.sleep(600)
            players = get_match_players(match['id'])
            send_to_all("", is_poll=True, poll_data={"question": "מי השחקן המצטיין שלכם היום?", "options": players, "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"end_{today_key}\n")

    # --- שלב 3: היסטוריה (רביעי) ---
    if now.weekday() == 2 and now.hour == 12 and f"hist_{today_key}" not in tasks_done:
        hist = get_ai_response("סכם 3 אירועים היסטוריים משמעותיים של הפועל פתח תקווה השבוע בעבר. עברית.")
        if hist:
            send_to_all(f"📚 **פינת ההיסטוריה השבועית**\n\n{hist}")
            with open(task_file, 'a') as f: f.write(f"hist_{today_key}\n")

    print("🏁 סיום.")

if __name__ == "__main__": main()
