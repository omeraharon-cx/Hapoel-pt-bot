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

# --- הגדרות ליבה ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"

# --- מקורות ספורט מזוקקים בלבד ---
RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss2.xml", # פיד ספורט נקי יותר
    "https://rss.walla.co.il/feed/7",
    "https://sport1.maariv.co.il/feed/"
]

# הרחבת מילות מפתח כדי לתפוס כתבות על שחקנים (כמו בוני)
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה", "בוני אמניס", "אמניס", "פורצ'ן"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text, is_poll=False, poll_data=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    method = "sendPoll" if is_poll else "sendMessage"
    payload = {"chat_id": ADMIN_ID, **(poll_data if is_poll else {"text": text, "parse_mode": "Markdown"})}
    try:
        r = requests.post(url + method, json=payload, timeout=20)
        return r.status_code == 200
    except: return False

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=10).json()
        return [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
    except: return ["models/gemini-1.5-flash"]

def check_for_duplicate_topic(new_summary, recent_summaries):
    """בדיקת AI למניעת כפילויות נושאים מאתרים שונים"""
    if not recent_summaries: return False
    model = "models/gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
    
    prompt = (
        "You are a news editor. Compare the NEW SUMMARY with the list of RECENT SUMMARIES. "
        "If the NEW SUMMARY is about the exact same news event (e.g., same referee appointment, same player signing), reply ONLY with 'DUPLICATE'. "
        "Otherwise, reply 'UNIQUE'.\n\n"
        f"RECENT SUMMARIES:\n{recent_summaries}\n\n"
        f"NEW SUMMARY: {new_summary}"
    )
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return "DUPLICATE" in res.json()['candidates'][0]['content']['parts'][0]['text'].upper()
    except: return False

def get_ai_summary(text, models, title):
    if not text or len(text) < 100: return None
    prompt = (
        "אתה עיתונאי ספורט ואוהד הפועל פתח תקווה. כתוב תקציר של 3 משפטים בטון ענייני ומכובד. "
        "התייחס לקבוצה כ'הפועל'. בלי 'לוזונים'. אם הכתבה לא עוסקת בהפועל פתח תקווה באופן מהותי, החזר SKIP.\n\n"
        f"כותרת: {title}\nטקסט: {text[:3000]}"
    )
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
            if res.status_code == 200:
                out = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                return out if "SKIP" not in out.upper() else "SKIP"
        except: continue
    return None

def main():
    now_il = get_israel_time()
    print(f"--- {now_il.strftime('%H:%M:%S')} תחילת ריצה ---")
    
    # ניהול קבצי זיכרון
    for f in ["seen_links.txt", "recent_summaries.txt"]:
        if not os.path.exists(f): open(f, 'a').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f: recent_sums = f.read()

    models = get_available_models()

    for feed_url in RSS_FEEDS:
        print(f"📡 פיד: {feed_url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
            resp = requests.get(feed_url, headers=headers, timeout=30)
            feed = feedparser.parse(resp.content)
            print(f"🔍 נמצאו {len(feed.entries)} כתבות.")
            
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                title = entry.title
                if link in history: continue

                # שאיבת תוכן עמוקה
                try:
                    res_art = requests.get(entry.link, headers=headers, timeout=15)
                    soup = BeautifulSoup(res_art.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
                except: content = title

                search_area = (title + " " + content).lower()
                if any(k.lower() in search_area for k in HAPOEL_KEYS):
                    print(f"🎯 נמצאה כתבה פוטנציאלית: {title}")
                    summary = get_ai_summary(content, models, title)
                    
                    if summary and summary != "SKIP":
                        # בדיקת כפילות נושאים מול סיכומים קודמים
                        if check_for_duplicate_topic(summary, recent_sums):
                            print(f"⏭️ נמצא ככפילות נושא (אתר אחר כבר דיווח). מדלג.")
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                            continue

                        header = "*יש עדכון חדש על הפועל 💙*"
                        msg = f"{header}\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                        if send_telegram(msg):
                            # שמירה להיסטוריה ועדכון סיכומים אחרונים (שומרים רק 5 אחרונים)
                            with open("seen_links.txt", 'a', encoding='utf-8') as f: f.write(link + "\n")
                            history.add(link)
                            
                            all_sums = [summary] + recent_sums.split("|||")[:4]
                            with open("recent_summaries.txt", 'w', encoding='utf-8') as f: f.write("|||".join(all_sums))
                            print(f"✅ נשלחה כתבה!")
                            time.sleep(5)
        except Exception as e:
            print(f"LOG ERROR: {e}")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
