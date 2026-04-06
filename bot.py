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

# הגדרה להדפסה מיידית ללוגים של GitHub
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
LEAGUE_TABLE_URL = "https://www.sport5.co.il/liga.aspx?FolderID=44"
FALLBACK_POSTER = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# --- תרגום קבוצות (2026) ---
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", "Beitar Jerusalem": "בית\"ר ירושלים",
    "Hapoel Haifa": "הפועל חיפה", "Hapoel Jerusalem": "הפועל ירושלים",
    "Maccabi Netanya": "מכבי נתניה", "Maccabi Bnei Reineh": "מכבי בני ריינה",
    "F.C. Ashdod": "מ.ס. אשדוד", "Hapoel Hadera": "הפועל חדרה",
    "Maccabi Petach Tikva": "מכבי פתח תקווה", "Bnei Sakhnin": "בני סכנין",
    "Hapoel Tel Aviv": "הפועל תל אביב", "Ironi Kiryat Shmona": "עירוני קרית שמונה",
    "Ironi Tiberias": "עירוני טבריה", "Maccabi Bnei Raina": "מכבי בני ריינה"
}

WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

PLAYER_MAP = {
    "Omer Katz": "עומר כץ", "Shahar Rosen": "שחר רוזן", "Dror Nir": "דרור ניר",
    "Itay Rotman": "איתי רוטמן", "Orel Dgani": "אוראל דגני", "Alex Moussounda": "מוסונדה",
    "Idan Cohen": "עידן כהן", "Noam Cohen": "נועם כהן", "Tomer Altman": "אלטמן",
    "Nadav Niddam": "נדב נידם", "Roee David": "רועי דוד", "Ari Cohen": "ארי כהן",
    "Mamadi Diarra": "דיארה", "Yonatan Cohen": "יונתן כהן", "Andrade Euclides Claye": "קליי",
    "Chipuoka Songa": "סונגה", "Mark Costa": "קוסטה", "Shavit Mazal": "שביט מזל", "Boni Amians": "בוני"
}

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, is_poll=False, poll_data=None, photo_url=None, with_table=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    payload = {"chat_id": ADMIN_ID}
    if with_table:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]})
    if photo_url:
        method, payload = "sendPhoto", {**payload, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}
    elif is_poll:
        method, payload = "sendPoll", {**payload, **poll_data}
    else:
        method, payload = "sendMessage", {**payload, "text": text, "parse_mode": "Markdown"}
    
    try:
        r = requests.post(url + method, data=payload, timeout=15)
        print(f"LOG: Telegram {method} Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR: Telegram failed: {e}")
        return False

def get_available_models():
    print("LOG: בודק מודלים זמינים בגוגל...")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=10).json()
        models = [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        print(f"LOG: נמצאו {len(models)} מודלים.")
        return models if models else ["models/gemini-1.5-flash"]
    except Exception as e:
        print(f"LOG ERROR: Models fetch failed: {e}")
        return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, title):
    if not text or len(text) < 100:
        print(f"LOG: טקסט קצר מדי לסיכום ({len(text)} תווים).")
        return None
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. אתה עיתונאי ספורט ואוהד הפועל פתח תקווה. כתוב תקציר של 3 משפטים בטון ענייני ומכובד.\n"
        "2. השתמש בכינויים 'הפועל' או 'הכחולים'. איסור חמור על המילה 'לוזונים'.\n"
        "3. אם הכתבה לא עוסקת בהפועל פתח תקווה באופן מהותי, החזר רק: SKIP\n\n"
        f"### ARTICLE: {title} ###\n{text[:2500]}"
    )
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if res.status_code == 200:
                out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                print(f"LOG AI: מודל {model} החזיר תשובה (אורך: {len(out)})")
                return out if "SKIP" not in out.upper() else "SKIP"
            print(f"LOG AI: מודל {model} נכשל עם סטטוס {res.status_code}")
        except Exception as e:
            print(f"LOG AI ERROR: {model} exception: {e}")
    return None

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    print(f"--- {now_il.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    models = get_available_models()
    
    # טעינת זיכרון
    for f in ["seen_links.txt", "task_log.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = set(line.strip() for line in f)
    print(f"LOG: נטענו {len(history)} לינקים מההיסטוריה.")

    # 1. ניהול משחקים (API)
    print("LOG: בודק נתוני משחק ב-API...")
    try:
        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
        
        # Match Day
        r_next = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/0", headers=headers, timeout=10).json()
        if r_next.get('events'):
            next_ev = r_next['events'][0]
            ev_date = (datetime.fromtimestamp(next_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            if ev_date == today_str and f"matchday_{today_str}" not in tasks:
                print("LOG: מזהה יום משחק היום!")
                opp = next_ev['awayTeam']['name'] if str(next_ev['homeTeam']['id']) == TEAM_ID else next_ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp, opp)
                msg = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
                if send_telegram(msg, photo_url=FALLBACK_POSTER):
                    with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"matchday_{today_str}\n")

        # סיום משחק
        r_last = requests.get(f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0", headers=headers, timeout=10).json()
        if r_last.get('events'):
            last_ev = r_last['events'][0]
            l_date = (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
            if l_date == today_str and last_ev.get('status', {}).get('type') in ['finished', 'FT']:
                print(f"LOG: זוהה משחק שהסתיים היום בסטטוס {last_ev['status']['type']}.")
                if f"final_{today_str}" not in tasks:
                    is_h = str(last_ev['homeTeam']['id']) == TEAM_ID
                    my, opp = (last_ev['homeScore']['display'], last_ev['awayScore']['display']) if is_h else (last_ev['awayScore']['display'], last_ev['homeScore']['display'])
                    opp_name = last_ev['awayTeam']['name'] if is_h else last_ev['homeTeam']['name']
                    opp_heb = TEAM_TRANSLATION.get(opp_name, opp_name)
                    
                    if my > opp:
                        txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb}\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
                    elif my == opp:
                        txt = f"תיקו בסיום המשחק של הפועל ({my}-{opp}), ממשיכים הלאה בכל הכוח. יאללה הפועלללל 💙"
                    else:
                        txt = f"הפסד בסיום המשחק ({my}-{opp}), לא נורא מרימים את הראש וממשיכים הלאה בכל הכוחח.\n\nיאלה הפועל מלחמההה 💙"
                    
                    if send_telegram(txt, with_table=True):
                        with open("task_log.txt", 'a', encoding='utf-8') as f: f.write(f"final_{today_str}:{now_il.strftime('%H:%M')}\n")
                        tasks.add(f"final_{today_str}:{now_il.strftime('%H:%M')}")
    except Exception as e:
        print(f"LOG ERROR: API check failed: {e}")

    # 2. סריקת כתבות
    print(f"LOG: מתחיל סריקת {len(RSS_FEEDS)} מקורות RSS...")
    for feed_url in RSS_FEEDS:
        print(f"📡 פיד: {feed_url}")
        try:
            resp = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            feed = feedparser.parse(resp.content)
            print(f"🔍 נמצאו {len(feed.entries)} כתבות בפיד.")
            
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                title = entry.title
                
                if link in history or any(title[:25] in h for h in history):
                    continue
                
                print(f"🧐 בוחן כתבה: {title}")
                
                # פילטר זמן (72 שעות)
                pub = entry.get('published_parsed')
                if pub:
                    pub_dt = datetime(*pub[:6]) + timedelta(hours=3)
                    if now_il - pub_dt > timedelta(hours=72):
                        print(f"⏰ ישנה מדי ({pub_dt.strftime('%d/%m %H:%M')}). מדלג.")
                        continue

                # שאיבת תוכן
                try:
                    res_art = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res_art.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = entry.title

                # בדיקת מילות מפתח
                if any(k.lower() in (title + content).lower() for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה התאמה למילות מפתח. שולח ל-AI...")
                    summary = get_ai_summary(content, models, title)
                    
                    if summary == "SKIP":
                        print("🚫 AI החליט שהכתבה לא מהותית להפועל פ\"ת (SKIP).")
                        with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(f"{link} | {title}\n")
                        history.add(link)
                        continue
                    
                    if summary:
                        msg = f"*יש עדכון חדש על הפועל 💙*\n\n{html.escape(summary)}\n\n🔗 [לכתבה המלאה]({link})"
                        if send_telegram(msg):
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(f"{link} | {title}\n")
                            history.add(link)
                            print(f"✅ נשלחה בהצלחה לטלגרם.")
                            time.sleep(5)
                else:
                    print("❌ לא נמצאו מילות מפתח רלוונטיות בטקסט.")
        except Exception as e:
            print(f"LOG ERROR: שגיאה בפיד {feed_url}: {e}")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
