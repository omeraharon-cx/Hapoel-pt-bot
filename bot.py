import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys

# מוודא שההדפסות יופיעו מיד בלוג
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = "425605110"

RSS_FEEDS = [
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_full_article_text(url):
    """שואב טקסט מהכתבה בצורה אגרסיבית כדי למנוע 'תקציר חסר'"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # ניקוי רעשים
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'button']): 
            s.decompose()
        
        # חיפוש טקסט בתוך DIVים נפוצים של תוכן כתבה
        main_content = soup.find(['div', 'article'], class_=['article-content', 'article-body', 'content', 'story-text'])
        if main_content:
            text_blocks = main_content.find_all(['p', 'h2'])
        else:
            text_blocks = soup.find_all(['p', 'h2', 'h3'])
            
        full_text = " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 20])
        return full_text
    except:
        return ""

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except:
        return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models):
    # הורדתי מעט את הרף ל-100 תווים כדי לתפוס גם כתבות קצרות
    if not text or len(text) < 100: return None
    
    # הפרומפט המנצח שלך שנשמר בדיוק כפי שהיה
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Write a summary of the provided sports article in Hebrew.\n"
        "2. Length: Exactly 3 short sentences.\n"
        "3. Tone: Casual, friendly (friend-to-friend), but concise and non-biased. No slang or jokes.\n"
        "4. NO GREETINGS: Do NOT start with 'Hi', 'Hello', 'Friends' or any intro. Start directly with the news content.\n"
        "5. MANDATORY CONTEXT: Always relate the news to Hapoel Petah Tikva (The Blues).\n"
        "### ARTICLE TEXT ###\n"
        f"{text[:3000]}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    for model_path in models:
        for version in ['v1beta', 'v1']:
            try:
                url = f"https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(url, json=payload, timeout=15)
                data = response.json()
                if response.status_code == 200 and 'candidates' in data:
                    return data['candidates'][0]['content']['parts'][0]['text'].strip()
            except: continue
    return None

def main():
    print("🚀 סריקה התחילה...", flush=True)
    models = get_available_models()
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים"]
    new_found = 0

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}", flush=True)
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
            
            content = get_full_article_text(link)
            search_area = (title + " " + content).lower()
            
            if any(key in search_area for key in hapoel_keys) or "hapoelpt.com" in link:
                print(f"🎯 נמצאה כתבה: {title} (אורך טקסט: {len(content)})", flush=True)
                summary = get_ai_summary(content, models)
                
                header = "**יש עדכון חדש על הפועל 💙**"
                summary_final = summary if summary else "הכתבה ללא תקציר (תוכן קצר מדי) 🔵⚪️"
                msg = f"{header}\n\n{summary_final}\n\n🔗 [לכתבה המלאה]({link})"
                
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                             json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                new_found += 1
                time.sleep(5)

    print(f"🏁 סיום. נמצאו {new_found} כתבות חדשות.", flush=True)

if __name__ == "__main__":
    main()
