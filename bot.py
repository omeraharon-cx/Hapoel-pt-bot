import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai
import os
import time

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

client = genai.Client(api_key=GEMINI_API_KEY)

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style']): s.decompose()
        # מציאת טקסט הכתבה
        text_blocks = soup.find_all(['p', 'h2', 'div'], class_=['article-body', 'content']) 
        if not text_blocks: text_blocks = soup.find_all(['p', 'h2'])
        return " ".join([t.text for t in text_blocks if len(t.text) > 30]).replace('״', '"').replace("'", '"')
    except: return ""

def get_ai_summary(text):
    if not text: return None
    short_text = text[:2500] 
    try:
        time.sleep(5) # המתנה למניעת עומס על גוגל
        prompt = (
            f"אתה אוהד שרוף של הפועל פתח תקווה. סכם את הכתבה הבאה ב-3 משפטים. "
            f"התמקד אך ורק בזווית של הפועל פתח תקווה. הנה הטקסט: {short_text}"
        )
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return response.text if response.text else None
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return None

def main():
    print("🚀 מתחיל סריקת כתבות...")
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    new_found = 0
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]

    # 1. סריקת אתרי ספורט כלליים (עם סינון מילות מפתח)
    for feed_url in RSS_FEEDS:
        print(f"🔎 סורק מקור RSS: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
            
            content = get_full_article_text(link)
            if any(key in (title + " " + content).lower() for key in hapoel_keys):
                print(f"🎯 נמצאה התאמה ב-RSS: {title}")
                summary = get_ai_summary(content)
                summary_final = summary if summary else "💙 ללא תקציר הכתבה - יאלה הפועל 🔵⚪"
                
                msg = f"*עדכון על הפועל:*\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(5)

    # 2. סריקת אתר רשמי (ללא סינון - כל מה שחדש נשלח עם תקציר!)
    print("🌐 בודק אתר רשמי...")
    try:
        resp = requests.get("https://www.hapoelpt.com/news", timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        # חיפוש לינקים לכתבות (בדרך כלל מכילים /post/ או /news/)
        for a in soup.find_all('a', href=True):
            link = a['href']
            if "/post/" in link or "/news/" in link:
                full_url = link if link.startswith("http") else f"https://www.hapoelpt.com{link}"
                if full_url not in history:
                    print(f"🎯 ידיעה חדשה מהאתר הרשמי: {full_url}")
                    
                    # פה התיקון: הבוט קורא את הכתבה ומסכם אותה!
                    content = get_full_article_text(full_url)
                    summary = get_ai_summary(content)
                    summary_final = summary if summary else "💙 ללא תקציר הכתבה - יאלה הפועל 🔵⚪"
                    
                    msg = f"*עדכון על הפועל (אתר רשמי):*\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({full_url})"
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                 json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                    
                    with open(db_file, 'a') as f: f.write(full_url + "\n")
                    new_found += 1
                    time.sleep(5)
    except Exception as e:
        print(f"⚠️ שגיאה באתר הרשמי: {e}")

    print(f"🏁 סיום. נמצאו {new_found} כתבות חדשות.")

if __name__ == "__main__":
    main()
