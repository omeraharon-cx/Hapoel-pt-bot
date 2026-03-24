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
    "https://sport1.mariv.co.il/feed/"
]

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']): s.decompose()
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3'])
        full_text = " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
        return full_text
    except: return ""

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url)
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models):
    if not text or len(text) < 150: return None
    prompt = (
        f"תכתוב עדכון קצר וכיפי לקריאה על הכתבה הבאה ב-3 משפטים. "
        f"הסגנון צריך להיות זורם ולא רשמי (כמו הודעה זריזה לחבר), אבל בלי הומור או בדיחות. "
        f"תתמקד בעיקר מהזווית של הפועל פתח תקווה ותעשה את זה פשוט וקולע. "
        f"הנה הטקסט: {text[:3000]}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    headers = {'Content-Type': 'application/json'}
    for model_path in models:
        for version in ['v1beta', 'v1']:
            try:
                url = f"https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                data = response.json()
                if response.status_code == 200 and 'candidates' in data:
                    return data['candidates'][0]['content']['parts'][0]['text']
            except: continue
    return None

def main():
    print("🚀 סריקה התחילה...")
    models = get_available_models()
    db_file = "seen_links.txt"
    
    # בדיקה מה יש בהיסטוריה
    if not os.path.exists(db_file):
        history = []
        print("📂 קובץ היסטוריה לא נמצא, יוצר חדש.")
    else:
        with open(db_file, 'r') as f:
            history = f.read().splitlines()
        print(f"📚 נמצאו {len(history)} קישורים בהיסטוריה.")

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    new_found = 0

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק את הפיד: {feed_url}")
        feed = feedparser.parse(feed_url)
        print(f"🔍 נמצאו {len(feed.entries)} כתבות בפיד.")
        
        for entry in feed.entries:
            link, title = entry.link, entry.title
            
            # בדיקה אם כבר ראינו
            if link in history or title in history:
                continue
            
            # אם הגענו לכאן, הכתבה "חדשה" לבוט
            print(f"🆕 בודק כתבה חדשה: {title}")
            content = get_full_article_text(link)
            search_area = (title + " " + content).lower()
            
            if any(key in search_area for key in hapoel_keys) or "hapoelpt.com" in link:
                print(f"🎯 הכתבה רלוונטית! מעבד...")
                summary = get_ai_summary(content, models)
                
                header = "**יש עדכון חדש על הפועל 💙**"
                summary_final = summary if summary else "הכתבה ללא תקציר 🔵⚪️"
                msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f:
                    f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(5)

    print(f"🏁 סיום. שלחתי {new_found} הודעות חדשות.")

if __name__ == "__main__":
    main()
