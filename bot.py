import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai # הספרייה החדשה של 2026
import os
import time

# הגדרות
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://www.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# אתחול ה-AI בגרסה החדשה
client = genai.Client(api_key=GEMINI_API_KEY)

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style']): s.decompose()
        text_blocks = soup.find_all(['p', 'h2'])
        return " ".join([t.text for t in text_blocks if len(t.text) > 30]).replace('״', '"').replace("'", '"')
    except: return ""

def get_ai_summary(text):
    if not text: return None
    try:
        prompt = (
            f"אתה אוהד שרוף של הפועל פתח תקווה. סכם את הכתבה הבאה ב-3 משפטים ממצים. "
            f"דגש קריטי: התייחס אך ורק להקשר של הפועל פתח תקווה. "
            f"אם מדובר בדרבי או משחק נגד מכבי פתח תקווה, הדגש את הזווית של הפועל, השחקנים שלה וההשלכות עבורה. "
            f"הנה התוכן: {text[:5000]}"
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def send_telegram_msg(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except: pass

def main():
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    new_processed = []
    
    # מילות מפתח לחיפוש
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
                
            content = get_full_article_text(link)
            full_text_to_check = (title + " " + content).lower()
            
            # הלוגיקה החדשה: אם הפועל מוזכרת, אנחנו לוקחים את הכתבה (גם אם מכבי שם)
            has_hapoel = any(key in full_text_to_check for key in hapoel_keys)
            
            if has_hapoel:
                summary = get_ai_summary(content)
                if summary:
                    msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                else:
                    msg = f"⚽ *כתבה חדשה (ה-AI בעומס)*\n\n_{title}_\n\n🔗 [לחצו לקריאה המלאה]({link})"
                
                send_telegram_msg(msg)
                new_processed.append(link)
                new_processed.append(title)
                time.sleep(15)

    # אתר רשמי
    try:
        resp = requests.get("https://www.hapoelpt.com/news", timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            link = a['href']
            if "/news/" in link:
                full_url = link if link.startswith("http") else f"https://www.hapoelpt.com{link}"
                if full_url not in history:
                    send_telegram_msg(f"🔵 *חדשות מהאתר הרשמי*\n\n🔗 [לכתבה]({full_url})")
                    new_processed.append(full_url)
                    time.sleep(5)
    except: pass

    if new_processed:
        with open(db_file, 'a') as f:
            for item in new_processed: f.write(item + "\n")

if __name__ == "__main__":
    main()
