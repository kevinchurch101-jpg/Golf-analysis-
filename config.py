"""
Fairway Intel — Central Configuration
All API keys, schedule times, framework constants, and system settings.
"""
 
import os
from dataclasses import dataclass, field
from typing import Dict, List
 
# ─────────────────────────────────────────────
# API KEYS (from GitHub Secrets / environment)
# ─────────────────────────────────────────────
DATAGOLF_KEY    = os.environ.get("DATAGOLF_KEY", "")
ODDS_API_KEY    = os.environ.get("ODDS_API_KEY", "")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
GH_TOKEN        = os.environ.get("GH_TOKEN_PUSH", "")
 
# ─────────────────────────────────────────────
# GITHUB REPO
# ─────────────────────────────────────────────
GITHUB_REPO     = "kevinchurch101-jpg/Golf-analysis-"
GITHUB_BRANCH   = "main"
OUTPUT_FILE     = "index.html"
 
# ─────────────────────────────────────────────
# ANTHROPIC
# ─────────────────────────────────────────────
ANTHROPIC_MODEL     = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 4096
ANTHROPIC_BUDGET    = 5.00          # $5/month hard cap
 
# ─────────────────────────────────────────────
# SCHEDULE (ET) — cron strings for GitHub Actions
# Also used by local scheduler
# ─────────────────────────────────────────────
SCHEDULE = {
    "sunday_night":     "0 4 * * 1",    # Sunday 11pm ET = Monday 4am UTC
    "monday_6am":       "0 11 * * 1",   # Monday 6am ET  = Monday 11am UTC
    "monday_10am":      "0 15 * * 1",   # Monday 10am ET = Monday 3pm UTC
    "monday_7pm":       "0 0 * * 2",    # Monday 7pm ET  = Tuesday 12am UTC
    "tuesday_930am":    "30 14 * * 2",  # Tuesday 9:30am ET
    "tuesday_6pm":      "0 23 * * 2",   # Tuesday 6pm ET
    "wednesday_9am":    "0 14 * * 3",   # Wednesday 9am ET
    "wednesday_11am":   "0 16 * * 3",   # Wednesday 11am ET
    "wednesday_4pm":    "0 21 * * 3",   # Wednesday 4pm ET
}
 
# Which runs pull odds (odds release Monday 5-8am ET)
ODDS_RUNS = {
    "sunday_night", "monday_6am", "monday_10am",
    "monday_7pm", "tuesday_930am", "tuesday_6pm",
    "wednesday_9am", "wednesday_11am", "wednesday_4pm",
}
# Sunday night is articles + course setup ONLY — no odds
ARTICLES_ONLY_RUNS = {"sunday_night"}
 
# ─────────────────────────────────────────────
# DATAGOLF API
# ─────────────────────────────────────────────
DG_BASE = "https://feeds.datagolf.com"
 
DG_ENDPOINTS = {
    "player_list":          f"{DG_BASE}/get-player-list",
    "tour_schedule":        f"{DG_BASE}/get-schedule",
    "field_updates":        f"{DG_BASE}/field-updates/get-field",
    "dg_rankings":          f"{DG_BASE}/preds/get-dg-rankings",
    "pre_tournament_preds": f"{DG_BASE}/preds/pre-tournament",
    "skill_decompositions": f"{DG_BASE}/historical-raw/skill-decompositions",
    "skill_ratings":        f"{DG_BASE}/preds/skill-ratings",
    "approach_skill":       f"{DG_BASE}/preds/approach-skill",
    "fantasy_defaults":     f"{DG_BASE}/preds/fantasy-projection-defaults",
    "live_preds":           f"{DG_BASE}/preds/live-tournament-stats",
    "live_stats":           f"{DG_BASE}/preds/live-tournament-stats",
    "live_hole_scoring":    f"{DG_BASE}/preds/live-hole-scoring-stats",
    "historical_event_ids": f"{DG_BASE}/historical-raw/event-ids",
    "historical_rounds":    f"{DG_BASE}/historical-raw/round-scoring-stats",
    "historical_sg":        f"{DG_BASE}/historical-raw/round-scoring-stats",
    "historical_event_finishes": f"{DG_BASE}/historical-dfs/event-finishes",
    "historical_odds":      f"{DG_BASE}/historical-odds/outrights",
}
 
# Stat markets to pull from pre-tournament predictions
DG_PRED_MARKETS = ["win", "top_5", "top_10", "top_20", "make_cut"]
 
# Skill rating stat columns we care about
DG_SKILL_COLS = ["sg_putt", "sg_arg", "sg_app", "sg_ott", "sg_t2g", "sg_total",
                 "driving_dist", "driving_acc", "gir", "scrambling"]
 
# Approach yardage buckets
APPROACH_BUCKETS = ["100_125", "125_150", "150_175", "175_200", "200_225", "225_250", "250_275"]
 
# ─────────────────────────────────────────────
# ODDS API
# ─────────────────────────────────────────────
ODDS_BASE   = "https://api.the-odds-api.com/v4"
ODDS_SPORT  = "golf_pga"
ODDS_BOOKS  = ["draftkings", "betmgm", "fanduel", "caesars", "bet365"]
ODDS_PRIMARY_BOOKS = ["draftkings", "bet365"]
ODDS_MARKETS = ["outrights", "h2h"]    # outrights = winner market
 
# ─────────────────────────────────────────────
# FRAMEWORK CONSTANTS
# ─────────────────────────────────────────────
 
# Ball-striking form window
FORM_WINDOW = {
    "intriguing":        (1, 2),
    "comfortable":       (3, 5),
    "super_confident":   (6, 99),
}
SG_BALL_STRIKING_THRESHOLD = 0.20   # combined OTT+APP above career mean
SG_LOPSIDED_FLAG_THRESHOLD = 0.40   # one component this far below career = outlier flag
SG_SPIKE_OUTRIGHT      = 2.0     # 2+ SG total/round for outright
SG_WEEKLY_FLOOR        = 8.0     # 8-12+ SG for the week ball-striking
SG_CEILING_DEMO        = 2.5     # 2.5+ SG/round ceiling demonstrated
 
# Distance tier thresholds (yards vs Tour average)
DISTANCE_TIERS = {
    "elite_bomber":  15,     # +15 or more
    "above_average":  5,     # +5 to +15
    "average":       -5,     # -5 to +5
    "short":        -999,    # below -5
}
 
# Price flags
OUTRIGHT_MIN_ODDS      = 30      # 30/1 minimum for outright consideration
HENLEY_VALUE_TRIGGER   = 30      # Henley only intriguing at 30/1+
STRAKA_TRIGGER_NORMAL  = 45      # Must consider Straka at 45/1
STRAKA_TRIGGER_WEAK    = 30      # Must consider Straka at 30/1 in weak fields
HOVLAND_JT_TRIGGER     = 40      # Auto-consider Hovland/JT at 40/1+
KEITH_MITCHELL_TRIGGER = 50      # Only at 50/1+
FALLEN_STAR_TRIGGER    = 100     # Fallen stars intriguing at 100/1+
THORBJORNSEN_TRIGGER   = 50      # Only at bombers courses 50/1+
 
# McCarthy/Burns tier: elite career putter APP spike trigger
MCCCARTHY_APP_SPIKE    = 0.0     # Above career mean is sufficient
MCCARTHY_CAREER_PUTT   = 0.414
 
# Fowler APP threshold
FOWLER_APP_TRIGGER     = 0.300
FOWLER_MIN_ODDS        = 40
 
# Designation codes
DESIGNATIONS = {
    "EXTRA_CONFIRM_PLUS":  "EXTRA CONFIRM +",
    "FRAMEWORK":           "FRAMEWORK",
    "EXTRA_CONFIRM_MINUS": "EXTRA CONFIRM -",
    "FALLEN_STAR":         "FALLEN STAR",
}
 
# Tier labels
TIERS = {
    "S": "S Tier — Primary Targets",
    "A": "A Tier — Strong Plays",
    "B": "B Tier — Positions / FRL",
    "C": "C Tier — Pass / Monitor",
    "FADE": "Fade — Active Fades",
}
 
# Pool event tiers
POOL_TIERS = {
    "SIGNATURE": "Signature ($20M+)",
    "MAJOR":     "Major",
    "REGULAR":   "Regular ($8-10M)",
}
POOL_MAX_USES = 2
 
# ─────────────────────────────────────────────
# ARTICLE SOURCES
# ─────────────────────────────────────────────
ARTICLE_SOURCES = [
    {
        "name":     "Haslbauer",
        "outlet":   "lineups.com",
        "weight":   10,        # HIGHEST
        "note":     "Up to 3+ articles/week, more for majors. Preview, longshots, final card.",
        "urls": [
            "https://www.lineups.com/golf/picks",
            "https://www.lineups.com/golf/matchups",
        ],
    },
    {
        "name":     "Steve Bamford",
        "outlet":   "golfbettingsystem.co.uk",
        "weight":   9,
        "note":     "8-event SG rankings + weather forecast + wind by round + course conditions.",
        "urls": [
            "https://www.golfbettingsystem.co.uk",
        ],
    },
    {
        "name":     "Ben Coley",
        "outlet":   "sportinglife.com",
        "weight":   8,
        "note":     "Strong instincts, good longshots.",
        "urls": [
            "https://www.sportinglife.com/golf",
        ],
    },
    {
        "name":     "Steve Rawlings",
        "outlet":   "betfair.com",
        "weight":   7,
        "note":     "Course read, wind analysis, architecture.",
        "urls": [
            "https://betting.betfair.com/golf",
        ],
    },
    {
        "name":     "Dave Tindall",
        "outlet":   "betfair.com",
        "weight":   7,
        "note":     "Solid weekly preview.",
        "urls": [
            "https://betting.betfair.com/golf",
        ],
    },
    {
        "name":     "Tom Jacobs",
        "outlet":   "oddschecker.com",
        "weight":   6,
        "note":     "Good supplementary.",
        "urls": [
            "https://www.oddschecker.com/golf",
        ],
    },
    {
        "name":     "Sharpside / Matt Gannon",
        "outlet":   "sharpside.ai",
        "weight":   6,
        "note":     "Expected approach yardages, key stat buckets.",
        "urls": [
            "https://sharpside.ai/golf",
        ],
    },
]
 
# ─────────────────────────────────────────────
# STATE FILE
# ─────────────────────────────────────────────
STATE_FILE = "state/weekly_state.json"
STATE_VERSION = "3.0"
 
# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
LOG_DATE   = "%Y-%m-%d %H:%M:%S ET"
