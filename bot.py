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

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- מאגר פוסטרים ליום משחק ---
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# --- הגדרות תוכן ---
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
        print(f"LOG [TELEGRAM]: {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    # שימוש בנתיב v1 ובמודל הבסיסי ביותר - הכי פחות סיכוי ל-404
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        data = res.json()
        if 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"LOG ERROR [AI]: {data}")
        return None
    except Exception as e:
        print(f"LOG ERROR [AI]: {e}")
        return None

def scrape_sport5():
    """סריקה ישירה של דף הבית של ספורט 5"""
    links = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        r = requests.get("https://www.sport5.co.il/liga.aspx?FolderID=64", headers=headers, timeout=15)
        soup = BeautifulSoup(r.content, 'html.parser')
        # מחפש את כל הלינקים שמובילים לכתבות
        for a in soup.find_all('a', href=True):
            url = a['href']
            title = a.get_text().strip()
            if ('articles.aspx' in url or '/articles/' in url) and len(title) > 20:
                if not url.startswith('http'): url = "https://www.sport5.co.il" + url
                links.append({'title': title, 'link': url})
    except: pass
    return links

# --- לוגיקה מרכזית ---

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%Y-%m-%d %H:%M:%S')} (Israel) ---")

    # יצירת קבצים אם חסרים
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. פינת ההיסטוריה (ימי רביעי החל מ-10:00)
    if now_il.weekday() == 2 and now_il.hour >= 10 and f"history_{today_str}" not in tasks:
        prompt = "כתוב 2 עובדות היסטוריות קצרות ומרגשות על הפועל פתח תקווה. הוסף אימוג'ים והתחל ב'הידעת?'."
        fact = get_ai_response(prompt)
        if fact:
            if send_telegram(f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", payload={"chat_id": ADMIN_ID, "text": f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", "parse_mode": "Markdown"}):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול יום משחק
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            
            if ev_date == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)

                # Match-Day (12:00)
                if now_il.hour >= 12 and f"matchday_{today_str}" not in tasks:
                    md_text = f"*Match-Day*\nהפועל שלנו תעלה בעוד כמה שעות לכר הדשא נגד *{opp_heb}*.\nמקווים לצאת עם נצחון חשוב.\n\nקדימה הפועל לתת את הלב בשביל הסמל - יאללה מלחמה 💙"
                    photo_payload = {"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text, "parse_mode": "Markdown"}
                    if send_telegram(md_text, method="sendPhoto", payload=photo_payload):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
                
                # הימורים (15:00)
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    if send_telegram("", method="sendPoll", payload={"chat_id": ADMIN_ID, "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}?", "options": ["ניצחון 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")
    except: pass

    # 3. סריקת כתבות
    all_articles = []
    # RSS רגיל
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(requests.get(feed_url, timeout=15).content)
            for entry in feed.entries[:15]: all_articles.append({'title': entry.title, 'link': entry.link})
        except: continue
    
    # סריקה ישירה של ספורט 5
    all_articles.extend(scrape_sport5())

    for art in all_articles:
        link = art['link'].split('?')[0].replace("https://svcamz.", "https://www.")
        if link in history: continue
        
        try:
            art_res = requests.get(link, timeout=10)
            soup = BeautifulSoup(art_res.content, 'html.parser')
            content = art['title'] + " " + " ".join([p.get_text() for p in soup.find_all('p')])
            
            if any(k.lower() in content.lower() for k in HAPOEL_KEYS):
                prompt = f"כתוב תקציר של 3 משפטים לאוהדי הפועל פתח תקווה. אם הכתבה לא עוסקת בהם ישירות, החזר 'SKIP'.\n\nכתבה: {content[:2500]}"
                summary = get_ai_response(prompt)
                
                if summary and "SKIP" not in summary.upper():
                    # בדיקת כפילויות חכמה
                    dup_prompt = f"האם התקציר הבא עוסק באותו נושא בדיוק כמו אחד מהבאים? ענה 'YES' או 'NO'.\n\nקודמים: {recent_sums[-1500:]}\n\nחדש: {summary}"
                    if "YES" not in (get_ai_response(dup_prompt) or "NO").upper():
                        msg = f"*עדכון כחול 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                        if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                            with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "\n")
                            time.sleep(5)
        except: continue

if __name__ == "__main__": main()
