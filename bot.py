import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# הגדרות שמושכות מידע מה"כספת" של גיטהאב
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110" # זה יכול להישאר ככה, זה לא סודי

# מקורות החדשות
RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://m.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml"
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_article_summary(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        # שואב את הטקסט של הכתבה
        paragraphs = soup.find_all('p')
        text = " ".join([p.text for p in paragraphs[:10]])
        
        prompt = f"סכם את הכתבה הבאה ב-3 עד 4 משפטים קצרים וממצים עבור אוהד הפועל פתח תקווה. הנה התוכן: {text}"
        summary = model.generate_content(prompt)
        return summary.text
    except Exception as e:
        print(f"Error fetching article: {e}")
        return None

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def main():
    # ניהול היסטוריה כדי שלא תקבל אותה כתבה פעמיים
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    
    with open(db_file, 'r') as f:
        seen_links = f.read().splitlines()

    new_links = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            # מחפש מילות מפתח בכותרת
            if "הפועל פתח תקווה" in entry.title or "הפועל פת" in entry.title:
                if entry.link not in seen_links:
                    summary = get_article_summary(entry.link)
                    if summary:
                        msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({entry.link})"
                        send_telegram_msg(msg)
                        new_links.append(entry.link)

    # עדכון קובץ ההיסטוריה
    with open(db_file, 'a') as f:
        for link in new_links:
            f.write(link + "\n")

if __name__ == "__main__":
    main()
