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

# הגדרה להדפסה מיידית ללוגים של GitHub Actions
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- פוסטר יום משחק (הלינק הישיר ששלחת) ---
MATCHDAY_POSTER_URL = "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png" 

# --- הגדרות תוכן ---
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
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss2.xml",
    "https://rss.walla.co.il/feed/7",
    "https://sport1.maariv.co.il/feed/"
]

# --- פונקציות עזר ---

def get_israel_time():
    """מחזיר את הזמן הנוכחי בישראל (UTC+3)"""
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=25)
        print(f"LOG: Telegram {method} Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR: Telegram failed: {e}")
        return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- {now_il.strftime('%H:%M:%S')} (שעון ישראל) תחילת ריצה ---")

    # יצירת קבצי זיכרון אם לא קיימים
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # 1. פינת ההיסטוריה האינסופית (ימי רביעי)
    if now_il.weekday() == 2 and now_il.hour >= 10 and f"history_{today_str}" not in tasks:
        print("LOG: מייצר עובדות היסטוריות בעזרת AI...")
        prompt = "כתוב 2 עובדות היסטוריות קצרות, מרגשות ואמיתיות על הפועל פתח תקווה. אחת משנות ה-50/60 ואחת משנות ה-90/2000. התחל ב'הידעת?'."
        fact = get_ai_response(prompt)
        if fact:
            msg = f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"
            if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                with open("task_log.txt", 'a') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול יום משחק (פוסטר וסקר הימורים)
    try:
        headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            
            if ev_date == today_str and f"matchday_{today_str}" not in tasks:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                msg = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
                
                # שליחת הפוסטר
                photo_payload = {"chat_id": ADMIN_ID, "photo": MATCHDAY_POSTER_URL, "caption": msg, "parse_mode": "Markdown"}
                print("LOG: מנסה לשלוח פוסטר Matchday...")
                if not send_telegram(msg, method="sendPhoto", payload=photo_payload):
                    print("LOG ERROR: שליחת תמונה נכשלה, שולח טקסט בלבד.")
                    send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"})
                
                # סקר הימורים
                poll_payload = {
                    "chat_id": ADMIN_ID,
                    "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}? 💰",
                    "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"],
                    "is_anonymous": False
                }
                send_telegram("", method="sendPoll", payload=poll_payload)
                
                with open("task_log.txt", 'a') as f: f.write(f"matchday_{today_str}\n")
    except Exception as e:
        print(f"LOG: Match check skip ({e})")

    # 3. סריקת כתבות
    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:30]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue
                
                try:
                    art_res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(art_res.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                if any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    prompt = f"אתה עיתונאי ספורט ואוהד הפועל פתח תקווה. כתוב תקציר של 3 משפטים בטון ענייני. אם הכתבה לא עוסקת בעיקר בהפועל, החזר SKIP.\n\nכתבה: {content[:2500]}"
                    summary = get_ai_response(prompt)
                    
                    if summary and "SKIP" not in summary.upper():
                        msg = f"*יש עדכון חדש על הפועל 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                        if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                            time.sleep(5)
        except: continue

    print("--- סיום ריצה ---")

if __name__ == "__main__":
    main()
