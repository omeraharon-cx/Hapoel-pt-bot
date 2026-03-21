import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# הגדרות אבטחה
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

# מקורות המידע
RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://m.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_article_summary(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.text for p in paragraphs[:12]])
        prompt = f"סכם את הכתבה הבאה ב-3 עד 4 משפטים קצרים וממצים עבור אוהד הפועל פתח תקווה. הנה התוכן: {text}"
        summary = model.generate_content(prompt)
        return summary.text
    except:
        return None

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_official_site(history):
    new_found = []
    try:
        url = "https://www.hapoelpt.com/news"
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            link = a['href']
            if "/news/" in link and len(link) > 10:
                full_url = link if link.startswith("http") else f"https://www.hapoelpt.com{link}"
                if full_url not in history:
                    summary = get_article_summary(full_url)
                    if summary:
                        send_telegram_msg(f"🔵 *חדשות מהאתר הרשמי*\n\n{summary}\n\n🔗 [לכתבה המלאה]({full_url})")
                        new_found.append(full_url)
    except: pass
    return new_found

def main():
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    new_processed = []
    # מילות המפתח המורחבות והמדויקות
    keywords = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פ\"ת", "הפועל פת", "מלאבס", "מלאבסים", "הכחולים"]

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            if any(key in title for key in keywords):
                if link not in history and title not in history:
                    summary = get_article_summary(link)
                    if summary:
                        msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                        send_telegram_msg(msg)
                        new_processed.append(link)
                        new_processed.append(title)

    official_updates = check_official_site(history)
    new_processed.extend(official_updates)

    if new_processed:
        with open(db_file, 'a') as f:
            for item in new_processed:
                f.write(item + "\n")

if __name__ == "__main__":
    main()
