import feedparser
import requests
import os
import time
import sys
import random
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlunparse

# הגדרה שמכריחה את פייתון להוציא לוגים מיד (חשוב ל-GitHub Actions)
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות ליבה (Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# --- הגדרות סביבת עבודה (Toggle) ---
# False = הודעות מגיעות רק אליך (אדמין) לצרכי בדיקה
# True = הודעות נשלחות לכל מי שרשום בקובץ subscribers.txt
BROADCAST_MODE = True 

# --- סגל שחקנים (מעודכן לפי 365Scores - כולל ירין לוי, גולאני וגושה) ---
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "נועם כהן", "בוני", "דיארה"]

PLAYER_MAP = { 
    "Omer Katz": "עומר כץ", 
    "Orel Dgani": "אוראל דגני", 
    "Nadav Niddam": "נדב נידם", 
    "Yonatan Cohen": "יונתן כהן", 
    "Roee David": "רועי דוד", 
    "Itay Rotman": "איתי רוטמן", 
    "Alex Moussounda": "מוסונדה", 
    "Mark Costa": "קוסטה", 
    "Shavit Mazal": "שביט מזל", 
    "Andrade Euclides Claye": "קליי", 
    "Chipuoka Songa": "סונגה", 
    "Tomer Altman": "אלטמן", 
    "Dror Nir": "דרור ניר", 
    "Shahar Rosen": "שחר רוזן", 
    "Idan Cohen": "עידן כהן",
    "Noam Cohen": "נועם כהן", 
    "Boni Amanis": "בוני", 
    "Fortune Diarra": "דיארה",
    "Matan Gosha": "מתן גושה", 
    "Yarin Levi": "ירין לוי", 
    "Daniel Joulani": "דניאל גולאני"
}

# --- מאגר פוסטרים (6 פוסטרים שונים לרוטציה) ---
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# --- שירי ניצחון להודעות סיום משחק ---
WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# --- לוח משחקים ידני מלא (עד סוף העונה - גיבוי ל-API) ---
BACKUP_SCHEDULE = {
    "2026-04-18": "הפועל באר שבע",
    "2026-04-25": "הפועל תל אביב",
    "2026-04-28": "בית\"ר ירושלים",
    "2026-05-02": "מכבי חיפה",
    "2026-05-05": "מכבי תל אביב",
    "2026-05-09": "הפועל באר שבע",
    "2026-05-12": "הפועל תל אביב",
    "2026-05-16": "מכבי חיפה",
    "2026-05-19": "בית\"ר ירושלים",
    "2026-05-23": "מכבי תל אביב"
}

# --- תרגום שמות קבוצות מלעז לעברית ---
TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה", 
    "Maccabi Tel Aviv": "מכבי תל אביב", 
    "Hapoel Beer Sheva": "הפועל באר שבע", 
    "Beitar Jerusalem": "בית\"ר ירושלים",
    "Maccabi Bnei Reineh": "מכבי בני ריינה", 
    "Ironi Tiberias": "עירוני טבריה",
    "Bnei Sakhnin": "בני סכנין", 
    "M.S. Ashdod": "מ.ס. אשדוד", 
    "Hapoel Tel Aviv": "הפועל תל אביב", 
    "Hapoel Haifa": "הפועל חיפה", 
    "Maccabi Netanya": "מכבי נתניה", 
    "Hapoel Jerusalem": "הפועל ירושלים",
    "Ironi Kiryat Shmona": "עירוני קרית שמונה", 
    "Maccabi Petah Tikva": "מכבי פתח תקווה",
    "Hapoel Petah Tikva": "הפועל פתח תקווה"
}

# --- הגדרות סריקה וחיפוש ---
HAPOEL_KEYS = ["הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת", "מלאבס", "הכחולים", "הפועל מבנה"]

RSS_FEEDS = [
    "https://www.hapoelpt.com/blog-feed.xml",
    "https://news.google.com/rss/search?q=הפועל+פתח+תקווה&hl=he&gl=IL&ceid=IL:he",
    "https://rss.walla.co.il/feed/2", # תוקן ל-2 (ספורט) במקום 3 (כלכלה)
    "https://www.one.co.il/cat/rss/",
    "https://www.sport5.co.il/Public/Rss/Rss.aspx?FolderID=64",
    "https://www.ynet.co.il/Integration/StoryRss3.xml"
]

RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7'
}

# --- פונקציות עזר ---

def get_israel_time():
    """מחזיר את הזמן הנוכחי בישראל"""
    return datetime.utcnow() + timedelta(hours=3)

def clean_url(url):
    """מנקה פרמטרים מיותרים מלינקים תוך שמירה על מזהי כתבה קריטיים (docID)"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        new_params = {}
        
        # שמירה על פרמטרים קריטיים לאתרים ספציפיים כדי למנוע כפילויות שגויות
        if "sport5.co.il" in url:
            if "docID" in params: 
                new_params["docID"] = params["docID"]
            if "FolderID" in params: 
                new_params["FolderID"] = params["FolderID"]
        elif "sport1.maariv.co.il" in url or "sport1.co.il" in url:
            # בספורט 1 המזהה נמצא בתוך נתיב הלינק, לכן נחזיר את הקישור ללא פרמטרים בכלל
            return url.split('?')[0]
        elif "hapoelpt.com" in url:
            return url # לא נוגעים בלינקים של האתר הרשמי
            
        if not new_params:
            return url.split('?')[0]
            
        new_query = "&".join([f"{k}={v[0]}" for k, v in new_params.items()])
        return urlunparse(parsed._replace(query=new_query))
    except:
        return url.split('?')[0]

def send_telegram(text, method="sendMessage", payload=None):
    """שולח הודעה לטלגרם - תומך בשידור לכל המנויים או רק לאדמין"""
    recipients = [ADMIN_ID]
    if BROADCAST_MODE and os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r", encoding='utf-8') as f:
            recipients.extend([line.strip() for line in f if line.strip()])
    
    recipients = list(set(recipients)) # הסרת כפילויות
    
    overall_status = True
    for chat_id in recipients:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
        curr_payload = payload.copy() if payload else {}
        curr_payload["chat_id"] = chat_id
        
        if method in ["sendMessage", "sendPhoto"]:
            curr_payload["parse_mode"] = "Markdown"
        if "text" not in curr_payload and text:
            curr_payload["text"] = text
            
        try:
            # שימוש ב-curr_payload המתוקן למניעת NameError
            r = requests.post(url, json=curr_payload, timeout=25)
            if r.status_code != 200: 
                overall_status = False
        except:
            overall_status = False
            
    return overall_status

def get_ai_response(prompt):
    """פונה ל-Gemini API לקבלת טקסט מעובד"""
    if not GEMINI_API_KEY: return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: 
        return None

def extract_article_data(url):
    """מחלץ תוכן טקסטואלי ותמונה מכתבה"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=15, allow_redirects=True)
        soup = BeautifulSoup(resp.content, 'html.parser')
        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image: 
            image = og_image["content"]
        
        # סינון תמונות לוגו של גוגל
        if image and ("googleusercontent" in image or "google.com/logos" in image): 
            image = None
            
        # זיהוי גוף הכתבה באתרים השונים
        container = (soup.find('div', class_='article-body') or 
                     soup.find('div', class_='article-content') or 
                     soup.find('article') or 
                     soup.find('div', id='article-content') or 
                     soup.find('div', class_='content'))
                     
        if container:
            content = " ".join([el.get_text() for el in container.find_all(['p', 'h1', 'h2', 'h3'])])
        else:
            content = " ".join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2'])])
            
        return content, image, resp.url
    except: 
        return "", None, url

# --- לוגיקה מרכזית ---
def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    current_week = now_il.strftime('%Y-%U')
    print(f"--- תחילת ריצה: {now_il.strftime('%H:%M:%S')} ---", flush=True)

    # וידוא קבצים מערכת
    for f in ["seen_links.txt", "task_log.txt", "recent_summaries.txt", "schedule.json"]:
        if not os.path.exists(f): 
            open(f, 'a', encoding='utf-8').close()
    
    with open("seen_links.txt", 'r', encoding='utf-8') as f: history = set(line.strip() for line in f)
    with open("task_log.txt", 'r', encoding='utf-8') as f: tasks = f.read()
