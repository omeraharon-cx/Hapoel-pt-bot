import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
import html
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
LEAGUE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264423"
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "מבנה"]

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש-אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def escape_html(text):
    if not text: return ""
    return html.escape(text)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    try:
        payload = {"chat_id": ADMIN_ID, "parse_mode": "HTML"}
        if is_poll:
            poll_data["options"] = [str(opt)[:100] for opt in poll_data["options"]]
            r = requests.post(f"{url_base}/sendPoll", json={**payload, **poll_data}, timeout=10)
        elif photo_url:
            payload.update({"photo": photo_url, "caption": text, "reply_markup": reply_markup})
            r = requests.post(f"{url_base}/sendPhoto", json=payload, timeout=15)
            if r.status_code != 200:
                r = requests.post(f"{url_base}/sendMessage", json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup})
        else:
            payload.update({"text": text, "reply_markup": reply_markup})
            r = requests.post(f"{url_base}/sendMessage", json=payload, timeout=10)
        
        print(f"DEBUG: Telegram Status {r.status_code}")
        if r.status_code != 200:
            print(f"DEBUG ERROR DETAILS: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=12)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2']) if len(t.get_text()) > 20])
    except: return ""

def get_ai_summary(text, title, recent_summaries):
    if not GEMINI_API_KEY: return None
    context = "\n".join(recent_summaries)
    prompt = (
        f"אתה עיתונאי ספורט מומחה עבור אוהדי הפועל פתח תקווה. "
        f"משימה: כתוב תקציר של בדיוק 4 עד 5 משפטים על הכתבה. "
        f"טון: ענייני, בגובה העיניים, לא רשמי מדי. התמקד רק במידע שרלוונטי להפועל פתח תקווה. "
        f"וודא שהמידע לא כפול מהעדכונים האחרונים האלו: {context}. "
        f"אם זה כפול או לא רלוונטי, החזר רק את המילה: SKIP\n"
        f"טקסט הכתבה: {text[:3500]}"
    )
    try:
        # עדכון לגרסה v1 שפותר את שגיאת ה-404
        api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return result if "SKIP" not in result.upper() else None
        else:
            print(f"DEBUG: Gemini API Error {res.status_code}: {res.text}")
    except Exception as e: 
        print(f"DEBUG: Gemini Exception: {e}")
    return None

def get_match_data():
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    now_il = get_israel_time()
    # בודקים משחקים של היום ושל אתמול (חשוב למעברי חצות)
    dates_to_check = [now_il.strftime('%Y-%m-%d'), (now_il - timedelta(days=1)).strftime('%Y-%m-%d')]
    
    for endpoint in ["next", "last"]:
        try:
            url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/{endpoint}/0"
            res = requests.get(url, headers=headers, timeout=10).json()
            for event in res.get('events', []):
                dt = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
                if dt in dates_to_check:
                    is_home = str(event['homeTeam']['id']) == TEAM_ID
                    opp_raw = event['awayTeam']['name'] if is_home else event['homeTeam']['name']
                    return {
                        "id": event['id'], "opp": TEAM_TRANSLATIONS.get(opp_raw, opp_raw),
                        "status": event.get('status', {}).get('type'),
                        "date": dt,
                        "my_score": event.get('homeScore', {}).get('display', 0) if is_home else event.get('awayScore', {}).get('display', 0),
                        "opp_score": event.get('awayScore', {}).get('display', 0) if is_home else event.get('homeScore', {}).get('display', 0)
                    }
        except: continue
    return None

def get_mvp_players(event_id):
    url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        players = [p['player']['name'] for p in res.get(side, {}).get('lineup', [])]
        if not players: raise Exception("No players found")
        return players[:10]
    except: return ["עומר כץ", "רם לוי", "מתן גושה", "דרור ניר", "רועי דוד", "גולן בני", "אביב סלם", "עידן ורד"]

def main():
    now = get_israel_time()
    print(f"--- ריצה: {now.strftime('%H:%M:%S')} ---")

    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(line.strip() for line in f if line.strip())
    with open(db_file, 'r') as f: history = set(line.strip() for line in f if line.strip())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-15:]

    match = get_match_data()
    if match:
        m_date = match['date']
        
        # פוסטר (רק ביום המשחק עצמו)
        if now.strftime('%Y-%m-%d') == m_date:
            if now.hour >= 8 and f"matchday_{m_date}" not in tasks:
                msg = f"<b>MATCH DAY!</b> 💙\n\nהפועל שלנו מול {escape_html(match['opp'])}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
                if send_to_telegram(msg, photo_url=HAPOEL_LOGO_URL):
                    with open(task_file, 'a') as f: f.write(f"matchday_{m_date}\n")
            
            if now.hour >= 15 and f"betting_{m_date}" not in tasks:
                poll = {"question": f"הימור שלכם מול {match['opp']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
                if send_to_telegram("", is_poll=True, poll_data=poll):
                    with open(task_file, 'a') as f: f.write(f"betting_{m_date}\n")

        # סיום משחק וסקר MVP (עובד גם אם עברנו את חצות)
        if match['status'] in ['finished', 'FT']:
            if f"final_msg_{m_date}" not in tasks:
                if match['my_score'] > match['opp_score']:
                    txt = f"{random.choice(WIN_CHANTS)}\n\n<b>ניצחון ענק!</b> {match['my_score']}-{match['opp_score']} להפועל! 💙"
                elif match['my_score'] == match['opp_score']:
                    txt = f"תיקו בסיום המשחק. ⚽\nהתוצאה: {match['my_score']}-{match['opp_score']}.\n\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
                else:
                    txt = f"סיום המשחק. התוצאה: {match['opp_score']}-{match['my_score']} ליריבה. מרימים את הראש! יאללה הפועל מלחמה! 💙"
                
                markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
                if send_to_telegram(txt, reply_markup=markup):
                    # שומרים גם את השעה של שליחת הודעת הסיום
                    with open(task_file, 'a') as f: f.write(f"final_msg_{m_date}:{now.strftime('%H:%M')}\n")

            # בדיקת שליחת סקר MVP
            final_task_line = [t for t in tasks if t.startswith(f"final_msg_{m_date}:")]
            if final_task_line and f"mvp_poll_{m_date}" not in tasks:
                # מחלצים את השעה שבה נשלחה הודעת הסיום
                try:
                    time_str = final_task_line[0].split(":")[-2:]
                    # יוצרים אובייקט זמן של הודעת הסיום (יכול להיות מאתמול)
                    f_hour, f_min = int(time_str[0]), int(time_str[1])
                    # בדיקה פשוטה: אם עברו 10 דקות מאז הודעת הסיום
                    # (לצורך הפשטות, אם השעה הנוכחית שונה משעת הסיום או שעברו 10 דקות באותה שעה)
                    if (now.hour != f_hour) or (now.minute >= f_min + 10):
                        print("🎯 שולח סקר MVP...")
                        players = get_mvp_players(match['id'])
                        poll = {"question": "מי המצטיין שלכם הערב? ⚽️", "options": players, "is_anonymous": False}
                        if send_to_telegram("", is_poll=True, poll_data=poll):
                            with open(task_file, 'a') as f: f.write(f"mvp_poll_{m_date}\n")
                except: pass

    # 2. סריקת כתבות
    print("📡 מתחיל סריקת עומק לכתבות...")
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            if entry.link in history: continue
            
            full_text = get_full_article_text(entry.link)
            combined_text = (entry.title + " " + full_text).lower()
            
            if any(k in combined_text for k in HAPOEL_KEYS):
                print(f"🎯 נמצא אזכור בכתבה: {entry.title}")
                summary = get_ai_summary(full_text, entry.title, recent)
                if summary:
                    msg = f"💙 <b>עדכון חדש</b>\n\n{escape_html(summary)}\n\n🔗 <a href='{entry.link}'>לכתבה המלאה</a>"
                    if send_to_telegram(msg):
                        with open("seen_links.txt", "a") as f: f.write(entry.link + "\n")
                        with open("recent_summaries.txt", "a", encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                        history.add(entry.link)
                        time.sleep(5)
                else:
                    print(f"DEBUG: Summary for '{entry.title}' was skipped (AI decided SKIP or Error)")

    print("--- סיום ריצה מוצלח ---")

if __name__ == "__main__": main()
