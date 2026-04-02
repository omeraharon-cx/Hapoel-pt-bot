import feedparser
import requests
from bs4 import BeautifulSoup
import os
import time
import sys
from datetime import datetime, timedelta
import calendar

# מוודא שההדפסות יופיעו מיד בלוג של GitHub
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110" # ה-ID שלך כמנהל

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/RSS.aspx",
    "https://www.ynet.co.il/Integration/StoryRss1854.xml",
    "https://rss.walla.co.il/feed/3",
    "https://sport1.maariv.co.il/feed/"
]

def get_subscribers():
    """מנהל את רשימת המנויים ובודק אם יש נרשמים חדשים בטלגרם"""
    sub_file = "subscribers.txt"
    if not os.path.exists(sub_file):
        with open(sub_file, 'w') as f: f.write(ADMIN_ID + "\n")
    
    with open(sub_file, 'r') as f:
        subs = set(line.strip() for line in f if line.strip())

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        response = requests.get(url, timeout=10).json()
        if response.get("ok"):
            for update in response.get("result", []):
                chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                if chat_id and chat_id not in subs:
                    print(f"👤 מנוי חדש הצטרף: {chat_id}")
                    subs.add(chat_id)
                    welcome_msg = "ברוכים הבאים לעדכוני הפועל פתח תקווה! 💙\nמעכשיו תקבלו כאן תקצירים של כל הכתבות הכי חשובות על הכחולים."
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                 json={"chat_id": chat_id, "text": welcome_msg})
            
            with open(sub_file, 'w') as f:
                for s in subs: f.write(s + "\n")
    except Exception as e:
        print(f"⚠️ שגיאה בבדיקת מנויים: {e}")
    
    return list(subs)

def get_full_article_text(url):
    """שואב את תוכן הכתבה בצורה נקייה"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=25)
        soup = BeautifulSoup(response.content, 'html.parser')
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'button']): s.decompose()
        text_blocks = soup.find_all(['p', 'h1', 'h2', 'h3'])
        full_text = " ".join([t.get_text().strip() for t in text_blocks if len(t.get_text()) > 25])
        return full_text
    except: return ""

def get_available_models():
    """מוודא אילו מודלים פתוחים ב-API למניעת שגיאות 404"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        models.sort(key=lambda x: '1.5-flash' not in x)
        return models
    except: return ["models/gemini-1.5-flash"]

def get_ai_summary(text, models, recent_summaries):
    """מפיק תקציר חכם עם מניעת כפילויות"""
    if not text or len(text) < 100: return None
    summaries_context = "\n".join([f"- {s}" for s in recent_summaries])
    
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Analyze the article. Is it PRIMARILY about Hapoel Petah Tikva? If not, return ONLY: SKIP\n"
        f"2. Compare this news to these recent updates:\n{summaries_context}\n"
        "3. If this news covers the exact same event/result (win/loss/draw) already mentioned, return ONLY: DUPLICATE\n"
        "4. Otherwise, write a 3-sentence Hebrew summary. \n"
        "   - Tone: Casual, friend-to-friend, NO greetings (No 'Hi', No 'Friends').\n"
        "   - Mandatory: Focus on the result and the impact on Hapoel Petah Tikva.\n"
        "\n"
        "### ARTICLE TEXT ###\n"
        f"{text[:3000]}"
    )
    
    payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]}
    
    for model_path in models:
        for version in ['v1beta', 'v1']:
            try:
                url = f"https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(url, json=payload, timeout=15)
                data = response.json()
                if response.status_code == 200 and 'candidates' in data:
                    res = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    if "SKIP" in res.upper() or "DUPLICATE" in res.upper(): return "REJECTED"
                    return res
            except: continue
    return None

def main():
    print("🚀 סריקה התחילה (גרסת הזהב)...", flush=True)
    subscribers = get_subscribers()
    models = get_available_models()
    
    db_file = "seen_links.txt"
    summary_db = "recent_summaries.txt"
    if not os.path.exists(db_file): open(db_file, 'w').close()
    if not os.path.exists(summary_db): open(summary_db, 'w', encoding='utf-8').close()
        
    with open(db_file, 'r') as f: history = f.read().splitlines()
    with open(summary_db, 'r', encoding='utf-8') as f: recent_summaries = f.read().splitlines()[-15:]

    hapoel_keys = ["הפועל פתח תקווה", "הפועל פתח-תקווה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]
    new_found = 0

    for feed_url in RSS_FEEDS:
        print(f"📡 בודק פיד: {feed_url}", flush=True)
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link, title = entry.link, entry.title
            
            # סנן תאריך (7 ימים)
            published = entry.get('published_parsed')
            if published:
                dt_published = datetime.fromtimestamp(calendar.timegm(published))
                if datetime.now() - dt_published > timedelta(days=7): continue

            if link in history or title in history: continue
            
            content = get_full_article_text(link)
            content_lower = content.lower()
            is_official = "hapoelpt.com" in link
            is_in_title = any(key in title.lower() for key in hapoel_keys)
            count_in_body = sum(content_lower.count(key) for key in hapoel_keys)
            
            # לוגיקת החלטה אם לבדוק את הכתבה
            if is_official or is_in_title or count_in_body >= 2 or (count_in_body == 1 and len(content) < 600):
                print(f"🎯 מעבד כתבה: {title}", flush=True)
                summary = get_ai_summary(content, models, recent_summaries)
                
                if summary == "REJECTED":
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    continue

                if summary:
                    header = "**יש עדכון חדש על הפועל 💙**"
                    msg = f"{header}\n\n{summary}\n\n🔗 [לכתבה המלאה]({link})"
                    
                    for cid in subscribers:
                        try:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                         json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"})
                        except: pass
                    
                    with open(db_file, 'a') as f: f.write(link + "\n" + title + "\n")
                    with open(summary_db, 'a', encoding='utf-8') as f: f.write(summary.replace("\n", " ") + "\n")
                    new_found += 1
                    time.sleep(5)

    print(f"🏁 סיום. נשלחו {new_found} עדכונים.", flush=True)

if __name__ == "__main__":
    main()
