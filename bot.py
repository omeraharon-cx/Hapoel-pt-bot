import requests
import json
import os
import random
from datetime import datetime

# --- הגדרות בסיס לטסט ---
ADMIN_ID = "425605110"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# הלינק החדש של ONE שביקשת
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"
FALLBACK_POSTER = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

# סגל השחקנים (תוכנית ב')
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "איתי רוטמן", "דרור ניר", "עידן כהן", "שחר רוזן", "ממאדי דיארה"]

WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

def send_telegram_test(method, payload):
    """פונקציה גנרית לשליחה לטלגרם בטסט"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"LOG: Sent {method}, Status: {r.status_code}, Response: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"LOG ERROR: {e}")
        return False

def run_full_simulation():
    print("🚀 מתחיל סימולציה מלאה של יום משחק (גרסה מתוקנת)...")
    
    opp_heb = "טסט" # שם היריבה המדומה

    # --- 1. הודעת Matchday עם פוסטר ---
    print("שולח Matchday...")
    md_text = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
    payload_md = {
        "chat_id": ADMIN_ID,
        "photo": FALLBACK_POSTER,
        "caption": md_text,
        "parse_mode": "Markdown"
    }
    send_telegram_test("sendPhoto", payload_md)

    # --- 2. סקר הימורים ---
    print("שולח סקר הימורים...")
    payload_bet = {
        "chat_id": ADMIN_ID,
        "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}?",
        "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"],
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_bet)

    # --- 3. הודעת סיום משחק (ניצחון) עם כפתור ל-ONE ---
    print("שולח הודעת סיום...")
    win_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb}\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
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
        "question": "מי המצטיין שלכם היום? ⚽️",
        "options": DEFAULT_PLAYERS[:10], # טלגרם מגבילה ל-10 אפשרויות
        "is_anonymous": False
    }
    send_telegram_test("sendPoll", payload_mvp)

    print("🏁 סיום סימולציה.")

if __name__ == "__main__":
    run_full_simulation()
