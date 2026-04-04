import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import urllib.parse
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# --- נתוני המועדון (קבועים) ---
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/leagueboard.aspx?FolderID=44"
# כתובת CDN יציבה ללוגו המועדון (לא בינה מלאכותית)
HAPOEL_LOGO_URL = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

TEAM_TRANSLATIONS = {
    "Hapoel Be'er Sheva": "הפועל באר שבע",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Maccabi Haifa": "מכבי חיפה",
    "Beitar Jerusalem": "בית''ר ירושלים",
    "Hapoel Petah Tikva": "הפועל פתח תקווה",
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Tel Aviv": "הפועל תל אביב"
}

# רשימת השירים להגרלה בניצחון
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
                # Fallback לטקסט אם התמונה נכשלה
                if r.status_code != 200:
                    r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
            else:
                payload.update({"text": text, "reply_markup": reply_markup})
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
            if r.status_code == 200: success = True
        except: pass
    return success

def get_ai_response(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        time.sleep(2) # הגנה מ-429
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        return " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2']) if len(t.get_text()) > 20])
    except: return ""

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

def get_mvp_players(event_id):
    url = f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        side = 'home' if str(res.get('home', {}).get('team', {}).get('id')) == TEAM_ID else 'away'
        return [p['player']['name'] for p in res.get(side, {}).get('lineup', [])][:10]
    except: return ["עומר כץ", "רם לוי", "מתן גושה", "דרור ניר", "רועי דוד"]

def main():
    now = get_israel_time()
    today_str = now.strftime('%Y-%m-%d')
    print(f"--- תחילת ריצה תשתיתית סופית: {now.strftime('%H:%M:%S')} ---")

    db_file, task_file, sum_db = "seen_links.txt", "task_log.txt", "recent_summaries.txt"
    for f in [db_file, task_file, sum_db]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent = f.read().splitlines()[-10:]

    # 1. יום משחק (SportAPI7)
    match = get_match_data()
    if match:
        # פוסטר וסקר בוקר (אחרי 8:00)
        # שימוש במפתח stable_final כדי למנוע כפילויות לעד
        if now.hour >= 8 and f"matchday_stable_final_v1_{today_str}" not in tasks_done:
            msg = f"MATCH DAY! 💙\n\nהפועל שלנו מול {match['opp']}\nמביאים 3 נקודות בעזרת השם.\n\nיאללה הפועל! ⚽️"
            send_to_telegram(msg, photo_url=HAPOEL_LOGO_URL)
            with open(task_file, 'a') as f: f.write(f"matchday_stable_final_v1_{today_str}\n")

        # הימורים (אחרי 15:00)
        if now.hour >= 15 and f"betting_stable_final_v1_{today_str}" not in tasks_done:
            poll = {"question": f"איך יסתיים המשחק מול {match['opp']}?", "options": ["ניצחון 💙", "תיקו", "הפסד"], "is_anonymous": False}
            if send_to_telegram("", is_poll=True, poll_data=poll):
                with open(task_file, 'a') as f: f.write(f"betting_stable_final_v1_{today_str}\n")

        # סיום משחק (FT/finished)
        if match['status'] in ['finished', 'FT'] and f"final_stable_final_v1_{today_str}" not in tasks_done:
            if match['my_score'] > match['opp_score']:
                chant = random.choice(WIN_CHANTS)
                txt = f"{chant}\n\nניצחון ענק! התוצאה הסופית: {match['my_score']}-{match['opp_score']} להפועל! 💙"
            elif match['my_score'] == match['opp_score']:
                txt = f"תיקו בסיום המשחק של הפועל. ⚽\nהתוצאה: {match['my_score']}-{match['opp_score']}.\n\nיוצאים עם נקודה וממשיכים חזק בכל הכוח.\n\nיאללה הפועל מלחמה! 💙"
            else:
                txt = f"סיום המשחק. התוצאה: {match['opp_score']}-{match['my_score']} ליריבה. מרימים את הראש!\n\nיאללה הפועל מלחמה! 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]}
            if send_to_telegram(txt, reply_markup=markup):
                # שומרים את זמן השליחה לסקר MVP (עוד 10 דקות)
                with open(task_file, 'a') as f: f.write(f"final_msg_stable_final_v1_{today_str}:{now.strftime('%H:%M')}\n")

        # בדיקה לסקר MVP (10 דקות אחרי)
        final_msg_task = [t for t in tasks_done if t.startswith(f"final_msg_stable_final_v1_{today_str}")]
        if final_msg_task and f"mvp_poll_stable_final_v1_{today_str}" not in tasks_done:
            time_parts = final_msg_task[0].split(":")[-2:]
            send_time = now.replace(hour=int(time_parts[0]), minute=int(time_parts[1]))
            if now >= send_time + timedelta(minutes=10):
                players = get_mvp_players(match['id'])
                poll = {"question": "מי המצטיין שלכם הערב? ⚽️", "options": players, "is_anonymous": False}
                if send_to_telegram("", is_poll=True, poll_data=poll):
                    with open(task_file, 'a') as f: f.write(f"mvp_poll_stable_final_v1_{today_str}\n")

    # 2. RSS (כתבות)
    feed = feedparser.parse("https://www.hapoelpt.com/blog-feed.xml")
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    for entry in feed.entries[:5]:
        if entry.link not in history:
            if any(k in entry.title.lower() for k in hapoel_keys) or "hapoelpt.com" in entry.link:
                # קורא את כל הכתבה ושולח ל-AI
                text = get_full_article_text(entry.link)
                recent_ctx = "\n".join(recent)
                prompt = (
                    f"כתוב תקציר של בדיוק 4 עד 5 משפטים על הידיעה הבאה עבור אוהדי הפועל פתח תקווה. "
                    f"טון: חברי וענייני בגובה העיניים. אל תכתוב מילות פתיחה. התמקד רק במה שקשור להפועל פתח תקווה. "
                    f"מנע כפילויות עם: {recent_ctx}. \nטקסט הכתבה: {text[:3000]}"
                )
                summary = get_ai_response(prompt)
                display = summary if summary else entry.title
                msg = f"💙 **עדכון חדש**\n\n{display}\n\n🔗 [לכתבה המלאה]({entry.link})"
                if send_to_telegram(msg):
                    with open(db_file, 'a') as f: f.write(entry.link + "\n")
                    if summary:
                        with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
