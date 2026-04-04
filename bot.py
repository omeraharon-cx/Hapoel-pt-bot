import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta

# הגדרה להדפסה מיידית ללוגים בעברית
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני המועדון ---
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

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש*אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    print(f"DEBUG: שולח הודעה לטלגרם... (is_poll={is_poll})")
    try:
        payload = {"chat_id": ADMIN_ID, "parse_mode": "Markdown"}
        if is_poll:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={**payload, **poll_data}, timeout=10)
        elif photo_url:
            payload.update({"photo": photo_url, "caption": text, "reply_markup": reply_markup})
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json=payload, timeout=15)
            if r.status_code != 200:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
        else:
            payload.update({"text": text, "reply_markup": reply_markup})
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
        print(f"DEBUG: Telegram status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"DEBUG ERROR Telegram: {e}")
        return False

def get_full_article_text(url):
    print(f"DEBUG: שולף טקסט מלא מהכתבה: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2']) if len(t.get_text()) > 20])
    except Exception as e:
        print(f"DEBUG ERROR Scraping: {e}")
        return ""

def get_ai_summary(url, title, recent_summaries):
    if not GEMINI_API_KEY: return None
    print(f"DEBUG: מבקש מה-AI לסכם את: {title}")
    article_text = get_full_article_text(url)
    context = "\n".join(recent_summaries)
    
    prompt = (
        f"אתה עיתונאי ספורט עבור אוהדי הפועל פתח תקווה. "
        f"משימה: כתוב תקציר של בדיוק 4 עד 5 משפטים על הכתבה. "
        f"טון: ענייני, בגובה העיניים, לא רשמי מדי. התמקד רק במידע שרלוונטי להפועל פתח תקווה. "
        f"וודא שזה לא כפול מהתקצירים הבאים: {context}. "
        f"אם זה כפול או לא רלוונטי להפועל פתח תקווה, החזר רק את המילה: SKIP\n"
        f"טקסט: {article_text[:3500]}"
    )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            print(f"DEBUG: AI response: {result[:50]}...")
            return result if "SKIP" not in result.upper() else None
        else:
            print(f"DEBUG AI ERROR: {res.status_code}")
    except Exception as e:
        print(f"DEBUG ERROR AI: {e}")
    return None

def get_match_data():
    print("DEBUG: מושך נתוני משחקים מה-API...")
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    today = get_israel_time().strftime('%Y-%m-%d')
    for endpoint in ["next", "last"]:
        try:
            url = f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/{endpoint}/0"
            res = requests.get(url, headers=headers, timeout=10).json()
            for event in res.get('events', []):
                dt = datetime.fromtimestamp(event['startTimestamp']).strftime('%Y-%m-%d')
                if dt == today:
                    is_home = str(event['homeTeam']['id']) == TEAM_ID
                    opp_raw = event['awayTeam']['name'] if is_home else event['homeTeam']['name']
                    print(f"DEBUG: נמצא משחק להיום נגד {opp_raw}")
                    return {
                        "id": event['id'], "opp": TEAM_TRANSLATIONS.get(opp_raw, opp_raw),
                        "status": event.get('status', {}).get('type'),
                        "my_score": event.get('homeScore', {}).get('display', 0) if is_home else event.get('awayScore', {}).get('display', 0),
                        "opp_score": event.get('awayScore', {}).get('display', 0) if is_home else event.get('homeScore', {}).get('display', 0)
                    }
        except: continue
    return None

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה: {now.strftime('%H:%M:%S')} ---")

    # ניהול קבצים
    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(f.read().splitlines())
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-15:]

    print(f"DEBUG: {len(tasks)} משימות ביומן, {len(history)} לינקים בהיסטוריה.")

    # 1. בדיקת רביעי היסטורי
    if now.weekday() == 2 and 10 <= now.hour <= 12:
        if f"hist_{today_str}" not in tasks:
            print("DEBUG: מפעיל 'רביעי היסטורי'...")
            prompt = "ספר לאוהדי הפועל פתח תקווה על אירוע היסטורי מהעבר של המועדון. כתוב ב-4 משפטים, טון חברי ומרגש."
            txt = get_ai_response(prompt)
            if txt and send_to_telegram(f"📜 **רביעי היסטורי**\n\n{txt}"):
                with open(task_file, 'a') as f: f.write(f"hist_{today_str}\n")

    # 2. ניהול משחק
    match = get_match_data()
    if match:
        # Matchday
        if now.hour >= 8 and f"matchday_{today_str}" not in tasks:
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            if send_to_telegram(msg, photo_url=HAPOEL_LOGO_URL):
                with open(task_file, 'a') as f: f.write(f"matchday_{today_str}\n")
        
        # הימורים
        if now.hour >= 15 and f"betting_{today_str}" not in tasks:
            poll = {"question": f"הימור שלכם מול {match['opp']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
            if send_to_telegram("", is_poll=True, poll_data=poll):
                with open(task_file, 'a') as f: f.write(f"betting_{today_str}\n")

        # סיום משחק
        if match['status'] in ['finished', 'FT']:
            if f"finish_msg_{today_str}" not in tasks:
                if match['my_score'] > match['opp_score']:
                    txt = f"{random.choice(WIN_CHANTS)}\n\nניצחון ענק! {match['my_score']}-{match['opp_score']} להפועל! 💙"
                elif match['my_score'] == match['opp_score']:
                    txt = f"תיקו בסיום המשחק. ⚽\nהתוצאה: {match['my_score']}-{match['opp_score']}.\n\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
                else:
                    txt = f"סיום המשחק בטרנר. התוצאה: {match['opp_score']}-{match['my_score']} ליריבה. מרימים את הראש! יאללה הפועל מלחמה! 💙"
                
                markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
                if send_to_telegram(txt, reply_markup=markup):
                    with open(task_file, 'a') as f: f.write(f"finish_msg_{today_str}:{now.strftime('%H:%M')}\n")

            # סקר MVP
            final_task = [t for t in tasks if t.startswith(f"finish_msg_{today_str}:")]
            if final_task and f"mvp_poll_{today_str}" not in tasks:
                time_parts = final_task[0].split(":")[-2:]
                finish_time = now.replace(hour=int(time_parts[0]), minute=int(time_parts[1]))
                if now >= finish_time + timedelta(minutes=10):
                    # כאן היית יכול לשלוף הרכבים, כרגע רשימה קבועה לבדיקה
                    poll = {"question": "מי המצטיין שלכם הערב? ⚽️", "options": ["עומר כץ", "רם לוי", "מתן גושה", "דרור ניר", "אחר"], "is_anonymous": False}
                    if send_to_telegram("", is_poll=True, poll_data=poll):
                        with open(task_file, 'a') as f: f.write(f"mvp_poll_{today_str}\n")

    # 3. סריקת RSS
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    for url in RSS_FEEDS:
        print(f"DEBUG: סורק פיד: {url}")
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            if entry.link not in history:
                if any(k in entry.title.lower() for k in hapoel_keys) or "hapoelpt.com" in entry.link:
                    print(f"DEBUG: נמצאה כתבה: {entry.title}")
                    summary = get_ai_summary(entry.link, entry.title, recent)
                    if summary:
                        msg = f"💙 **עדכון חדש**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                        if send_to_telegram(msg):
                            with open(db_file, 'a') as f: f.write(entry.link + "\n")
                            with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                            history.add(entry.link)
                            recent.append(summary)
                            time.sleep(5)

    print("--- סיום ריצה מוצלח. ---")

if __name__ == "__main__":
    main()
