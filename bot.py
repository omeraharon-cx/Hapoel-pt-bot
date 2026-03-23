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
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style']): s.decompose()
        text_blocks = soup.find_all(['p', 'h2'])
        text = " ".join([t.text for t in text_blocks if len(t.text) > 30])
        print(f"📄 אורך הטקסט שנשאב מהכתבה: {len(text)} תווים")
        return text
    except Exception as e:
        print(f"⚠️ שגיאה בשאיבת תוכן הכתבה: {e}")
        return ""

def get_ai_summary(text):
    if not text or len(text) < 100:
        print("🛑 הטקסט קצר מדי או ריק, לא שולח ל-AI")
        return None
    
    # ניסיון בודד וממוקד עם המודל הכי יציב
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt = f"אתה אוהד שרוף של הפועל פתח תקווה. סכם ב-3 משפטים מהזווית של הפועל פתח תקווה בלבד: {text[:3000]}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        print(f"🤖 פונה ל-AI לסיום סיכום...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        data = response.json()
        
        if response.status_code == 200:
            if 'candidates' in data and data['candidates']:
                summary = data['candidates'][0]['content']['parts'][0]['text']
                print("✅ תקציר הופק בהצלחה!")
                return summary
        
        print(f"❌ שגיאת AI (קוד {response.status_code}): {data}")
        return None
    except Exception as e:
        print(f"❌ תקלה חמורה בפנייה ל-AI: {e}")
        return None

def main():
    print("🚀 סריקה התחילה...")
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
                print(f"🎯 מצאתי כתבה רלוונטית: {title}")
                summary = get_ai_summary(content)
                
                header = "**יש עדכון חדש על הפועל 💙**"
                summary_final = summary if summary else "הכתבה ללא תקציר 🔵⚪️"
                msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(3)

    print(f"🏁 סיום. נמצאו {new_found} כתבות.")

if __name__ == "__main__":
    main()
