import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
import json
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = "425605110"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/liga.aspx?FolderID=44"

# מקורות RSS - הוספתי נתיבים חלופיים לספורט 5
RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.sport5.co.il/RSS.aspx", 
    "https://www.ynet.co.il/Integration/StoryRss2.xml",
    "https://rss.walla.co.il/feed/7",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=20)
        return r.status_code == 200
    except: return False

def get_ai_summary(text, title):
    """מסכם רק אם הפועל פ"ת היא הנושא המרכזי"""
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        "אתה עיתונאי ספורט ואוהד שרוף של הפועל פתח תקווה. "
        "משימה 1: בדוק האם הכתבה עוסקת בעיקרה (מעל 50%) בהפועל פתח תקווה. "
        "אם הקבוצה מוזכרת רק כיריבה עתידית, או כחלק מרשימת תוצאות, או שהכתבה היא על קבוצה אחרת (כמו הפועל תל אביב) - החזר 'SKIP'. "
        "משימה 2: אם הכתבה רלוונטית, כתוב תקציר של 3-4 משפטים בטון ענייני, כחול ומכובד. בלי 'לוזונים'.\n\n"
        f"כותרת: {title}\nטקסט: {text[:3000]}"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        if "SKIP" in out.upper(): return "SKIP"
        return out
    except: return None

def is_duplicate_news(new_title, history_file="recent_titles.txt"):
    """בדיקה חכמה למניעת כפילויות מאתרים שונים על אותו נושא"""
    if not os.path.exists(history_file): open(history_file, 'w').close()
    with open(history_file, 'r', encoding='utf-8') as f:
        recent = f.read().splitlines()
    
    # בדיקה אם יש מילים משותפות משמעותיות בכותרת (למשל 'עומר פרץ' ו-'חוזה')
    new_words = set(new_title.split())
    for old_title in recent:
        old_words = set(old_title.split())
        common = new_words.intersection(old_words)
        if len(common) >= 3: # אם יש 3 מילים זהות בכותרת, זה כנראה אותו נושא
            return True
            
    # שמירה וניהול רשימה של 10 כותרות אחרונות
    recent = [new_title] + recent[:9]
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(recent))
    return False

def main():
    now_il = get_israel_time()
    print(f"--- {now_il.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}")
        try:
            # Headers מתקדמים לעקיפת חסימות (במיוחד ספורט 5)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml;q=0.9, */*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            resp = requests.get(feed_url, headers=headers, timeout=20)
            feed = feedparser.parse(resp.content)
            
            for entry in feed.entries[:30]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue
                
                # חילוץ תוכן
                try:
                    art_resp = requests.get(entry.link, headers=headers, timeout=15)
                    soup = BeautifulSoup(art_resp.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h2'])])
                except: content = entry.title

                # בדיקת מילות מפתח
                if any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    
                    # בדיקת כפילות נושא (מאתר אחר)
                    if is_duplicate_news(entry.title):
                        print(f"⏭️ כפילות נושא זוהתה: {entry.title}")
                        with open(db_file, 'a', encoding='utf-8') as f: f.write(link + "\n")
                        continue

                    print(f"🎯 נמצאה כתבה רלוונטית פוטנציאלית: {entry.title}")
                    summary = get_ai_summary(content, entry.title)
                    
                    if summary == "SKIP" or not summary:
                        print("🚫 הכתבה לא עוסקת בעיקרה בהפועל פ\"ת. מדלג.")
                        with open(db_file, 'a', encoding='utf-8') as f: f.write(link + "\n")
                        continue
                    
                    msg = f"*יש עדכון חדש על הפועל 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg):
                        with open(db_file, 'a', encoding='utf-8') as f: f.write(link + "\n")
                        history.add(link)
                        time.sleep(5)
        except Exception as e:
            print(f"⚠️ שגיאה בפיד {feed_url}: {e}")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
