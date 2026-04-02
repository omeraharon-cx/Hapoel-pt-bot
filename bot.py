import os
import requests
import sys
from datetime import datetime

# קידוד לעברית
sys.stdout.reconfigure(encoding='utf-8')

# --- הגדרות מערכת (Secrets מ-GitHub) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
ADMIN_ID = "425605110"

# המזהה של הפועל פתח תקווה
HAPOEL_TEAM_ID = "5199"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"})

def get_ai_message(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except: return None

# --- הודעת בוקר של משחק ---
def check_match_day():
    if not RAPIDAPI_KEY: return
    url = f"https://sportapi7.p.rapidapi.com/api/v1/team/{HAPOEL_TEAM_ID}/events/next/0"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "sportapi7.p.rapidapi.com"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        next_event = res.get('events', [{}])[0]
        start_ts = next_event.get('startTimestamp')
        if not start_ts: return
        
        match_date = datetime.fromtimestamp(start_ts).date()
        if match_date == datetime.now().date():
            state_file = "match_day_notified.txt"
            today_str = str(match_date)
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    if f.read().strip() == today_str: return
            
            msg = "יום של משחק הפועל 💙\nעוד כמה שעות הפועל תעלה לכר הדשא ותתן את הנשמה!\nתשרפו את הדשא ותביאו נצחון!\n\nיאלללה הפועללללל!"
            send_telegram(msg)
            with open(state_file, 'w') as f: f.write(today_str)
    except: pass

# --- הודעת סיום משחק ---
def check_match_results():
    if not RAPIDAPI_KEY: return
    url = f"https://sportapi7.p.rapidapi.com/api/v1/team/{HAPOEL_TEAM_ID}/events/last/0"
    headers = {"x-rapidapi-key": RAPIDAPI_KEY, "x-rapidapi-host": "sportapi7.p.rapidapi.com"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        match = res.get('events', [{}])[0]
        if match.get('status', {}).get('type') != 'finished': return
        
        event_id = str(match.get('id'))
        db_file = "seen_results.txt"
        if not os.path.exists(db_file): open(db_file, 'w').close()
        with open(db_file, 'r') as f:
            if event_id in f.read(): return
            
        h_score, a_score = match['homeScore']['display'], match['awayScore']['display']
        h_name, a_name = match['homeTeam']['name'], match['awayTeam']['name']
        
        is_h_home = "Petach Tikva" in h_name
        win = (is_h_home and h_score > a_score) or (not is_h_home and a_score > h_score)
        draw = h_score == a_score

        if draw:
            # ניסוח מדויק שביקשת לתיקו
            final_msg = "תיקו בסיום המשחק, הפועל יוצאת עם נקודה.\nממשיכים חזק כל הדרך - יאללה הפועל\nהיום יוצאים למלחמה 💙"
        elif win:
            # פקודה ל-AI עם השירים והוויב של הטירוף
            prompt = f"""Hapoel Petah Tikva won {h_score}-{a_score}! Write a crazy victory message in Hebrew.
            Integrate chants like: 'מי שלא קופץ לוזון', 'שער 4 מעודד האצטדיון רועד', 'כחול עולה', 'אמרו לו הפועל אז הלך לאורווה'.
            Be emotional, hardcore fan style, use blue emojis. Always end with 'יאללה הפועל 💙'."""
            final_msg = get_ai_message(prompt)
        else:
            # הודעת ניחום
            prompt = f"Hapoel Petah Tikva lost {h_score}-{a_score}. Write a comforting message in Hebrew, encourage fans to keep heads up. Always end with 'יאללה הפועל 💙'."
            final_msg = get_ai_message(prompt)
            
        if final_msg:
            full_msg = f"⚽ **סיום משחק!**\n\n{final_msg}\n\n📊 תוצאה: {h_name} {h_score} - {a_score} {a_name}"
            send_telegram(full_msg)
            with open(db_file, 'a') as f: f.write(event_id + "\n")
    except: pass

def main():
    check_match_day()
    check_match_results()

if __name__ == "__main__":
    main()
