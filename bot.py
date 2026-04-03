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

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

TEAM_ID = "5199" 
LEAGUE_ID = "877"

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
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

# --- פונקציות ניהול מנויים ---

def get_subscribers():
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f:
        return list(set(line.strip() for line in f if line.strip()))

def update_subscribers():
    print("DEBUG: בודק מצטרפים חדשים בטלגרם...")
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

# --- פונקציות שליחה ---

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

# --- פונקציות תוכן ו-AI ---

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3'])
        return " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
    except: return ""

def get_ai_summary(text, recent_summaries):
    if not text or len(text) < 100: return None
    
    # המתנה קריטית למניעת חסימת 429 (מכסה חינמית)
    time.sleep(12)
    
    # שימוש בכתובת v1beta ובדגם gemini-2.0-flash (היחיד שגוגל מוצא ב-2026)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    summaries_context = "\n".join([f"- {s}" for s in recent_summaries])
    prompt = (
        "1. Analyze the article. Is it PRIMARILY about Hapoel Petah Tikva? If not, return ONLY: SKIP\n"
        f"2. Check if this news describes the EXACT SAME event as any of these recent updates:\n{summaries_context}\n"
        "3. If it is a duplicate, return ONLY: DUPLICATE\n"
        "4. Otherwise, write a 3-sentence Hebrew summary. Casual tone, NO greetings, focus on Hapoel PT.\n"
        f"\nARTICLE TEXT:\n{text[:3000]}"
    )

    try:
        response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]}, timeout=25)
        data = response.json()
        
        if response.status_code != 200:
            print(f"❌ שגיאת AI (סטטוס {response.status_code}): {data.get('error', {}).get('message', 'Unknown error')}")
            return None
            
        summary = data['candidates'][0]['content']['parts'][0]['text'].strip()
        if "SKIP" in summary.upper() or "DUPLICATE" in summary.upper(): return "REJECTED"
        return summary
    except: return None

# --- פונקציות כדורגל (RapidAPI) ---

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

def get_match_players(fixture_id):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players = res['response'][0]['players']
        return [p['player']['name'] for p in players if (p['statistics'][0]['games']['minutes'] or 0) > 0][:10]
    except: return ["שחקן סגל", "שחקן אחר"]

# --- ריצה ראשית ---

def main():
    print("🚀 סריקה התחילה (גרסת 2026 משולבת - בסיס 26.3)...", flush=True)
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    
    update_subscribers()

    db_file, summary_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, summary_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
        
    with open(db_file, 'r') as f: history = f.read().splitlines()
    with open(summary_db, 'r', encoding='utf-8') as f: recent_summaries = f.read().splitlines()[-10:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    hapoel_keys = ["הפועל פ״ת", "הפועל פתח-תקוה", "הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל ״מבנה״ פתח-תקוה", "הכחולים", "המלאבסים", "הפועל פת"]

    # 2. סריקת RSS
    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}", flush=True)
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            
            # סנן תאריך (שבוע אחרון)
            published = entry.get('published_parsed')
            if published and now - datetime.fromtimestamp(calendar.timegm(published)) > timedelta(days=7): continue

            if link in history or title in history: continue

            content = get_full_article_text(link)
            is_official = "hapoelpt.com" in link or "hapoelpt.com" in feed_url
            is_in_title = any(key in title.lower() for key in hapoel_keys)
            count_in_body = sum(content.lower().count(key) for key in hapoel_keys)

            if is_official or is_in_title or count_in_body >= 2:
                print(f"🎯 מעבד כתבה: {title}", flush=True)
                summary = get_ai_summary(content, recent_summaries)

                if summary == "REJECTED":
                    print(f"⏭️ AI החליט לדלג (לא רלוונטי או כפול).", flush=True)
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    continue

                if summary:
                    msg = f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    send_to_all(msg)
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    with open(summary_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    time.sleep(5)

    # 3. לוגיקת יום משחק
    match = check_match_status()
    if match:
        if now.hour < 12 and f"poster_{today_key}" not in tasks_done:
            img_desc = get_ai_summary(f"Describe a cinematic matchday poster: Hapoel Petah Tikva vs {match['opp_name']}, blue and white stadium.", [])
            if img_desc and "REJECTED" not in img_desc:
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

    # 4. פינת היסטוריה (רביעי ב-12:00)
    if now.weekday() == 2 and now.hour == 12 and f"hist_{today_key}" not in tasks_done:
        hist_text = get_ai_summary("Tell a short, interesting historical fact about Hapoel Petah Tikva football club in Hebrew.", [])
        if hist_text and "REJECTED" not in hist_text:
            send_to_all(f"📚 **פינת ההיסטוריה השבועית**\n\n{hist_text}")
            with open(task_file, 'a') as f: f.write(f"hist_{today_key}\n")

    print("🏁 סיום.")

if __name__ == "__main__":
    main()
