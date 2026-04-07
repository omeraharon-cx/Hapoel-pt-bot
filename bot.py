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
LEAGUE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# פוסטר יום משחק (וודא שהקישור הזה עובד בדפדפן!)
MATCHDAY_POSTER_URL = "https://i.ibb.co/vz7fDkF/tifo-samurai.jpg" 

# --- בנק היסטוריה מורחב (שולח 2 בשבוע) ---
HISTORICAL_EVENTS = [
    "ב-1955 הפועל פ\"ת זכתה באליפות הראשונה בתולדותיה, תחת הדרכת המאמן איגנץ מולנר. 🏆",
    "נחום סטלמך כבש את השער המפורסם מול ברית המועצות ב-1956 בנגיחה שהפכה למיתוס. ⚽",
    "הפועל פ\"ת היא הקבוצה היחידה בישראל שזכתה ב-5 אליפויות רצופות (1959-1963). 💙",
    "הזכייה האחרונה בגביע המדינה הייתה ב-1992, עם ניצחון 1:3 על מכבי תל אביב בגמר. 🏆",
    "אצטדיון 'האורווה' המיתולוגי נחנך ב-1967 והיה מבצרה של הקבוצה במשך עשורים. 🏟️",
    "בועז קופמן הוא מלך השערים של הקבוצה בכל הזמנים עם 121 שערי ליגה. ⚽",
    "בשנת 1961 הפועל פ\"ת ניצחה את נבחרת סיירה לאון 1:3 במשחק ידידות היסטורי. 🌍",
    "זכריה רדלר, מגדולי הבלמים של המועדון, רשם 219 הופעות במדים הכחולים. 🛡️",
    "בעונת 1954/55 הקבוצה סיימה את הליגה ללא הפסד ביתי אחד. 🏠",
    "ג'רי חלדי, קפטן הקבוצה בשנות ה-50, היה המנהיג של תור הזהב הכחול. 💙",
    "הפועל פ\"ת הייתה הקבוצה הישראלית הראשונה שהופיעה בבול רשמי של דואר ישראל. 📮",
    "בשנת 1991 הקבוצה הגיעה לרבע גמר גביע המחזיקות האירופי. 🇪🇺",
    "הדרבי הראשון של פתח תקווה שוחק ב-1941, והסתיים בניצחון כחול 0:1. 🔵",
    "יצחק ויסוקר, מהשוערים הגדולים בישראל, גדל והצטיין בהפועל פ\"ת במשך 11 עונות. 🧤",
    "מני בסון ז\"ל כבש צמד בגמר הגביע של 1992 והפך לגיבור הניצחון. ⚽",
    "הקבוצה הוקמה בשנת 1934 על ידי פועלי המושבה פתח תקווה. 🛠️",
    "ניר לוין הוביל את הקבוצה כמאמן לזכייה בגביע הטוטו בשנת 2005. 🏆"
]

TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Bnei Reineh": "מכבי בני ריינה", "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", "M.S. Ashdod": "מ.ס. אשדוד"
}

def send_telegram(text, method="sendMessage", payload=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=20)
        return r.status_code == 200
    except: return False

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- {now_il.strftime('%H:%M:%S')} ריצה ---")
    
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)

    # --- 1. הודעת היסטוריה (יום רביעי, 2 עובדות) ---
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        events = random.sample(HISTORICAL_EVENTS, 2)
        msg = "📜 *פינת ההיסטוריה הכחולה:*\n\n" + "\n".join([f"🔹 {e}" for e in events])
        if send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"}):
            with open("task_log.txt", 'a') as f: f.write(f"history_{today_str}\n")

    # --- 2. יום משחק (Matchday) ---
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            
            if ev_date == today_str and f"matchday_{today_str}" not in tasks:
                is_home = str(next_ev['homeTeam']['id']) == TEAM_ID
                opp = next_ev['awayTeam']['name'] if is_home else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                msg = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
                
                # ניסיון שליחה עם תמונה, אם נכשל - שולח טקסט בלבד
                photo_payload = {"chat_id": ADMIN_ID, "photo": MATCHDAY_POSTER_URL, "caption": msg, "parse_mode": "Markdown"}
                if not send_telegram(msg, method="sendPhoto", payload=photo_payload):
                    send_telegram(msg, payload={"chat_id": ADMIN_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open("task_log.txt", 'a') as f: f.write(f"matchday_{today_str}\n")
    except: pass

    # (שאר הלוגיקה של הכתבות והסיום נשארת כפי שהייתה...)

if __name__ == "__main__":
    main()
