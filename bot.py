def get_ai_summary(text, models):
    if not text or len(text) < 150: return None
    
    # הוראות ברורות וחסינות למודל
    prompt = (
        "### INSTRUCTIONS ###\n"
        "1. Write a summary of the provided sports article in Hebrew.\n"
        "2. Length: Exactly 3 short sentences.\n"
        "3. Tone: Casual, friendly (friend-to-friend), but concise and non-biassed.\n"
        "4. NO GREETINGS: Do NOT start with 'Hi', 'Hello', 'Friends' or any intro. Start directly with the news.\n"
        "5. MANDATORY CONTEXT: Always relate the news to Hapoel Petah Tikva (The Blues). \n"
        "   - If the team is mentioned, summarize what was said about them.\n"
        "   - If it's general news, explain how it impacts Hapoel Petah Tikva specifically.\n"
        "\n"
        "### ARTICLE TEXT ###\n"
        f"{text[:3000]}"
    )
    
    # הגדרות בטיחות מקסימליות למניעת חסימות שווא
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    headers = {'Content-Type': 'application/json'}

    for model_path in models:
        for version in ['v1beta', 'v1']:
            try:
                url = f"https://generativelanguage.googleapis.com/{version}/{model_path}:generateContent?key={GEMINI_API_KEY}"
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                data = response.json()
                if response.status_code == 200 and 'candidates' in data:
                    summary = data['candidates'][0]['content']['parts'][0]['text']
                    return summary.strip()
            except: continue
    return None
