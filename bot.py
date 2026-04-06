import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import html
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = "425605110"

# מילות מפתח לסינון ראשוני (לוודא שזה כדורגל ולא אבו דאבי)
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"DEBUG: Telegram Response: {r.status_code}")
        return r.status_code == 200
    except: return False

def get_ai_summary(text, title):
    if not GEMINI_API_KEY: return None
    # שימוש במודל v1beta המעודכן
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # הנחיה מפורשת לטון של אוהד כחול
    prompt = (
        "אתה עיתונאי ספורט ואוהד שרוף של הפועל פתח תקווה. "
        "כתוב תקציר של 4 משפטים בטון אוהד, כחול ומלא גאווה. "
        "התייחס לקבוצה כ'הפועל', 'המלאבסים' או 'הכחולים'. "
        "חובה לקשר את תוכן הכתבה להפועל פתח תקווה ולמה שחשוב לאוהדים שלה. "
        "אם הכתבה לא קשורה אלינו בשום צורה, כתוב אך ורק את המילה: SKIP.\n\n"
        f"כותרת: {title}\nטקסט הכתבה: {text[:3000]}"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return out if "SKIP" not in out.upper() else "SKIP"
        print(f"DEBUG AI Error {res.status_code}")
    except: pass
    return None

def main():
    now = get_israel_time()
    print(f"--- {now.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)

    for url in RSS_FEEDS:
        print(f"סורק מקור: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:40]: # סורקים עמוק כדי לא לפספס
                clean_link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if clean_link in history: continue
                
                # חילוץ טקסט מלא לטובת ה-AI
                try:
                    res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    article_body = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: article_body = entry.title

                full_content = (entry.title + " " + article_body).lower()
                
                # סינון ראשוני: רק אם זה באמת קשור להפועל פ"ת
                if any(k in full_content for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    
                    ai_summary = get_ai_summary(article_body, entry.title)
                    
                    if ai_summary == "SKIP":
                        print("AI החליט שהכתבה לא רלוונטית.")
                        continue
                    
                    if ai_summary:
                        # הודעה עם תקציר בטון אוהד
                        msg = f"💙 <b>עדכון חדש</b>\n\n{html.escape(ai_summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        # Fallback לבקשתך אם ה-AI נכשל (למשל 404)
                        msg = f"💙 <b>{html.escape(entry.title)}</b>\n\nכתבה ללא תקציר 🙏\n\n🔗 {entry.link}"

                    if send_telegram(msg):
                        with open(db_file, 'a', encoding='utf-8') as f: f.write(clean_link + "\n")
                        history.add(clean_link)
                        time.sleep(2)
        except Exception as e:
            print(f"שגיאה בסריקה: {e}")
    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
