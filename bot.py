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

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Hapoel Tel Aviv": "הפועל תל אביב", "M.S. Ashdod": "מ.ס. אשדוד", "Bnei Sakhnin": "בני סכנין"
}

# --- פונקציות עזר ---

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_ai_response(prompt):
    """מנגנון פלייאוף: מנסה את המודלים של 2026 אחד אחד עד שאחד מבקיע"""
    if not GEMINI_API_KEY: return None
    
    # רשימת המודלים המעודכנת ל-2026
    models_to_try = ["gemini-2.0-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash-latest"]
    
    for model_id in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
        try:
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.status_code == 200:
                print(f"DEBUG [AI SUCCESS]: עבד עם מודל {model_id}!")
                return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"DEBUG [AI TRY]: מודל {model_id} החזיר {res.status_code}")
        except:
            continue
    
    print("DEBUG [AI FATAL]: שום מודל לא ענה. בדוק את ה-API Key ב-Google AI Studio.")
    return None

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"DEBUG [TELEGRAM]: {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def scrape_sport5_headlines():
    """סורק אגרסיבי לספורט 5 - מוציא לינקים ישירות מה-HTML"""
    links = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    try:
        r = requests.get("https://www.sport5.co.il/liga.aspx?FolderID=64", headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            title = a.get_text().strip()
            if ('article' in href or '.aspx' in href) and len(title) > 25:
                full_url = href if href.startswith('http') else "https://www.sport5.co.il" + href
                links.append({'title': title, 'link': full_url})
    except: pass
    return links

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

    # 1. יום משחק (פוסטר ב-12:00, הימורים ב-15:00)
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
                
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    if send_telegram("", method="sendPoll", payload={"chat_id": ADMIN_ID, "question": f"הימורים נגד {opp_heb}?", "options": ["ניצחון 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")
    except: pass

    # 2. סריקת כתבות
    print("DEBUG [RSS]: סורק כתבות חדשות...")
    all_articles = []
    feeds = ["https://www.hapoelpt.com/blog-feed.xml", "https://www.one.co.il/cat/rss/", "https://www.ynet.co.il/Integration/StoryRss2.xml", "https://rss.walla.co.il/feed/7"]
    for url in feeds:
        try:
            f = feedparser.parse(requests.get(url, timeout=15).content)
            for e in f.entries[:25]: all_articles.append({'title': e.title, 'link': e.link})
        except: continue
    
    all_articles.extend(scrape_sport5_headlines())

    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            soup = BeautifulSoup(requests.get(link, timeout=10).content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                print(f"DEBUG [MATCH]: נמצאה כתבה רלוונטית: {link}")
                prompt = f"סכם ב-3 משפטים לאוהדי הפועל פתח תקווה. אם הכתבה לא עוסקת בהם, החזר רק את המילה SKIP.\n\nכתבה: {content[:2500]}"
                summary = get_ai_response(prompt)
                
                if summary and "SKIP" not in summary.upper():
                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "\n")
                        time.sleep(5)
        except: continue

if __name__ == "__main__": main()
