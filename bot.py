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

TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Bnei Reineh": "מכבי בני ריינה", "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", "M.S. Ashdod": "מ.ס. אשדוד", 
    "Hapoel Haifa": "הפועל חיפה", "Maccabi Netanya": "מכבי נתניה", 
    "Hapoel Jerusalem": "הפועל ירושלים", "Hapoel Hadera": "הפועל חדרה", 
    "Ironi Kiryat Shmona": "עירוני קרית שמונה", "Maccabi Petah Tikva": "מכבי פתח תקווה"
}

# ✅ שינוי 1: נוסף Google News (עוקף חסימת sport5) + פסיק תקין בכל שורה
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=הפועל+פתח+תקווה&hl=he&gl=IL&ceid=IL:he",
    "https://rss.walla.co.il/feed/7",
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss2.xml"
]

# ✅ שינוי 2: כותרות שמתחזות לדפדפן - בלעדיהן sport5 חוסם
RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    'Accept-Language': 'he-IL,he;q=0.9,en;q=0.8',
}

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    if payload is None:
        payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    else:
        payload["chat_id"] = ADMIN_ID
        if method in ["sendMessage", "sendPhoto"]: payload["parse_mode"] = "Markdown"
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

# ✅ שינוי 3: חילוץ תוכן חכם - sport5 בנוי אחרת משאר האתרים
def extract_article_content(soup, url):
    if "sport5.co.il" in url:
        container = (
            soup.find('div', class_='article-body') or
            soup.find('div', class_='articleBody') or
            soup.find('article') or
            soup.find('div', attrs={'itemprop': 'articleBody'})
        )
        if container:
            return " ".join([el.get_text() for el in container.find_all(['p', 'h1', 'h2', 'h3', 'span'])])
        print("DEBUG [SPORT5]: לא נמצא container, חוזר לחיפוש כללי")
    return " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---")

    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = f.read()
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. היסטוריה שבועית (רביעי ב-12:00)
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        fact = get_ai_response("כתוב 2 עובדות היסטוריות קצרות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. הוסף אימוג'ים והתחל ב'הידעת?'.")
        if fact:
            if send_telegram(f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. יום משחק וסיום משחק (API)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            if (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                
                if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
                    md_text = f"*Match-Day*\nנגד *{opp_heb}*.\nקדימה הפועל לתת את הלב - יאללה מלחמה 💙"
                    if send_telegram(None, "sendPhoto", {"chat_id": ADMIN_ID, "photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
                
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    if send_telegram(None, "sendPoll", {"chat_id": ADMIN_ID, "question": f"מה ההימור נגד {opp_heb}?", "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"], "is_anonymous": False}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")

        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers_api, timeout=15).json()
        if r_last.get('events'):
            last_ev = r_last['events'][0]
            if (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                if f"final_{today_str}" not in tasks and last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                    is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                    my, opp_s = (last_ev['homeScore']['display'], last_ev['awayScore']['display']) if is_h else (last_ev['awayScore']['display'], last_ev['homeScore']['display'])
                    opp_heb = TEAM_TRANSLATION.get(last_ev['awayTeam']['name'] if is_h else last_ev['homeTeam']['name'], "היריבה")
                    
                    if my > opp_s:
                        res_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\n3 נקודות נגד {opp_heb} ({my}-{opp_s}) 💙"
                    elif my == opp_s:
                        res_txt = f"*סיום:* תיקו {my}-{opp_s} נגד {opp_heb}. ממשיכים הלאה 💙"
                    else:
                        res_txt = f"*סיום:* הפסד {my}-{opp_s} נגד {opp_heb}. מרימים את הראש 💙"
                    
                    if send_telegram(res_txt, payload={"chat_id": ADMIN_ID, "text": res_txt, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": ONE_TABLE_URL}]]}}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}\n")
                    
                    if f"mvp_{today_str}" not in tasks:
                        players = DEFAULT_PLAYERS
                        try:
                            r_lineups = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/event/{last_ev['id']}/lineups", headers=headers_api, timeout=15).json()
                            players = [PLAYER_MAP.get(p['player']['name'], p['player']['name']) for p in r_lineups['home' if is_h else 'away']['players']]
                        except: pass
                        send_telegram(None, "sendPoll", {"chat_id": ADMIN_ID, "question": "מי המצטיין היום? ⚽️", "options": players[:10], "is_anonymous": False})
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"mvp_{today_str}\n")
    except: pass

    # 3. סריקת כתבות (עד 3 לריצה)
    processed_count = 0
    print("DEBUG: מתחיל סריקה...")
    for feed_url in RSS_FEEDS:
        if processed_count >= 3: break
        try:
            # ✅ שינוי 2 בפעולה: RSS_HEADERS בכל בקשת פיד
            resp = requests.get(feed_url, headers=RSS_HEADERS, timeout=20)
            feed = feedparser.parse(resp.content)
            print(f"DEBUG [RSS]: {feed_url.split('/')[2]} — {len(feed.entries)} כתבות")

            for entry in feed.entries[:50]:
                if processed_count >= 3: break
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue

                content = entry.title
                try:
                    # ✅ שינוי 2+3 בפעולה: headers + חילוץ חכם לפי אתר
                    soup = BeautifulSoup(requests.get(entry.link, headers=RSS_HEADERS, timeout=15).content, 'html.parser')
                    content += " " + extract_article_content(soup, entry.link)
                except: pass

                if any(k.lower() in content.lower() for k in ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פ\"ת"]):
                    prompt = (
                        "אתה עורך חדשות מקצועי של הפועל פתח תקווה. "
                        "משימה: בדוק האם הכתבה עוסקת בעיקרה בקבוצה. אם כן, סכם ב-3 משפטים. אם לא, החזר SKIP. "
                        "קריטי: אל תתחיל במילים כמו 'כן', 'נו', 'הנה', 'בוודאי'. התחל ישר בגוף החדשות.\n\n"
                        f"טקסט: {content[:2500]}"
                    )
                    summary = get_ai_response(prompt)
                    
                    if summary and "SKIP" not in summary.upper():
                        # ✅ שינוי 4: פרומפט כפילות משופר + תנאי בדיקה תקין
                        dup_p = (
                            f"השווה בין הכותרת החדשה לסיכומים הקודמים.\n"
                            f"האם הם עוסקים באותו אירוע או חדשה ספציפית?\n"
                            f"החזר YES אם זו כפילות, NO אם זה נושא שונה.\n"
                            f"החזר רק המילה YES או NO בלבד, ללא שום טקסט נוסף.\n\n"
                            f"סיכומים קודמים: {recent_sums[-800:]}\n"
                            f"כותרת חדשה: {entry.title}"
                        )
                        if "YES" not in (get_ai_response(dup_p) or "NO").upper():
                            if send_telegram(f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"):
                                with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                                with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "|||")
                                processed_count += 1
                                time.sleep(10)
        except Exception as e:
            print(f"DEBUG ERROR: {feed_url.split('/')[2]} — {e}")

    print(f"--- סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ---")

if __name__ == "__main__": main()
