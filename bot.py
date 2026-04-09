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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה", "בוני אמניס", "אמניס", "פורצ'ן"]

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

VICTORY_SONGS = [
    "בכל מקום בארץ, בכל מקום בעולם! 💙\nhttps://www.youtube.com/watch?v=XunT_7DEX_Y",
    "הפועל פתח תקווה, את כל החיים! 🔵⚪",
    "מי שלא קופץ צהוב! 🦁",
    "הנה היא עולה, הקבוצה של המדינה! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    if not payload:
        payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    else:
        payload["chat_id"] = ADMIN_ID
        if method in ["sendMessage", "sendPhoto"]:
            payload["parse_mode"] = "Markdown"
    try:
        r = requests.post(url, json=payload, timeout=25)
        return r.status_code == 200
    except: return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"DEBUG [AI ERROR]: Status {res.status_code}")
        return None
    except: return None

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---")

    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'w', encoding='utf-8').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # --- 1. יום משחק וניצחונות ---
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            ev = r_next['events'][0]
            if (datetime.fromtimestamp(ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                with open("task_log.txt", 'r') as f: tasks = f.read()
                if now_il.hour >= 8 and f"matchday_{today_str}" not in tasks:
                    if send_telegram("בוקר יום משחק! יאללה הפועל 🦁💙", method="sendPhoto", payload={"photo": random.choice(MATCHDAY_POSTERS), "caption": "בוקר יום משחק! יאללה הפועל 🦁💙"}):
                        with open("task_log.txt", 'a') as f: f.write(f"matchday_{today_str}\n")
    except: pass

    # --- 2. סריקת כתבות ---
    # וואלה עברה להתחלה כדי שלא תתפספס
    feeds = ["https://rss.walla.co.il/feed/7", "https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.ynet.co.il/Integration/StoryRss2.xml", "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64"]
    
    all_articles = []
    for url in feeds:
        try:
            f = feedparser.parse(requests.get(url, timeout=15).content)
            # הגדלנו ל-40 כדי למצוא כתבות ישנות יותר מהיום
            for e in f.entries[:40]: all_articles.append({'title': e.title, 'link': e.link})
        except: continue

    processed_count = 0
    for art in all_articles:
        if processed_count >= 3: break
        
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            resp = requests.get(link, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                # פילטר AI מחמיר
                summary_prompt = (
                    "אתה עורך חדשות של הפועל פתח תקווה. "
                    "משימה: בדוק האם הכתבה עוסקת בעיקרה (מעל 50%) בהפועל פתח תקווה או במידע קריטי עבורה (כמו שיבוץ שופטים למשחק שלה, מועד משחק, או החלטת בית דין). "
                    "אם הכתבה היא כללית (למשל: תקצירי ליגה, חדשות על קבוצה אחרת) והפועל מוזכרת רק בדרך אגב או ברשימת תוצאות - החזר אך ורק את המילה SKIP. "
                    "אם הכתבה רלוונטית, כתוב סיכום של 3 משפטים בטון ענייני וכחול. בלי 'לוזונים'.\n\n"
                    f"כתבה: {content[:3000]}"
                )
                summary = get_ai_response(summary_prompt)
                
                if summary and "SKIP" not in summary.upper():
                    # בדיקת כפילות נושא
                    dup_prompt = f"האם הכותרת עוסקת באותו נושא בדיוק כמו הסיכומים האלו? החזר YES או NO.\nסיכומים: {recent_sums[-600:]}\nכותרת: {art['title']}"
                    if "YES" in (get_ai_response(dup_prompt) or ""):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        continue

                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary[:100] + "|||")
                        processed_count += 1
                        print(f"LOG SUCCESS: {link}")
                        time.sleep(10)
                else:
                    # אם ה-AI החליט לדלג, נרשום את הלינק כ'נראה' כדי שלא נבזבז עליו קריאות AI שוב
                    with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                    print(f"LOG SKIP: {link}")
        except: continue

if __name__ == "__main__":
    main()
