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

sys.stdout.reconfigure(encoding='utf-8')

# חבילת פענוח לינקים של Google News
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

# מודל Gemini
# 🆕 שדרוג ל-gemini-2.0-flash - אותה מכסה אבל מודל יותר חכם
# אופציות:
#   "gemini-2.5-flash-lite" - הכי זול אבל מכסה קטנה
#   "gemini-2.0-flash" - מאוזן (מומלץ! ✅)
#   "gemini-2.5-flash" - יותר חזק, אותה מכסה
GEMINI_MODEL = "gemini-2.0-flash"

# =====================================================
# 🎛️  מתג מצב הפעלה
# "ADMIN_ONLY" = הודעות רק אליך (לטסטים)
# "BROADCAST"  = הודעות לכל המנויים (פרודקשן)
# =====================================================
RUN_MODE = "ADMIN_ONLY"

# האם להפעיל את לוגיקת יום המשחק
ENABLE_MATCHDAY_LOGIC = True

# =====================================================
# 🆕 הגדרות חיסכון בטוקני API
# =====================================================
# כמה ימים אחורה מותר ללוח להיות לפני שנעדכן מה-API (גם אם לא נשבר)
SCHEDULE_REFRESH_DAYS = 7

# שעות לפני המשחק לשלוח הודעת הימורים (היה 3 שעות)
HOURS_BEFORE_MATCH_FOR_BETTING = 3

# שעות לפני המשחק לשלוח הודעת MatchDay (בוקר היום)
# נשלח בריצה הראשונה אחרי 11:00 ביום המשחק
MATCHDAY_MIN_HOUR = 11

# כמה דקות אחרי המשחק להמתין לפני בדיקת סיום (משחק כדורגל ~110 דק')
MATCH_DURATION_MINUTES = 110

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

MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# 🆕 תמונות גיבוי לכתבות בלי תמונה - של הפועל פ"ת (לא לוגו של אתר חדשות!)
# כברירת מחדל אנחנו משתמשים בפוסטרים של MatchDay, אבל אפשר לשים כאן תמונות אחרות
# (סמלים, צילומי מגרש, חבורות אוהדים וכו').
# רק להוסיף לינקים ל-imgbb או דומה.
FALLBACK_ARTICLE_IMAGES = MATCHDAY_POSTERS  # כרגע משתמשים באותן תמונות. אפשר להחליף.

WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאללה הפועל, כחול עולה 💙",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# לוח גיבוי - רק במקרה ש-API לא עובד (פורמט: "YYYY-MM-DD": "יריבה")
BACKUP_SCHEDULE = {
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

# מילות מפתח לזיהוי הפועל פ"ת
HAPOEL_KEYS = [
    "הפועל פתח תקווה", "הפועל פתח-תקוה", "הפועל פתח תקוה", "הפועל פ\"ת",
    "הפועל פ'ת", "הפועל פת", "הפועל מבנה", "מלאבס", "הכחולים מפ\"ת",
    "hapoel petah", "hapoel p.t",
    "אוראל דגני", "עומר כץ", "נדב נידם",
    "מתן גושה", "ירין לוי", "דניאל גולאני",
    "שביט מזל", "מארק קוסטה", "פורטונה דיארה", "בוני אמאניס",
    "בוני אמיאן",
]

PT_HINTS = ["פ\"ת", "פתח תקווה", "פתח תקוה", "פתח-תקוה", "מלאבס"]

# 🚫 מכבי פ"ת = הקבוצה היריבה!
MACCABI_PT_KEYS = [
    "מכבי פתח תקווה", "מכבי פתח תקוה", "מכבי פתח-תקוה", "מכבי פ\"ת",
    "מכבי פ'ת", "מכבי פת",
    "maccabi petah",
]

MACCABI_PT_PLAYERS = [
    "אור ישראלוב",
]

# מקורות RSS
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
    """מפענח לינקים של Google News"""
    if "news.google.com" not in google_url:
        return google_url
    if not HAS_GNEWS_DECODER:
        return None
    try:
        result = gnewsdecoder(google_url, interval=1)
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
    """ממיר URL לצורה אחידה"""
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


def is_about_maccabi_pt(text):
    """בודק אם הכתבה היא על מכבי פ"ת"""
    if not text:
        return False, ""
    text_lower = text.lower()

    # 🆕 קודם נבדוק אם הפועל פ"ת מוזכרת בטקסט - אם כן, זה לא חסימה!
    # (יכול להיות כתבה כללית ששתי הקבוצות מוזכרות בה)
    has_hapoel_pt = False
    for hkey in HAPOEL_KEYS[:11]:  # רק שמות הקבוצה הראשיים
        if hkey.lower() in text_lower:
            has_hapoel_pt = True
            break

    # אם הפועל פ"ת מוזכרת - הכתבה עוברת לבדיקות אחרות (לא חוסמים פה)
    if has_hapoel_pt:
        return False, ""

    # רק אם הפועל פ"ת *לא* מוזכרת - בודקים אם זו כתבת מכבי
    for key in MACCABI_PT_KEYS:
        if key.lower() in text_lower:
            return True, f"זוהה: '{key}' (ללא אזכור הפועל פ\"ת)"

    for player in MACCABI_PT_PLAYERS:
        if player.lower() in text_lower:
            return True, f"זוהה שחקן מכבי: '{player}' (ללא אזכור הפועל פ\"ת)"

    return False, ""


def is_relevant_to_hapoel_pt(text):
    """בודק אם הטקסט מתייחס להפועל פ"ת"""
    if not text:
        return False, "טקסט ריק"

    is_maccabi, m_reason = is_about_maccabi_pt(text)
    if is_maccabi:
        return False, f"כתבה על מכבי פ\"ת! ({m_reason})"

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


def get_recipients():
    """מחזיר את רשימת הנמענים לפי מצב הריצה"""
    if RUN_MODE == "ADMIN_ONLY":
        return [ADMIN_ID]
    recipients = [ADMIN_ID]
    if os.path.exists("subscribers.txt"):
        with open("subscribers.txt", "r", encoding='utf-8') as f:
            recipients.extend([line.strip() for line in f if line.strip()])
    return list(set(recipients))


def send_telegram(text, method="sendMessage", payload=None):
    """שולח הודעה לטלגרם"""
    recipients = get_recipients()
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


# 🆕 משתנה גלובלי שמסמן אם נחסמנו ע"י Gemini (חרגנו מהמכסה)
# אם True - נחזיר None לכל הקריאות הבאות בריצה הזו, חוסך זמן וטוקנים
GEMINI_QUOTA_EXCEEDED = False


def call_gemini(prompt, timeout=30, label="generic"):
    """קריאה ל-Gemini API"""
    global GEMINI_QUOTA_EXCEEDED

    if not GEMINI_API_KEY:
        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] ⚠️ אין מפתח API!", flush=True)
        return None

    # 🆕 אם כבר חרגנו מהמכסה - לא נמשיך לנסות
    if GEMINI_QUOTA_EXCEEDED:
        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] ⏭️ דילוג - מכסת Gemini הסתיימה לריצה הזו", flush=True)
        return None

    if DEBUG_GEMINI:
        prompt_preview = prompt[:200].replace('\n', ' ')
        print(f"  [GEMINI:{label}] 📤 שולח (אורך: {len(prompt)}): {prompt_preview}...", flush=True)

    url_g = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    try:
        res = requests.post(
            url_g,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=timeout
        )

        # 🆕 טיפול ב-429 - מכסה הסתיימה
        if res.status_code == 429:
            print(f"  [GEMINI:{label}] 🛑 חריגה ממכסת Gemini! מסמן שלא לנסות שוב בריצה זו.", flush=True)
            GEMINI_QUOTA_EXCEEDED = True
            return None

        if res.status_code != 200:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ❌ HTTP {res.status_code}: {res.text[:300]}", flush=True)
            return None

        data = res.json()

        if 'candidates' not in data or not data['candidates']:
            if DEBUG_GEMINI:
                print(f"  [GEMINI:{label}] ⚠️ אין candidates", flush=True)
            return None

        candidate = data['candidates'][0]
        if 'content' not in candidate or 'parts' not in candidate['content']:
            return None

        result = candidate['content']['parts'][0]['text'].strip()

        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] 📥 קיבל ({len(result)} תווים): {result[:300]}", flush=True)

        return result

    except Exception as e:
        if DEBUG_GEMINI:
            print(f"  [GEMINI:{label}] ❌ Exception: {e}", flush=True)
        return None


def is_article_main_topic_hapoel_pt(title, content):
    """בודק עם Gemini אם הפועל פ"ת היא הנושא העיקרי"""
    if not GEMINI_API_KEY:
        return True

    sample_content = content[:1500] if content else title

    prompt = (
        "האם הכתבה הבאה רלוונטית לאוהדי הפועל פתח תקווה (לא מכבי פתח תקווה!)? "
        "אוהדי הקבוצה רוצים לקבל כתבות על:\n"
        "- כל כתבה שעוסקת בהפועל פתח תקווה (גם אם היא הפסידה / היא קבוצת המשנה בכותרת)\n"
        "- משחקים של הפועל פ\"ת (גם אם הקבוצה היריבה היא הראשונה בכותרת!)\n"
        "- שחקנים, מאמנים, חיזוקים, פציעות של הפועל פ\"ת\n"
        "- לוח משחקים, סיקור משחקים, סיכומים, ראיונות עם הקבוצה\n\n"
        "אוהדים **לא** רוצים לקבל:\n"
        "- כתבות שעוסקות אך ורק במועדונים אחרים שמזכירות בחטף את הפועל פ\"ת\n"
        "- כתבות על מכבי פתח תקווה (זו קבוצה אחרת לחלוטין, היריבה!)\n"
        "- כתבות כלליות על ליגת העל בלי קשר ספציפי להפועל פ\"ת\n\n"
        "ענה YES אם כדאי לשלוח את הכתבה לאוהדים, NO אם לא.\n\n"
        f"כותרת: {title}\n\n"
        f"תחילת הכתבה: {sample_content}\n\n"
        "ענה YES או NO בלבד."
    )

    answer = call_gemini(prompt, timeout=20, label="topic-check")
    if not answer:
        return True
    return "YES" in answer.upper()


def get_ai_summary(title, content, is_official=False):
    """מחזיר תקציר עיתונאי"""
    if not content and not title:
        return None
    if len(content) < 80:
        return title if title else None

    if is_official:
        prompt = (
            "אתה כתב ספורט אוהד של הפועל פתח תקווה, שכותב לערוץ עדכונים של אוהדי הקבוצה. "
            "סכם את הודעת המועדון הבאה ב-4-5 משפטים בטון עיתונאי-אוהד: "
            "מקצועי ומדויק מצד אחד, אבל עם נימה חמה וקלילה של מי שאוהב את הקבוצה - לא ניטרלי קר. "
            "שמור על פרטים קונקרטיים שמופיעים בטקסט: תאריך/שעת המשחק, היריבה, מצב פציעות, "
            "ושלב את ציטוט מרכזי אחד מהמאמן או השחקן אם מופיע בכתבה (במרכאות, קצר ומדויק). "
            "הימנע מסלנג שכונתי, ביטויי הגזמה ('מטורף!', 'אדיר!') או קלישאות. "
            "אפשר להשתמש בכינויי חיבה כמו 'הכחולים' או 'חבורתו של עומר פרץ' כשמתאים. "
            "התחל ישר במידע ללא פתיחות מיותרות, וודא שמוזכר שם הקבוצה הפועל פתח תקווה לפחות פעם אחת. "
            "⚠️ חשוב: לא לערבב עם מכבי פתח תקווה - זו קבוצה אחרת לגמרי!\n\n"
            f"כותרת: {title}\n\nטקסט: {content[:3000]}\n\n"
            f"החזר רק את התקציר עצמו, ללא טקסט נוסף."
        )
    else:
        prompt = (
            "אתה כתב ספורט אוהד של הפועל פתח תקווה, שכותב לערוץ עדכונים של אוהדי הקבוצה. "
            "כתוב תקציר של 4-5 משפטים על הכתבה הבאה, "
            "תוך התמקדות בזווית הקשורה להפועל פתח תקווה. "
            "הטון צריך להיות **עיתונאי-אוהד**: מקצועי ומדויק, אבל עם נימה חמה של מי שאוהב את הקבוצה - "
            "לא יבש או ניטרלי קר. הימנע מסלנג שכונתי, ביטויי הגזמה ('מטורף!', 'נורא!') או קלישאות. "
            "אפשר להשתמש בכינויי חיבה כמו 'הכחולים' או 'חבורתו של עומר פרץ' במידה. "
            "ציין במפורש את שם הקבוצה הפועל פתח תקווה בתקציר. "
            "⚠️ חשוב: לא לערבב עם מכבי פתח תקווה - זו קבוצה אחרת לגמרי, היריבה!\n\n"
            f"כותרת: {title}\n\nטקסט: {content[:2500]}\n\n"
            f"החזר רק את התקציר עצמו, ללא טקסט נוסף."
        )

    summary = call_gemini(prompt, label="summary")
    if summary and len(summary) > 1000:
        summary = summary[:1000] + "..."
    return summary


def is_duplicate_content(new_title, recent_summaries):
    """
    🆕 בודק כפילות תוכן באמצעות חישוב דמיון מקומי (ללא Gemini!)
    חיסכון של עשרות קריאות API ביום.
    משווה את הכותרת החדשה מול כל הסיכומים האחרונים על בסיס מילים משותפות.
    """
    if not recent_summaries.strip() or len(recent_summaries) < 50:
        return False

    # ניקוי מילות חיבור נפוצות שלא מועילות לזיהוי כפילות
    stop_words = {
        "של", "על", "את", "אם", "מה", "כי", "זה", "לא", "גם", "עם", "אבל",
        "או", "כך", "רק", "כן", "כל", "הוא", "היא", "אני", "אתה", "אנחנו",
        "the", "a", "an", "and", "or", "but", "to", "of", "in", "on"
    }

    def tokenize(text):
        """מחלץ מילים משמעותיות מטקסט"""
        # הסרת סימני פיסוק והפיכה ל-lowercase
        cleaned = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text.lower())
        words = cleaned.split()
        return set(w for w in words if len(w) >= 3 and w not in stop_words)

    new_words = tokenize(new_title)
    if len(new_words) < 3:
        return False  # כותרת קצרה מדי לבדיקה

    # מפצלים את הסיכומים האחרונים (האחרונים 5)
    summaries = recent_summaries.split("|||")[-5:]

    for prev_summary in summaries:
        if not prev_summary.strip():
            continue
        prev_words = tokenize(prev_summary)
        if len(prev_words) < 3:
            continue

        # חישוב דמיון Jaccard (חיתוך / איחוד)
        intersection = new_words & prev_words
        union = new_words | prev_words
        if not union:
            continue

        similarity = len(intersection) / len(union)
        # אם 50% או יותר מהמילים זהות - כפילות
        if similarity >= 0.5:
            if DEBUG_VERBOSE:
                shared = ', '.join(list(intersection)[:5])
                print(f"DEBUG:   זוהתה כפילות מקומית (דמיון {similarity:.0%}, מילים: {shared})", flush=True)
            return True

    return False


def extract_article_data(url):
    """מחלץ תוכן ותמונה מכתבה"""
    try:
        resp = requests.get(url, headers=RSS_HEADERS, timeout=18, allow_redirects=True)
        final_url = resp.url
        soup = BeautifulSoup(resp.content, 'html.parser')

        image = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            img_url_lower = img_url.lower()
            # 🆕 פילטר מורחב נגד לוגואים דיפולטיביים של אתרים
            bad_image_indicators = [
                "googleusercontent", "google.com/logos", "placeholder",
                "/logo", "logo.", "logo_", "logo-",
                "default", "share_image", "share-image",
                "sport5_logo", "sport5-logo", "channel5",
                "one_logo", "ynet_logo", "walla_logo", "maariv_logo",
                "fb_share", "facebook_share", "og_default", "og-default",
                "_share.", "-share."
            ]
            if not any(bad in img_url_lower for bad in bad_image_indicators):
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


# =====================================================
# 🆕 פונקציות לניהול לוח משחקים חכם
# =====================================================

def load_schedule():
    """טוען את לוח המשחקים מקובץ JSON"""
    if not os.path.exists("schedule.json") or os.path.getsize("schedule.json") == 0:
        return {"last_update": None, "matches": {}}

    try:
        with open("schedule.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        # תאימות לאחור: אם הפורמט הישן (רק dict של תאריכים)
        if "matches" not in data:
            return {"last_update": None, "matches": data}
        return data
    except Exception as e:
        print(f"DEBUG: schedule.json corrupted: {e}", flush=True)
        return {"last_update": None, "matches": {}}


def save_schedule(schedule_data):
    """שומר את לוח המשחקים"""
    with open("schedule.json", 'w', encoding='utf-8') as f:
        json.dump(schedule_data, f, ensure_ascii=False, indent=2)


def needs_schedule_refresh(schedule_data):
    """
    🎯 קובע אם צריך לרענן את לוח המשחקים מה-API.
    מרענן רק אם:
    - אין לוח כלל
    - עברו יותר מ-SCHEDULE_REFRESH_DAYS ימים מהעדכון האחרון
    """
    if not schedule_data.get("matches"):
        return True

    last_update_str = schedule_data.get("last_update")
    if not last_update_str:
        return True

    try:
        last_update = datetime.fromisoformat(last_update_str)
        days_passed = (get_israel_time() - last_update).days
        return days_passed >= SCHEDULE_REFRESH_DAYS
    except:
        return True


def fetch_schedule_from_api(headers_api):
    """
    🎯 מביא את לוח המשחקים מה-API (קריאה אחת בשבוע!).
    מחזיר dict עם תאריך → {opponent, match_time_iso, match_id, is_home}
    """
    print("DEBUG: 📅 מעדכן לוח משחקים מה-API (פעם בשבוע)", flush=True)
    try:
        r_sched = requests.get(
            f"https://{RAPIDAPI_HOST}/api/v1/team/{TEAM_ID}/events/next/10",
            headers=headers_api, timeout=15
        ).json()

        if 'events' in r_sched and r_sched['events']:
            new_matches = {}
            for ev in r_sched['events']:
                # זמן המשחק בשעון ישראל
                match_time_il = datetime.fromtimestamp(ev['startTimestamp']) + timedelta(hours=3)
                d_key = match_time_il.strftime('%Y-%m-%d')

                is_home = str(ev['homeTeam']['id']) == TEAM_ID
                opp_raw = ev['awayTeam']['name'] if is_home else ev['homeTeam']['name']
                opp_heb = TEAM_TRANSLATION.get(opp_raw, opp_raw)

                new_matches[d_key] = {
                    "opponent": opp_heb,
                    "match_time_iso": match_time_il.isoformat(),
                    "match_id": ev.get('id'),
                    "is_home": is_home
                }
            print(f"DEBUG: ✅ לוח עודכן עם {len(new_matches)} משחקים", flush=True)
            return new_matches
        else:
            print("DEBUG: ⚠️ ה-API לא החזיר משחקים", flush=True)
            return None
    except Exception as e:
        print(f"DEBUG: ❌ שגיאה בקבלת לוח: {e}", flush=True)
        return None


def get_match_today(schedule_data):
    """
    🎯 מחזיר את פרטי המשחק של היום (אם יש), או None.
    מבוסס רק על קובץ ה-schedule, לא קורא ל-API!
    """
    today_str = get_israel_time().strftime('%Y-%m-%d')
    matches = schedule_data.get("matches", {})

    if today_str in matches:
        match = matches[today_str]
        # תאימות לאחור - אם הפורמט הישן (רק שם יריבה)
        if isinstance(match, str):
            return {"opponent": match, "match_time_iso": None, "match_id": None, "is_home": None}
        return match

    return None


# =====================================================
# --- לוגיקה מרכזית ---
# =====================================================

def main():
    now_il = get_israel_time()
    today_str = now_il.strftime('%Y-%m-%d')

    print(f"=== תחילת ריצה: {now_il.strftime('%d/%m/%Y %H:%M:%S')} ===", flush=True)
    print(f"DEBUG: מצב הפעלה: {RUN_MODE}", flush=True)
    recipients = get_recipients()
    print(f"DEBUG: נמענים: {len(recipients)}", flush=True)
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
            "כתוב 2 עובדות היסטוריות קצרות ומעניינות על הפועל פתח תקווה (לא מכבי פתח תקווה!). "
            "אחת משנות ה-50 ואחת משנות ה-90. הוסף אימוג'ים מתאימים.",
            label="history-fact"
        )
        if fact and send_telegram(f"📜 *פינת ההיסטוריה הכחולה:* \n\n{fact}"):
            with open("task_log.txt", 'a', encoding='utf-8') as f:
                f.write(f"history_{today_str}\n")

    # =====================================================
    # 2. 🆕 ניהול לוח משחקים חכם
    # =====================================================
    headers_api = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST}
    schedule_data = load_schedule()

    # ⚠️ קריאה ל-API רק אם באמת צריך (פעם בשבוע)
    if needs_schedule_refresh(schedule_data):
        new_matches = fetch_schedule_from_api(headers_api)
        # 🛡️ חשוב: גם אם נכשלנו, נשמור last_update כדי לא לנסות שוב מיד!
        # נחכה שבוע נוסף לפני ניסיון חוזר.
        schedule_data["last_update"] = now_il.isoformat()
        if new_matches:
            schedule_data["matches"] = new_matches
        elif not schedule_data.get("matches"):
            # רק במקרה שאין לנו שום לוח - נשתמש בגיבוי
            print("DEBUG: משתמש בלוח גיבוי", flush=True)
            schedule_data["matches"] = {
                d: {"opponent": opp, "match_time_iso": None, "match_id": None, "is_home": None}
                for d, opp in BACKUP_SCHEDULE.items()
            }
        save_schedule(schedule_data)
    else:
        days_left = SCHEDULE_REFRESH_DAYS - (now_il - datetime.fromisoformat(schedule_data["last_update"])).days
        print(f"DEBUG: ✅ לוח עדכני ({len(schedule_data['matches'])} משחקים, רענון בעוד ~{days_left} ימים)", flush=True)

    # =====================================================
    # 3. 🆕 ניהול יום משחק - תזמון דינמי
    # =====================================================
    match_today = get_match_today(schedule_data) if ENABLE_MATCHDAY_LOGIC else None

    if match_today:
        opp_heb = match_today["opponent"]
        match_id = match_today.get("match_id")
        match_time_iso = match_today.get("match_time_iso")

        # פענוח שעת המשחק (אם זמינה)
        match_time = None
        if match_time_iso:
            try:
                match_time = datetime.fromisoformat(match_time_iso)
            except:
                pass

        if match_time:
            print(f"DEBUG: ⚽ יום משחק! נגד {opp_heb}, פתיחה ב-{match_time.strftime('%H:%M')}", flush=True)
        else:
            print(f"DEBUG: ⚽ יום משחק! נגד {opp_heb} (אין שעת התחלה - מצב גיבוי)", flush=True)

        # ============================================
        # 3א. הודעת MatchDay - בריצה הראשונה אחרי 11:00
        # ============================================
        if now_il.hour >= MATCHDAY_MIN_HOUR and f"matchday_{today_str}" not in tasks:
            md_text = (
                f"MatchDay Hapoel 💙\n"
                f"הפועל שלנו עולה היום נגד *{opp_heb}*"
            )
            if match_time:
                md_text += f" בשעה *{match_time.strftime('%H:%M')}*"
            md_text += (
                f".\n"
                f"יאללה הפועל, לתת הכל בשביל הסמל! 🚀\n\n"
                f"כשחקנים למגרש עולים - כל האוהדים שריםםםם\n"
                f"הפועל עולה עולההה, הפועל, הפועל עולהה 💙"
            )
            if send_telegram(None, "sendPhoto", {"photo": random.choice(MATCHDAY_POSTERS), "caption": md_text}):
                with open("task_log.txt", 'a', encoding='utf-8') as f:
                    f.write(f"matchday_{today_str}\n")
                print("DEBUG: ✅ נשלחה הודעת MatchDay", flush=True)

        # ============================================
        # 3ב. סקר הימורים - 3 שעות לפני המשחק (דינמי!)
        # ============================================
        if f"betting_{today_str}" not in tasks:
            send_betting = False
            if match_time:
                # שולחים אם נשארו מקסימום 3 שעות עד המשחק
                hours_until_match = (match_time - now_il).total_seconds() / 3600
                if 0 <= hours_until_match <= HOURS_BEFORE_MATCH_FOR_BETTING:
                    send_betting = True
                    print(f"DEBUG: 🎲 שולח הימורים ({hours_until_match:.1f} שעות עד המשחק)", flush=True)
            else:
                # מצב גיבוי - אם אין שעה, נשלח ב-15:00
                if now_il.hour >= 15:
                    send_betting = True

            if send_betting:
                poll_payload = {
                    "question": "זמן להמר, מי תנצח היום?",
                    "options": ["ניצחון כחול 💙", "תיקו", "הפסד 💔"],
                    "is_anonymous": False
                }
                if send_telegram(None, "sendPoll", poll_payload):
                    with open("task_log.txt", 'a', encoding='utf-8') as f:
                        f.write(f"betting_{today_str}\n")
                    print("DEBUG: ✅ נשלח סקר הימורים", flush=True)

        # ============================================
        # 3ג. תוצאת סיום + סקר MVP - דינמי!
        # ============================================
        # נבדוק רק אם המשחק כבר אמור להיגמר (לפי השעה + 110 דק')
        if f"final_{today_str}" not in tasks:
            should_check_result = False

            if match_time:
                # רק אם עברו לפחות 110 דקות מתחילת המשחק
                expected_end = match_time + timedelta(minutes=MATCH_DURATION_MINUTES)
                if now_il >= expected_end:
                    should_check_result = True
                    print(f"DEBUG: 🏁 המשחק אמור להיות גמור (התחיל ב-{match_time.strftime('%H:%M')})", flush=True)
                else:
                    minutes_to_end = int((expected_end - now_il).total_seconds() / 60)
                    print(f"DEBUG: ⏳ המשחק עדיין לא גמור ({minutes_to_end} דק' להערכת סיום)", flush=True)
            else:
                # מצב גיבוי - אם אין שעה ידועה, נבדוק רק אחרי 18:00
                if now_il.hour >= 18:
                    should_check_result = True

            # ⚠️ קריאה ל-API לבדיקת התוצאה - רק אם הזמן הגיע!
            if should_check_result:
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
                                # 🎯 המשחק נגמר - שולחים תוצאה ו-MVP
                                is_home_actual = str(last_ev['homeTeam']['id']) == TEAM_ID
                                my_score = last_ev['homeScore']['display'] if is_home_actual else last_ev['awayScore']['display']
                                opp_score = last_ev['awayScore']['display'] if is_home_actual else last_ev['homeScore']['display']

                                chant = random.choice(WIN_CHANTS)
                                res_txt = f"{chant}\n\n*סיום המשחק:* הפועל {my_score}, {opp_heb} {opp_score}."
                                markup = {"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": ONE_TABLE_URL}]]}
                                if send_telegram(res_txt, payload={"text": res_txt, "reply_markup": markup}):
                                    with open("task_log.txt", 'a', encoding='utf-8') as f:
                                        f.write(f"final_{today_str}\n")
                                    print("DEBUG: ✅ נשלחה תוצאת המשחק", flush=True)

                                # סקר MVP - מיד אחרי התוצאה (קוראים ל-API ללא ניידים)
                                if f"mvp_{today_str}" not in tasks:
                                    players_heb = DEFAULT_PLAYERS[:]
                                    try:
                                        event_id = last_ev.get('id')
                                        if event_id:
                                            r_lineup = requests.get(
                                                f"https://{RAPIDAPI_HOST}/api/v1/event/{event_id}/lineups",
                                                headers=headers_api, timeout=10
                                            ).json()
                                            side = 'home' if is_home_actual else 'away'
                                            players_raw = r_lineup.get(side, {}).get('players', [])
                                            if players_raw:
                                                players_heb = [
                                                    PLAYER_MAP.get(p.get('player', {}).get('name', ''),
                                                                   p.get('player', {}).get('name', ''))
                                                    for p in players_raw[:10]
                                                ]
                                                print(f"DEBUG: ✅ קיבלתי {len(players_heb)} שחקנים מה-API", flush=True)
                                    except Exception as e:
                                        print(f"DEBUG lineup error: {e}", flush=True)

                                    send_telegram(None, "sendPoll", {
                                        "question": "מי ה-MVP של המשחק?",
                                        "options": players_heb[:10],
                                        "is_anonymous": False
                                    })
                                    with open("task_log.txt", 'a', encoding='utf-8') as f:
                                        f.write(f"mvp_{today_str}\n")
                                    print("DEBUG: ✅ נשלח סקר MVP", flush=True)
                            else:
                                # המשחק עדיין באוויר או טרם התחיל
                                print(f"DEBUG: ⏳ המשחק עדיין לא הסתיים (status: {status_type})", flush=True)
                except Exception as e:
                    print(f"DEBUG match result error: {e}", flush=True)
    else:
        if ENABLE_MATCHDAY_LOGIC:
            print(f"DEBUG: 🚫 אין משחק היום ({today_str})", flush=True)

    # =====================================================
    # 4. סריקת כתבות RSS
    # =====================================================
    processed_count = 0
    MAX_ARTICLES_PER_RUN = 8

    stats = {
        "total_seen": 0, "filtered_already_seen": 0, "filtered_too_old": 0,
        "filtered_wrong_domain": 0, "filtered_not_relevant": 0,
        "filtered_maccabi_pt": 0, "filtered_not_main_topic": 0,
        "filtered_duplicate_content": 0, "filtered_no_summary": 0,
        "filtered_decode_failed": 0, "sent": 0, "errors": 0
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
                print(f"DEBUG: ⚠️ פיד ריק!", flush=True)
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

                # 🚫 בדיקה מקדימה: מכבי פ"ת?
                if not is_official:
                    is_maccabi, m_reason = is_about_maccabi_pt(title + " " + rss_summary)
                    if is_maccabi:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: 🚫 מכבי פ\"ת ({m_reason}): {title[:50]}", flush=True)
                        stats["filtered_maccabi_pt"] += 1
                        continue

                # טיפול בלינקים מגוגל
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
                    if DEBUG_VERBOSE:
                        print(f"DEBUG: ✓ רלוונטי בגוגל ({reason}): {title[:55]}", flush=True)
                    real_link = decode_google_news_url(raw_link)
                    if not real_link:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ⚠️ פענוח נכשל - מדלג", flush=True)
                        stats["filtered_decode_failed"] += 1
                        continue
                    raw_link = real_link
                else:
                    raw_link = raw_link.replace("https://svcamz.", "https://www.")
                    if domain_filter and domain_filter not in raw_link.lower():
                        stats["filtered_wrong_domain"] += 1
                        continue

                clean_l = normalize_url(raw_link)
                if clean_l in history:
                    stats["filtered_already_seen"] += 1
                    continue

                pub_parsed = entry.get('published_parsed')
                if pub_parsed:
                    try:
                        pub_dt = datetime(*pub_parsed[:6])
                        if (now_il - pub_dt) > timedelta(days=5):
                            stats["filtered_too_old"] += 1
                            continue
                    except:
                        pass

                if not is_google and not is_official:
                    is_rel, reason = is_relevant_to_hapoel_pt(title + " " + rss_summary)
                    if not is_rel:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG: ⏭️ לא רלוונטי בכותרת: {title[:60]}", flush=True)
                        stats["filtered_not_relevant"] += 1
                        continue
                    if DEBUG_VERBOSE:
                        print(f"DEBUG: ✓ רלוונטי בכותרת ({reason}): {title[:60]}", flush=True)

                print(f"DEBUG: 🔍 בודק: {title[:65]}", flush=True)

                content, image, final_url = extract_article_data(raw_link)
                clean_l = normalize_url(final_url)

                if clean_l in history:
                    stats["filtered_already_seen"] += 1
                    continue

                if len(content) < 50:
                    content = rss_summary or title

                # 🚫 בדיקה שנייה: מכבי פ"ת בתוכן
                if not is_official:
                    is_maccabi, m_reason = is_about_maccabi_pt(content[:2000])
                    if is_maccabi:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   🚫 מכבי פ\"ת בתוכן: {m_reason}", flush=True)
                        stats["filtered_maccabi_pt"] += 1
                        continue

                if not is_official:
                    full_text_for_check = title + " " + content[:1500]
                    is_rel, reason = is_relevant_to_hapoel_pt(full_text_for_check)
                    if not is_rel:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ⏭️ לא רלוונטי בתוכן", flush=True)
                        stats["filtered_not_relevant"] += 1
                        continue

                # 🎯 בדיקה: הפועל פ"ת היא הנושא העיקרי?
                # 🆕 חיסכון: דילוג אם הכותרת ברורה (כדי לחסוך קריאות Gemini)
                if not is_official:
                    title_lower = title.lower()
                    # אם שם הקבוצה המלא מופיע בכותרת - מספיק ברור, לא צריך לבדוק
                    title_has_clear_mention = any(
                        clear_key in title_lower for clear_key in [
                            "הפועל פתח תקווה", "הפועל פתח תקוה", "הפועל פתח-תקוה",
                            "הפועל פ\"ת", "הפועל פ'ת"
                        ]
                    )

                    if not title_has_clear_mention:
                        # רק אם לא ברור מהכותרת - נשאל את Gemini
                        if not is_article_main_topic_hapoel_pt(title, content):
                            if DEBUG_VERBOSE:
                                print(f"DEBUG:   ⏭️ הפועל פ\"ת לא הנושא העיקרי", flush=True)
                            stats["filtered_not_main_topic"] += 1
                            continue
                    else:
                        if DEBUG_VERBOSE:
                            print(f"DEBUG:   ✓ כותרת ברורה - דילוג על topic-check", flush=True)

                if is_duplicate_content(title, recent_sums):
                    print(f"DEBUG:   ⏭️ כפילות תוכן", flush=True)
                    stats["filtered_duplicate_content"] += 1
                    continue

                summary = get_ai_summary(title, content, is_official=is_official)

                if not summary or len(summary) < 15:
                    if is_official:
                        summary = title
                    else:
                        stats["filtered_no_summary"] += 1
                        continue

                full_msg = f"*עדכון חדש על הפועל ⚽️💙*\n\n{summary}\n\n🔗 [לכתבה המלאה]({clean_l})"
                # 🆕 אם אין תמונה לכתבה, נשתמש בתמונת גיבוי של הפועל פ"ת
                # (במקום לשלוח טקסט בלבד או לוגו של אתר חדשות)
                photo_to_send = image if image else random.choice(FALLBACK_ARTICLE_IMAGES)
                success = send_telegram(None, "sendPhoto", {"photo": photo_to_send, "caption": full_msg})

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
                    stats["errors"] += 1

        except Exception as e:
            print(f"DEBUG RSS ERROR ({source_name}): {e}", flush=True)
            stats["errors"] += 1

    # ניקוי
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
    print(f"  🚫 מכבי פ\"ת:         {stats['filtered_maccabi_pt']}", flush=True)
    print(f"  🎯 לא נושא עיקרי:    {stats['filtered_not_main_topic']}", flush=True)
    print(f"  כפילות תוכן:        {stats['filtered_duplicate_content']}", flush=True)
    print(f"  בעיית תקציר:        {stats['filtered_no_summary']}", flush=True)
    print(f"  פענוח לינק נכשל:    {stats['filtered_decode_failed']}", flush=True)
    print(f"  שגיאות:             {stats['errors']}", flush=True)
    print(f"  ✅ נשלחו לטלגרם:    {stats['sent']}", flush=True)
    print(f"=== סיום ריצה: {get_israel_time().strftime('%H:%M:%S')} ===", flush=True)


if __name__ == "__main__":
    main()
