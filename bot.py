import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
import random
import html
from datetime import datetime, timedelta

# הדפסה מיידית ללוגים
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = "425605110"

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.status_code == 200
    except: return False

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=10).json()
        models = [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models if models else ["models/gemini-1.5-flash"]
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, title):
    if not text or len(text) < 100: return None
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Write a 3-sentence summary in Hebrew. Tone: Casual, friend-to-friend, NO greetings.\n"
        "2. Focus ONLY on Hapoel Petah Tikva. If not the main subject, return ONLY: SKIP\n\n"
        f"### ARTICLE TEXT ###\n{text[:3000]}"
    )
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            data = res.json()
            if res.status_code == 200 and 'candidates' in data:
                summary = data['candidates'][0]['content']['parts'][0]['text'].strip()
                if "SKIP" in summary.upper() and len(summary) < 10: return "SKIP"
                return summary
        except: continue
    return None

def main():
    now_il = get_israel_time()
    print(f"--- {now_il.strftime('%H:%M:%S')} ריצה (גרסת לוגים מורחבת) ---")
    
    models = get_available_models()
    print(f"🤖 מודלים זמינים: {len(models)}")
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file): open(db_file, 'a').close()
    with open(db_file, 'r') as f: history = set(line.strip() for line in f)

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                link = entry.link.split('?')[0].replace("https://svcamz.", "https://www.")
                title = entry.title
                
                # לוג מעקב לכל כתבה
                print(f"🔍 בוחן: {title[:50]}...")

                if link in history:
                    print("⏭️ כבר נשלחה בעבר. מדלג.")
                    continue

                # פילטר זמן - הגדלתי ל-72 שעות כדי לתפוס את יום ראשון
                pub = entry.get('published_parsed')
                if pub:
                    pub_dt = datetime(*pub[:6]) + timedelta(hours=3)
                    if now_il - pub_dt > timedelta(hours=72):
                        print(f"⏰ ישנה מדי ({pub_dt.strftime('%d/%m %H:%M')}). מדלג.")
                        continue

                # שאיבת תוכן
                try:
                    res = requests.get(entry.link, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(res.content, 'html.parser')
                    content = " ".join([p.get_text() for p in soup.find_all(['p', 'h2'])])
                except: content = title

                # בדיקת מילות מפתח
                if any(k.lower() in (title + content).lower() for k in HAPOEL_KEYS) or "hapoelpt.com" in link:
                    print(f"🎯 נמצאה התאמה! שולח ל-AI...")
                    summary = get_ai_summary(content, models, title)
                    
                    if summary == "SKIP":
                        print("🚫 AI החליט שהכתבה לא מספיק רלוונטית.")
                        continue
                    
                    header = "*יש עדכון חדש על הפועל 💙*"
                    summary_final = summary if summary else "הכתבה ללא תקציר (תוכן קצר מדי) 🔵⚪️"
                    msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                    
                    if send_telegram(msg):
                        with open(db_file, 'a') as f: f.write(link + "\n")
                        history.add(link)
                        print(f"✅ נשלחה בהצלחה!")
                        time.sleep(5)
                else:
                    print("❌ לא נמצאו מילות מפתח רלוונטיות.")
        except Exception as e:
            print(f"⚠️ שגיאה בפיד {feed_url}: {e}")

    print("--- סיום ריצה ---")

if __name__ == "__main__": main()
