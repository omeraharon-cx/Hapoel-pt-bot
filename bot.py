import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os

# הגדרות אבטחה מה-Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

# רשימת המקורות לסריקה
RSS_FEEDS = [
    "https://www.one.co.il/rss",
    "https://m.sport5.co.il/Rss.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# הגדרת מודל ה-AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def get_full_article_text(url):
    """שואב את כל פסקאות הטקסט מהכתבה כדי לבדוק מילות מפתח"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        return " ".join([p.text for p in paragraphs])
    except:
        return ""

def get_ai_summary(text):
    """שולח את הטקסט המלא ל-Gemini לקבלת תקציר ממוקד"""
    try:
        # מגבילים את הטקסט הנשלח כדי לא לחרוג ממכסות (כ-4000 תווים ראשונים)
        prompt = f"סכם את הכתבה הבאה ב-3 עד 4 משפטים קצרים וממצים עבור אוהד הפועל פתח תקווה. הנה התוכן: {text[:4000]}"
        summary = model.generate_content(prompt)
        return summary.text
    except:
        return None

def send_telegram_msg(text):
    """שולח את ההודעה המעוצבת לטלגרם"""
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
    # מילות המפתח המדויקות שביקשת
    keywords = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פ\"ת", "הפועל פת", "מלאבס", "מלאבסים", "הכחולים"]

    for feed_url in RSS_FEEDS:
        print(f"סורק מקור: {feed_url}")
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.link
            title = entry.title
            
            # אם כבר טיפלנו בכתבה הזו בעבר - דלג
            if link in history or title in history:
                continue
                
            # סריקת עומק: כניסה לכתבה ובדיקת הטקסט המלא
            full_text = get_full_article_text(link)
            
            # בדיקה אם אחת ממילות המפתח מופיעה בכותרת או בתוכן
            if any(key in title for key in keywords) or any(key in full_text for key in keywords):
                print(f"נמצאה התאמה רלוונטית: {title}")
                summary = get_ai_summary(full_text)
                if summary:
                    msg = f"⚽ *עדכון הפועל פתח תקווה*\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    send_telegram_msg(msg)
                    new_processed.append(link)
                    new_processed.append(title)

    # סריקה מיוחדת לאתר הרשמי
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

    # שמירת היסטוריה כדי לא לשלוח שוב את אותן כתבות בריצה הבאה
    if new_processed:
        with open(db_file, 'a') as f:
            for item in new_processed:
                f.write(item + "\n")

if __name__ == "__main__":
    main()
