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

# רשימת הפידים המעודכנת - הוספתי את האתר הרשמי של הפועל
RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml", # האתר הרשמי/אוהדים
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_full_article_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']): s.decompose()
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3'])
        full_text = " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
        return full_text
    except: return ""

def get_available_models():
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models):
    if not text or len(text) < 100: return None
    
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Analyze if the provided article is PRIMARILY about Hapoel Petah Tikva.\n"
        "2. If Hapoel Petah Tikva is the main subject, write a 3-sentence summary in Hebrew.\n"
        "3. Tone: Casual, friend-to-friend, NO greetings (No 'Hi', No 'Friends').\n"
        "4. MANDATORY: Focus on the impact on Hapoel Petah Tikva and the specific news/result.\n"
        "\n"
        "### ARTICLE TEXT ###\n"
        f"{text[:3000]}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
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
                    res = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    if "SKIP" in res.upper() and len(res) < 10:
                        return "REJECTED_BY_AI"
                    return res
            except: continue
    return None

def main():
    print("🚀 סריקה התחילה (כולל האתר הרשמי)...", flush=True)
    models = get_available_models()
    db_file = "seen_links.txt"
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f: f.write("")
    with open(db_file, 'r') as f:
        history = f.read().splitlines()

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]
    new_found = 0

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}", flush=True)
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            link, title = entry.link, entry.title
            if link in history or title in history: continue
            
            content = get_full_article_text(link)
            content_lower = content.lower()
            title_lower = title.lower()
            
            is_in_title = any(key in title_lower for key in hapoel_keys)
            count_in_body = sum(content_lower.count(key) for key in hapoel_keys)
            
            # אם זה מהאתר הרשמי - אנחנו תמיד רוצים לבדוק את זה לעומק
            is_official = "hapoelpt.com" in link or "hapoelpt.com" in feed_url
            
            should_check = False
            if is_official or is_in_title or count_in_body >= 2 or (count_in_body == 1 and len(content) < 600):
                should_check = True

            if should_check:
                print(f"🎯 מעבד כתבה: {title}", flush=True)
                summary = get_ai_summary(content, models)
                
                if summary == "REJECTED_BY_AI":
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    continue

                if summary:
                    header = "**יש עדכון חדש על הפועל 💙**"
                    msg = f"{header}\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                 json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                    
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    new_found += 1
                    time.sleep(5)

    print(f"🏁 סיום. נשלחו {new_found} כתבות.", flush=True)

if __name__ == "__main__":
    main()
