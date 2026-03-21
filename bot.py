import feedparser
import requests
import os

# שליפת נתונים מהכספת
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

def send_telegram_msg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print(f"Status: {r.status_code}, Response: {r.text}")

def main():
    print("בודק כתבות...")
    # מילת מפתח כללית לטסט
    keyword = "מכבי" 
    feed = feedparser.parse("https://www.one.co.il/rss")
    
    for entry in feed.entries:
        if keyword in entry.title:
            print(f"נמצאה כתבה: {entry.title}")
            msg = f"🚀 *הבוט עובד!*\nהנה כתבה שמצאתי:\n{entry.title}\n{entry.link}"
            send_telegram_msg(msg)
            return # שולח רק אחת בשביל הטסט

if __name__ == "__main__":
    main()
