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

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- הגדרות תוכן ופוסטרים ---
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
    "Bnei Sakhnin": "בני סכנין", "M.S. Ashdod": "מ.ס. אשדוד", "Hapoel Tel Aviv": "הפועל תל אביב",
    "Hapoel Haifa": "הפועל חיפה", "Maccabi Netanya": "מכבי נתניה", "Hapoel Jerusalem": "הפועל ירושלים"
}

WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "קליי", "סונגה", "אלטמן"]

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
        return r.status_code == 200
    except: return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    # תיקון הנתיב ל-API כדי למנוע 404
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        data = res.json()
        if 'candidates' in data and len(data['candidates']) > 0:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"LOG ERROR: AI response structure invalid: {data}")
        return None
    except Exception as e:
        print(f"LOG ERROR: AI call failed: {e}")
        return None

def scrape_sport5():
    """סריקה ישירה של אתר ספורט 5 למקרה שה-RSS חסום"""
    articles = []
    url = "https://www.sport5.co.il/liga.aspx?FolderID=64" # ליגת העל
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.content, 'html.parser')
        # חיפוש כתבות במבנה החדש של ספורט 5
        for item in soup.select('.news-item, .main-article, .secondary-article'):
            link_tag = item.find('a')
            title_tag = item.find(['h2', 'h3', 'span'])
            if link_tag and title_tag:
                link = link_tag['href']
                if not link.startswith('http'): link = 'https://www.sport5.co.il' + link
                articles.append({'title': title_tag.get_text().strip(), 'link': link})
    except Exception as e:
        print(f"LOG ERROR: Sport5 Scraping failed: {e}")
    return articles

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- {now_il.strftime('%H:%M:%S')} (Israel) תחילת ריצה ---")

    # ניהול קבצי זיכרון
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. פינת ההיסטוריה (ימי רביעי) - פולבק חזק
    if now_il.weekday() == 2 and now_il.hour >= 10 and f"history_{today_str}" not in tasks:
        prompt = "כתוב 2 עובדות היסטוריות קצרות, מרגשות ואמיתיות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. התחל ב'הידעת?'."
        fact = get_ai_response(prompt)
        if not fact: fact = "הידעת? הפועל פתח תקווה מחזיקה בשיא של 5 אליפויות רצופות (1959-1963)!"
        msg = f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"
        if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
            with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. יום משחק (API)
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
                    md_text = f"*Match-Day*\nהפועל שלנו תעלה בעוד כמה שעות לכר הדשא נגד *{opp_heb}*.\nמקווים לצאת עם נצחון חשוב.\n\nקדימה הפועל יאללה מלחמה 💙"
                    photo_p = {"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text, "parse_mode": "Markdown"}
                    if send_telegram(md_text, method="sendPhoto", payload=photo_p):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    poll_p = {"chat_id": ADMIN_ID, "question": f"הימורים נגד {opp_heb}?", "options": ["ניצחון 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}
                    if send_telegram("", method="sendPoll", payload=poll_p):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")
    except: pass

    # 3. סריקת כתבות (כולל המעקף של ספורט 5)
    all_articles = []
    # א. סריקת RSS רגיל
    browser_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36', 'Referer': 'https://www.google.com/'}
    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=browser_headers, timeout=20)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:15]:
                all_articles.append({'title': entry.title, 'link': entry.link})
        except: continue

    # ב. פריצה לספורט 5 (סריקה ישירה)
    all_articles.extend(scrape_sport5())

    # עיבוד כל הכתבות שנמצאו
    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            art_res = requests.get(link, headers=browser_headers, timeout=15)
            soup = BeautifulSoup(art_res.content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
        except: content = art['title']

        if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
            prompt = f"האם יש עדכון מהותי על הפועל פתח תקווה? אם כן, כתוב תקציר של 3 משפטים. אם לא, החזר 'SKIP'.\n\nכתבה: {content[:3000]}"
            summary = get_ai_response(prompt)
            if summary and "SKIP" not in summary.upper():
                dup_p = f"האם התקציר הבא עוסק באותו נושא בדיוק כמו הקודמים? 'YES' או 'NO'.\n\nקודמים: {recent_sums[-1000:]}\n\nחדש: {summary}"
                if "YES" not in (get_ai_response(dup_p) or "NO").upper():
                    msg = f"*יש עדכון חדש על הפועל 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                        with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "\n---\n")
                        time.sleep(5)

if __name__ == "__main__": main()
