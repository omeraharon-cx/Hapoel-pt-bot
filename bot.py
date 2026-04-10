import feedparser
import requests
import os
import time
import sys
import random
from bs4 import BeautifulSoup
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

# הלינק המדויק לטבלת הליגה
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "קליי", "סונגה", "אלטמן"]

PLAYER_MAP = { 
    "Omer Katz": "עומר כץ", "Orel Dgani": "אוראל דגני", "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", "Roee David": "רועי דוד", "Itay Rotman": "איתי רוטמן", 
    "Alex Moussounda": "מוסונדה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", 
    "Andrade Euclides Claye": "קליי", "Chipuoka Songa": "סונגה", "Tomer Altman": "אלטמן", 
    "Dror Nir": "דרור ניר", "Shahar Rosen": "שחר רוזן", "Idan Cohen": "עידן כהן"
}

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# עדכון קבוצות ליגת העל 2026 - הפועל ת"א בפנים, חדרה בחוץ
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Bnei Reineh": "מכבי בני ריינה", "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", "M.S. Ashdod": "מ.ס. אשדוד", 
    "Hapoel Tel Aviv": "הפועל תל אביב", "Hapoel Haifa": "הפועל חיפה", 
    "Maccabi Netanya": "מכבי נתניה", "Hapoel Jerusalem": "הפועל ירושלים",
    "Ironi Kiryat Shmona": "עירוני קרית שמונה", "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://news.google.com/rss/search?q=הפועל+פתח+תקווה&hl=he&gl=IL&ceid=IL:he",
    "https://rss.walla.co.il/feed/7",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss2.xml"
]

RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    if payload is None:
        payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    else:
        payload["chat_id"] = ADMIN_ID
        if "parse_mode" not in payload:
            payload["parse_mode"] = "Markdown"
    try:
        r = requests.post(url, json=payload, timeout=25)
        return r.status_code == 200
    except: return False

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def extract_article_data(url):
    """מחלץ תוכן ותמונה ראשית מהכתבה"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image: image = og_image["content"]
        
        if "sport5.co.il" in url:
            container = soup.find('div', class_='article-body') or soup.find('article')
            content = " ".join([el.get_text() for el in container.find_all(['p', 'h1', 'h2'])]) if container else ""
        else:
            content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
        return content, image
    except: return "", None

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---")

    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. יום משחק (RapidAPI)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            if (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                with open("task_log.txt", 'r') as f: tasks = f.read()
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
                    md_text = f"*Match-Day*\nנגד *{opp_heb}*. יאללה מלחמה! 💙"
                    if send_telegram(None, "sendPhoto", {"photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
    except: pass

    # 2. סריקת כתבות (עד 3 לריצה)
    processed_count = 0
    for feed_url in RSS_FEEDS:
        if processed_count >= 3: break
        try:
            resp = requests.get(feed_url, headers=RSS_HEADERS, timeout=20)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:40]:
                if processed_count >= 3: break
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue

                content, image = extract_article_data(link)
                if not content: content = entry.title

                if any(k.lower() in (entry.title + content).lower() for k in ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פ\"ת", "מלאבס"]):
                    prompt = (
                        "אתה כתב ספורט חד וחד משמעי, אוהד הפועל פתח תקווה. "
                        "תקצר את הכתבה ב-3 משפטים קצרים בגובה העיניים. "
                        "חוקים קריטיים: "
                        "1. תתחיל ישר במידע. אסור להגיד 'הכתבה עוסקת ב', 'הנה תקציר', 'כן' או 'נו'. "
                        "2. תמיד תזכיר את 'הפועל' או 'הפועל פתח תקווה' בתוך התקציר. "
                        "3. אם הכתבה לא חשובה, החזר SKIP.\n\n"
                        f"טקסט: {content[:3000]}"
                    )
                    summary = get_ai_response(prompt)
                    
                    if summary and "SKIP" not in summary.upper():
                        dup_p = f"האם הכותרת החדשה היא כפילות? ענה YES או NO.\nקודמים: {recent_sums[-800:]}\nחדש: {entry.title}"
                        if "YES" not in (get_ai_response(dup_p) or "NO").upper():
                            full_msg = f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                            success = False
                            if image: success = send_telegram(None, "sendPhoto", {"photo": image, "caption": full_msg})
                            if not success: success = send_telegram(full_msg)
                            
                            if success:
                                with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                                with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "|||")
                                processed_count += 1
                                time.sleep(10)
        except Exception as e:
            print(f"DEBUG ERROR: {feed_url} — {e}")

if __name__ == "__main__": main()
