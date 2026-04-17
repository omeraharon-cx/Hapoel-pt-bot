import feedparser
import requests
import os
import time
import sys
import random
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlunparse

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
# False = הודעות מגיעות רק אליך (אדמין) לצרכי בדיקה
# True = הודעות נשלחות לכל מי שרשום בקובץ subscribers.txt
BROADCAST_MODE = False 

# --- סגל שחקנים (מעודכן לפי 365Scores - כולל ירין לוי, גולאני וגושה) ---
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "נועם כהן", "בוני", "דיארה"]

PLAYER_MAP = { 
    "Omer Katz": "עומר כץ", 
    "Orel Dgani": "אוראל דגני", 
    "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", 
    "Roee David": "רועי דוד", 
    "Itay Rotman": "איתי רוטמן", 
    "Alex Moussounda": "מוסונדה", 
    "Mark Costa": "קוסטה", 
    "Shavit Mazal": "שביט מזל", 
    "Andrade Euclides Claye": "קליי", 
    "Chipuoka Songa": "סונגה", 
    "Tomer Altman": "אלטמן", 
    "Dror Nir": "דרור ניר", 
    "Shahar Rosen": "שחר רוזן", 
    "Idan Cohen": "עידן כהן",
    "Noam Cohen": "נועם כהן", 
    "Boni Amanis": "בוני", 
    "Fortune Diarra": "דיארה",
    "Matan Gosha": "מתן גושה", 
    "Yarin Levi": "ירין לוי", 
    "Daniel Joulani": "דניאל גולאני"
}

# --- מאגר פוסטרים (6 פוסטרים שונים לרוטציה) ---
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# --- שירי ניצחון להודעות סיום משחק ---
WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# --- לוח משחקים ידני מלא (עד סוף העונה - גיבוי ל-API) ---
BACKUP_SCHEDULE = {
    "2026-04-18": "הפועל באר שבע",
    "2026-04-22": "הפועל תל אביב",
    "2026-04-25": "בית\"ר ירושלים",
    "2026-05-02": "מכבי חיפה",
    "2026-05-05": "מכבי תל אביב",
    "2026-05-09": "הפועל באר שבע",
    "2026-05-13": "הפועל תל אביב",
    "2026-05-16": "מכבי חיפה",
    "2026-05-20": "בית\"ר ירושלים",
    "2026-05-23": "מכבי תל אביב"
}

# --- תרגום שמות קבוצות מלעז לעברית ---
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", 
    "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", 
    "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Bnei Reineh": "מכבי בני ריינה", 
    "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", 
    "M.S. Ashdod": "מ.ס. אשדוד", 
    "Hapoel Tel Aviv": "הפועל תל אביב", 
    "Hapoel Haifa": "הפועל חיפה", 
    "Maccabi Netanya": "מכבי נתניה", 
    "Hapoel Jerusalem": "הפועל ירושלים",
    "Ironi Kiryat Shmona": "עירוני קרית שמונה", 
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

# --- הגדרות סריקה וחיפוש ---
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
    """מחזיר את הזמן הנוכחי בישראל"""
    return datetime.utcnow() + timedelta(hours=3)

def clean_url(url):
    """מנקה פרמטרים מיותרים מלינקים (כמו fbclid) תוך שמירה על מזהי כתבה קריטיים (docID)"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        new_params = {}
        
        # שמירה על פרמטרים קריטיים לאתרים ספציפיים כדי למנוע כפילויות שגויות
        if "sport5.co.il" in url:
            if "docID" in params: 
                new_params["docID"] = params["docID"]
            if "FolderID" in params: 
                new_params["FolderID"] = params["FolderID"]
        elif "sport1.maariv.co.il" in url or "sport1.co.il" in url:
            # בספורט 1 המזהה נמצא בתוך נתיב הלינק, לכן נחזיר את הקישור ללא פרמטרים בכלל
            return url.split('?')[0]
        elif "hapoelpt.com" in url:
            return url # לא נוגעים בלינקים של האתר הרשמי
            
        if not new_params:
            return url.split('?')[0]
            
        new_query = "&".join([f"{k}={v[0]}" for k, v in new_params.items()])
        return urlunparse(parsed._replace(query=new_query))
    except:
        return url.split('?')[0]

def send_telegram(text, method="sendMessage", payload=None):
    """שולח הודעה לטלגרם - תומך בשידור לכל המנויים או רק לאדמין"""
    recipients = [ADMIN_ID]
    if BROADCAST_MODE and os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r", encoding='utf-8') as f:
            recipients.extend([line.strip() for line in f if line.strip()])
    
    recipients = list(set(recipients)) # הסרת כפילויות
    
    overall_status = True
    for chat_id in recipients:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
        curr_payload = payload.copy() if payload else {}
        curr_payload["chat_id"] = chat_id
        
        if method in ["sendMessage", "sendPhoto"]:
            curr_payload["parse_mode"] = "Markdown"
        if "text" not in current_payload and text:
            current_payload["text"] = text
            
        try:
            r = requests.post(url, json=curr_payload, timeout=25)
            if r.status_code != 200: 
                overall_status = False
        except:
            overall_status = False
            
    return overall_status

def get_ai_response(prompt):
    """פונה ל-Gemini API לקבלת טקסט מעובד"""
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: 
        return None

def extract_article_data(url):
    """מחלץ תוכן טקסטואלי ותמונה מכתבה"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(resp.content, 'html.parser')
        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image: 
            image = og_image["content"]
        
        # סינון תמונות לוגו של גוגל
        if image and ("googleusercontent" in image or "google.com/logos" in image): 
            image = None
            
        # זיהוי גוף הכתבה באתרים השונים
        container = (soup.find('div', class_='article-body') or 
                     soup.find('div', class_='article-content') or 
                     soup.find('article') or 
                     soup.find('div', id='article-content') or 
                     soup.find('div', class_='content'))
                     
        if container:
            content = " ".join([el.get_text() for el in container.find_all(['p', 'h1', 'h2', 'h3'])])
        else:
            content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
        return content, image, resp.url
    except: 
        return "", None, url

# --- לוגיקה מרכזית ---
def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    current_week = now_il.strftime('%Y-%U')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---", flush=True)

    # וידוא קבצי מערכת
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt", "schedule.json"]:
        if not os.path.exists(f): 
            open(f, 'a', encoding='utf-8').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = f.read()
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    # 1. פינת ההיסטוריה (יום רביעי בשעה 12:00)
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        fact_prompt = "כתוב 2 עובדות היסטוריות קצרות ומעניינות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. הוסף אימוג'ים מתאימים."
        fact = get_ai_response(fact_prompt)
        if fact and send_telegram(f"📜 *פינת ההיסטוריה הכחולה:* \n\n{fact}"):
            with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"history_{today_str}\n")

    # 2. ניהול לוח משחקים (עדכון שבועי מה-API לחיסכון במכסה)
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    local_schedule = {}
    try:
        if os.path.exists("schedule.json") and os.path.getsize("schedule.json") > 0:
            with open("schedule.json", 'r', encoding='utf-8') as f: 
                local_schedule = json.load(f)

        if f"sched_update_{current_week}" not in tasks or not local_schedule:
            print("DEBUG: מעדכן לוח משחקים שבועי מה-API...", flush=True)
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
                print("DEBUG: הלוח התעדכן בהצלחה.", flush=True)
            else:
                print("DEBUG: ה-API חסום, משתמש בלוח גיבוי ידני.", flush=True)
                local_schedule.update(BACKUP_SCHEDULE)
    except: 
        local_schedule.update(BACKUP_SCHEDULE)

    # 3. ניהול יום משחק (פוסטר בבוקר, הימורים בצהריים, תוצאה בערב)
    if today_str in local_schedule:
        opp_heb = local_schedule[today_str]
        print(f"DEBUG: היום יש משחק נגד {opp_heb}!", flush=True)

        # הודעת בוקר - MatchDay
        if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
            md_text = (f"MatchDay Hapoel 💙\nהפועל שלנו תעלה היום נגד *{opp_heb}*.\n"
                       f"יאללה הפועל, לתת הכל בשביל הסמל! 🚀\n\n"
                       f"כשחקנים למגרש עולים - כל האוהדים שריםםםם\n"
                       f"הפועל עולה עולההה, הפועל, הפועל עולהה 💙")
            if send_telegram(None, "sendPhoto", {"photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")

        # סקר הימורים
        if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
            poll_payload = {"question": "זמן להמר, מי תנצח היום?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד 💔"], "is_anonymous": False}
            if send_telegram(None, "sendPoll", poll_payload):
                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"betting_{today_str}\n")

        # סיום משחק וסקר MVP (פונים ל-API רק מהשעה 18:00)
        if now_il.hour >= 18 and f"final_{today_str}" not in tasks:
            try:
                r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers_api, timeout=15).json()
                if r_last.get('events'):
                    last_ev = r_last['events'][0]
                    if (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d') == today_str:
                        if last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                            is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                            my, opp_s = (last_ev['homeScore']['display'], last_ev['awayScore']['display']) if is_h else (last_ev['awayScore']['display'], last_ev['homeScore']['display'])
                            
                            if my > opp_s: 
                                res_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון! הפועל 3 נקודות נגד {opp_heb}!* ({my}-{opp_s})"
                            elif my == opp_s: 
                                res_txt = f"תיקו {my}-{opp_s} נגד {opp_heb}. ממשיכים הלאה. יאללה הפועל 💙"
                            else: 
                                res_txt = f"הפסד {my}-{opp_s} נגד {opp_heb}. מרימים את הראש. יאללה הפועל מלחמה 💙"
                                
                            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה (ONE)", "url": ONE_TABLE_URL}]]}
                            if send_telegram(res_txt, payload={"text": res_txt, "reply_markup": markup}):
                                with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}\n")
                                
                                # שליחת סקר MVP
                                if f"mvp_{today_str}" not in tasks:
                                    mvp_payload = {"question": "מי היה ה-MVP של המשחק לדעתך?", "options": DEFAULT_PLAYERS[:10], "is_anonymous": False}
                                    send_telegram(None, "sendPoll", mvp_payload)
                                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"mvp_{today_str}\n")
            except: 
                pass

    # 4. סריקת כתבות RSS (עד 5 כתבות חדשות לריצה)
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
                
                # בדיקת טריות (עד 7 ימים אחורה)
                pub_parsed = entry.get('published_parsed')
                if pub_parsed and (now_il - datetime(*pub_parsed[:6])) > timedelta(days=7): 
                    continue

                content, image, final_link = extract_article_data(raw_link := entry.link.replace("https://svcamz.", "https://www."))
                
                # ניקוי הלינק תוך שמירה על docID לספורט 5 וספורט 1
                clean_l = clean_url(final_link)
                
                # סינון גוגל ניוז: מאשרים רק ספורט 5 וספורט 1 (השאר יגיעו מהפידים הישירים)
                if "google" in feed_url:
                    if not any(s in clean_l for s in ["sport5.co.il", "sport1.maariv.co.il", "sport1.co.il"]):
                        continue

                if clean_l in history: 
                    continue
                    
                if not content: 
                    content = entry.title
                is_off = "hapoelpt.com" in clean_l

                if is_off or any(k.lower() in (entry.title + content).lower() for k in HAPOEL_KEYS):
                    if is_off:
                        p_prompt = f"סכם את הודעת המועדון ב-3 משפטים ענייניים. התחל ישר במידע.\n\nטקסט: {content[:3000]}"
                    else:
                        # שיפור הטון העיתונאי והדרישה ל-3-4 משפטים חובה
                        p_prompt = ("כתוב תקציר עיתונאי של 3-4 משפטים על הפועל פתח תקווה. הטון צריך להיות מעניין, מקצועי וחד. "
                                    "חובה להזכיר את המילה 'הפועל' בתקציר. אל תחזיר SKIP אם מדובר בכתבה על הפועל פ\"ת.\n\n"
                                    f"טקסט: {content[:2500]}")
                    
                    summary = get_ai_response(p_prompt)
                    
                    # פילטר סופי לוודא שהתקציר איכותי ומדויק
                    if summary and "SKIP" not in summary.upper() and len(summary) > 20:
                        dup_check_prompt = f"האם הידיעה הזו מדווחת על אותו נושא בדיוק כמו באלו? ענה YES או NO.\nקודמים: {recent_sums[-800:]}\nחדש: {entry.title}"
                        if is_off or "YES" not in (get_ai_response(dup_check_prompt) or "NO").upper():
                            full_msg = f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({clean_l})"
                            if (send_telegram(None, "sendPhoto", {"photo": image, "caption": full_msg}) if image else send_telegram(full_msg)):
                                history.add(clean_l)
                                with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(clean_l + "\n")
                                with open("recent_summaries.txt", 'a', encoding='utf-8') as f: f.write(summary + "|||")
                                processed_count += 1
                                print(f"DEBUG: נשלח בהצלחה: {entry.title}", flush=True)
                                time.sleep(10)
        except Exception as e: 
            print(f"DEBUG RSS ERROR: {e}", flush=True)

    print(f"--- סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ---", flush=True)

if __name__ == "__main__": main()
