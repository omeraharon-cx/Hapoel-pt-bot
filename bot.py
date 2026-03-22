import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
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

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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
        prompt = f"סכם ב-3 משפטים עבור אוהד הפועל פתח תקווה: {text[:4000]}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"AI Quota Issue: {e}")
        return None # מחזיר None כדי שנדע להשתמש בגיבוי

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
    # רק מילים של הפועל פ"ת - בלי ישראל!
    keywords = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "פ\"ת", "מלאבס", "הכחולים"]

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
                
            content = get_full_article_text(link)
            if any(key in title or key in content for key in keywords):
                summary = get_ai_summary(content)
                
                if summary:
                    msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                else:
                    # מנגנון גיבוי אם ה-AI חסום
                    msg = f"⚽ *כתבה חדשה (ה-AI בעומס)*\n\n_{title}_\n\n🔗 [לחצו לקריאה המלאה]({link})"
                
                send_telegram_msg(msg)
                new_processed.append(link)
                new_processed.append(title)
                print(f"נשלחה הודעה על: {title}")
                time.sleep(10) # המתנה של 10 שניות כדי לא לחרוג מהמכסה

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
