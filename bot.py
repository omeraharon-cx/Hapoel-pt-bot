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

# --- מאגר פוסטרים ליום משחק ---
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# --- תרגום שחקנים (API -> Hebrew) ---
PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Orel Dgani": "אוראל דגני", "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", "Roee David": "רועי דוד", "Itay Rotman": "איתי רוטמן",
    "Alex Moussounda": "מוסונדה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל",
    "Andrade Euclides Claye": "קליי", "Chipuoka Songa": "סונגה", "Tomer Altman": "אלטמן",
    "Dror Nir": "דרור ניר", "Shahar Rosen": "שחר רוזן", "Idan Cohen": "עידן כהן"
}

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
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
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
        print(f"LOG: Telegram {method} Status: {r.status_code}")
        return r.status_code == 200
    except: return False

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
    print(f"--- {now_il.strftime('%H:%M:%S')} (Israel Time) תחילת ריצה ---")

    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. פינת ההיסטוריה (ימי רביעי ב-12:00)
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        prompt = "כתוב 2 עובדות היסטוריות קצרות, מרגשות ואמיתיות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. הוסף אימוג'ים מתאימים והתחל ב'הידעת?'."
        fact = get_ai_response(prompt)
        if fact:
            msg = f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"
            if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול יום משחק (API)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        # בדיקת משחק היום
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers_api, timeout=15).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            
            if ev_date == today_str:
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)

                # הודעת Match-Day (12:00)
                if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
                    md_text = (
                        f"*Match-Day*\n"
                        f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n"
                        f"מקווים לצאת עם נצחון חשוב.\n\n"
                        f"קדימה הפועל לתת את הלב בשביל הסמל - יאללה מלחמה 💙"
                    )
                    selected_poster = random.choice(MATCHDAY_POSTERS)
                    photo_payload = {"chat_id": ADMIN_ID, "photo": selected_poster, "caption": md_text, "parse_mode": "Markdown"}
                    if send_telegram(md_text, method="sendPhoto", payload=photo_payload):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")
                
                # סקר הימורים (15:00)
                if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
                    poll_payload = {
                        "chat_id": ADMIN_ID, "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}? 💰",
                        "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"], "is_anonymous": False
                    }
                    if send_telegram("", method="sendPoll", payload=poll_payload):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")

        # בדיקת סיום משחק
        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers_api, timeout=15).json()
        if r_last.get('events'):
            last_ev = r_last['events'][0]
            l_date = (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            if l_date == today_str and last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                event_id = last_ev['id']
                if f"final_{today_str}" not in tasks:
                    is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                    my, opp = (last_ev['homeScore']['display'], last_ev['awayScore']['display']) if is_h else (last_ev['awayScore']['display'], last_ev['homeScore']['display'])
                    opp_heb = TEAM_TRANSLATION.get(last_ev['awayTeam']['name'] if is_h else last_ev['homeTeam']['name'], "היריבה")
                    
                    res_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות נגד {opp_heb} (תוצאה: {my}-{opp})\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙" if my > opp else \
                              f"תיקו בסיום המשחק ({my}-{opp}), ממשיכים הלאה. יאללה הפועלללל 💙" if my == opp else \
                              f"הפסד בסיום המשחק ({my}-{opp}), מרימים את הראש וממשיכים הלאה. יאללה הפועל מלחמה 💙"
                    
                    if send_telegram(res_txt, payload={"chat_id": ADMIN_ID, "text": res_txt, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": [[{"text": "📊 לטבלת הליגה (ONE)", "url": ONE_TABLE_URL}]]}}):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}:{now_il.strftime('%H:%M')}\n")
                
                # סקר MVP (ניסיון לקחת שחקנים מה-API)
                final_entry = [t for t in tasks if t.startswith(f"final_{today_str}:")]
                if final_entry and f"mvp_{today_str}" not in tasks:
                    f_time_parts = final_entry[0].split(":")[-2:]
                    f_time = now_il.replace(hour=int(f_time_parts[0]), minute=int(f_time_parts[1]))
                    
                    if now_il >= f_time + timedelta(minutes=10):
                        print("LOG: מנסה למשוך הרכבים מה-API עבור סקר MVP...")
                        r_lineups = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups", headers=headers_api, timeout=15).json()
                        
                        players_to_poll = []
                        if 'home' in r_lineups:
                            is_home = str(last_ev['homeTeam']['id']) == TEAM_ID
                            side = 'home' if is_home else 'away'
                            for p in r_lineups.get(side, {}).get('players', []):
                                name_eng = p.get('player', {}).get('name')
                                # תרגום או שם מקורי
                                players_to_poll.append(PLAYER_MAP.get(name_eng, name_eng))
                        
                        # אם יש שחקנים - שלח סקר. אם אין - אל תשלח (חכה לריצה הבאה)
                        if players_to_poll:
                            poll_mvp = {"chat_id": ADMIN_ID, "question": "מי המצטיין שלכם היום? ⚽️", "options": players_to_poll[:10], "is_anonymous": False}
                            if send_telegram("", method="sendPoll", payload=poll_mvp):
                                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"mvp_{today_str}\n")
                        else:
                            print("LOG: הרכבים עדיין לא זמינים ב-API, מחכה לריצה הבאה.")
    except: pass

    # 3. סריקת כתבות
    headers_browser = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/'
    }

    for feed_url in RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=headers_browser, timeout=20)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:20]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                if link in history: continue
                
                try:
                    art_res = requests.get(entry.link, headers=headers_browser, timeout=15)
                    soup = BeautifulSoup(art_res.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                if any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    prompt = f"האם הכתבה הבאה עוסקת בעיקרה בהפועל פתח תקווה? אם כן, כתוב תקציר של 3 משפטים בטון ענייני ומכובד. אם לא, החזר 'SKIP'.\n\nכתבה: {content[:2500]}"
                    summary = get_ai_response(prompt)
                    
                    if summary and "SKIP" not in summary.upper():
                        # מניעת כפילויות נושאים
                        dup_prompt = f"האם התקציר הבא עוסק באותו נושא בדיוק כמו אחד מהבאים? ענה 'YES' או 'NO'.\n\nקודמים: {recent_sums[-2000:]}\n\nחדש: {summary}"
                        if "YES" not in (get_ai_response(dup_prompt) or "NO").upper():
                            msg = f"*יש עדכון חדש על הפועל 💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                            if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
                                with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                                with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "\n---\n")
                                time.sleep(5)
        except: continue

if __name__ == "__main__": main()
