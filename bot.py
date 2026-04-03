import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
from datetime import datetime, timedelta
import calendar

# מוודא שההדפסות יופיעו מיד בלוג
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מזהים (RapidAPI) ---
TEAM_ID = "5199" 
LEAGUE_ID = "877"

# --- הגדרות מערכת (Secrets) ---
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
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    with open(sub_file, 'r') as f:
        return list(set(line.strip() for line in f if line.strip()))

def send_to_all(text, reply_markup=None, is_poll=False, poll_data=None, photo_url=None):
    subs = get_subscribers()
    for cid in subs:
        try:
            if is_poll and poll_data:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPoll"
                payload = {"chat_id": cid, **poll_data}
                requests.post(url, json=payload, timeout=10)
            elif photo_url:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                payload = {"chat_id": cid, "photo": photo_url, "caption": text, "parse_mode": "Markdown"}
                if reply_markup: payload["reply_markup"] = reply_markup
                requests.post(url, json=payload, timeout=15)
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
                if reply_markup: payload["reply_markup"] = reply_markup
                requests.post(url, json=payload, timeout=10)
        except: pass

def get_ai_response(prompt):
    url_base = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    url = f"{url_base}?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, json=payload, timeout=20).json()
        return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

def check_match_status():
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"}
    today = datetime.now().strftime('%Y-%m-%d')
    params = {"team": TEAM_ID, "date": today}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        if res.get('results', 0) > 0:
            m = res['response'][0]
            opp = m['teams']['away']['name'] if str(m['teams']['home']['id']) == TEAM_ID else m['teams']['home']['name']
            return {
                "id": m['fixture']['id'], "status": m['fixture']['status']['short'],
                "my_score": m['goals']['home'] if str(m['teams']['home']['id']) == TEAM_ID else m['goals']['away'],
                "opp_score": m['goals']['away'] if str(m['teams']['home']['id']) == TEAM_ID else m['goals']['home'],
                "opp_name": opp, "venue": m['fixture']['venue']['name']
            }
    except: return None
    return None

def main():
    print(f"🚀 סריקה התחילה: {datetime.now()}", flush=True)
    now = datetime.now()
    today_key = now.strftime('%Y-%m-%d')
    task_file = "task_log.txt"
    if not os.path.exists(task_file): open(task_file, 'w').close()
    with open(task_file, 'r') as f: tasks_done = f.read().splitlines()

    match = check_match_status()
    
    if match:
        # 1. הודעת Match Day (בבוקר - סביב 10:00)
        if now.hour == 10 and f"match_poster_{today_key}" not in tasks_done:
            # יצירת פרומפט לפוסטר AI
            prompt_for_ai = f"Create a cinematic football match day poster for Hapoel Petah Tikva vs {match['opp_name']}. Blue and white colors, stadium atmosphere, high resolution, digital art style."
            img_prompt = get_ai_response(f"Translate this to a detailed DALL-E style prompt in English: {prompt_for_ai}")
            photo_url = f"https://pollinations.ai/p/{img_prompt.replace(' ', '%20')}" if img_prompt else "https://hapoelpt.com/static/media/logo.png"
            
            match_day_text = (
                "Match Day 💙\n\n"
                "הפועל שלנו תעלה בעוד כמה שעות לכר הדשא\n"
                "יאללה הפועל לתת את הלב בשביל הסמל.\n"
                "מביאים 3 נקודות בע״ה\n\n"
                "קדימה הפועללל ⚽️"
            )
            send_to_all(match_day_text, photo_url=photo_url)
            with open(task_file, 'a') as f: f.write(f"match_poster_{today_key}\n")

        # 2. הודעת הימורים (15:00)
        if now.hour == 15 and f"match_bet_{today_key}" not in tasks_done:
            send_to_all("", is_poll=True, poll_data={
                "question": f"איך יסתיים המשחק היום מול {match['opp_name']}?",
                "options": ["ניצחון כחול 💙", "תיקו", "הפסד (חס וחלילה)"],
                "is_anonymous": False
            })
            with open(task_file, 'a') as f: f.write(f"match_bet_{today_key}\n")

        # 3. סיום משחק (FT)
        if match['status'] == 'FT' and f"match_end_{today_key}" not in tasks_done:
            # ... (כאן נשאר הקוד של סיום המשחק עם כפתור הטבלה והסקר)
            pass

    # ... (שאר הקוד של RSS ופינת ההיסטוריה בימי רביעי ב-12:00)
    print("🏁 סיום.")

if __name__ == "__main__":
    main()
