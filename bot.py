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
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

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

# --- פונקציות עזר ---

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    # ניסיון למודל הכי יציב
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        else:
            print(f"DEBUG [AI ERROR]: Status {res.status_code}, Response: {res.text}")
            return None
    except Exception as e:
        print(f"DEBUG [AI EXCEPTION]: {e}")
        return None

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"DEBUG [TELEGRAM]: Sent {method}, Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG [TELEGRAM ERROR]: {e}")
        return False

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} (Israel) ---")

    # ניהול קבצי זיכרון
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. היסטוריה (ימי רביעי) - בדיקת לוג
    if now_il.weekday() == 2:
        print(f"DEBUG [HISTORY]: היום יום רביעי. משימות שכבר בוצעו: {tasks}")
        if now_il.hour >= 10 and f"history_{today_str}" not in tasks:
            print("DEBUG [HISTORY]: שולח בקשה ל-AI לפינת ההיסטוריה...")
            fact = get_ai_response("כתוב 2 עובדות היסטוריות קצרות ומרגשות על הפועל פתח תקווה. הוסף אימוג'ים והתחל ב'הידעת?'.")
            if fact:
                if send_telegram(fact, payload={"chat_id": ADMIN_ID, "text": f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", "parse_mode": "Markdown"}):
                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")
    else:
        print(f"DEBUG [HISTORY]: היום לא יום רביעי (היום יום {now_il.weekday()})")

    # 2. ניהול יום משחק
    print("DEBUG [API]: בודק משחקים קרובים...")
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            print(f"DEBUG [API]: נמצא משחק בתאריך {ev_date}")
            if ev_date == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                if now_il.hour >= 12 and f"matchday_{today_str}" not in tasks:
                    print("DEBUG [MATCH]: שולח פוסטר יום משחק...")
                    md_text = f"*Match-Day*\nהפועל שלנו נגד *{opp_heb}*.\nיאללה מלחמה 💙"
                    if send_telegram(md_text, method="sendPhoto", payload={"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text, "parse_mode": "Markdown"}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
    except Exception as e:
        print(f"DEBUG [API ERROR]: {e}")

    # 3. סריקת כתבות
    print("DEBUG [RSS]: מתחיל סריקת פידים...")
    feeds = [
        "https://www.hapoelpt.com/blog-feed.xml",
        "https://www.one.co.il/cat/rss/",
        "https://www.ynet.co.il/Integration/StoryRss2.xml",
        "https://rss.walla.co.il/feed/7"
    ]
    
    for url in feeds:
        print(f"DEBUG [RSS]: סורק את {url}")
        try:
            f = feedparser.parse(requests.get(url, timeout=15).content)
            for e in f.entries[:10]:
                link = e.link.split('?')[0]
                print(f"DEBUG [CHECK]: בודק כתבה: {e.title[:40]}... ({link})")
                
                if link in history:
                    print(f"DEBUG [SKIP]: הלינק כבר קיים בהיסטוריה.")
                    continue
                
                # שאיבת תוכן לזיהוי מילות מפתח
                try:
                    soup = BeautifulSoup(requests.get(link, timeout=10).content, 'html.parser')
                    content = e.title + " " + " ".join([p.get_text() for p in soup.find_all('p')])
                except:
                    content = e.title

                if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                    print(f"DEBUG [MATCH]: נמצאה מילת מפתח! שולח ל-AI לסיכום...")
                    prompt = f"כתוב תקציר של 3 משפטים לאוהדי הפועל פתח תקווה. אם הכתבה לא עוסקת בהם ישירות (למשל רק אזכור קטן), החזר רק את המילה SKIP.\n\nכתבה: {content[:2000]}"
                    summary = get_ai_response(prompt)
                    
                    print(f"DEBUG [AI RESPONSE]: {summary}")
                    
                    if summary and "SKIP" not in summary.upper():
                        msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                        if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                            time.sleep(5)
                else:
                    print(f"DEBUG [IGNORE]: לא נמצאה מילת מפתח בכתבה.")
        except Exception as e:
            print(f"DEBUG [RSS ERROR]: {e} בפיד {url}")

if __name__ == "__main__":
    main()
