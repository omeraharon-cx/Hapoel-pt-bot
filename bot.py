import requests
import random
import json
import os
from datetime import datetime, timedelta

# --- הגדרות בסיס לטסט ---
ADMIN_ID = "425605110"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
LEAGUE_TABLE_URL = "https://www.sport5.co.il/liga.aspx?FolderID=44"
FALLBACK_POSTER = "https://www.hapoelpt.com/wp-content/uploads/2023/08/cropped-logo-1.png"

WIN_CHANTS = [
    "כמו דמיון חופשי שנינו ביחד רק את ואני... 💙",
    "כחול עולה עולה, כחול עולה עולה! 💙",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙",
    "אלך אחריך גם עד סוף העולם! 💙"
]

DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "איתי רוטמן", "דרור ניר", "עידן כהן"]

def send_telegram_test(text, is_poll=False, poll_data=None, photo_url=None, with_table=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
    payload = {"chat_id": ADMIN_ID, "parse_mode": "Markdown"}
    if with_table:
        payload["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": "📊 לטבלת הליגה", "url": LEAGUE_TABLE_URL}]]})
    if photo_url:
        method, payload = "sendPhoto", {**payload, "photo": photo_url, "caption": text}
    elif is_poll:
        method, payload = "sendPoll", {**payload, **poll_data}
    else:
        method, payload = "sendMessage", {**payload, "text": text}
    
    r = requests.post(url + method, data=payload)
    print(f"LOG: Sent {method}, Status: {r.status_code}")

def run_full_simulation():
    print("🚀 מתחיל סימולציה מלאה של יום משחק...")
    
    # הגדרת יריבה לטסט
    opp_heb = "טסט"

    # --- 1. הודעת Matchday (כאילו בוקר) ---
    print("נשלחת הודעת Matchday...")
    msg_md = f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n\nלתת הכל בשביל הסמל, כחול עולה עולה - יאללה הפועל מלחמה 💙"
    send_telegram_test(msg_md, photo_url=FALLBACK_POSTER)

    # --- 2. הודעת הימורים (כאילו 15:00) ---
    print("נשלחת הודעת הימורים...")
    send_telegram_test("💰 *זמן הימורים!* מה תהיה התוצאה היום נגד טסט? כתבו בתגובות! 👇")

    # --- 3. הודעת סיום משחק - ניצחון (כאילו נגמר המשחק) ---
    print("נשלחת הודעת ניצחון...")
    win_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb}\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
    send_telegram_test(win_txt, with_table=True)

    # --- 4. סקר MVP (כאילו עברו 10 דקות) ---
    print("נשלח סקר MVP...")
    poll = {"question": "מי המצטיין שלכם נגד טסט? ⚽️", "options": DEFAULT_PLAYERS[:10], "is_anonymous": False}
    send_telegram_test("", is_poll=True, poll_data=poll)

if __name__ == "__main__":
    run_full_simulation()
