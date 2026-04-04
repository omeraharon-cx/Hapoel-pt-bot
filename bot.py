import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import urllib.parse
from datetime import datetime, timedelta
import calendar

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- הגדרות ספורט (SportAPI7) ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

# רשימת הפידים המלאה
RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# מילון תרגום קבוצות
TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']): s.decompose()
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3'])
        return " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
    except: return ""

def get_ai_summary(text, recent_summaries):
    if not text or len(text) < 100: return None
    summaries_context = "\n".join([f"- {s}" for s in recent_summaries])
    
    prompt = (
        "1. Analyze the article. Is it PRIMARILY about Hapoel Petah Tikva? If not, return ONLY: SKIP\n"
        f"2. Check if this is a duplicate of these recent updates:\n{summaries_context}\n"
        "3. If duplicate, return ONLY: DUPLICATE\n"
        "4. Otherwise, write a 3-sentence Hebrew summary. Casual tone, NO greetings, focus on news impact.\n"
        f"\nTEXT: {text[:3000]}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        time.sleep(5) # הגנה מחסימת מכסה
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            if "SKIP" in result.upper() or "DUPLICATE" in result.upper(): return "REJECTED"
            return result
    except: pass
    return None

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    for cid in subs:
        try:
            if is_poll:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}, timeout=15)
            else:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e: print(f"TELEGRAM ERROR: {e}")

def check_for_match():
    url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            events = response.json().get('events', [])
            today = get_israel_time().strftime('%Y-%m-%d')
            for event in events:
                dt = datetime.fromtimestamp(event.get('startTimestamp', 0))
                if dt.strftime('%Y-%m-%d') == today:
                    home = TEAM_TRANSLATIONS.get(event['homeTeam']['name'], event['homeTeam']['name'])
                    away = TEAM_TRANSLATIONS.get(event['awayTeam']['name'], event['awayTeam']['name'])
                    opp = away if str(event['homeTeam']['id']) == TEAM_ID else home
                    return {"opp": opp, "status": event.get('status', {}).get('type', 'unknown')}
    except: pass
    return None

def main():
    now = get_israel_time()
    print(f"🚀 ריצה מאוחדת התחילה: {now.strftime('%H:%M:%S')}")

    # טעינת היסטוריה
    db_file, sum_db = "seen_links.txt", "recent_summaries.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    if not os.path.exists(sum_db): open(sum_db, 'w').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent_summaries = f.read().splitlines()[-15:]

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

    # 1. סריקת RSS (לוגיקה מה-26.3)
    for feed_url in RSS_FEEDS:
        print(f"📡 בודק: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
            
            # בדיקת תאריך (עד שבוע אחורה)
            pub = entry.get('published_parsed')
            if pub and datetime.now() - datetime.fromtimestamp(calendar.timegm(pub)) > timedelta(days=7): continue

            # בדיקת רלוונטיות
            content = get_full_article_text(link)
            if any(key in (title + content).lower() for key in hapoel_keys) or "hapoelpt.com" in link:
                print(f"🎯 מעבד כתבה: {title}")
                summary = get_ai_summary(content, recent_summaries)
                
                if summary and summary != "REJECTED":
                    msg = f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    send_to_telegram(msg)
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    time.sleep(5)

    # 2. בדיקת יום משחק (התשתית החדשה)
    match = check_for_match()
    task_file = "task_log.txt"
    if not os.path.exists(task_file): open(task_file, 'w').close()
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    if match:
        today_key = now.strftime('%Y-%m-%d')
        if f"match_final_{today_key}" not in tasks_done:
            print(f"⚽ נמצא משחק נגד {match['opp']}")
            msg = f"MATCH DAY! 💙\n\nהפועל מול {match['opp']}\nמביאים 3 נקודות בעזרת השם! ⚽️"
            poster = f"https://pollinations.ai/p/cinematic%20football%20stadium%20blue%20Hapoel%20Petah%20Tikva%20matchday%20poster"
            send_to_telegram(msg, photo_url=poster)
            
            poll = {"question": f"הימור שלכם מול {match['opp']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד"], "is_anonymous": False}
            send_to_telegram("", is_poll=True, poll_data=poll)
            with open(task_file, 'a') as f: f.write(f"match_final_{today_key}\n")

    print("🏁 סיום ריצה.")

if __name__ == "__main__": main()
