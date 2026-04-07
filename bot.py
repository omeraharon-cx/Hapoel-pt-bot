import requests
import json
import os
import random
from datetime import datetime

# --- הגדרות בסיס לטסט ---
ADMIN_ID = "425605110"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"
FALLBACK_POSTER = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# סגל שחקנים מעודכן (תוכנית ב') - מוגבל ל-10 עבור הסקר
DEFAULT_PLAYERS = [
    "עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", 
    "קוסטה", "שביט מזל", "קליי", "סונגה", "אלטמן"
]

WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

HISTORICAL_EVENTS = [
    "ב-1955 הפועל פ\"ת זכתה באליפות הראשונה בתולדותיה! 🏆",
    "נחום סטלמך כבש את השער המפורסם מול ברית המועצות ב-1956. ⚽",
    "הפועל פ\"ת מחזיקה בשיא של 5 אליפויות רצופות (1959-1963)! 💙",
    "הזכייה האחרונה בגביע המדינה הייתה ב-1992, עם שער של וואליד באדיר. 🏆",
    "האצטדיון המיתולוגי של הקבוצה היה 'האורווה', שם נכתבו סיפורים בלתי נשכחים. 🏟️"
]

def send_telegram_test(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"LOG: Sent {method}, Status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR: {e}")
        return False

def run_full_simulation():
    print("🚀 מתחיל סימולציה מלאה (גרסה סופית לטסט)...")
    
    opp_heb = "טסט" 

    # --- 1. הודעת Matchday עם פוסטר (בוקר) ---
    print("שולח Matchday...")
    md_text = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
    payload_md = {
        "chat_id": ADMIN_ID,
        "photo": FALLBACK_POSTER,
        "caption": md_text,
        "parse_mode": "Markdown"
    }
    send_telegram_test("sendPhoto", payload_md)

    # --- 2. סקר הימורים (15:00) ---
    print("שולח סקר הימורים...")
    payload_bet = {
        "chat_id": ADMIN_ID,
        "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}?",
        "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"],
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_bet)

    # --- 3. הודעת סיום משחק (ניצחון מדומה 2-0) ---
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

    # --- 4. סקר שחקן מצטיין ---
    print("שולח סקר שחקן מצטיין...")
    payload_mvp = {
        "chat_id": ADMIN_ID,
        "question": f"מי המצטיין שלכם נגד {opp_heb}? ⚽️",
        "options": DEFAULT_PLAYERS,
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_mvp)

    # --- 5. פינת ההיסטוריה (יום רביעי) ---
    print("שולח פינת היסטוריה...")
    events = random.sample(HISTORICAL_EVENTS, 3)
    hist_msg = "📜 *פינת ההיסטוריה הכחולה:*\n\n" + "\n".join([f"🔹 {e}" for e in events])
    payload_hist = {
        "chat_id": ADMIN_ID,
        "text": hist_msg,
        "parse_mode": "Markdown"
    }
    send_telegram_test("sendMessage", payload_hist)

    print("🏁 סיום סימולציה מושלם.")

if __name__ == "__main__":
    run_full_simulation()
