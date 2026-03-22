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
        headers = {'User-Agent': 'Mozilla/5.0'} # מתחזה לדפדפן כדי שלא יחסמו אותנו
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # מחפש טקסט ביותר מקומות (גם פסקאות וגם דיבים של תוכן)
        text_blocks = soup.find_all(['p', 'div', 'h2'])
        full_text = " ".join([t.text for t in text_blocks if len(t.text) > 20])
        
        # נירמול גרשיים: הופך את כל סוגי הגרשיים והצ'ופצ'יקים לתו אחד סטנדרטי
        normalized_text = full_text.replace('״', '"').replace("'", '"').replace('"', '"')
        return normalized_text
    except:
        return ""

def get_ai_summary(text):
    try:
        prompt = f"סכם את הכתבה הבאה ב-3 עד 4 משפטים קצרים וממצים עבור אוהד הפועל פתח תקווה. הנה התוכן: {text[:4000]}"
        summary = model.generate_content(prompt)
        return summary.text
    except:
        return None

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def main():
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    new_processed = []
    # רשימת מילים גמישה יותר (כולל כתיב חסר וסוגי גרשיים)
    keywords = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "פ\"ת", "מלאבס", "הכחולים"]

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.link
            title = entry.title
            
            if link in history or title in history:
                continue
                
            content = get_full_article_text(link)
            
            # בדיקה אם אחת המילים נמצאת בכותרת או בתוכן (אחרי נירמול)
            title_norm = title.replace('״', '"').replace("'", '"')
            if any(key in title_norm for key in keywords) or any(key in content for key in keywords):
                summary = get_ai_summary(content)
                if summary:
                    msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    send_telegram_msg(msg)
                    new_processed.append(link)
                    new_processed.append(title)

    # אתר רשמי
    try:
        url = "https://www.hapoelpt.com/news"
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        for a in soup.find_all('a', href=True):
            link = a['href']
            if "/news/" in link:
                full_url = link if link.startswith("http") else f"https://www.hapoelpt.com{link}"
                if full_url not in history:
                    text = get_full_article_text(full_url)
                    summary = get_ai_summary(text)
                    if summary:
                        send_telegram_msg(f"🔵 *חדשות מהאתר הרשמי*\n\n{summary}\n\n🔗 [לכתבה המלאה]({full_url})")
                        new_processed.append(full_url)
    except: pass

    if new_processed:
        with open(db_file, 'a') as f:
            for item in new_processed:
                f.write(item + "\n")

if __name__ == "__main__":
    main()
