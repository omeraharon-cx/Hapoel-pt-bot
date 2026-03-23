import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import google.generativeai as genai

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

# אתחול ה-AI בשיטה הרשמית
genai.configure(api_key=GEMINI_API_KEY)

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer']): s.decompose()
        text_blocks = soup.find_all(['p', 'h2'])
        return " ".join([t.text for t in text_blocks if len(t.text) > 30])
    except: return ""

def get_ai_summary(text):
    if not text or len(text) < 150: return None
    
    # ניסיון להשתמש במודל הפלאש היציב ביותר ל-2026
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"סכם את הכתבה הבאה ב-3 משפטים קצרים וקולעים. "
            f"התמקד אך ורק בזווית של הפועל פתח תקווה. "
            f"הנה התוכן: {text[:3000]}"
        )
        
        # הגדרות בטיחות מקלות כדי למנוע חסימות שווא
        safety = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt, safety_settings=safety)
        return response.text
    except Exception as e:
        print(f"❌ שגיאת AI רשמית: {e}")
        # אם המודל לא נמצא, ננסה את מודל הפרו כגיבוי אחרון
        try:
            model_pro = genai.GenerativeModel('gemini-pro')
            response = model_pro.generate_content(prompt)
            return response.text
        except:
            return None

def main():
    print("🚀 סריקה התחילה (גרסת הספרייה הרשמית)...")
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
                print(f"🎯 מצאתי: {title}")
                summary = get_ai_summary(content)
                
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
