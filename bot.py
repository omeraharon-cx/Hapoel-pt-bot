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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_ai_response(prompt):
    """שימוש במודל 2.0 פלאש - המודל המעודכן ביותר ל-2026"""
    if not GEMINI_API_KEY: return None
    # מעבר למודל 2.0 כדי למנוע את ה-404 שראינו בלוג
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        
        print(f"DEBUG [AI ERROR]: סטטוס {res.status_code}. הודעה: {res.text[:150]}")
        return "STOP_ALL"
    except Exception as e:
        print(f"DEBUG [AI EXCEPTION]: {e}")
        return "STOP_ALL"

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"DEBUG [TELEGRAM]: {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---")

    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. יום משחק
    if now_il.hour >= 12 and f"matchday_{today_str}" not in tasks:
        headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        try:
            r = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=10).json()
            if r.get('events') and (datetime.fromtimestamp(r['events'][0]['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                if send_telegram("Match Day! 💙", method="sendPhoto", payload={"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": "Match Day! יאללה מלחמה 💙", "parse_mode": "Markdown"}):
                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
        except: pass

    # 2. סריקת כתבות
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.ynet.co.il/Integration/StoryRss2.xml", "https://rss.walla.co.il/feed/7"]
    
    all_articles = []
    for url in feeds:
        try:
            f = feedparser.parse(requests.get(url, timeout=15).content)
            for e in f.entries[:20]: all_articles.append({'title': e.title, 'link': e.link})
        except: continue

    # מעבדים רק כתבה אחת בכל ריצה כדי לשמור על הפרויקט החדש "נקי"
    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            soup = BeautifulSoup(requests.get(link, headers=headers, timeout=10).content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                print(f"DEBUG [MATCH]: נמצאה כתבה: {link}. מבקש תקציר מ-Gemini 2.0...")
                
                # המתנה קטנה לפני הקריאה ליתר ביטחון
                time.sleep(5)
                
                summary = get_ai_response(f"סכם ב-3 משפטים לאוהדי הפועל פתח תקווה. כתבה: {content[:2500]}")
                
                if summary == "STOP_ALL":
                    print("LOG: נעצר עקב שגיאה טכנית מול גוגל.")
                    return 

                if summary and "SKIP" not in summary.upper():
                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        print("LOG: הצלחה! כתבה נשלחה.")
                        return 
        except: continue

if __name__ == "__main__": main()
