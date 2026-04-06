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

# מילות מפתח מדויקות - "מבנה" הוסרה כמילה בודדת
HAPOEL_KEYS = [
    "הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", 
    "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה פתח-תקוה", 
    "הפועל מבנה פתח תקווה", "הפועל מבנה פתח תקוה"
]

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"DEBUG: Telegram Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def get_ai_summary(text, title):
    if not GEMINI_API_KEY: return None
    # שימוש בנתיב v1beta עם הגדרת מודל מלאה למניעת 404
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = (f"אתה עיתונאי ספורט. כתוב תקציר של 4 משפטים על הכתבה הבאה עבור אוהדי הפועל פתח תקווה. "
              f"אם הכתבה לא קשורה לקבוצה, כתוב רק את המילה SKIP.\n\nטקסט הכתבה: {text[:3000]}")
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return out if "SKIP" not in out.upper() else "SKIP"
        print(f"DEBUG Gemini API Error {res.status_code}: {res.text}")
    except Exception as e:
        print(f"DEBUG AI Exception: {e}")
    return None

def main():
    now = get_israel_time()
    print(f"--- {now.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r') as f: history = set(line.strip() for line in f)

    print(f"DEBUG: היסטוריית לינקים טעונה ({len(history)} לינקים)")

    for url in RSS_FEEDS:
        print(f"DEBUG: סורק מקור: {url}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                if entry.link in history: continue
                
                content_to_check = (entry.title + " " + entry.get('summary', '')).lower()
                
                # בדיקה אם אחת ממילות המפתח המדויקות מופיעה
                if any(k in content_to_check for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה התאמה פוטנציאלית: {entry.title}")
                    
                    # חילוץ טקסט מלא ל-AI
                    try:
                        res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                        soup = BeautifulSoup(res.content, 'html.parser')
                        article_body = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                    except: article_body = entry.title

                    ai_out = get_ai_summary(article_body, entry.title)
                    
                    if ai_out == "SKIP":
                        print(f"DEBUG: AI החליט שהכתבה לא רלוונטית לקבוצה. מדלג.")
                        continue
                    
                    if ai_out:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{html.escape(ai_out)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        # "נוהל חירום" - שולח בלי AI רק אם מופיע השם המפורש של הקבוצה בכותרת
                        if any(x in entry.title for x in ["הפועל", "פתח תקווה", "פתח-תקוה", "פ\"ת"]):
                            msg = f"💙 <b>{html.escape(entry.title)}</b>\n\n🔗 {entry.link}"
                        else:
                            print(f"DEBUG: AI נכשל והכותרת לא וודאית. מדלג כדי למנוע טעויות.")
                            continue

                    if send_telegram(msg):
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        history.add(entry.link)
                        time.sleep(2)
        except Exception as e:
            print(f"DEBUG RSS Error: {e}")
            continue

    print("--- סיום ריצה ---")

if __name__ == "__main__":
    main()
