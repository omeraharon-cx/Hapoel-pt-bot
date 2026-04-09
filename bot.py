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

# מילות המפתח המקוריות
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Hapoel Tel Aviv": "הפועל תל אביב", "M.S. Ashdod": "מ.ס. אשדוד", "Bnei Sakhnin": "בני סכנין"
}

# --- פונקציות עזר ---

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_ai_response(prompt):
    """שימוש במודל 2.0 בלבד עם מנגנון הגנה מעומס"""
    if not GEMINI_API_KEY: return None
    
    # שימוש במודל gemini-2.0-flash בלבד - כי ראינו בלוג שהוא היחיד שעובד (נתן 429 ולא 404)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    for attempt in range(3):
        try:
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
            
            if res.status_code == 200:
                return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            
            elif res.status_code == 429:
                wait = 40 * (attempt + 1)
                print(f"DEBUG [AI]: עומס (429). מחכה {wait} שניות...")
                time.sleep(wait)
            
            else:
                print(f"DEBUG [AI ERROR]: סטטוס {res.status_code}. הודעה: {res.text[:100]}")
                return None
        except Exception as e:
            print(f"DEBUG [AI EXCEPTION]: {e}")
            time.sleep(5)
            
    return None

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"DEBUG [TELEGRAM]: {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} (Israel) ---")

    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. יום משחק (פוסטר)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            if ev_date == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                if now_il.hour >= 12 and f"matchday_{today_str}" not in tasks:
                    md_text = f"*Match-Day*\nהפועל שלנו נגד *{opp_heb}*.\nיאללה מלחמה 💙"
                    if send_telegram(md_text, method="sendPhoto", payload={"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text, "parse_mode": "Markdown"}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
    except: pass

    # 2. סריקת כתבות
    print("DEBUG [RSS]: סורק פידים...")
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.ynet.co.il/Integration/StoryRss2.xml", "https://rss.walla.co.il/feed/7"]
    
    all_articles = []
    for url in feeds:
        try:
            f = feedparser.parse(requests.get(url, timeout=15).content)
            for e in f.entries[:40]: # סריקה עמוקה כדי למצוא את וואלה
                all_articles.append({'title': e.title, 'link': e.link})
        except: continue

    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            resp = requests.get(link, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                print(f"DEBUG [MATCH]: נמצאה כתבה: {link}. מבקש תקציר מ-Gemini 2.0...")
                
                # המתנה חובה של 25 שניות לפני כל פנייה ל-AI כדי למנוע עומס (429)
                time.sleep(25)
                
                prompt = (
                    "אתה כתב ספורט אוהד הפועל פתח תקווה. סכם את הכתבה ב-3 משפטים. "
                    "אם הכתבה לא עוסקת בהפועל פתח תקווה באופן מהותי, החזר SKIP.\n\n"
                    f"כתבה: {content[:3000]}"
                )
                summary = get_ai_response(prompt)
                
                if summary and "SKIP" not in summary.upper():
                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "\n")
                        # הפסקה קטנה נוספת
                        time.sleep(10)
        except: continue

if __name__ == "__main__": main()
