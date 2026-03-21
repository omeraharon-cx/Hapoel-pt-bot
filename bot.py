import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# הגדרות אבטחה מהכספת של GitHub
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

# רשימת מקורות RSS (כולל וואלה וספורט 1)
RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://m.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",           # וואלה! ספורט
    "https://sport1.maariv.co.il/feed/"         # ספורט 1
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_article_summary(url):
    """שואב תוכן ומסכם אותו בעזרת AI"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.text for p in paragraphs[:12]]) # קורא קצת יותר טקסט לדיוק
        
        prompt = f"סכם את הכתבה הבאה ב-3 עד 4 משפטים קצרים וממצים עבור אוהד הפועל פתח תקווה. הנה התוכן: {text}"
        summary = model.generate_content(prompt)
        return summary.text
    except:
        return None

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_official_site(seen_links):
    """סורק מיוחד לאתר הרשמי של הפועל פתח תקווה - עמוד החדשות בלבד"""
    new_links = []
    try:
        url = "https://www.hapoelpt.com/news"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # מחפש קישורים שמובילים לכתבות חדשות בתוך עמוד החדשות
        for a in soup.find_all('a', href=True):
            link = a['href']
            # מוודא שהקישור הוא לכתבת חדשות מלאה ולא דף כללי
            if "/news/" in link and len(link) > 10:
                full_url = link if link.startswith("http") else f"https://www.hapoelpt.com{link}"
                
                if full_url not in seen_links:
                    summary = get_article_summary(full_url)
                    if summary:
                        msg = f"🔵 *חדשות מהאתר הרשמי*\n\n{summary}\n\n🔗 [לכתבה המלאה]({full_url})"
                        send_telegram_msg(msg)
                        new_links.append(full_url)
    except Exception as e:
        print(f"Error checking official site: {e}")
    return new_links

def main():
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    
    with open(db_file, 'r') as f:
        seen_links = f.read().splitlines()

    new_processed_links = []

    # 1. בדיקת מקורות RSS (ONE, ספורט 5, וואלה, ספורט 1)
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            title = entry.title
            # מחפש מילות מפתח
            keywords = ["הפועל פתח תקווה", "הפועל פת", "מלאבס", "הכחולים"]
            if any(key in title for key in keywords):
                if entry.link not in seen_links:
                    summary = get_article_summary(entry.link)
                    if summary:
                        msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                        send_telegram_msg(msg)
                        new_processed_links.append(entry.link)

    # 2. בדיקת האתר הרשמי (סריקה מיוחדת)
    official_links = check_official_site(seen_links)
    new_processed_links.extend(official_links)

    # עדכון היסטוריה
    if new_processed_links:
        with open(db_file, 'a') as f:
            for link in new_processed_links:
                f.write(link + "\n")

if __name__ == "__main__":
    main()
