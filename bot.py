import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# הגדרות
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://m.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"שגיאה בגישה לכתבה: {response.status_code}")
            return ""
        soup = BeautifulSoup(response.content, 'html.parser')
        text_blocks = soup.find_all(['p', 'div'])
        full_text = " ".join([t.text for t in text_blocks if len(t.text) > 20])
        return full_text.replace('״', '"').replace("'", '"')
    except Exception as e:
        print(f"שגיאה בשאיבת טקסט: {e}")
        return ""

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print(f"סטטוס שליחה לטלגרם: {r.status_code}")

def main():
    print("מתחיל ריצה דיאגנוסטית...")
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    keywords = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "פ\"ת", "מלאבס", "הכחולים", "ישראל"]
    found_any = False

    for feed_url in RSS_FEEDS:
        print(f"--- בודק מקור: {feed_url} ---")
        feed = feedparser.parse(feed_url)
        print(f"נמצאו {len(feed.entries)} כתבות ב-RSS")
        
        for entry in feed.entries[:5]: # בודק רק את ה-5 הראשונות מכל אתר לניסיון
            title = entry.title
            link = entry.link
            print(f"בודק כתבה: {title}")
            
            content = get_full_article_text(link)
            print(f"אורך טקסט שנשאב: {len(content)} תווים")
            
            if any(key in title or key in content for key in keywords):
                print("!!! נמצאה התאמה !!! מנסה לסכם ולשלוח...")
                found_any = True
                prompt = f"סכם ב-2 משפטים: {content[:2000]}"
                try:
                    summary = model.generate_content(prompt)
                    send_telegram_msg(f"✅ בדיקה: {title}\n\n{summary.text}")
                except Exception as e:
                    print(f"שגיאה ב-AI: {e}")

    if not found_any:
        print("סיימתי לסרוק ולא מצאתי שום התאמה למילות המפתח.")

if __name__ == "__main__":
    main()
