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
        
        # ניקוי זבל
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe']): s.decompose()
        
        # חיפוש טקסט בבלוקים נפוצים
        text_blocks = soup.find_all(['p', 'h2', 'div.article-content', 'div.content'])
        full_text = " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
        
        print(f"📄 נשאבו {len(full_text)} תווים מהכתבה.")
        return full_text
    except Exception as e:
        print(f"⚠️ שגיאה בשאיבת תוכן: {e}")
        return ""

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url)
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except:
        return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models):
    if not text or len(text) < 150:
        print(f"🛑 תקציר בוטל: הטקסט קצר מדי ({len(text)} תווים).")
        return None
    
    # הפרומפט הענייני והאובייקטיבי שביקשת
    prompt = (
        f"סכם את הכתבה הבאה ב-3 משפטים קצרים בצורה עניינית, אובייקטיבית וברורה. "
        f"התמקד בעובדות המרכזיות בלבד מהזווית של הפועל פתח תקווה. "
        f"אל תשתמש בכינויי שייכות (כמו 'שלנו'), אל תהיה רגשי, והנגש את המידע לקריאה מהירה: {text[:2800]}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    headers = {'Content-Type': 'application/json'}

    for model_path in models:
        for version in ['v1', 'v1beta']:
            try:
                url = f"https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                data = response.json()
                
                if response.status_code == 200:
                    if 'candidates' in data and data['candidates']:
                        candidate = data['candidates'][0]
                        # בדיקה אם גוגל חסמה את התשובה בגלל בטיחות
                        if candidate.get('finishReason') == 'SAFETY':
                            print(f"🛡️ גוגל חסמה את התקציר למודל {model_path} בגלל סיבות בטיחות.")
                            continue
                        return candidate['content']['parts'][0]['text']
                elif response.status_code == 429:
                    print(f"⏳ מכסה נגמרה למודל {model_path}, מנסה את הבא...")
            except:
                continue
    print("❌ לא ניתן היה להפיק תקציר מאף מודל.")
    return None

def main():
    print("🚀 סריקה התחילה (גרסת דיאגנוסטיקה)...")
    models = get_available_models()
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
                print(f"🎯 נמצאה כתבה: {title}")
                summary = get_ai_summary(content, models)
                
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
