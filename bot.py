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

# הגדרה שמכריחה את פייתון להוציא לוגים מיד - קריטי ל-GitHub Actions
sys.stdout.reconfigure(encoding='utf-8')

# ⚠️ חבילה חיצונית לפענוח לינקים של Google News
# יש להוסיף ל-requirements.txt: googlenewsdecoder
try:
    from googlenewsdecoder import gnewsdecoder
    HAS_GNEWS_DECODER = True
except ImportError:
    HAS_GNEWS_DECODER = False
    print("WARN: googlenewsdecoder לא מותקן - יש להוסיף ל-requirements.txt!", flush=True)

# =====================================================
# --- הגדרות ליבה (Secrets) ---
# =====================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

ADMIN_ID = "425605110"
TEAM_ID = "5199"
RAPIDAPI_HOST = "sportapi7.p.rapidapi.com"
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# 🔄 מודל Gemini עדכני (1.5 הוצא משימוש!)
# אופציות: gemini-2.5-flash-lite (זול ומהיר), gemini-2.5-flash (מאוזן), gemini-2.5-pro (חזק)
GEMINI_MODEL = "gemini-2.5-flash-lite"

# False = הודעות מגיעות רק אליך (אדמין) לצרכי בדיקה
# True  = הודעות נשלחות לכל המנויים
BROADCAST_MODE = True

# מצבי דיבוג
DEBUG_VERBOSE = True
DEBUG_GEMINI = True

# =====================================================
# --- סגל שחקנים ומאמן ---
# =====================================================
DEFAULT_PLAYERS = [
    "עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד",
    "קוסטה", "שביט מזל", "נועם כהן", "בוני", "דיארה"
]

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

# =====================================================
# --- פוסטרים ושירי ניצחון ---
# =====================================================
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# =====================================================
# --- לוח משחקים גיבוי ---
# =====================================================
BACKUP_SCHEDULE = {
    "2026-04-18": "הפועל באר שבע",
    "2026-04-25": "הפועל תל אביב",
    "2026-04-28": 'בית"ר ירושלים',
    "2026-05-02": "מכבי חיפה",
    "2026-05-05": "מכבי תל אביב",
    "2026-05-09": "הפועל באר שבע",
    "2026-05-12": "הפועל תל אביב",
    "2026-05-16": "מכבי חיפה",
    "2026-05-19": 'בית"ר ירושלים',
    "2026-05-23": "מכבי תל אביב"
}

TEAM_TRANSLATION = {
    "Maccabi Haifa": "מכבי חיפה",
    "Maccabi Tel Aviv": "מכבי תל אביב",
    "Hapoel Beer Sheva": "הפועל באר שבע",
    "Beitar Jerusalem": 'בית"ר ירושלים',
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

# =====================================================
# --- מילות מפתח לזיהוי רלוונטיות ---
# =====================================================
HAPOEL_KEYS = [
    # שם הקבוצה - גרסאות שונות
    "הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת",
    "הפועל פ'ת", "הפועל פת", "הפועל מבנה", "מלאבס", "הכחולים מפ\"ת",
    "hapoel petah", "hapoel p.t",
    # שמות שחקנים מרכזיים
    "אוראל דגני", "עומר כץ", "נדב נידם", "יונתן כהן",
    "מתן גושה", "ירין לוי", "דניאל גולאני", "ירדן שועה",
    "שביט מזל", "מארק קוסטה", "פורטונה דיארה", "בוני אמאניס",
    "בוני אמיאן", "אור ישראלוב",
    # מאמן נוכחי
    "עומר פרץ",
]

PT_HINTS = ["פ\"ת", "פתח תקווה", "פתח תקוה", "פתח-תקוה", "מלאבס"]

# =====================================================
# --- מקורות RSS ---
# =====================================================
RSS_SOURCES = [
    {
        "name": 'האתר הרשמי - הפועל פ"ת',
        "url": "https://www.hapoelpt.com/blog-feed.xml",
        "is_official": True,
        "is_google": False,
        "domain_filter": None
    },
    {
        "name": "וואלה - כדורגל ישראלי",
        "url": "https://rss.walla.co.il/feed/156",
        "is_official": False,
        "is_google": False,
        "domain_filter": "walla.co.il"
    },
    {
        "name": "ווינט ספורט",
        "url": "https://www.ynet.co.il/Integration/StoryRss3.xml",
        "is_official": False,
        "is_google": False,
        "domain_filter": "ynet.co.il"
    },
    {
        "name": "ספורט5 - גוגל",
        "url": "https://news.google.com/rss/search?q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%A4%D7%AA%D7%97+%D7%AA%D7%A7%D7%95%D7%95%D7%94%22+site:sport5.co.il&hl=he&gl=IL&ceid=IL:he",
        "is_official": False,
        "is_google": True,
        "domain_filter": "sport5.co.il"
    },
    {
        "name": "מעריב ספורט1 - גוגל",
        "url": "https://news.google.com/rss/search?q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%A4%D7%AA%D7%97+%D7%AA%D7%A7%D7%95%D7%95%D7%94%22+site:sport1.maariv.co.il&hl=he&gl=IL&ceid=IL:he",
        "is_official": False,
        "is_google": True,
        "domain_filter": "sport1.maariv.co.il"
    },
    {
        "name": "ONE - גוגל",
        "url": "https://news.google.com/rss/search?q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%A4%D7%AA%D7%97+%D7%AA%D7%A7%D7%95%D7%95%D7%94%22+site:one.co.il&hl=he&gl=IL&ceid=IL:he",
        "is_official": False,
        "is_google": True,
        "domain_filter": "one.co.il"
    },
    {
        "name": "גוגל - כללי (fallback)",
        "url": "https://news.google.com/rss/search?q=%22%D7%94%D7%A4%D7%95%D7%A2%D7%9C+%D7%A4%D7%AA%D7%97+%D7%AA%D7%A7%D7%95%D7%95%D7%94%22&hl=he&gl=IL&ceid=IL:he",
        "is_official": False,
        "is_google": True,
        "domain_filter": None
    }
]

ALLOWED_DOMAINS = [
    "hapoelpt.com", "one.co.il", "walla.co.il",
    "ynet.co.il", "sport5.co.il", "sport1.maariv.co.il", "sport1.co.il"
]

RSS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Referer': 'https://www.google.com/'
}


# =====================================================
# --- פונקציות עזר ---
# =====================================================

def get_israel_time():
    return datetime.utcnow() + timedelta(hours=3)


def decode_google_news_url(google_url):
    """
    🔓 מפענח לינקים של Google News באמצעות ספריית googlenewsdecoder.
    מחזיר את ה-URL האמיתי או None אם נכשל.
    """
    if "news.google.com" not in google_url:
        return google_url

    if not HAS_GNEWS_DECODER:
        return None

    try:
        result = gnewsdecoder(google_url, interval=1)
        # הספרייה מחזירה dict עם status ו-decoded_url
        if result and result.get('status'):
            decoded = result.get('decoded_url', '')
            if decoded and "news.google.com" not in decoded:
                return decoded
        return None
    except Exception as e:
        if DEBUG_VERBOSE:
            print(f"DEBUG: שגיאה בפענוח Google News URL: {e}", flush=True)
        return None


def normalize_url(url):
    """ממיר URL לצורה אחידה למניעת כפילויות"""
    try:
        url = url.replace("https://svcamz.", "https://www.")
        url = url.replace("//amp.", "//www.")
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        params = parse_qs(parsed.query)
        keep_params = {}

        if "sport5.co.il" in domain:
            if "docID" in params:
                keep_params["docID"] = params["docID"]
        elif "sport1.maariv.co.il" in domain or "sport1.co.il" in domain:
            return parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
        elif "hapoelpt.com" in domain:
            return url.split('?')[0].rstrip("/")
        elif "walla.co.il" in domain or "ynet.co.il" in domain:
            return parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")
        elif "one.co.il" in domain:
            return parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")

        if not keep_params:
            return parsed.scheme + "://" + parsed.netloc + parsed.path.rstrip("/")

        new_query = "&".join([f"{k}={v[0]}" for k, v in keep_params.items()])
        return urlunparse(parsed._replace(query=new_query, fragment=""))
    except:
        return url.split('?')[0]


def is_relevant_to_hapoel_pt(text):
    """
    בודק אם הטקסט מתייחס להפועל פ"ת.
    מחזיר tuple: (האם רלוונטי, סיבה)
    """
    if not text:
        return False, "טקסט ריק"
    text_lower = text.lower()

    for key in HAPOEL_KEYS:
        if key.lower() in text_lower:
            return True, f"זוהה: '{key}'"

    if "הפועל" in text:
        for hint in PT_HINTS:
            if hint.lower() in text_lower:
                return True, f"זוהה צירוף: 'הפועל' + '{hint}'"

    return False, "לא נמצאה התאמה"


def get_google_entry_source_domain(entry):
    """מנסה לגלות מאיזה אתר באה הכתבה מ-RSS של גוגל"""
    src = entry.get('source', None)
    if src:
        if isinstance(src, dict):
            url = src.get('url', '') or src.get('href', '')
            if url:
                return url.lower()
            title = src.get('title', '') or src.get('value', '')
            return title.lower() if title else ""
        if isinstance(src, str):
            return src.lower()

    if 'source_detail' in entry:
        sd = entry['source_detail']
        if isinstance(sd, dict):
            url = sd.get('url', '') or sd.get('href', '')
            return url.lower() if url else ""

    title = entry.get('title', '')
    if ' - ' in title:
        suffix = title.rsplit(' - ', 1)[-1].lower()
        return suffix

    return ""


def matches_allowed_domain_from_google(entry, domain_filter=None):
    """בודק אם כתבה מ-Google News היא מאתר מורשה"""
    src_text = get_google_entry_source_domain(entry)

    if domain_filter:
        domain_keyword = domain_filter.split('.')[0]
        if domain_keyword.lower() in src_text:
            return True, src_text
        return False, src_text

    for allowed in ALLOWED_DOMAINS:
        keyword = allowed.split('.')[0].lower()
        if keyword in src_text:
            return True, src_text

    return False, src_text


def send_telegram(text, method="sendMessage", payload=None):
    """שולח הודעה לטלגרם"""
    recipients = [ADMIN_ID]
    if BROADCAST_MODE and os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r", encoding='utf-8') as f:
            recipients.extend([line.strip() for line in f if line.strip()])
    recipients = list(set(recipients))

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
            r = requests.post(url, json=curr_payload, timeout=25)
            if r.status_code != 200:
                print(f"DEBUG Telegram error {r.status_code}: {r.text[:200]}", flush=True)
                overall_status = False
        except Exception as e:
            print(f"DEBUG Telegram exception: {e}", flush=True)
            overall_status = False

    return overall_status


def call_gemini(prompt, timeout=30, label="generic"):
    """קריאה ל-Gemini API עם המודל החדש"""
    if not GEMINI_API_KEY:
        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] ⚠️ אין מפתח API!", flush=True)
        return None

    if DEBUG_GEMINI:
        prompt_preview = prompt[:200].replace('\n', ' ')
        print(f"  [GEMINI:{label}] 📤 שולח (אורך: {len(prompt)}): {prompt_preview}...", flush=True)

    # ⚠️ מודל מעודכן + v1 (לא v1beta)
    url_g = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    try:
        res = requests.post(
            url_g,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout
        )

        if res.status_code != 200:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ❌ HTTP {res.status_code}: {res.text[:300]}", flush=True)
            return None

        data = res.json()

        if 'candidates' not in data or not data['candidates']:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ⚠️ אין candidates: {json.dumps(data, ensure_ascii=False)[:300]}", flush=True)
            return None

        candidate = data['candidates'][0]
        finish_reason = candidate.get('finishReason', '')
        if finish_reason and finish_reason not in ['STOP', 'MAX_TOKENS']:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ⚠️ finishReason: {finish_reason}", flush=True)

        if 'content' not in candidate or 'parts' not in candidate['content']:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ⚠️ אין content בcandidate", flush=True)
            return None

        result = candidate['content']['parts'][0]['text'].strip()

        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] 📥 קיבל ({len(result)} תווים): {result[:300]}", flush=True)

        return result

    except Exception as e:
        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] ❌ Exception: {e}", flush=True)
        return None


def get_ai_summary(title, content, is_official=False):
    """מחזיר תקציר עיתונאי של הכתבה"""
    if not content and not title:
        return None

    if len(content) < 80:
        if DEBUG_VERBOSE:
            print(f"  תוכן קצר מאוד ({len(content)} תווים), נשתמש בכותרת", flush=True)
        return title if title else None

    if is_official:
        prompt = (
            "אתה עיתונאי ספורט. סכם את הודעת המועדון הבאה ב-3 משפטים ענייניים בסגנון עיתונאי ישיר. "
            "התחל ישר במידע, ללא פתיחות מיותרות כמו 'הכתבה מספרת'. "
            "ודא שמוזכר שם הקבוצה הפועל פתח תקווה לפחות פעם אחת.\n\n"
            f"כותרת: {title}\n\nטקסט: {content[:3000]}\n\n"
            f"החזר רק את התקציר עצמו, ללא טקסט נוסף."
        )
    else:
        prompt = (
            "אתה עיתונאי ספורט. כתוב תקציר עיתונאי של 4-5 משפטים על הכתבה הבאה, "
            "תוך התמקדות בזווית הקשורה להפועל פתח תקווה (גם אם היא לא הנושא הראשי). "
            "הטון צריך להיות מקצועי ומידעי - לא לא-רשמי. "
            "ציין במפורש את שם הקבוצה הפועל פתח תקווה בתקציר.\n\n"
            f"כותרת: {title}\n\nטקסט: {content[:2500]}\n\n"
            f"החזר רק את התקציר עצמו, ללא טקסט נוסף."
        )

    summary = call_gemini(prompt, label="summary")

    if summary and len(summary) > 1000:
        summary = summary[:1000] + "..."

    return summary


def is_duplicate_content(new_title, recent_summaries):
    """בודק עם Gemini אם הכתבה כפולה"""
    if not GEMINI_API_KEY or not recent_summaries.strip() or len(recent_summaries) < 50:
        return False
    prompt = (
        "האם הידיעה החדשה מדווחת על אותו אירוע ספציפי בדיוק כמו אחד מהסיכומים הקודמים? "
        "(לא בנושא דומה אלא בדיוק אותו אירוע). "
        "ענה YES או NO בלבד.\n\n"
        f"כותרת חדשה: {new_title}\n\n"
        f"סיכומים קודמים:\n{recent_summaries[-1000:]}"
    )
    answer = call_gemini(prompt, timeout=20, label="dup-check")
    return "YES" in (answer or "NO").upper()


def extract_article_data(url):
    """מחלץ תוכן ותמונה מכתבה"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=18, allow_redirects=True)
        final_url = resp.url
        soup = BeautifulSoup(resp.content, 'html.parser')

        # חילוץ תמונה
        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            if not any(bad in img_url for bad in ["googleusercontent", "google.com/logos", "placeholder", "logo"]):
                image = img_url

        domain = urlparse(final_url).netloc.lower()
        container = None

        if "one.co.il" in domain:
            container = (soup.find('div', class_='article-body') or
                         soup.find('div', {'id': 'articleText'}) or
                         soup.find('article'))
        elif "walla.co.il" in domain:
            container = (soup.find('div', class_='article-body') or
                         soup.find('div', {'data-cy': 'article-body'}) or
                         soup.find('article'))
        elif "sport5.co.il" in domain:
            container = (soup.find('div', class_='article-body') or
                         soup.find('div', class_='the-article') or
                         soup.find('div', {'id': 'articleContent'}) or
                         soup.find('article'))
        elif "sport1" in domain or "maariv" in domain:
            container = (soup.find('div', class_='article-body') or
                         soup.find('div', class_='article-text') or
                         soup.find('div', {'id': 'articleBody'}) or
                         soup.find('article'))
        elif "ynet.co.il" in domain:
            container = (soup.find('div', class_='article-body') or
                         soup.find('span', class_='text_editor_paragraph') or
                         soup.find('article'))
        elif "hapoelpt.com" in domain:
            container = (soup.find('div', class_='blog-post-content') or
                         soup.find('div', class_='sqs-layout') or
                         soup.find('article'))
        else:
            container = soup.find('article') or soup.find('div', class_='article-body')

        content = ""
        if container:
            paragraphs = container.find_all(['p', 'h1', 'h2', 'h3'])
            content = " ".join([el.get_text(separator=" ").strip() for el in paragraphs if el.get_text().strip()])

        if len(content) < 100:
            all_p = soup.find_all('p')
            content = " ".join([p.get_text(separator=" ").strip() for p in all_p if len(p.get_text()) > 30])

        content = " ".join(content.split())
        return content, image, final_url

    except Exception as e:
        print(f"DEBUG extract error ({url[:50]}): {e}", flush=True)
        return "", None, url


def is_domain_allowed(url):
    try:
        domain = urlparse(url).netloc.lower()
        return any(allowed in domain for allowed in ALLOWED_DOMAINS)
    except:
        return False


# =====================================================
# --- לוגיקה מרכזית ---
# =====================================================

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')
    current_week = now_il.strftime('%Y-%U')

    print(f"=== תחילת ריצה: {now_il.strftime('%d/%m/%Y %H:%M:%S')} ===", flush=True)
    print(f"DEBUG: GEMINI_API_KEY={'קיים' if GEMINI_API_KEY else 'חסר!'}", flush=True)
    print(f"DEBUG: TELEGRAM_TOKEN={'קיים' if TELEGRAM_TOKEN else 'חסר!'}", flush=True)
    print(f"DEBUG: RAPIDAPI_KEY={'קיים' if RAPIDAPI_KEY else 'חסר!'}", flush=True)
    print(f"DEBUG: GEMINI_MODEL={GEMINI_MODEL}", flush=True)
    print(f"DEBUG: googlenewsdecoder מותקן? {HAS_GNEWS_DECODER}", flush=True)

    # וידוא קיום קבצי מערכת
    for fname in ["seen_links.txt", "task_log.txt", "recent_summaries.txt", "schedule.json"]:
        if not os.path.exists(fname):
            open(fname, 'a', encoding='utf-8').close()

    with open("seen_links.txt", 'r', encoding='utf-8') as f:
        history = set(line.strip() for line in f if line.strip())
    with open("task_log.txt", 'r', encoding='utf-8') as f:
        tasks = f.read()
    with open("recent_summaries.txt", 'r', encoding='utf-8') as f:
        recent_sums = f.read()

    print(f"DEBUG: {len(history)} לינקים בהיסטוריה", flush=True)

    # =====================================================
    # 1. פינת ההיסטוריה - יום ד' שעה 12
    # =====================================================
    if now_il.weekday() == 2 and now_il.hour == 12 and f"history_{today_str}" not in tasks:
        fact = call_gemini(
            "כתוב 2 עובדות היסטוריות קצרות ומעניינות על הפועל פתח תקווה. "
            "אחת משנות ה-50 ואחת משנות ה-90. הוסף אימוג'ים מתאימים.",
            label="history-fact"
        )
        if fact and send_telegram(f"📜 *פינת ההיסטוריה הכחולה:* \n\n{fact}"):
            with open("task_log.txt", 'a', encoding='utf-8') as f:
                f.write(f"history_{today_str}\n")

    # =====================================================
    # 2. עדכון לוח משחקים
    # =====================================================
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    local_schedule = {}

    try:
        if os.path.exists("schedule.json") and os.path.getsize("schedule.json") > 0:
            with open("schedule.json", 'r', encoding='utf-8') as f:
                local_schedule = json.load(f)
    except:
        pass

    if f"sched_update_{current_week}" not in tasks or not local_schedule:
        print("DEBUG: מעדכן לוח משחקים...", flush=True)
        try:
            r_sched = requests.get(
                f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/10",
                headers=headers_api, timeout=15
            ).json()

            if 'events' in r_sched and r_sched['events']:
                new_sched = {}
                for ev in r_sched['events']:
                    d_key = (datetime.fromtimestamp(ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
                    opp_raw = (ev['awayTeam']['name'] if str(ev['homeTeam']['id']) == TEAM_ID
                               else ev['homeTeam']['name'])
                    new_sched[d_key] = TEAM_TRANSLATION.get(opp_raw, opp_raw)
                with open("schedule.json", 'w', encoding='utf-8') as f:
                    json.dump(new_sched, f, ensure_ascii=False)
                with open("task_log.txt", 'a', encoding='utf-8') as f:
                    f.write(f"sched_update_{current_week}\n")
                local_schedule = new_sched
                print(f"DEBUG: לוח עודכן עם {len(new_sched)} משחקים", flush=True)
            else:
                local_schedule.update(BACKUP_SCHEDULE)
        except Exception as e:
            print(f"DEBUG schedule error: {e}", flush=True)
            local_schedule.update(BACKUP_SCHEDULE)

    # =====================================================
    # 3. ניהול יום משחק
    # =====================================================
    if today_str in local_schedule:
        opp_heb = local_schedule[today_str]
        print(f"DEBUG: משחק היום נגד {opp_heb}", flush=True)

        if now_il.hour >= 11 and f"matchday_{today_str}" not in tasks:
            md_text = (
                f"MatchDay Hapoel 💙\n"
                f"הפועל שלנו עולה היום נגד *{opp_heb}*.\n"
                f"יאללה הפועל, לתת הכל בשביל הסמל! 🚀\n\n"
                f"כשחקנים למגרש עולים - כל האוהדים שריםםםם\n"
                f"הפועל עולה עולההה, הפועל, הפועל עולהה 💙"
            )
            if send_telegram(None, "sendPhoto", {"photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                with open("task_log.txt", 'a', encoding='utf-8') as f:
                    f.write(f"matchday_{today_str}\n")

        if now_il.hour >= 15 and f"betting_{today_str}" not in tasks:
            poll_payload = {
                "question": "זמן להמר, מי תנצח היום?",
                "options": ["ניצחון כחול 💙", "תיקו", "הפסד 💔"],
                "is_anonymous": False
            }
            if send_telegram(None, "sendPoll", poll_payload):
                with open("task_log.txt", 'a', encoding='utf-8') as f:
                    f.write(f"betting_{today_str}\n")

        if now_il.hour >= 18 and f"final_{today_str}" not in tasks:
            try:
                r_last = requests.get(
                    f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/last/0",
                    headers=headers_api, timeout=15
                ).json()

                if r_last.get('events'):
                    last_ev = r_last['events'][0]
                    ev_date = (datetime.fromtimestamp(last_ev['startTimestamp']) + timedelta(hours=3)).strftime('%Y-%m-%d')
                    if ev_date == today_str:
                        status_type = last_ev.get('status', {}).get('type', '')
                        if status_type in ['finished', 'FT', 'ended']:
                            is_home = str(last_ev['homeTeam']['id']) == TEAM_ID
                            my_score = last_ev['homeScore']['display'] if is_home else last_ev['awayScore']['display']
                            opp_score = last_ev['awayScore']['display'] if is_home else last_ev['homeScore']['display']

                            chant = random.choice(WIN_CHANTS)
                            res_txt = f"{chant}\n\n*סיום המשחק:* הפועל {my_score}, {opp_heb} {opp_score}."
                            markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": ONE_TABLE_URL}]]}
                            if send_telegram(res_txt, payload={"text": res_txt, "reply_markup": markup}):
                                with open("task_log.txt", 'a', encoding='utf-8') as f:
                                    f.write(f"final_{today_str}\n")

                            if f"mvp_{today_str}" not in tasks:
                                players_heb = DEFAULT_PLAYERS[:]
                                try:
                                    event_id = last_ev.get('id')
                                    if event_id:
                                        r_lineup = requests.get(
                                            f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups",
                                            headers=headers_api, timeout=10
                                        ).json()
                                        side = 'home' if is_home else 'away'
                                        players_raw = r_lineup.get(side, {}).get('players', [])
                                        if players_raw:
                                            players_heb = [
                                                PLAYER_MAP.get(p.get('player', {}).get('name', ''),
                                                               p.get('player', {}).get('name', ''))
                                                for p in players_raw[:10]
                                            ]
                                except Exception as e:
                                    print(f"DEBUG lineup error: {e}", flush=True)

                                send_telegram(None, "sendPoll", {
                                    "question": "מי ה-MVP של המשחק?",
                                    "options": players_heb[:10],
                                    "is_anonymous": False
                                })
                                with open("task_log.txt", 'a', encoding='utf-8') as f:
                                    f.write(f"mvp_{today_str}\n")
            except Exception as e:
                print(f"DEBUG match result error: {e}", flush=True)

    # =====================================================
    # 4. סריקת כתבות RSS
    # =====================================================
    processed_count = 0
    MAX_ARTICLES_PER_RUN = 8

    stats = {
        "total_seen": 0,
        "filtered_already_seen": 0,
        "filtered_too_old": 0,
        "filtered_wrong_domain": 0,
        "filtered_not_relevant": 0,
        "filtered_duplicate_content": 0,
        "filtered_no_summary": 0,
        "filtered_decode_failed": 0,
        "sent": 0,
        "errors": 0
    }

    print(f"\nDEBUG: === סריקת כתבות ({len(RSS_SOURCES)} מקורות) ===", flush=True)

    for source in RSS_SOURCES:
        if processed_count >= MAX_ARTICLES_PER_RUN:
            break

        feed_url = source["url"]
        source_name = source["name"]
        is_official = source.get("is_official", False)
        is_google = source.get("is_google", False)
        domain_filter = source.get("domain_filter")

        print(f"\nDEBUG: --- {source_name} ---", flush=True)

        try:
            r_rss = requests.get(feed_url, headers=RSS_HEADERS, timeout=20)
            print(f"DEBUG: HTTP {r_rss.status_code} ({len(r_rss.content)} bytes)", flush=True)
            feed = feedparser.parse(r_rss.content)

            if not feed.entries:
                print(f"DEBUG: ⚠️ פיד ריק! (bozo={feed.bozo})", flush=True)
                if feed.bozo and DEBUG_VERBOSE:
                    print(f"DEBUG: bozo_exception={feed.bozo_exception}", flush=True)
                continue

            print(f"DEBUG: {len(feed.entries)} כתבות בפיד", flush=True)
            articles_from_source = 0

            for entry in feed.entries[:30]:
                if processed_count >= MAX_ARTICLES_PER_RUN:
                    break
                if articles_from_source >= 3:
                    break

                stats["total_seen"] += 1

                raw_link = entry.get('link', '').strip()
                if not raw_link:
                    continue

                title = entry.get('title', '').strip()
                rss_summary = entry.get('summary', '')

                # ====== טיפול בלינקים מגוגל ======
                if is_google:
                    matches, src_text = matches_allowed_domain_from_google(entry, domain_filter)
                    if not matches:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: ⏭️ אתר לא מורשה: {title[:50]}", flush=True)
                        stats["filtered_wrong_domain"] += 1
                        continue
                    is_rel, reason = is_relevant_to_hapoel_pt(title + " " + rss_summary)
                    if not is_rel:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: ⏭️ לא רלוונטי בכותרת (גוגל): {title[:50]}", flush=True)
                        stats["filtered_not_relevant"] += 1
                        continue
                    # 🔓 פענוח לינק האמיתי דרך googlenewsdecoder
                    if DEBUG_VERBOSE:
                        print(f"DEBUG: ✓ רלוונטי בגוגל ({reason}): {title[:55]}", flush=True)
                        print(f"DEBUG:   מפענח לינק...", flush=True)
                    real_link = decode_google_news_url(raw_link)
                    if not real_link:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ⚠️ פענוח נכשל - מדלג", flush=True)
                        stats["filtered_decode_failed"] += 1
                        continue
                    if DEBUG_VERBOSE:
                        print(f"DEBUG:   ✓ פוענח: {real_link[:80]}", flush=True)
                    raw_link = real_link
                else:
                    raw_link = raw_link.replace("https://svcamz.", "https://www.")
                    if domain_filter and domain_filter not in raw_link.lower():
                        stats["filtered_wrong_domain"] += 1
                        continue

                # בדיקת כפילות
                clean_l = normalize_url(raw_link)
                if clean_l in history:
                    stats["filtered_already_seen"] += 1
                    continue

                # בדיקת טריות
                pub_parsed = entry.get('published_parsed')
                if pub_parsed:
                    try:
                        pub_dt = datetime(*pub_parsed[:6])
                        if (now_il - pub_dt) > timedelta(days=5):
                            stats["filtered_too_old"] += 1
                            continue
                    except:
                        pass

                # בדיקת רלוונטיות בכותרת (רק לאתרים שלא מגוגל)
                if not is_google and not is_official:
                    is_rel, reason = is_relevant_to_hapoel_pt(title + " " + rss_summary)
                    if not is_rel:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: ⏭️ לא רלוונטי בכותרת: {title[:60]}", flush=True)
                        stats["filtered_not_relevant"] += 1
                        continue
                    else:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: ✓ רלוונטי בכותרת ({reason}): {title[:60]}", flush=True)

                print(f"DEBUG: 🔍 בודק: {title[:65]}", flush=True)

                # חילוץ תוכן
                content, image, final_url = extract_article_data(raw_link)
                clean_l = normalize_url(final_url)

                if clean_l in history:
                    stats["filtered_already_seen"] += 1
                    continue

                if len(content) < 50:
                    content = rss_summary or title
                    if DEBUG_VERBOSE:
                        print(f"DEBUG:   חילוץ נכשל ({len(content)} תווים), נשתמש ב-summary של ה-RSS", flush=True)

                # בדיקת רלוונטיות בתוכן
                if not is_official:
                    full_text_for_check = title + " " + content[:1500]
                    is_rel, reason = is_relevant_to_hapoel_pt(full_text_for_check)
                    if not is_rel:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ⏭️ לא רלוונטי בתוכן: {title[:60]}", flush=True)
                        stats["filtered_not_relevant"] += 1
                        continue
                    else:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ✓ רלוונטי בתוכן ({reason})", flush=True)

                # כפילות
                if is_duplicate_content(title, recent_sums):
                    print(f"DEBUG:   ⏭️ כפילות תוכן: {title[:60]}", flush=True)
                    stats["filtered_duplicate_content"] += 1
                    continue

                # תקציר
                summary = get_ai_summary(title, content, is_official=is_official)

                if not summary or len(summary) < 15:
                    if is_official:
                        summary = title
                        print(f"DEBUG:   Gemini נכשל - משתמש בכותרת כגיבוי", flush=True)
                    else:
                        print(f"DEBUG:   ⏭️ אין תקציר תקין: {title[:60]}", flush=True)
                        stats["filtered_no_summary"] += 1
                        continue

                # שליחה
                full_msg = f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({clean_l})"
                if image:
                    success = send_telegram(None, "sendPhoto", {"photo": image, "caption": full_msg})
                else:
                    success = send_telegram(full_msg)

                if success:
                    history.add(clean_l)
                    with open("seen_links.txt", 'a', encoding='utf-8') as f:
                        f.write(clean_l + "\n")
                    with open("recent_summaries.txt", 'a', encoding='utf-8') as f:
                        f.write(summary + "|||\n")
                    recent_sums += summary + "|||\n"
                    processed_count += 1
                    articles_from_source += 1
                    stats["sent"] += 1
                    print(f"DEBUG:   ✅ נשלח: {title[:60]}", flush=True)
                    time.sleep(8)
                else:
                    print(f"DEBUG:   ❌ שליחה נכשלה", flush=True)
                    stats["errors"] += 1

        except Exception as e:
            print(f"DEBUG RSS ERROR ({source_name}): {e}", flush=True)
            stats["errors"] += 1

    # ניקוי קבצים
    if len(history) > 500:
        with open("seen_links.txt", 'w', encoding='utf-8') as f:
            f.write("\n".join(list(history)[-400:]) + "\n")

    if len(recent_sums) > 5000:
        with open("recent_summaries.txt", 'w', encoding='utf-8') as f:
            f.write(recent_sums[-3000:])

    # סיכום
    print(f"\n=== סיכום הריצה ===", flush=True)
    print(f"  סך כתבות שנבדקו:    {stats['total_seen']}", flush=True)
    print(f"  כבר נשלחו בעבר:     {stats['filtered_already_seen']}", flush=True)
    print(f"  ישנות מדי:          {stats['filtered_too_old']}", flush=True)
    print(f"  אתר לא מורשה:       {stats['filtered_wrong_domain']}", flush=True)
    print(f"  לא רלוונטי:         {stats['filtered_not_relevant']}", flush=True)
    print(f"  כפילות תוכן:        {stats['filtered_duplicate_content']}", flush=True)
    print(f"  בעיית תקציר:        {stats['filtered_no_summary']}", flush=True)
    print(f"  פענוח לינק נכשל:    {stats['filtered_decode_failed']}", flush=True)
    print(f"  שגיאות:             {stats['errors']}", flush=True)
    print(f"  ✅ נשלחו לטלגרם:    {stats['sent']}", flush=True)
    print(f"=== סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ===", flush=True)


if __name__ == "__main__":
    main()
