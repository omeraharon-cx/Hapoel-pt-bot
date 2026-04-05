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

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, is_poll=False, poll_data=None):
    print(f"DEBUG: מנסה לשלוח הודעה לטלגרם... (is_poll={is_poll})")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    method = "sendPoll" if is_poll else "sendMessage"
    payload = {"chat_id": ADMIN_ID, **(poll_data if is_poll else {"text": text, "parse_mode": "HTML"})}
    try:
        r = requests.post(url + method, json=payload, timeout=10)
        print(f"DEBUG: תשובת טלגרם: {r.status_code}")
        if r.status_code != 200:
            print(f"DEBUG: שגיאת טלגרם מפורטת: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR: תקלה בשליחה לטלגרם: {e}")
        return False

def get_ai_summary(text, title):
    if not GEMINI_API_KEY: 
        print("DEBUG: חסר API KEY של Gemini!")
        return None
    print(f"DEBUG: שולח את הכתבה '{title[:30]}...' לסיכום ב-AI")
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"כתוב תקציר של 4 משפטים על הכתבה עבור אוהדי הפועל פתח תקווה. אם לא רלוונטי כתוב SKIP:\n{text[:3000]}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            summary = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"DEBUG: ה-AI החזיר סיכום (אורך: {len(summary)})")
            return summary if "SKIP" not in summary.upper() else None
        print(f"DEBUG: ה-AI נכשל עם סטטוס {res.status_code}: {res.text}")
    except Exception as e:
        print(f"DEBUG ERROR: תקלה בפנייה ל-AI: {e}")
    return None

def main():
    now = get_israel_time()
    print(f"--- תחילת ריצה: {now.strftime('%H:%M:%S')} ---")
    
    # בדיקת קבצים
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): 
            print(f"DEBUG: יוצר קובץ חסר: {f}")
            open(f, 'a').close()
    
    with open("seen_links.txt", 'r') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r') as f: tasks = set(line.strip() for line in f)
    print(f"DEBUG: היסטוריית לינקים טעונה ({len(history)} לינקים)")

    # 1. ניהול משחק (לוגים מורחבים)
    print("DEBUG: בודק נתוני משחק...")
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers, timeout=10)
        if r.status_code == 200:
            match = r.json().get('events', [{}])[0]
            m_date = datetime.fromtimestamp(match['startTimestamp']).strftime('%Y-%m-%d')
            print(f"DEBUG: נמצא משחק אחרון בתאריך {m_date}")
            if m_date == now.strftime('%Y-%m-%d') or m_date == (now - timedelta(days=1)).strftime('%Y-%m-%d'):
                if match.get('status', {}).get('type') in ['finished', 'FT']:
                    if f"final_{m_date}" not in tasks:
                        print("DEBUG: מזהה משחק שהסתיים ושטרם נשלח. שולח...")
                        # לוגיקת שליחה כאן...
        else:
            print(f"DEBUG: RapidAPI החזיר סטטוס {r.status_code}")
    except Exception as e:
        print(f"DEBUG: תקלה בבדיקת משחק: {e}")

    # 2. סריקת כתבות
    print(f"📡 מתחיל סריקת {len(RSS_FEEDS)} מקורות RSS...")
    for url in RSS_FEEDS:
        print(f"DEBUG: סורק מקור: {url}")
        try:
            feed = feedparser.parse(url)
            print(f"DEBUG: נמצאו {len(feed.entries)} כתבות במקור זה")
            for entry in feed.entries[:10]:
                if entry.link in history:
                    continue
                
                print(f"DEBUG: בודק כתבה חדשה: {entry.title}")
                
                # בדיקת מילות מפתח
                found_key = None
                for k in HAPOEL_KEYS:
                    if k.lower() in (entry.title + entry.get('summary', '')).lower():
                        found_key = k
                        break
                
                if found_key:
                    print(f"🎯 נמצאה מילת מפתח '{found_key}' בכתבה: {entry.title}")
                    
                    # ניסיון חילוץ טקסט מלא
                    try:
                        res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                        soup = BeautifulSoup(res.content, 'html.parser')
                        full_text = " ".join([p.get_text() for p in soup.find_all('p')])
                    except: 
                        print("DEBUG: נכשל חילוץ טקסט מלא, משתמש בכותרת בלבד")
                        full_text = entry.title

                    summary = get_ai_summary(full_text, entry.title)
                    
                    if summary:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{html.escape(summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        msg = f"💙 <b>{html.escape(entry.title)}</b>\n\n🔗 {entry.link}"
                        print("DEBUG: שולח ללא סיכום AI (דילוג או תקלה)")

                    if send_telegram(msg):
                        with open("seen_links.txt", 'a') as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        print(f"✅ כתבה נשלחה בהצלחה: {entry.title}")
                        time.sleep(2)
                else:
                    # לוג כדי להבין למה כתבות רגילות לא נתפסות
                    if "הפועל" in entry.title:
                        print(f"DEBUG: הכתבה '{entry.title}' מכילה 'הפועל' אך לא מילת מפתח מדויקת")
        except Exception as e:
            print(f"DEBUG ERROR RSS: תקלה בסריקת RSS {url}: {e}")

    print(f"--- סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ---")

if __name__ == "__main__":
    main()
