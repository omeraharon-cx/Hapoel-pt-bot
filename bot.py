import feedparser
import requests
from bs4 import BeautifulSoup
from google import genai
import os
import time

# הגדרות (Secrets של GitHub)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

# רשימת מקורות
RSS_FEEDS = [
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

# אתחול ה-AI
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
            f"הנה התוכן: {text[:5000]}"
        )
        # הוספת הגדרות בטיחות מקלות כדי למנוע חסימות שווא על כתבות ספורט
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt,
            config={
                'safety_settings': [
                    {'category': 'HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARASSMENT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
                ]
            }
        )
        return response.text
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
    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה",
