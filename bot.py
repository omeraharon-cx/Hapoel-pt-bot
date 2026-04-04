import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta
import calendar

# הגדרה להדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני המועדון ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/leagueboard.aspx?FolderID=44"
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# רשימת הפידים המלאה
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
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה",
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Tel Aviv": "הפועל תל אביב"
}

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ש*אה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם! 💙"
]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_to_telegram(text, photo_url=None, is_poll=False, poll_data=None, reply_markup=None):
    subs = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r") as f:
            subs = list(set([line.strip() for line in f if line.strip()]))
    
    success = False
    for cid in subs:
        try:
            payload = {"chat_id": cid, "parse_mode": "Markdown"}
            if is_poll:
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={**payload, **poll_data}, timeout=10)
            elif photo_url:
                payload.update({"photo": photo_url, "caption": text, "reply_markup": reply_markup})
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json=payload, timeout=15)
                if r.status_code != 200:
                    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
            else:
                payload.update({"text": text, "reply_markup": reply_markup})
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
            if r.status_code == 200: success = True
        except: pass
    return success

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2']) if len(t.get_text()) > 20])
    except: return ""

def get_ai_summary(url, title, recent_summaries):
    if not GEMINI_API_KEY: return None
    article_text = get_full_article_text(url)
    context = "\n".join(recent_summaries)
    
    prompt = (
        f"אתה עיתונאי ספורט עבור אוהדי הפועל פתח תקווה. "
        f"1. בדוק אם הכתבה עוסקת בעיקר בהפועל פתח תקווה. "
        f"2. בדוק אם המידע כאן כבר מופיע בעדכונים האחרונים: {context}. "
        f"אם זה כפול או לא רלוונטי, החזר רק את המילה: SKIP\n"
        f"3. אחרת, כתוב תקציר של בדיוק 4-5 משפטים. טון ענייני בגובה העיניים, לא רשמי מדי. "
        f"התמקד רק בחלק שקשור להפועל פתח תקווה ובאיך זה משפיע עליה. "
        f"\nטקסט הכתבה: {article_text[:3500]}"
    )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(api_url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        if res.status_code == 200:
            result = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            return result
    except: pass
    return None

def get_match_data():
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
    print(f"--- תחילת ריצה הרמטית: {now.strftime('%H:%M:%S')} ---")

    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks = set(f.read().splitlines())
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-15:]

    # 1. יום משחק
    match = get_match_data()
    if match:
        if now.hour >= 8 and f"matchday_stable_final_v1_{today_str}" not in tasks:
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            send_to_telegram(msg, photo_url=HAPOEL_LOGO_URL)
            with open(task_file, 'a') as f: f.write(f"matchday_stable_final_v1_{today_str}\n")

        if now.hour >= 15 and f"betting_stable_final_v1_{today_str}" not in tasks:
            poll = {"question": f"איך יסתיים המשחק מול {match['opp']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
            if send_to_telegram("", is_poll=True, poll_data=poll):
                with open(task_file, 'a') as f: f.write(f"betting_stable_final_v1_{today_str}\n")

        if match['status'] in ['finished', 'FT'] and f"final_stable_final_v1_{today_str}" not in tasks:
            if match['my_score'] > match['opp_score']:
                txt = f"{random.choice(WIN_CHANTS)}\n\nניצחון ענק! התוצאה הסופית: {match['my_score']}-{match['opp_score']} להפועל! 💙"
            elif match['my_score'] == match['opp_score']:
                txt = f"תיקו בסיום המשחק של הפועל. ⚽\nהתוצאה: {match['my_score']}-{match['opp_score']}.\n\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
            else:
                txt = f"סיום המשחק. התוצאה: {match['opp_score']}-{match['my_score']} ליריבה. מרימים את הראש!\n\nיאללה הפועל מלחמה! 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
            if send_to_telegram(txt, reply_markup=markup):
                with open(task_file, 'a') as f: f.write(f"final_stable_final_v1_{today_str}\n")

    # 2. RSS (כתבות)
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    for feed_url in RSS_FEEDS:
        print(f"📡 בודק: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            if entry.link not in history:
                if any(k in entry.title.lower() for k in hapoel_keys) or "hapoelpt.com" in entry.link:
                    summary = get_ai_summary(entry.link, entry.title, recent)
                    
                    # סנן כפילויות קשיח
                    if not summary or "SKIP" in summary.upper():
                        print(f"⏭️ מדלג על כפילות/לא רלוונטי: {entry.title}")
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        continue

                    msg = f"💙 **עדכון חדש**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                    if send_to_telegram(msg):
                        with open(db_file, 'a') as f: f.write(entry.link + "\n")
                        with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                        history.add(entry.link)
                        recent.append(summary)
                        time.sleep(5)

    print("🏁 סיום ריצה.")

if __name__ == "__main__": main()
