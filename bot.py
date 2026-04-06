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

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה פתח-תקוה"]

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
    # ניסיון להשתמש במודל ה-8B הקטן והיציב יותר למניעת 404
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent?key={GEMINI_API_KEY}"
    prompt = (f"אתה עיתונאי ספורט אוהד הפועל פתח תקווה. כתוב תקציר של 4 משפטים בטון ענייני אך אוהד. "
              f"התייחס לקבוצה כ'הפועל' או 'המלאבסים'. אם הכתבה לא קשורה אלינו, כתוב SKIP.\n\n"
              f"כותרת: {title}\nטקסט: {text[:2500]}")
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return out if "SKIP" not in out.upper() else "SKIP"
        print(f"DEBUG AI Error {res.status_code}: {res.text}")
    except: pass
    return None

def main():
    now = get_israel_time()
    print(f"--- {now.strftime('%H:%M:%S')} ריצה ---")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)

    # בדיקת משחק (שקטה, כדי שלא תקרוס ב-429)
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        # כאן תהיה הלוגיקה של ה-API כשהמכסה תתאפס...
    except: pass

    print(f"📡 סורק {len(RSS_FEEDS)} מקורות RSS...")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            # סורקים 30 כתבות כדי לא לפספס כאלו שנדחקו
            for entry in feed.entries[:30]:
                link = entry.link.split('?')[0] # ניקוי לינקים מפרמטרים של מובייל
                if link in history: continue
                
                # קריאת תוכן הכתבה לסריקה עמוקה
                try:
                    res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    article_text = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: article_text = entry.title

                full_content = (entry.title + " " + article_text).lower()
                
                if any(k in full_content for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה: {entry.title}")
                    
                    ai_out = get_ai_summary(article_text, entry.title)
                    
                    if ai_out == "SKIP": continue
                    
                    if ai_out:
                        msg = f"💙 <b>עדכון חדש</b>\n\n{html.escape(ai_out)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    else:
                        # שליחה בלי AI רק אם המילה הפועל מופיעה (למנוע טעויות כמו הבוקר)
                        if "הפועל" in entry.title or "פתח תקווה" in entry.title:
                            msg = f"💙 <b>{html.escape(entry.title)}</b>\n\n🔗 {entry.link}"
                        else: continue

                    if send_telegram(msg):
                        with open(db_file, 'a', encoding='utf-8') as f: f.write(link + "\n")
                        history.add(link)
                        time.sleep(2)
        except: continue
    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
