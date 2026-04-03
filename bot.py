import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
from datetime import datetime, timedelta
import calendar

# כיוון לוגים ל-GitHub
sys.stdout.reconfigure(encoding='utf-8')

TEAM_ID = "5199" 
LEAGUE_ID = "877"

WIN_CHANTS = [
    "אמרו לו הפועל אז הלך לאורווה, אמרו לו מכבי אז הוא צעק ״ש*אה״\nאלך אחריך גם עד סוף העולם, אקפו אשתגע יאללה ביחד כולםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון",
    "אלך אחריך גם עד סוף העולם, אקפוץ אשתגע יאללה ביחד כולם",
    "כמו דמיון חופשייי, שנינו ביחדדד רק את ואני\nכחול עולה עולה... יאללה הפועלללל, כחול עולה"
]

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_subscribers():
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file): open(sub_file, 'w').write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f: return list(set(line.strip() for line in f if line.strip()))

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    print(f"DEBUG: שולח הודעה ל-{len(subs)} רשומים")
    for cid in subs:
        try:
            if is_poll:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll", json={"chat_id": cid, **poll_data}, timeout=10)
            elif photo_url:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", json={"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=15)
            else:
                res = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text, "parse_mode": "Markdown", "reply_markup": reply_markup}, timeout=10)
            print(f"DEBUG: תגובת טלגרם: {res.status_code}")
        except Exception as e: print(f"DEBUG ERROR טלגרם: {e}")

def get_ai_response(prompt):
    print("DEBUG: פונה ל-Gemini...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    # הגדרות בטיחות - אומרים ל-AI לא לחסום תוכן ספורט
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": safety_settings
    }
    
    try:
        res = requests.post(url, json=payload, timeout=25)
        data = res.json()
        
        if res.status_code != 200:
            print(f"DEBUG ERROR: Gemini API {res.status_code}: {res.text}")
            return None
            
        if 'candidates' not in data or not data['candidates']:
            print(f"DEBUG ERROR: No candidates in response. Full data: {data}")
            return None
            
        return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"DEBUG ERROR Gemini Exception: {e}")
        return None

def get_full_article_text(url):
    print(f"DEBUG: מנסה לשלוף טקסט מ-{url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        text = " ".join([t.get_text().strip() for t in soup.find_all(['p', 'h1', 'h2', 'h3']) if len(t.get_text()) > 25])
        print(f"DEBUG: נשלפו {len(text)} תווים")
        return text
    except Exception as e:
        print(f"DEBUG ERROR Scraping: {e}")
        return ""

def get_match_players(fixture_id):
    print(f"DEBUG: שואב שחקנים למשחק {fixture_id}...")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/players"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"fixture": fixture_id, "team": TEAM_ID}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        players_data = res['response'][0]['players']
        played = [p['player']['name'] for p in players_data if (p['statistics'][0]['games']['minutes'] or 0) > 0]
        return played[:10]
    except Exception as e:
        print(f"DEBUG ERROR Players API: {e}")
        return ["עומר כץ", "רם לוי", "דרור ניר", "רוי נאווי", "מתן פלג", "אופק אושר", "מתן גושה", "שחקן אחר"]

def check_match_status():
    print("DEBUG: בודק RapidAPI לסטטוס משחק...")
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    params = {"team": TEAM_ID, "date": datetime.now().strftime('%Y-%m-%d')}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            print(f"DEBUG: נמצא משחק! סטטוס: {m['fixture']['status']['short']}")
            is_home = str(m['teams']['home']['id']) == TEAM_ID
            return {
                "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
                "my_score": m['goals']['home'] if is_home else m['goals']['away'],
                "opp_score": m['goals']['away'] if is_home else m['goals']['home'],
                "opp_name": m['teams']['away']['name'] if is_home else m['teams']['home']['name'],
                "venue": m['fixture']['venue']['name']
            }
    except Exception as e: print(f"DEBUG ERROR RapidAPI: {e}")
    return None

def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}", flush=True)
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    
    db_file, sum_db, task_file = "seen_links.txt", "recent_summaries.txt", "task_log.txt"
    for f in [db_file, sum_db, task_file]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open(db_file, 'r') as f: history = set(f.read().splitlines())
    with open(sum_db, 'r', encoding='utf-8') as f: recent_sums = f.read().splitlines()[-15:]
    with open(task_file, 'r') as f: tasks_done = set(f.read().splitlines())

    h_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

    # 1. סריקת RSS (כתבות)
    print("📰 שלב 1: סריקת כתבות RSS")
    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if entry.link in history: continue
            
            is_relevant = any(k in entry.title.lower() for k in h_keys) or "hapoelpt.com" in entry.link
            
            if is_relevant:
                print(f"🎯 נמצאה כתבה: {entry.title}")
                content = get_full_article_text(entry.link)
                prompt = f"Summarize this in 3 Hebrew sentences about Hapoel Petah Tikva. Return SKIP if not relevant. TEXT: {content[:2000]}"
                summary = get_ai_response(prompt)
                
                if summary and "SKIP" not in summary.upper():
                    send_to_all(f"**יש עדכון חדש על הפועל 💙**\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})")
                    with open(sum_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
            
            history.add(entry.link)
            with open(db_file, 'a') as f: f.write(entry.link + "\n")

    # 2. לוגיקת משחקים
    print("⚽️ שלב 2: בדיקת משחקים")
    match = check_match_status()
    if match:
        if now.hour < 12 and f"match_poster_{today_key}" not in tasks_done:
            print("🎨 מפעיל לוגיקת פוסטר")
            p_prompt = f"Match day poster Hapoel Petah Tikva vs {match['opp_name']}, blue/white, cinematic"
            img_desc = get_ai_response(f"Translate to DALL-E prompt: {p_prompt}")
            if img_desc:
                url = f"https://pollinations.ai/p/{img_desc.replace(' ', '%20')}"
                send_to_all("Match Day 💙\n\nהפועל שלנו תעלה בעוד כמה שעות לכר הדשא\nיאללה הפועל לתת את הלב בשביל הסמל.\nמביאים 3 נקודות בע״ה\n\nקדימה הפועללל ⚽️", photo_url=url)
                with open(task_file, 'a') as f: f.write(f"match_poster_{today_key}\n")

        if now.hour == 15 and f"match_bet_{today_key}" not in tasks_done:
            print("🗳 מפעיל לוגיקת הימורים")
            send_to_all("", is_poll=True, poll_data={"question": f"איך יסתיים המשחק היום מול {match['opp_name']}?", "options": ["ניצחון כחול 💙", "תיקו", "הפסד (חס וחלילה)"], "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"match_bet_{today_key}\n")

        if match['status'] == 'FT' and f"match_end_{today_key}" not in tasks_done:
            print("🏁 זיהוי סיום משחק!")
            if match['my_score'] > match['opp_score']:
                msg = f"{random.choice(WIN_CHANTS)}\n\nיופי הפועללל, איזה נצחון גדול.\nהבאנו 3 נקודות חשובות.\nיאלללה הפועל 💙"
            elif match['my_score'] == match['opp_score']:
                msg = "תיקו בסיום המשחק של הפועל, ממשיכים הלאה בכל הכוח\nיאללה הפועללללל 💙"
            else:
                msg = "הפסד כואב של הפועל, לא נורא הפועל להרים את הראש.\nממשיכים הלאה חזק, קדימה הפועל מלחמההה 💙"
            
            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": "https://www.football.co.il/leagues/israeli-premier-league/table"}]]}
            send_to_all(msg, reply_markup=markup)
            
            print("⏳ מחכה 10 דקות לסקר...")
            time.sleep(600)
            players = get_match_players(match['id'])
            send_to_all("", is_poll=True, poll_data={"question": "מי השחקן המצטיין שלכם היום? ⚽️", "options": players, "is_anonymous": False})
            with open(task_file, 'a') as f: f.write(f"match_end_{today_key}\n")

    print("🏁 סיום.")

if __name__ == "__main__": main()
