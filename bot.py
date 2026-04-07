import requests
import json
import os
import random
from datetime import datetime

# --- הגדרות בסיס לטסט ---
ADMIN_ID = "425605110"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# הלינק לטבלה של ONE
ONE_TABLE_URL = "https://m.one.co.il/Mobile/Leagues/LeagueSelector.aspx?l=1&bz=20264712"

# מאגר הפוסטרים המלא (6 תמונות)
MATCHDAY_POSTERS = [
    "https://i.ibb.co/LhxyQDdW/2026-04-07-12-21-58.png",
    "https://i.ibb.co/GfBwY4J1/IMG-7023.jpg",
    "https://i.ibb.co/tM8QhJ8P/IMG-7022.jpg",
    "https://i.ibb.co/tP2zMFH5/IMG-7021.jpg",
    "https://i.ibb.co/ch9zN8Ly/IMG-7020.jpg",
    "https://i.ibb.co/v4phbhv3/IMG-7019.jpg"
]

# סגל שחקנים מעודכן (10 שחקנים)
DEFAULT_PLAYERS = ["עומר כץ", "אוראל דגני", "נדב נידם", "יונתן כהן", "רועי דוד", "קוסטה", "שביט מזל", "קליי", "סונגה", "אלטמן"]

# השירים החדשים והמרגשים
WIN_CHANTS = [
    "כמו דמיון חופשייייי שנינו ביחדדד את ואני - כחול עולה עולה יאלה הפועלללל כחולה עולה",
    "אלך אחריך גם עד סוף העולםם, אקפוץ אשתגעע יאללה ביחדד כולםםםםם",
    "מי שלא קופץ לוזון, מי שלא קופץ לוזון! 💙"
]

def send_telegram_test(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        r = requests.post(url, json=payload, timeout=20)
        print(f"LOG: Sent {method}, Status: {r.status_code}")
        return r.status_code == 200
    except: return False

def get_ai_fact_test():
    """טסט לייצור עובדה היסטורית"""
    if not GEMINI_API_KEY: return "עובדה ללא AI: הפועל פתח תקווה נוסדה בשנת 1934."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = "כתוב 2 עובדות היסטוריות קצרות, מרגשות ואמיתיות על הפועל פתח תקווה. אחת משנות ה-50 ואחת משנות ה-90. התחל ב'הידעת?'."
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25).json()
        return res['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return "שגיאה ב-AI, אבל הבוט ימשיך לעבוד עם עובדת גיבוי."

def run_final_test():
    print("🎬 מתחיל טסט מסכם לפני פרודקשן...")
    opp_heb = "טסט סופי"

    # 1. הגרלת פוסטר ו-Matchday
    selected_poster = random.choice(MATCHDAY_POSTERS)
    md_text = (
        f"*Matchday*\n"
        f"הפועל שלנו תעלה בעוד כמה שעות לכר הדשא לשחק נגד *{opp_heb}*.\n"
        f"מקווים לצאת עם נצחון חשוב.\n\n"
        f"קדימה הפועל לתת את הלב בשביל הסמל - יאללה מלחמה 💙"
    )
    send_telegram_test("sendPhoto", {"chat_id": ADMIN_ID, "photo": selected_poster, "caption": md_text, "parse_mode": "Markdown"})

    # 2. סקר הימורים
    send_telegram_test("sendPoll", {
        "chat_id": ADMIN_ID,
        "question": f"זמן הימורים! מה תהיה התוצאה היום נגד {opp_heb}?",
        "options": ["ניצחון להפועל 💙", "תיקו", "הפסד כואב 💔"],
        "is_anonymous": False
    })

    # 3. הודעת סיום (שירים חדשים)
    win_txt = f"{random.choice(WIN_CHANTS)}\n\n*איזההה נצחון של הפועלללל!*\nיוצאים עם 3 נקודות במשחק נגד {opp_heb} (תוצאה: 1-0)\nכל הכבוד הפועל, לתת הכל בשביל הסמל 💙"
    send_telegram_test("sendMessage", {
        "chat_id": ADMIN_ID, "text": win_txt, "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": [[{"text": "📊 לטבלת הליגה (ONE)", "url": ONE_TABLE_URL}]]}
    })

    # 4. סקר MVP (סגל מעודכן)
    send_telegram_test("sendPoll", {
        "chat_id": ADMIN_ID, "question": "מי המצטיין שלכם היום? ⚽️", "options": DEFAULT_PLAYERS, "is_anonymous": False
    })

    # 5. פינת היסטוריה (AI)
    fact = get_ai_fact_test()
    send_telegram_test("sendMessage", {
        "chat_id": ADMIN_ID, "text": f"📜 *פינת ההיסטוריה הכחולה:*\n\n{fact}", "parse_mode": "Markdown"
    })

    print("🏁 הטסט הסתיים. בדוק את הטלגרם!")

if __name__ == "__main__":
    run_final_test()
