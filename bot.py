import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta

# מוודא שההדפסות יופיעו מיד בלוג
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199" 

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ״ש*אה״\nאלך אחריך גם עד סוף העולם, אקפו אשתגע יאללה ביחד כולםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

# --- ניהול מנויים ---
def get_subscribers():
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f:
        return list(set(line.strip() for line in f if line.strip()))

def update_subscribers():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("ok"):
            subs = get_subscribers()
            for update in res.get("result", []):
                msg = update.get("message", {})
                if msg.get("text") == "/start":
                    cid = str(msg["chat"]["id"])
                    if cid not in subs:
                        with open("subscribers.txt", "a") as f: f.write(cid + "\n")
                        print(f"✅ מנוי חדש נוסף: {cid}")
    except: pass

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        except: pass

# --- AI וכתבות ---
def get_ai_summary(text, recent_summaries):
    if not text or len(text) < 100: return None
    # המתנה כדי לא להיחסם
    time.sleep(10)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    summaries_context = "\n".join([f"- {s}" for s in recent_summaries])
    prompt = f"Summarize in 3 Hebrew sentences for Hapoel PT fans. Casual tone. If not primarily about Hapoel PT, return SKIP. Duplicates to avoid: {summaries_context}. TEXT: {text[:2500]}"
    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if response.status_code == 429: return "QUOTA_EXCEEDED"
        data = response.json()
        res = data['candidates'][0]['content']['parts'][0]['text'].strip()
        return "REJECTED" if "SKIP" in res.upper() else res
    except: return None

def check_match_status():
    today = get_israel_time().strftime('%Y-%m-%d')
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    
    # ניסיון 1: לפי תאריך
    params = {"team": TEAM_ID, "date": today}
    print(f"DEBUG: בודק משחקים לתאריך {today}...")
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            return parse_match(res['response'][0])
        
        # ניסיון 2: המשחק הבא (אם התאריך ב-API שונה)
        print("DEBUG: מחפש בלוח המשחקים הכללי...")
        params = {"team": TEAM_ID, "next": "1"}
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            return parse_match(res['response'][0])
    except: pass
    return None

def parse_match(m):
    is_home = str(m['teams']['home']['id']) == TEAM_ID
    return {
        "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
        "my_score": m['goals']['home'] if is_home else m['goals']['away'],
        "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
        "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name']
    }

def get_match_players(fixture_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players = res['response'][0]['players']
        return [p['player']['name'] for p in players if (p['statistics'][0]['games']['minutes'] or 0) > 0][:10]
    except: 
        return ["שחקן סגל 1", "שחקן סגל 2", "שחקן סגל 3", "שחקן אחר"]

def main():
    now = get_israel_time()
    today_key = now.strftime('%Y-%m-%d')
    print(f"🚀 סריקה התחילה: {now.strftime('%H:%M:%S')} (ישראל)")
    
    update_subscribers()
    db_file, sum_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, sum_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent_summaries = f.read().splitlines()[-10:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    # המילים המדויקות שלך!
    hapoel_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל ״מבנה״ פתח-תקוה", "הכחולים", "המלאבסים", "הפועל פת"]

    # 1. RSS
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history: continue
            try:
                res = requests.get(link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                soup = BeautifulSoup(res.content, 'html.parser')
                content = " ".join([t.get_text() for t in soup.find_all(['p', 'h1', 'h2'])])
                if any(k in (title + content).lower() for k in hapoel_keys) or "hapoelpt.com" in link:
                    summary = get_ai_summary(content, recent_summaries)
                    if summary == "QUOTA_EXCEEDED":
                        send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{title}\n\n🔗 [לכתבה המלאה]({link})")
                    elif summary and summary != "REJECTED":
                        send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})")
                        with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    with open(db_file, 'a') as f: f.write(link + "\n")
                    history.add(link)
            except: continue

    # 2. יום משחק
    match = check_match_status()
    if match:
        print(f"⚽ נמצא משחק מול {match['opp_name']}!")
        
        # פוסטר
        if now.hour >= 8 and f"poster_{today_key}" not in tasks_done:
            img_desc = get_ai_summary(f"Matchday poster Hapoel Petah Tikva vs {match['opp_name']}, cinematic blue theme.", [])
            if not img_desc or img_desc in ["QUOTA_EXCEEDED", "REJECTED"]:
                img_desc = f"Football%20poster%20Hapoel%20Petah%20Tikva%20vs%20{match['opp_name']}%20stadium%20blue"
            
            url = f"https://pollinations.ai/p/{img_desc.replace(' ', '%20')}"
            send_to_all("Match Day 💙\n\nהפועל שלנו עולה הערב למגרש!\nיאללה הפועל לתת את הלב בשביל הסמל.\nמביאים 3 נקודות בע״ה! ⚽️", photo_url=url)
            with open(task_file, 'a') as f: f.write(f"poster_{today_key}\n")

        # הימורים
        if now.hour >= 14 and f"bet_{today_key}" not in tasks_done:
            send_to_all("", is_poll=True, poll_data={"question": f"איך יסתיים המשחק מול {match['opp_name']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"bet_{today_key}\n")

        # סיום משחק
        if match['status'] == 'FT' and f"end_{today_key}" not in tasks_done:
            res_msg = f"{random.choice(WIN_CHANTS)}\n\nסיום המשחק. {match['my_score']}:{match['opp_score']} להפועל. יאללה הפועל! 💙"
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": "https://www.football.co.il/leagues/israeli-premier-league/table"}]]}
            send_to_all(res_msg, reply_markup=markup)
            time.sleep(5)
            players = get_match_players(match['id'])
            send_to_all("", is_poll=True, poll_data={"question": "מי השחקן המצטיין שלכם היום?", "options": players, "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"end_{today_key}\n")

    print("🏁 סיום.")

if __name__ == "__main__": main()
