import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264423"
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# רשימת מילות מפתח רחבה יותר לזיהוי כתבות
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

# תיקון: הסרתי סימני Markdown בעייתיים מהשירים
WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש-אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        if is_poll:
            r = requests.post(f"{url_base}/sendPoll", json={"chat_id": ADMIN_ID, **poll_data})
        elif photo_url:
            r = requests.post(f"{url_base}/sendPhoto", json={"chat_id": ADMIN_ID, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup})
            if r.status_code != 200: # גיבוי בטקסט בלבד
                r = requests.post(f"{url_base}/sendMessage", json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup})
        else:
            r = requests.post(f"{url_base}/sendMessage", json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup})
        print(f"DEBUG: Telegram Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2']) if len(t.get_text()) > 20])
    except: return ""

def get_ai_summary(url, title, recent_summaries):
    if not GEMINI_API_KEY: return None
    article_text = get_full_article_text(url)
    prompt = (
        f"כתוב תקציר של 4-5 משפטים לאוהדי הפועל פתח תקווה על הכתבה. "
        f"טון חברי, בגובה העיניים. התמקד רק במה שרלוונטי להפועל פתח תקווה. "
        f"אם הכתבה לא עוסקת בהם או שהיא כפולה של המידע הזה: {recent_summaries}, החזר רק את המילה: SKIP\n"
        f"טקסט הכתבה: {article_text[:3000]}"
    )
    try:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return result if "SKIP" not in result.upper() else None
    except: pass
    return None

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now.strftime('%H:%M:%S')} ---")

    # טעינת קבצים
    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(line.strip() for line in f if line.strip())
    with open(db_file, 'r') as f: history = set(line.strip() for line in f if line.strip())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-15:]

    print(f"DEBUG: נטענו {len(tasks)} משימות ו-{len(history)} לינקים.")

    # 1. בדיקת משחק
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0"
        res = requests.get(url, headers=headers, timeout=10).json()
        for event in res.get('events', []):
            ev_date = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
            if ev_date == today_str:
                is_home = str(event['homeTeam']['id']) == TEAM_ID
                opp_raw = event['awayTeam']['name'] if is_home else event['homeTeam']['name']
                opp = TEAM_TRANSLATIONS.get(opp_raw, opp_raw)
                status = event.get('status', {}).get('type')
                
                # מניעת כפילות - בדיקה קשיחה
                if status in ['finished', 'FT'] and f"finish_{today_str}" not in tasks:
                    print(f"🎯 זיהוי סיום משחק מול {opp}")
                    my_score = event.get('homeScore', {}).get('display', 0) if is_home else event.get('awayScore', {}).get('display', 0)
                    opp_score = event.get('awayScore', {}).get('display', 0) if is_home else event.get('homeScore', {}).get('display', 0)
                    
                    if my_score > opp_score:
                        txt = f"{random.choice(WIN_CHANTS)}\n\nניצחון ענק! {my_score}-{opp_score} להפועל! 💙"
                    elif my_score == opp_score:
                        txt = f"תיקו {my_score}-{opp_score} בסיום. ⚽\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
                    else:
                        txt = f"סיום המשחק. {opp_score}-{my_score} ליריבה.\nמרימים את הראש, יאללה הפועל מלחמה! 💙"
                    
                    markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
                    if send_to_telegram(txt, reply_markup=markup):
                        with open(task_file, 'a') as f: f.write(f"finish_{today_str}\n")
                        tasks.add(f"finish_{today_str}")
    except Exception as e:
        print(f"DEBUG Match Error: {e}")

    # 2. RSS
    RSS_FEEDS = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.sport5.co.il/RSS.aspx", "https://rss.walla.co.il/feed/3"]
    for feed_url in RSS_FEEDS:
        print(f"📡 סורק: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            if entry.link in history: continue
            
            # בדיקת רלוונטיות
            is_relevant = any(k in entry.title.lower() for k in HAPOEL_KEYS) or "hapoelpt.com" in entry.link
            if is_relevant:
                print(f"🎯 כתבה נמצאה: {entry.title}")
                summary = get_ai_summary(entry.link, entry.title, recent)
                if summary:
                    msg = f"💙 **עדכון חדש**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                    if send_to_telegram(msg):
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        time.sleep(5)

    print("--- סיום ריצה ---")

if __name__ == "__main__":
    main()
