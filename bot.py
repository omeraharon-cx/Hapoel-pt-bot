import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import json

# הגדרות
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

RSS_FEEDS = [
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        text_blocks = soup.find_all(['p', 'h2'])
        return " ".join([t.text for t in text_blocks if len(t.text) > 30])
    except: return ""

def find_working_model():
    """פונקציה ששואלת את גוגל איזה מודלים פתוחים לשימוש"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url)
        data = response.json()
        if 'models' in data:
            # מחפשים מודל שיש לו 'flash' בשם והוא תומך ביצירת תוכן
            for m in data['models']:
                if 'generateContent' in m['supportedGenerationMethods']:
                    if '1.5-flash' in m['name'] or '2.0-flash' in m['name']:
                        print(f"✅ נמצא מודל תקין: {m['name']}")
                        return m['name']
            return data['models'][0]['name'] # ברירת מחדל - המודל הראשון ברשימה
    except:
        return "models/gemini-1.5-flash"

def get_ai_summary(text, model_name):
    if not text or len(text) < 150: return None
    
    # שימוש ב-v1beta כי הוא הכי גמיש
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt = f"אתה אוהד שרוף של הפועל פתח תקווה. סכם ב-3 משפטים קצרים מהזווית של הפועל פתח תקווה בלבד: {text[:2500]}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = response.json()
        if response.status_code == 200 and 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"❌ שגיאה במודל {model_name}: {data.get('error', {}).get('message', 'Unknown')}")
            return None
    except:
        return None

def main():
    print("🚀 סריקה התחילה (מצב סריקת מודלים)...")
    
    # שלב 1: מציאת המודל שעובד אצלך כרגע
    active_model = find_working_model()
    
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    new_found = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
            
            content = get_full_article_text(link)
            if any(key in (title + " " + content).lower() for key in hapoel_keys) or "hapoelpt.com" in link:
                print(f"🎯 מעבד כתבה: {title}")
                summary = get_ai_summary(content, active_model)
                
                header = "**יש עדכון חדש על הפועל 💙**"
                summary_final = summary if summary else "הכתבה ללא תקציר 🔵⚪️"
                msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(5)

    print(f"🏁 סיום. נמצאו {new_found} כתבות.")

if __name__ == "__main__":
    main()
