import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
# ניקוי רווחים מהמפתח ליתר ביטחון
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_ai_response(prompt):
    """
    פתרון שורש: משתמשים אך ורק במודל gemini-2.0-flash.
    הוכחנו בלוגים שזה המודל היחיד שקיים (לא מחזיר 404).
    """
    if not GEMINI_API_KEY: return None
    
    model = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # אם יש 429 (עומס), אנחנו עוצרים כדי לא להיחסם
        print(f"LOG: AI Response Status {res.status_code}. Content: {res.text[:200]}")
        return "RATE_LIMIT" if res.status_code == 429 else None
        
    except Exception as e:
        print(f"LOG: AI Request Exception: {e}")
        return None

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        return r.status_code == 200
    except: return False

def main():
    now_il = get_israel_time()
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---")

    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)

    # פידים
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.ynet.co.il/Integration/StoryRss2.xml", "https://rss.walla.co.il/feed/7"]
    
    all_articles = []
    for url in feeds:
        try:
            # הגדלת timeout ל-20 שניות למניעת ה-Read Timeout שראינו ב-ONE
            resp = requests.get(url, timeout=20)
            f = feedparser.parse(resp.content)
            for e in f.entries[:15]: all_articles.append({'title': e.title, 'link': e.link})
        except: continue

    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            # הגדלת timeout ל-20 שניות גם כאן
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            resp = requests.get(link, headers=headers, timeout=20)
            soup = BeautifulSoup(resp.content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                print(f"DEBUG [MATCH]: נמצאה כתבה: {link}")
                
                summary = get_ai_response(f"סכם ב-3 משפטים לאוהדי הפועל פתח תקווה. כתבה: {content[:2500]}")
                
                if summary == "RATE_LIMIT":
                    print("LOG: חריגה מהמכסה (429). הבוט יעבוד בריצה הבאה.")
                    return 

                if summary and "SKIP" not in summary.upper():
                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        print(f"LOG: Article sent: {link}")
                        return # שליחה אחת בכל פעם כדי לשמור על המכסה של הפרויקט החדש
        except Exception as e:
            print(f"LOG: Error processing {link}: {e}")
            continue

if __name__ == "__main__": main()
