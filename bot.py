import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# מילות מפתח - הורחב כדי לוודא ששום דבר לא מתפספס בגלל רווח או מקף
HAPOEL_KEYS = [
    "הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", 
    "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה", "קוז'וק"
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

def get_ai_summary(text):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"תקציר ספורטיבי ב-4 משפטים עבור אוהדי הפועל פתח תקווה. אם לא רלוונטי לקבוצה כתוב SKIP:\n{text[:3000]}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return out if "SKIP" not in out.upper() else "SKIP"
    except: pass
    return None

def main():
    now = get_israel_time()
    print(f"--- {now.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r') as f: history = set(line.strip() for line in f)
    
    print(f"DEBUG: זיכרון טעון: {len(history)} לינקים")

    print("📡 סורק מקורות RSS...")
    for url in RSS_FEEDS:
        print(f"--- סורק מקור: {url.split('/')[2]} ---")
        try:
            feed = feedparser.parse(url)
            print(f"נמצאו {len(feed.entries)} כתבות במקור")
            for entry in feed.entries[:10]:
                # לוג לכל כותרת כדי לראות שהסריקה חיה
                is_seen = "נצפתה בעבר" if entry.link in history else "חדשה!"
                print(f"בודק: {entry.title[:50]}... [{is_seen}]")
                
                if entry.link in history: continue
                
                content = (entry.title + " " + entry.get('summary', '')).lower()
                
                # חיפוש מילות מפתח
                matched_key = None
                for k in HAPOEL_KEYS:
                    if k.lower() in content:
                        matched_key = k
                        break
                
                if matched_key:
                    print(f"🎯 התאמה! מילת מפתח: {matched_key}")
                    
                    try:
                        res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                        soup = BeautifulSoup(res.content, 'html.parser')
                        text = " ".join([p.get_text() for p in soup.find_all('p')])
                    except: text = entry.title

                    ai_out = get_ai_summary(text)
                    if ai_out == "SKIP":
                        print("AI החליט לדלג.")
                        continue
                    
                    if ai_out:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{html.escape(ai_out)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        msg = f"💙 <b>{html.escape(entry.title)}</b>\n\n🔗 {entry.link}"

                    if send_telegram(msg):
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        print(f"✅ נשלחה בהצלחה!")
                        time.sleep(2)
        except Exception as e:
            print(f"שגיאה במקור {url}: {e}")
            continue

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
