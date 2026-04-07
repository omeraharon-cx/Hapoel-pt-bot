import requests
import json
import os
import random
from datetime import datetime

# --- הגדרות בסיס לטסט בלבד ---
ADMIN_ID = "425605110"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# הלינקים שביקשת
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"
MATCHDAY_POSTER_URL = "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png" 

# סגל שחקנים מעודכן (תוכנית ב' - בדיוק 10 שחקנים לסקר)
DEFAULT_PLAYERS = [
    "עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", 
    "קוסטה", "שביט מזל", "קליי", "סונגה", "אלטמן"
]

WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

# --- פונקציות שליחה ---

def send_telegram_test(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=20)
        print(f"LOG: Sent {method}, Status: {r.status_code}, Response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR: {e}")
        return False

def get_ai_fact():
    """מייצר עובדה היסטורית לטסט בעזרת AI"""
    if not GEMINI_API_KEY: return "עובדת טסט: הפועל פ\"ת זכתה ב-5 אליפויות רצופות."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = "כתוב 2 עובדות היסטוריות קצרות, מרגשות ואמיתיות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. התחל ב'הידעת?'."
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return "שגיאת AI בייצור עובדה."

def run_test_simulation():
    print("🚀 מריץ טסט מלא: כל ההודעות יישלחו עכשיו!")
    
    opp_heb = "טסט (יריבה דמיונית)"

    # 1. הודעת Matchday עם פוסטר (הסמוראי)
    print("שולח Matchday...")
    md_text = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
    payload_md = {
        "chat_id": ADMIN_ID,
        "photo": MATCHDAY_POSTER_URL,
        "caption": md_text,
        "parse_mode": "Markdown"
    }
    send_telegram_test("sendPhoto", payload_md)

    # 2. סקר הימורים (3 אופציות)
    print("שולח סקר הימורים...")
    payload_bet = {
        "chat_id": ADMIN_ID,
        "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}?",
        "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"],
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_bet)

    # 3. הודעת סיום משחק (ניצחון 2-0 עם כפתור ל-ONE)
    print("שולח הודעת סיום...")
    win_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb} (תוצאה: 2-0)\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
    payload_final = {
        "chat_id": ADMIN_ID,
        "text": win_txt,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [[{"text": "📊 לטבלת הליגה (ONE)", "url": ONE_TABLE_URL}]]
        }
    }
    send_telegram_test("sendMessage", payload_final)

    # 4. סקר שחקן מצטיין (עם הסגל המעודכן)
    print("שולח סקר שחקן מצטיין...")
    payload_mvp = {
        "chat_id": ADMIN_ID,
        "question": "מי המצטיין שלכם היום? ⚽️",
        "options": DEFAULT_PLAYERS,
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_mvp)

    # 5. פינת ההיסטוריה האינסופית (AI)
    print("שולח פינת היסטוריה...")
    fact = get_ai_fact()
    hist_msg = f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}"
    payload_hist = {
        "chat_id": ADMIN_ID,
        "text": hist_msg,
        "parse_mode": "Markdown"
    }
    send_telegram_test("sendMessage", payload_hist)

    print("🏁 סיום הטסט. אם הכל הגיע - אנחנו מוכנים לפרודקשן!")

if __name__ == "__main__":
    run_test_simulation()
