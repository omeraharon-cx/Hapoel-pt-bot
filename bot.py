import feedparser
import requests
import os
import time
import sys
import random
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# הגדרה שמכריחה את פייתון להוציא לוגים מיד (חשוב ל-GitHub Actions)
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- הגדרות סביבת עבודה (Toggle) ---
# שנה ל-True כדי לשלוח לכל המנויים ב-subscribers.txt | שנה ל-False לשליחה לאדמין בלבד (טסטים)
BROADCAST_MODE = True 

# --- סגל שחקנים (10 שחקנים מעודכן) ---
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "נועם כהן", "בוני", "דיארה"]

PLAYER_MAP = { 
    "Omer Katz": "עומר כץ", "Orel Dgani": "אוראל דגני", "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", "Roee David": "רועי דוד", "Itay Rotman": "איתי רוטמן", 
    "Alex Moussounda": "מוסונדה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", 
    "Andrade Euclides Claye": "קליי", "Chipuoka Songa": "סונגה", "Tomer Altman": "אלטמן", 
    "Dror Nir": "דרור ניר", "Shahar Rosen": "שחר רוזן", "Idan Cohen": "עידן כהן",
    "Noam Cohen": "נועם כהן", "Boni Amanis": "בוני", "Fortune Diarra": "דיארה",
    "Matan Gosha": "מתן גושה"
}

# --- מאגר פוסטרים (6) ---
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# --- שירי ניצחון ---
WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# --- לוח משחקים ידני (גיבוי למקרה שהמכסה נגמרת) ---
# עדכן כאן תאריכים רק אם ה-API לא עובד. פורמט: "YYYY-MM-DD": "שם היריבה"
BACKUP_SCHEDULE = {
    "2026-04-11": "הפועל תל אביב"
}

# --- תרגום קבוצות ליגת העל 2026 ---
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

# --- הגדרות סריקה ---
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://news.google.com/rss/search?q=הפועל+פתח+תקווה&hl=he&gl=IL&ceid=IL:he",
    "https://rss.walla.co.il/feed/3",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss3.xml"
]

RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# --- פונקציות עזר ---
def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, method="sendMessage", payload=None):
    # הגדרת רשימת נמענים
    recipients = [ADMIN_ID]
    if BROADCAST_MODE and os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r", encoding='utf-8') as f:
            recipients.extend([line.strip() for line in f if line.strip()])
    
    recipients = list(set(recipients)) # ניקוי כפילויות
    
    overall_success = True
    for chat_id in recipients:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
        current_payload = payload.copy() if payload else {}
        current_payload["chat_id"] = chat_id
        
        if method in ["sendMessage", "sendPhoto"]:
            current_payload["parse_mode"] = "Markdown"
        if "text" not in current_payload and text:
            current_payload["text"] = text
            
        try:
            r = requests.post(url, json=current_payload, timeout=25)
            if r.status_code != 200: overall_success = False
        except:
            overall_success = False
            
    return overall_success

def get_ai_response(prompt):
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def extract_article_data(url):
    """מחלץ תוכן ותמונה - פותר לינקים של גוגל ומעקף ספורט 5"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=15, allow_redirects=True)
        final_url = resp.url
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image: image = og_image["content"]
        
        if image and ("googleusercontent" in image or "google.com/logos" in image):
            image = None

        container = (
            soup.find('div', class_='article-body') or 
            soup.find('div', class_='article-content') or
            soup.find('article') or
            soup.find('div', id='article-content') or
            soup.find('div', class_='content')
        )
        if container:
            content = " ".join([el.get_text() for el in container.find_all(['p', 'h1', 'h2', 'h3'])])
        else:
            content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            content += " " + " ".join([p.get_text() for p in soup.find_all('p')])
            
        return content, image, final_url
    except: return "", None, url

# --- לוגיקה מרכזית ---
def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    current_week = now_il.strftime('%Y-%U') # זיהוי השבוע בשנה
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---", flush=True)

    # וידוא קבצים
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt", "schedule.json"]:
        if not os.path.exists(f): 
            open(f, 'a', encoding='utf-8').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = f.read()
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. פינת ההיסטוריה (רביעי ב-12:00)
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        fact = get_ai_response("כתוב 2 עובדות היסטוריות קצרות על הפועל פתח תקווה. הוסף אימוג'ים.")
        if fact:
            if send_telegram(f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול לוח משחקים שבועי (חיסכון ב-API)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    local_schedule = {}
    try:
        if os.path.exists("schedule.json") and os.path.getsize("schedule.json") > 0:
            with open("schedule.json", 'r', encoding='utf-8') as f: local_schedule = json.load(f)

        if f"sched_update_{current_week}" not in tasks or not local_schedule:
            print("DEBUG: מנסה לעדכן לוח משחקים שבועי מה-API...", flush=True)
            r_sched = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/10", headers=headers_api, timeout=15).json()
            if 'events' in r_sched:
                new_sched = {}
                for ev in r_sched['events']:
                    d_key = (datetime.fromtimestamp(ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
                    opp_raw = ev['awayTeam']['name'] if str(ev['homeTeam']['id']) == TEAM_ID else ev['homeTeam']['name']
                    new_sched[d_key] = TEAM_TRANSLATION.get(opp_raw, opp_raw)
                with open("schedule.json", 'w', encoding='utf-8') as f: json.dump(new_sched, f)
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"sched_update_{current_week}\n")
                local_schedule = new_sched
                print("DEBUG: הלוח התעדכן בהצלחה מה-API.", flush=True)
            else:
                print("DEBUG: API לא זמין, משתמש בלוח גיבוי ידני.", flush=True)
                local_schedule.update(BACKUP_SCHEDULE)
    except Exception as e: print(f"DEBUG SCHED ERROR: {e}", flush=True)

    # 3. ניהול יום משחק (מבוסס לוח מקומי/גיבוי)
    if today_str in local_schedule:
        opp_heb = local_schedule[today_str]
        print(f"DEBUG: היום יש משחק נגד {opp_heb}!", flush=True)

        if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
            md_text = (f"MatchDay Hapoel 💙\nהפועל שלנו תעלה בעוד מספר שעות לכר הדשא נגד *{opp_heb}*.\n"
                       f"יאללה הפועל, לתת הכל בשביל הסמל!\nמלחמה היום הפועלללל 🚀\n\n"
                       f"כשחקנים למגרש עולים - כל האוהדים שריםםםם\n"
                       f"הפועל עולה עולההה, הפועל, הפועל עולהה 💙")
            if send_telegram(None, "sendPhoto", {"photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")

        if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
            if send_telegram(None, "sendPoll", {"question": "זמן להמר, מי תנצח היום?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")

        # תוצאת סיום וסקר MVP (פונים ל-API רק בסוף המשחק)
        if now_il.hour >= 18 and f"final_{today_str}" not in tasks:
            try:
                r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers_api, timeout=15).json()
                if r_last.get('events'):
                    last_ev = r_last['events'][0]
                    if (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                        if last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                            is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                            my, opp_s = (last_ev['homeScore']['display'], last_ev['awayScore']['display']) if is_h else (last_ev['awayScore']['display'], last_ev['homeScore']['display'])
                            if my > opp_s: res_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות נגד {opp_heb} (תוצאה: {my}-{opp_s})\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
                            elif my == opp_s: res_txt = f"תיקו {my}-{opp_s} בסיום המשחק. ממשיכים הלאה. יאללה הפועלללל 💙"
                            else: res_txt = f"הפסד {my}-{opp_s} בסיום המשחק. מרימים את הראש וממשיכים הלאה. יאללה הפועל מלחמה 💙"
                            if send_telegram(res_txt, payload={"text": res_txt, "reply_markup": {"inline_keyboard": [[{"text": "📊 לטבלת הליגה (ONE)", "url": ONE_TABLE_URL}]]}}):
                                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}\n")
                                if f"mvp_{today_str}" not in tasks:
                                    send_telegram(None, "sendPoll", {"question": "מי ה-MVP לדעתך?", "options": DEFAULT_PLAYERS[:10], "is_anonymous": False})
                                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"mvp_{today_str}\n")
            except Exception as e: print(f"DEBUG MATCH LIVE ERROR: {e}", flush=True)

    # 4. סריקת כתבות RSS
    processed_count = 0
    print("DEBUG: מתחיל סריקה...", flush=True)
    for feed_url in RSS_FEEDS:
        if processed_count >= 5: break
        print(f"DEBUG: סורק פיד: {feed_url}", flush=True)
        try:
            resp = requests.get(feed_url, headers=RSS_HEADERS, timeout=20)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:45]:
                if processed_count >= 5: break
                pub_parsed = entry.get('published_parsed')
                if pub_parsed and (now_il - datetime(*pub_parsed[:6])) > timedelta(days=7): continue

                content, image, final_link = extract_article_data(raw_link := entry.link.replace("https://svcamz.", "https://www."))
                clean_link = final_link.split('?')[0] if "sport5" not in final_link and "hapoelpt" not in final_link else final_link
                
                if "google" in feed_url:
                    if not any(s in clean_link for s in ["sport5.co.il", "sport1.maariv.co.il", "sport1.co.il", "maariv.co.il"]): continue

                if clean_link in history: continue
                if not content: content = entry.title
                is_official = "hapoelpt.com" in clean_link

                if is_official or any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    p = f"תקצר ב-3 משפטים עיתונאיים חדים. חוקים: 1. התחל ישר במידע. 2. תמיד תזכיר את 'הפועל'. 3. אם הכתבה ברובה על קבוצה אחרת, החזר 'SKIP'.\n\n{content[:2500]}"
                    summary = get_ai_response(p)
                    if (not summary or "SKIP" in summary.upper()) and any(k.lower() in entry.title.lower() for k in HAPOEL_KEYS) and not is_official:
                         summary = entry.title if "SKIP" not in (summary or "").upper() else "SKIP"

                    if summary and "SKIP" not in summary.upper() and len(summary) > 10:
                        dup_p = f"האם הידיעה הזו מדווחת על אותו נושא בדיוק כמו באלו? ענה YES או NO.\nקודמים: {recent_sums[-800:]}\nחדש: {entry.title}"
                        if is_official or "YES" not in (get_ai_response(dup_p) or "NO").upper():
                            full_msg = f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({clean_link})"
                            if (send_telegram(None, "sendPhoto", {"photo": image, "caption": full_msg}) if image else send_telegram(full_msg)):
                                history.add(clean_link)
                                with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(clean_link + "\n")
                                with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "|||")
                                processed_count += 1
                                time.sleep(10)
        except Exception as e: print(f"DEBUG RSS ERROR: {e}", flush=True)

    print(f"--- סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ---", flush=True)

if __name__ == "__main__": main()
