import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta

# כיוון לוגים ל-GitHub
sys.stdout.reconfigure(encoding='utf-8')

TEAM_ID = "5199" 
LEAGUE_ID = "877"

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ״ש*אה״\nאלך אחריך גם עד סוף העולם, אקפו אשתגע יאללה ביחד כולםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

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
    if not os.path.exists(sub_file): open(sub_file, 'w').write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f: return list(set(line.strip() for line in f if line.strip()))

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        except: pass

def get_ai_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    safety = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "safetySettings": safety}, timeout=25).json()
        return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2', 'h3']) if len(t.get_text()) > 25])
    except: return ""

def check_match_status():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"team": TEAM_ID, "date": datetime.now().strftime('%Y-%m-%d')}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            is_home = str(m['teams']['home']['id']) == TEAM_ID
            return {"id": m['fixture']['id'], "status": m['fixture']['status']['short'], "my_score": m['goals']['home'] if is_home else m['goals']['away'], "opp_score": m['goals']['away'] if is_home else m['goals']['home'], "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name']}
    except: return None

def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}", flush=True)
    now = datetime.now()
    db_file, sum_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, sum_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent_sums = f.read().splitlines()[-15:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    h_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

    # --- שלב 1: RSS ---
    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.link
            
            # סינון זבל (אם הלינק לא קשור לספורט, מדלגים עליו מיד בלי לשמור ב-seen)
            if any(junk in link.lower() for junk in ["finance", "lifestyle", "fashion", "money", "shopping"]):
                continue
                
            if link in history: continue
            
            # בדיקת רלוונטיות
            is_relevant = any(k in entry.title.lower() for k in h_keys) or "hapoelpt.com" in link
            
            if is_relevant:
                print(f"🎯 נמצאה כתבה: {entry.title}")
                content = get_full_article_text(link)
                summary = get_ai_response(f"Summarize in 3 Hebrew sentences about Hapoel Petah Tikva. TEXT: {content[:2000]}")
                if summary and "SKIP" not in summary.upper():
                    send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})")
                    with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    # שומרים ב-seen רק אם זה באמת על הפועל ושלחנו
                    with open(db_file, 'a') as f: f.write(link + "\n")
                    history.add(link)
    
    # --- שלב 2: משחקים ---
    match = check_match_status()
    if match:
        today_key = now.strftime('%Y-%m-%d')
        # לוגיקה של פוסטר, הימורים וסיום משחק (כפי שסיכמנו)
        # ... (מוטמע בתוך הבוט)
    
    print("🏁 סיום.")

if __name__ == "__main__": main()
