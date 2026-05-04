# Hapoel-PT-Bot — Context for Claude Code

## 🎯 What This Project Does

A Telegram bot that delivers updates about **Hapoel Petah Tikva** (הפועל פתח תקווה) football club to a Telegram channel. The bot:

1. **Scans RSS feeds** from Israeli sports sites every 45 minutes
2. **Filters** for relevant articles (about Hapoel PT specifically)
3. **Summarizes** them via Gemini AI in a journalistic-fan tone
4. **Posts** to Telegram with image + summary + link
5. **Manages match days** with automated MatchDay/Betting/Result/MVP messages

Runs on **GitHub Actions** scheduled cron every 45 minutes.

---

## 📂 Repository Structure

```
Hapoel-pt-bot/
├── bot.py                          # Main bot logic (~1200 lines)
├── requirements.txt                # Python dependencies
├── .github/workflows/main.yml     # GitHub Actions cron schedule
├── seen_links.txt                  # Persistent: already-sent article URLs
├── recent_summaries.txt            # Persistent: last summaries (dup detection)
├── task_log.txt                    # Persistent: per-day task completion markers
├── schedule.json                   # Persistent: weekly match schedule cache
├── subscribers.txt                 # List of Telegram chat IDs for broadcast
└── CLAUDE.md                       # This file
```

---

## 🔧 Tech Stack

- **Python 3** (no framework)
- **Gemini API** (`gemini-2.5-flash`) — article summarization & topic relevance
- **one.co.il public JSON API** (`/api/team/6`) — match schedule + recent results (free, no quota)
- **Telegram Bot API** — message delivery
- **googlenewsdecoder** (Python lib) — decodes Google News RSS encoded URLs
- **feedparser**, **beautifulsoup4**, **lxml** — RSS parsing & HTML scraping

---

## 🔑 Required Secrets (configured in GitHub Settings → Secrets)

- `GEMINI_API_KEY` — Google AI Studio
- `TELEGRAM_TOKEN` — BotFather token

(`RAPIDAPI_KEY` is no longer used — can be removed from GitHub Secrets.)

---

## 🎛️ Key Configuration (top of bot.py)

```python
GEMINI_MODEL = "gemini-2.5-flash"   # 2.0-flash had its free tier dropped to 0 in May 2026
RUN_MODE = "ADMIN_ONLY"              # "ADMIN_ONLY" for testing, "BROADCAST" for production
ENABLE_MATCHDAY_LOGIC = True
HOURS_BEFORE_MATCH_FOR_BETTING = 3   # Betting poll sent 3h before kickoff
MATCH_DURATION_MINUTES = 110         # When to start checking for results
```

**Admin Telegram ID:** `425605110`
**Team ID (one.co.il):** `6`

---

## 🚦 Article Filtering Pipeline (in order)

For each RSS entry, the code applies these filters sequentially:

1. **Domain whitelist** — only allowed sites pass
2. **`is_about_maccabi_pt`** — blocks articles about **Maccabi PT** (the rival club!)
3. **Google News domain check** — for Google News feeds, verifies source via `<source>` tag
4. **`is_relevant_to_hapoel_pt`** — title/summary must mention Hapoel PT keywords
5. **URL deduplication** — skip if already in `seen_links.txt`
6. **Freshness** — skip articles older than 5 days
7. **Content extraction** — fetch full article via `extract_article_data()`
8. **Maccabi PT check #2** — re-check on full content
9. **Relevance check #2** — re-check on full content
10. **Topic-check via Gemini** — only if title isn't crystal clear (saves API calls!)
11. **Local duplicate detection** — Jaccard similarity on word sets (NOT Gemini)
12. **Summary via Gemini** — final journalistic summary
13. **Send to Telegram** — with image (or fallback poster if no image)

---

## ⚠️ CRITICAL DOMAIN KNOWLEDGE

### The "Two Petah Tikva Clubs" Problem
- **Hapoel Petah Tikva** (הפועל פ"ת) — OUR club. Plays in Premier League. Blue colors.
- **Maccabi Petah Tikva** (מכבי פ"ת) — RIVAL club. Plays in National League. Red colors.

These are **completely different clubs**. The bot must NEVER send articles about Maccabi PT.

The filter logic: if **only** Maccabi is mentioned (no Hapoel) → block. If both mentioned → pass to next filters.

### Current Squad/Staff Keywords (`HAPOEL_KEYS`)
- Coach: **עומר פרץ** (Omer Peretz) — common name, must combine with team context
- Players: אוראל דגני, עומר כץ, נדב נידם, מארק קוסטה, פורטונה דיארה, בוני אמיאן, etc.
- Stadium: מלאבס

### Maccabi PT Keywords (`MACCABI_PT_KEYS` — for blocking)
- Player to block: אור ישראלוב

---

## 💰 API Quota Management

### one.co.il (`/api/team/6`)
- **Quota**: none (free public API)
- **Strategy**: 1 call per run (~32/day). Same call serves both schedule and result lookup.
- **Returns** `upcomingMatches` (next fixtures) + `recentMatches` (results with score, isStarted, lastEvent)
- `schedule.json` is a **fallback cache** only — used when one.co.il is unavailable
- `BACKUP_SCHEDULE` (hardcoded dict) is the last-resort fallback

### Gemini API
- **Free tier**: per-model, varies (check https://ai.google.dev/gemini-api/docs/rate-limits)
- **Resets**: midnight Pacific Time = 10:00 AM Israel (PDT) / 11:00 AM Israel (PST)
- ⚠️ `gemini-2.0-flash` was dropped from free tier (limit: 0) in May 2026 — code now uses `gemini-2.5-flash`
- **Auto-fallback**: when primary model returns 429, `call_gemini` automatically retries with `GEMINI_FALLBACK_MODEL` (`gemini-2.5-flash-lite` — separate quota). Tracked per-model in `GEMINI_EXHAUSTED_MODELS` set.
- **Alert cadence**: admin alert only when *both* models exhaust, and at most once every `GEMINI_ALERT_COOLDOWN_DAYS` (3 days). Persisted in `gemini_last_alert.txt`.
- **Optimizations**:
  - `topic-check` skipped when title clearly mentions full Hapoel PT name
  - `dup-check` is local Jaccard similarity (no Gemini)
  - `MAX_ARTICLES_PER_RUN = 6` (was 8)

---

## 🏟️ Match Day Flow (when today's date matches a date in schedule.json)

| Time | Action | Source |
|------|--------|--------|
| 11:00+ | MatchDay message with random poster + opponent name | Local |
| Match time -3h | Betting poll | Local time calc |
| Match time +110min | Check `recentMatches` for today's score. If finished: send result + WIN_CHANTS | one.co.il (already fetched) |
| Same as above | Send MVP poll with `DEFAULT_PLAYERS` | Static |

---

## 📰 Active RSS Sources

1. **hapoelpt.com** — official club site (highest priority, treated as `is_official`)
2. **walla.co.il** feed/156 — Israeli football
3. **ynet.co.il** sport
4. **Google News** queries with `site:` operator for: sport5.co.il, sport1.maariv.co.il, one.co.il
5. **Google News** general fallback (filtered by `ALLOWED_DOMAINS` whitelist)

ONE.co.il direct RSS is broken (404) — accessed via Google News.

---

## ✅ Recent Improvements (April-May 2026)

- Fixed broken f-string in summary prompt (was sending literal `{content[:2500]}` to Gemini)
- Migrated from dead `gemini-1.5-flash` → `gemini-2.0-flash`
- Added `googlenewsdecoder` to resolve real URLs from Google News encoded links
- Switched walla feed/22 (general news) → feed/156 (Israeli football)
- Added Maccabi PT blocklist (rival club)
- Replaced Gemini-based duplicate detection with local Jaccard similarity
- **Replaced RapidAPI / API-Football with one.co.il public API** — free, no quota, single call serves schedule + results
- Removed `TEAM_TRANSLATION` and `PLAYER_MAP` (one.co.il returns Hebrew natively)
- Dynamic timing: betting 3h before match, results 110min after kickoff
- Tone: journalistic-fan (warm but professional, no slang)
- Fallback images from MATCHDAY_POSTERS when article has no image
- Filter out news site default logos from `og:image`

---

## 🐛 Known Issues / Things to Watch

- one.co.il is an unofficial public API — if they change the JSON shape, schedule/results break. Admin gets a one-time daily alert via `one_api_down` marker. `BACKUP_SCHEDULE` + cached `schedule.json` keep things going.
- Gemini daily quota — can run out if too many articles to process (mitigated by `GEMINI_QUOTA_EXCEEDED` flag)
- Some Google News links may fail to decode — those articles are skipped

---

## 🧪 How to Test Locally

```bash
# Set environment variables
export GEMINI_API_KEY="your_key"
export TELEGRAM_TOKEN="your_token"

# Make sure RUN_MODE = "ADMIN_ONLY" in bot.py for safe testing!

# Install dependencies
pip install -r requirements.txt

# Run once
python bot.py
```

**WARNING**: Local runs use the same persistent files (seen_links.txt, schedule.json). Articles processed locally will be marked as "seen" and won't be sent again from the GitHub Actions run.

---

## 🤝 Working Style Preferences

- **Hebrew is fine for explanations** — the user is Hebrew-speaking
- **Minimize API calls** — both Gemini and API-Football quotas are scarce
- **Always preserve filter pipeline ordering** — it's optimized to skip expensive checks early
- **Test in `ADMIN_ONLY` mode first** before pushing changes that affect output
- **Don't break the persistence files** (seen_links.txt, schedule.json, etc.) — they accumulate state across runs
