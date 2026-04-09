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

# הדפסה מיידית ללוגים (חשוב ל-GitHub Actions)
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- מאגר פוסטרים ---
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
    "Maccabi Bnei Reineh": "מכבי בני ריינה", "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", "M.S. Ashdod": "מ.ס. אשדוד", "Hapoel Tel Aviv": "הפועל תל אביב"
}

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.ynet.co.il/Integration/StoryRss2.xml",
    "https://rss.walla.co.il/feed/7",
    "https://sport1.maariv.co.il/feed/"
]

# --- פונקציות עזר ---

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"LOG [TELEGRAM]: {method} Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR [TELEGRAM]: {e}")
        return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: 
        print("LOG ERROR [AI]: Missing API KEY")
        return None
    
    # שימוש בנתיב v1 היציב
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        print(f"LOG [AI]: Sending prompt to Gemini...")
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        data = res.json()
        
        if res.status_code != 200:
            print(f"LOG ERROR [AI]: Status {res.status_code}, Response: {res.text}")
            return None
            
        if 'candidates' in data:
            result = data['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"LOG [AI]: Success! Response length: {len(result)}")
            return result
        return None
    except Exception as e:
        print(f"LOG ERROR [AI]: Connection failed: {e}")
        return None

def scrape_sport5_headlines():
    print("LOG [SCRAPE]: Starting Sport5 direct scrape...")
    links = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        r = requests.get("https://www.sport5.co.il/liga.aspx?FolderID=64", headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        # חיפוש לינקים של ספורט 5
        for a in soup.select('a[href*="sport5.co.il/articles"]'):
            title = a.get_text().strip()
            url = a['href']
            if len(title) > 15:
                if not url.startswith('http'): url = "https://www.sport5.co.il" + url
                links.append({'title': title, 'link': url})
        print(f"LOG [SCRAPE]: Found {len(links)} potential links on Sport5")
    except Exception as e:
        print(f"LOG ERROR [SCRAPE]: {e}")
    return links

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%Y-%m-%d %H:%M:%S')} (יום {now_il.strftime('%A')}) ---")

    # ניהול קבצים
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    
    # 1. פינת ההיסטוריה (ימי רביעי)
    if now_il.weekday() == 2:
        print(f"LOG [HISTORY]: Today is Wednesday. Hour: {now_il.hour}")
        if now_il.hour >= 10 and f"history_{today_str}" not in tasks:
            print("LOG [HISTORY]: Triggering AI for history facts...")
            fact = get_ai_response("כתוב 2 עובדות היסטוריות קצרות ומרגשות על הפועל פתח תקווה. הוסף אימוג'ים והתחל ב'הידעת?'.")
            if fact:
                if send_telegram(f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", payload={"chat_id": ADMIN_ID, "text": f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", "parse_mode": "Markdown"}):
                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")
        else:
            print("LOG [HISTORY]: Already sent today or too early.")

    # 2. יום משחק (API)
    print("LOG [API]: Checking for matches...")
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            print(f"LOG [API]: Next match found for: {ev_date}")
            
            if ev_date == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                
                # Match-Day (12:00)
                if now_il.hour >= 12 and f"matchday_{today_str}" not in tasks:
                    print("LOG [MATCH]: Triggering Match-Day post...")
                    md_text = f"*Match-Day*\nהפועל שלנו נגד *{opp_heb}*.\nיאללה מלחמה 💙"
                    if send_telegram(md_text, method="sendPhoto", payload={"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text, "parse_mode": "Markdown"}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
                
                # הימורים (15:00)
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    print("LOG [MATCH]: Triggering Betting poll...")
                    if send_telegram("", method="sendPoll", payload={"chat_id": ADMIN_ID, "question": f"הימורים נגד {opp_heb}?", "options": ["ניצחון 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")
        else:
            print("LOG [API]: No upcoming matches found in API.")
    except Exception as e:
        print(f"LOG ERROR [API]: {e}")

    # 3. סריקת כתבות
    print("LOG [ARTICLES]: Starting RSS scan...")
    all_arts = []
    for feed_url in RSS_FEEDS:
        try:
            f = feedparser.parse(requests.get(feed_url, timeout=15).content)
            print(f"LOG [RSS]: Scanned {feed_url}, found {len(f.entries)} entries")
            for e in f.entries[:10]: all_arts.append({'title': e.title, 'link': e.link})
        except: continue
    
    all_arts.extend(scrape_sport5_headlines())

    for art in all_arts:
        link = art['link'].split('?')[0]
        if link in history: continue
        
        try:
            print(f"LOG [CHECK]: Testing article: {art['title'][:40]}...")
            soup = BeautifulSoup(requests.get(link, timeout=10).content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all('p')])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                print(f"LOG [MATCH]: Keyword found in {link}. Sending to AI...")
                summary = get_ai_response(f"סכם ב-3 משפטים לאוהדי הפועל פתח תקווה. אם לא עליהם, רשום SKIP.\n\nכתבה: {content[:2000]}")
                if summary and "SKIP" not in summary.upper():
                    msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        print(f"LOG [SUCCESS]: Sent article: {link}")
                        time.sleep(3)
        except Exception as e:
            print(f"LOG ERROR [ARTICLE]: {link} -> {e}")

    print(f"--- סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ---")

if __name__ == "__main__": main()
