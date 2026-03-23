import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import json

# הגדרות (Secrets של GitHub)
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
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style']): s.decompose()
        text_blocks = soup.find_all(['p', 'h2'])
        return " ".join([t.text for t in text_blocks if len(t.text) > 30])
    except: return ""

def get_ai_summary(text):
    if not text: return None
    
    # בשנת 2026, אנחנו מנסים קודם את הגרסה היציבה (v1) ואז את הבטא (v1beta)
    # אנחנו גם מנסים את השמות הכי נפוצים של המודל
    api_versions = ["v1", "v1beta"]
    model_names = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-2.0-flash-exp"]
    
    prompt = f"אתה אוהד שרוף של הפועל פתח תקווה. סכם את הכתבה ב-3 משפטים קצרים מהזווית של הפועל פתח תקווה: {text[:2500]}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': GEMINI_API_KEY
    }

    for ver in api_versions:
        for model in model_names:
            try:
                url = f"https://generativelanguage.googleapis.com/{ver}/models/{model}:generateContent"
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'candidates' in data:
                        return data['candidates'][0]['content']['parts'][0]['text']
                
                # אם קיבלנו 404, פשוט נמשיך למודל הבא ברשימה
                continue
            except:
                continue
    
    print("❌ כל ניסיונות ה-AI נכשלו (404/Auth/Quota)")
    return None

def main():
    print("🚀 מתחיל סריקה...")
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
            is_official = "hapoelpt.com" in link
            if is_official or any(key in (title + " " + content).lower() for key in hapoel_keys):
                
                print(f"🎯 מעבד כתבה: {title}")
                summary = get_ai_summary(content)
                
                # עיצוב ההודעה בדיוק כפי שביקשת (הכותרת בבולד)
                header = "**יש עדכון חדש על הפועל 💙**"
                
                if summary:
                    msg = f"{header}\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                else:
                    msg = f"{header}\n\nהכתבה ללא תקציר 🔵⚪️\n\n🔗 [לכתבה המלאה]({link})"
                
                # שליחה לטלגרם
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(5)

    print(f"🏁 סיום. נמצאו {new_found} כתבות.")

if __name__ == "__main__":
    main()
