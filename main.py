"""
Fairway Intel — Main Orchestrator
Runs all 9 scheduled weekly runs. Incremental not full rewrite each time.
Sunday 11pm: articles + course setup only (no odds)
Monday 6am onward: odds layer in
Wednesday 4pm: final card
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Optional

import pytz

import config
from data.datagolf   import pull_all_weekly_data, get_field_updates
from data.odds       import get_full_odds_snapshot, find_value_plays
from data.articles   import (fetch_all_articles, summarize_article_bundle,
                              search_for_prior_year_articles,
                              extract_course_structure_from_prior_year,
                              build_prior_year_course_summary)
from data.weather    import get_full_weather

from analysis.framework import build_player_framework_score
from analysis.players   import get_player, PLAYER_DB
from analysis.course    import get_course_profile, build_course_profile_from_description
from analysis.frl       import rank_frl_candidates, build_frl_card
from analysis.pool      import PoolUsageTracker, build_pool_section, determine_event_tier
from analysis.prompt    import (
    build_sunday_analysis_prompt,
    build_incremental_update_prompt,
    call_claude_api,
    parse_claude_response,
)

from output.html_builder import build_full_html
from output.briefing     import (
    build_briefing_from_claude_response,
    update_briefing_incrementally,
    generate_placeholder_briefing,
    format_briefing_for_html,
)
from output.github_push  import push_html, push_state_file, fetch_state_file, test_connection

# Logging setup
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE,
)
log = logging.getLogger("fairway_intel.main")

ET = pytz.timezone("America/New_York")


# ─────────────────────────────────────────────────────────────
# RUN TYPE DETECTION
# ─────────────────────────────────────────────────────────────

def detect_run_type() -> str:
    """
    Detect which scheduled run this is based on env var or current time.
    GitHub Actions passes RUN_TYPE env var. Local runs use time-based detection.
    """
    import os
    run_type = os.environ.get("RUN_TYPE")
    if run_type:
        return run_type

    now_et = datetime.now(ET)
    dow    = now_et.weekday()   # 0=Mon … 6=Sun
    hour   = now_et.hour
    minute = now_et.minute

    if dow == 6 and hour >= 23:         return "sunday_night"
    if dow == 0 and hour == 6:          return "monday_6am"
    if dow == 0 and hour == 10:         return "monday_10am"
    if dow == 0 and hour >= 19:         return "monday_7pm"
    if dow == 1 and hour == 9:          return "tuesday_930am"
    if dow == 1 and hour >= 18:         return "tuesday_6pm"
    if dow == 2 and hour == 9:          return "wednesday_9am"
    if dow == 2 and hour == 11:         return "wednesday_11am"
    if dow == 2 and hour >= 16:         return "wednesday_4pm"

    return "manual"


def is_odds_run(run_type: str) -> bool:
    return run_type not in config.ARTICLES_ONLY_RUNS


def is_final_run(run_type: str) -> bool:
    return run_type == "wednesday_4pm"


# ─────────────────────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────────────────────

def load_state() -> Dict:
    """Load state from GitHub repo. Always merge with defaults so missing keys never crash."""
    defaults = _default_state()

    raw = fetch_state_file()
    if not raw:
        log.info("[Main] No existing state — loading empty template.")
        try:
            with open(config.STATE_FILE, "r") as f:
                raw = json.load(f)
        except FileNotFoundError:
            log.warning("[Main] No local state file — using minimal default.")
            return defaults

    # Deep-merge: defaults provide missing top-level keys and sub-keys
    # so that a bare {} or partial state never causes KeyErrors downstream
    def _merge(base: Dict, override: Dict) -> Dict:
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = _merge(result[k], v)
            else:
                result[k] = v
        return result

    state = _merge(defaults, raw)
    log.info("[Main] State loaded and merged with defaults.")
    return state


def save_state(state: Dict) -> bool:
    """Save state to GitHub repo."""
    ok, msg = push_state_file(state)
    if ok:
        log.info(f"[Main] State saved: {msg}")
    else:
        log.error(f"[Main] State save failed: {msg}")
    return ok


def _default_state() -> Dict:
    return {
        "_version": config.STATE_VERSION,
        "event": {}, "weather": {}, "field": [], "odds": {"by_player": {}},
        "dg_predictions": {"by_player": {}}, "skill_ratings": {"by_player": {}},
        "approach_skill": {"by_player": {}}, "course_history": {"by_player": {}},
        "frl_stats": {"by_player": {}}, "articles": {"processed": [], "blocked": [], "key_narratives": []},
        "analysis": {
            "briefing_paragraph": "", "overall_ranking": [], "value_ranking": [],
            "tiers": {"S": [], "A": [], "B": [], "C": [], "FADE": []},
            "player_notes": {}, "last_updated": None,
        },
        "bet_card": {"outrights": [], "positions": [], "frl": [], "hard_fades": [], "last_updated": None},
        "pool": {}, "flags": {
            "blocked_articles": [], "odds_gaps": [], "data_anomalies": [],
            "analysis_uncertainties": [], "manual_interventions": [],
            "article_log": [], "calibration_suggestions": [], "withdrawals": [],
        },
        "run_log": [],
    }


# ─────────────────────────────────────────────────────────────
# DATA PULL LAYER
# ─────────────────────────────────────────────────────────────

def pull_datagolf_data(state: Dict) -> Dict:
    """Pull all DataGolf endpoints and merge into state."""
    log.info("[Main] Pulling DataGolf data…")
    dg_data = pull_all_weekly_data()

    state["field"] = dg_data.get("field", state.get("field", []))

    # Skill ratings — keyed by player name
    ratings = dg_data.get("skill_ratings", {})
    state.setdefault("skill_ratings", {})["by_player"] = ratings
    state["skill_ratings"]["last_updated"] = _now()

    # Approach skill
    approach = dg_data.get("approach_skill", {})
    state.setdefault("approach_skill", {})["by_player"] = approach
    state["approach_skill"]["last_updated"] = _now()

    # Predictions
    preds = dg_data.get("predictions", {})
    state.setdefault("dg_predictions", {})["by_player"] = preds
    state["dg_predictions"]["last_updated"] = _now()

    # Extract event name and course from field data if not already set
    field = state.get("field", [])
    if field and not state.get("event", {}).get("name"):
        # DataGolf field data often includes event_name in the response metadata
        first_player = field[0] if field else {}
        event_name = first_player.get("event_name") or first_player.get("tournament_name")
        course_name = first_player.get("course_name") or first_player.get("course")
        if event_name:
            state.setdefault("event", {})["name"] = event_name
            log.info(f"[Main] Event name from field data: {event_name}")
        if course_name:
            state.setdefault("event", {})["course"] = course_name

    # Enrich event with course_type from known course profiles
    if not state.get("event", {}).get("course_type"):
        from analysis.course import get_course_profile
        course_key = (state.get("event", {}).get("course") or "").lower().replace(" ", "_")
        cp = get_course_profile(course_key)
        if cp:
            state.setdefault("event", {})["course_type"]   = cp.course_type
            state["event"]["course_avg_acc"]                = cp.course_avg_acc
            state["event"]["rough_penalty"]                 = cp.rough_penalty
            state["event"]["distance_multiplier"]           = cp.distance_multiplier
            log.info(f"[Main] Course profile matched: {cp.name} | type={cp.course_type}")
    
    # Detect event from active odds sport key — do NOT hardcode any specific tournament
    if not state.get("event", {}).get("name"):
        from data.odds import get_active_golf_sport_key
        from analysis.course import get_course_profile

        sport_key = get_active_golf_sport_key() or ""
        log.info(f"[Main] Detecting event from odds sport key: {sport_key}")

        SPORT_KEY_MAP = {
            "golf_masters_tournament_winner": {
                "name": "Masters Tournament",
                "course": "Augusta National Golf Club",
                "location": "Augusta, GA",
                "par": 72, "yardage": 7545, "event_tier": "MAJOR",
                "course_key": "augusta_national",
            },
            "golf_pga_championship": {
                "name": "PGA Championship",
                "course": "TBD", "location": "TBD",
                "par": 72, "yardage": 7500, "event_tier": "MAJOR",
                "course_key": None,
            },
            "golf_us_open": {
                "name": "U.S. Open",
                "course": "TBD", "location": "TBD",
                "par": 70, "yardage": 7500, "event_tier": "MAJOR",
                "course_key": None,
            },
            "golf_the_open_championship": {
                "name": "The Open Championship",
                "course": "TBD", "location": "TBD",
                "par": 70, "yardage": 7300, "event_tier": "MAJOR",
                "course_key": None,
            },
        }

        event_info = SPORT_KEY_MAP.get(sport_key)
        if event_info:
            course_key = event_info.pop("course_key", None)
            state.setdefault("event", {}).update(event_info)
            if course_key:
                cp = get_course_profile(course_key)
                if cp:
                    state["event"]["course_type"]         = cp.course_type
                    state["event"]["rough_penalty"]       = cp.rough_penalty
                    state["event"]["distance_multiplier"] = cp.distance_multiplier
                    state["event"]["dominant_stat"]       = cp.dominant_stat
                    state["event"]["course_notes"]        = cp.course_notes
                    state["event"]["angle_penalty"]       = cp.angle_penalty
            log.info(f"[Main] Event detected from sport key: {state['event']['name']}")
        else:
            # Regular PGA Tour event — detect from field data or DG schedule
            event_detected = False

            # Strategy A: field data often has event_name in each player entry
            field = state.get("field", [])
            for player in field[:5]:
                ename = player.get("event_name") or player.get("tournament_name") or player.get("event")
                cname = player.get("course_name") or player.get("course")
                if ename and len(ename) > 3:
                    state.setdefault("event", {})["name"]   = ename
                    if cname:
                        state["event"]["course"] = cname
                    log.info(f"[Main] Event name from field data: {ename}")
                    event_detected = True
                    break

            # Strategy B: DG schedule — match by date window
            if not event_detected:
                try:
                    from data.datagolf import get_tour_schedule
                    from datetime import date, timedelta
                    schedule = get_tour_schedule(tour="pga")
                    if schedule:
                        today = date.today().isoformat()
                        # Look 3 days back and 7 days forward to catch current week
                        window_start = (date.today() - timedelta(days=3)).isoformat()
                        window_end   = (date.today() + timedelta(days=7)).isoformat()
                        for event in schedule:
                            start = event.get("date", event.get("start_date", ""))
                            end   = event.get("end_date", start)
                            if not start:
                                continue
                            if start <= window_end and end >= window_start:
                                ename = event.get("event_name") or event.get("name", "")
                                cname = event.get("course") or event.get("course_name", "")
                                loc   = event.get("location", "")
                                if ename:
                                    state.setdefault("event", {})["name"]   = ename
                                    if cname: state["event"]["course"]       = cname
                                    if loc:   state["event"]["location"]     = loc
                                    log.info(f"[Main] Event from DG schedule: {ename}")
                                    event_detected = True
                                    break
                except Exception as e:
                    log.warning(f"[Main] Could not get event from DG schedule: {e}")

            # Strategy C: field endpoint often has event_name at top level
            if not event_detected:
                try:
                    from data.datagolf import get_field_updates
                    raw_field = get_field_updates()
                    if isinstance(raw_field, dict):
                        ename = raw_field.get("event_name") or raw_field.get("tournament")
                        cname = raw_field.get("course")
                        if ename:
                            state.setdefault("event", {})["name"] = ename
                            if cname: state["event"]["course"] = cname
                            log.info(f"[Main] Event from field endpoint: {ename}")
                            event_detected = True
                except Exception as e:
                    log.warning(f"[Main] Could not get event from field endpoint: {e}")

            if not event_detected:
                log.warning("[Main] Could not detect current event name — showing as pending")

    log.info(f"[Main] DataGolf: {len(state['field'])} field players, "
             f"{len(ratings)} skill ratings, {len(preds)} predictions.")
    return state


def pull_odds_data(state: Dict) -> Dict:
    """Pull odds and merge into state."""
    log.info("[Main] Pulling odds…")
    odds_snap = get_full_odds_snapshot()

    if not odds_snap:
        log.warning("[Main] No odds returned — flagging.")
        state["flags"]["data_anomalies"].append(f"No odds returned at {_now()}")
        return state

    state.setdefault("odds", {})["by_player"] = odds_snap
    state["odds"]["last_updated"] = _now()

    # Flag players in field with no odds
    field_names = {p.get("name", "") for p in state.get("field", [])}
    odds_names  = set(odds_snap.keys())
    missing     = field_names - odds_names
    for name in sorted(missing)[:20]:   # Cap at 20 flags
        state["flags"]["odds_gaps"].append(f"{name} — no odds found at {_now()}")

    log.info(f"[Main] Odds: {len(odds_snap)} players. {len(missing)} gaps flagged.")
    return state


def pull_articles(state: Dict) -> Dict:
    """Fetch and process articles."""
    log.info("[Main] Fetching articles…")
    bundle = fetch_all_articles()
    summary = summarize_article_bundle(bundle)

    # Log processed articles
    for a in bundle.successful:
        entry = {"source": a.source_name, "title": a.title, "time": _now()}
        state["articles"]["processed"].append(entry)
        state["flags"]["article_log"].append(f"✓ {a.source_name} — {a.title[:60]}")

    # Flag blocked articles — never silently skip
    for b in bundle.blocked:
        entry = {"source": b.source_name, "url": b.url, "reason": b.block_reason, "time": _now()}
        state["articles"]["blocked"].append(entry)
        flag = f"BLOCKED: {b.source_name} ({b.outlet}) — {b.block_reason} — {b.url}"
        state["flags"]["blocked_articles"].append(flag)
        log.warning(f"[Main] Article blocked: {flag}")

    state["articles"]["last_sweep"] = _now()

    log.info(f"[Main] Articles: {len(bundle.successful)} success, {len(bundle.blocked)} blocked.")
    return state, summary


def pull_weather(state: Dict) -> Dict:
    """Fetch weather for tournament venue."""
    event = state.get("event", {})
    location = event.get("location") or event.get("course")
    start_date = (event.get("dates") or "").split("–")[0].strip()

    if not location:
        log.warning("[Main] No event location for weather fetch.")
        return state

    log.info(f"[Main] Fetching weather for '{location}'…")
    weather = get_full_weather(location=location, tournament_start_date=start_date or "2026-04-10")

    state["weather"] = weather
    state["weather"]["bamford_forecast"] = state.get("weather", {}).get("bamford_forecast")
    log.info(f"[Main] Weather fetched. Wave split: {weather.get('wave_split_matters', False)}")
    return state


# ─────────────────────────────────────────────────────────────
# ANALYSIS LAYER
# ─────────────────────────────────────────────────────────────

def run_claude_analysis(state: Dict, run_type: str, article_summary: Optional[Dict] = None) -> Dict:
    """
    Call Claude API with appropriate prompt for this run type.
    Sunday: full analysis. Subsequent runs: incremental updates.
    """
    log.info(f"[Main] Running Claude analysis for run type: {run_type}…")

    # Build prompt
    if run_type == "sunday_night":
        if article_summary:
            state["articles"]["key_narratives"] = article_summary.get("articles", [])
        prior_summary = state.get("articles", {}).get("prior_year_summary_text", "")
        prompt = build_sunday_analysis_prompt(state, prior_year_summary=prior_summary)
    elif run_type in ("monday_6am", "monday_10am") and state["odds"].get("by_player"):
        prompt = build_incremental_update_prompt(state, "odds_update", state["odds"]["by_player"])
    elif run_type in ("monday_7pm", "tuesday_930am", "tuesday_6pm") and article_summary:
        prompt = build_incremental_update_prompt(state, "article_update", article_summary)
    elif run_type in ("wednesday_9am", "wednesday_11am", "wednesday_4pm"):
        prompt = build_incremental_update_prompt(state, "odds_update", state["odds"].get("by_player", {}))
    else:
        log.info("[Main] No Claude call warranted for this run type.")
        return state

    response = call_claude_api(prompt)

    if response:
        parsed = parse_claude_response(response)
        state = _merge_analysis(state, parsed, run_type)
        log.info(f"[Main] Claude analysis merged.")
    else:
        log.warning("[Main] Claude API returned no response.")
        # Generate placeholder if this is the first run
        if not state["analysis"].get("briefing_paragraph"):
            state["analysis"]["briefing_paragraph"] = generate_placeholder_briefing(
                state.get("event", {}), state.get("weather", {})
            )

    state["analysis"]["last_updated"] = _now()
    return state


def run_frl_analysis(state: Dict) -> Dict:
    """Run FRL scoring and build FRL section of bet card."""
    log.info("[Main] Running FRL analysis…")
    field = state.get("field", [])
    weather = state.get("weather", {})
    skill_ratings = state.get("skill_ratings", {}).get("by_player", {})
    odds_snap = state.get("odds", {}).get("by_player", {})

    # Enrich field with odds + skill data
    frl_stats = state.get("frl_stats", {}).get("by_player", {})
    enriched_field = []
    for player in field:
        name = player.get("name", "")
        skills    = skill_ratings.get(name, {})
        odds_data = odds_snap.get(name, {})
        frl_data  = frl_stats.get(name, {})
        enriched = {
            **player,
            "sg_ott": skills.get("sg_ott"),
            "sg_app": skills.get("sg_app"),
            "sg_putt_recent": skills.get("sg_putt"),
            "odds_american": odds_data.get("best_price"),
            "implied_prob": odds_data.get("implied_prob"),
            # Player-specific R1 scoring history at this course
            "r1_scoring_avg_hist": frl_data.get("r1_scoring_avg_hist"),
            "birdie_rate": frl_data.get("birdie_rate"),
        }
        enriched_field.append(enriched)

    candidates = rank_frl_candidates(
        field_data=enriched_field,
        weather_data=weather,
        course_r1_scoring_avg=state.get("event", {}).get("r1_scoring_avg"),
    )

    from analysis.frl import get_frl_top_targets
    top = get_frl_top_targets(candidates, n=5)
    frl_card = build_frl_card(top, max_bets=3)
    state["bet_card"]["frl"] = frl_card

    log.info(f"[Main] FRL: {len(frl_card)} targets identified.")
    return state


def run_pool_analysis(state: Dict) -> Dict:
    """Build pool section. Always completely separate from bet card."""
    log.info("[Main] Running pool analysis…")
    event = state.get("event", {})
    field = state.get("field", [])

    event_tier = determine_event_tier(
        event.get("name") or "",
        event.get("purse"),
    )
    state["event"]["event_tier"] = event_tier

    usage_data = state.get("pool", {}).get("usage_tracker", {})
    usage_tracker = PoolUsageTracker(usage_data)

    preds = state.get("dg_predictions", {}).get("by_player", {})

    # Mark LIV players in field
    from analysis.players import get_player
    enriched_field = []
    for p in field:
        name = p.get("name", "")
        profile = get_player(name)
        enriched_field.append({**p, "is_liv": profile.is_liv if profile else False})

    pool = build_pool_section(
        field_data=enriched_field,
        usage_tracker=usage_tracker,
        event_name=event.get("name", ""),
        event_tier=event_tier,
        dg_predictions=preds,
    )

    state["pool"] = pool
    primary_pick = pool.get('primary_pick') or {}
    log.info(f"[Main] Pool: primary={primary_pick.get('player', 'TBD')}, "
             f"tier={event_tier}")
    return state


def run_value_analysis(state: Dict) -> Dict:
    """Cross-reference odds vs DG predictions to find value plays."""
    log.info("[Main] Running value analysis…")
    odds_snap = state.get("odds", {}).get("by_player", {})
    preds     = state.get("dg_predictions", {}).get("by_player", {})

    if not odds_snap or not preds:
        log.info("[Main] Odds or predictions not available yet — skipping value analysis.")
        return state

    value_plays = find_value_plays(odds_snap, preds, min_odds=30)
    value_ranking = [
        {
            "player": v["player"],
            "odds":   f'+{v["best_price_american"]}',
            "edge":   v["edge"],
            "note":   f'DG: {v["dg_win_prob"]:.1%} | Market: {v["implied_prob"]:.1%} | Edge: +{v["edge"]:.1%}',
        }
        for v in value_plays[:15]
    ]
    state["analysis"]["value_ranking"] = value_ranking
    log.info(f"[Main] Value analysis: {len(value_plays)} value plays identified.")
    return state


# ─────────────────────────────────────────────────────────────
# OUTPUT LAYER
# ─────────────────────────────────────────────────────────────

def publish(state: Dict) -> bool:
    """Build HTML and push to GitHub Pages."""
    log.info("[Main] Building HTML…")
    html = build_full_html(state)

    log.info("[Main] Pushing to GitHub Pages…")
    ok, msg = push_html(html)

    if ok:
        log.info(f"[Main] Published: {msg}")
    else:
        log.error(f"[Main] Publish failed: {msg}")
        state["flags"]["data_anomalies"].append(f"Publish failed at {_now()}: {msg}")

    return ok


# ─────────────────────────────────────────────────────────────
# MERGE HELPERS
# ─────────────────────────────────────────────────────────────

def _merge_analysis(state: Dict, parsed: Dict, run_type: str) -> Dict:
    """Merge Claude API response into state. Incremental — never full rewrite."""
    analysis = state.setdefault("analysis", {})
    bet_card = state.setdefault("bet_card", {})

    if parsed.get("briefing_paragraph"):
        if run_type == "sunday_night":
            analysis["briefing_paragraph"] = format_briefing_for_html(
                build_briefing_from_claude_response(parsed["raw_response"])
            )
        else:
            # Incremental update
            new_info = parsed.get("briefing_paragraph", "")
            if new_info:
                analysis["briefing_paragraph"] = update_briefing_incrementally(
                    analysis.get("briefing_paragraph", ""),
                    new_info,
                    "article_update" if "article" in run_type else "odds_context",
                )

    if parsed.get("overall_ranking"):
        analysis["overall_ranking"] = parsed["overall_ranking"]
    if parsed.get("value_ranking"):
        analysis["value_ranking"] = parsed["value_ranking"]
    if parsed.get("tiers"):
        for tier_key in ("S", "A", "B", "C", "FADE"):
            if parsed["tiers"].get(tier_key):
                analysis["tiers"][tier_key] = parsed["tiers"][tier_key]

    if parsed.get("flags"):
        for flag in parsed["flags"]:
            state["flags"]["analysis_uncertainties"].append(f"[Claude] {flag}")

    return state


# ─────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────

def run(run_type: Optional[str] = None, force_full: bool = False):
    """
    Main run function. Called by GitHub Actions or local scheduler.
    run_type: override run type (e.g. "sunday_night")
    force_full: if True, run all steps regardless of run_type
    """
    run_type = run_type or detect_run_type()
    start    = datetime.now(ET)
    log.info(f"\n{'='*60}")
    log.info(f"[Main] Starting run: {run_type} at {start.strftime('%Y-%m-%d %H:%M ET')}")
    log.info(f"{'='*60}")

    # 1. Test connection
    ok, msg = test_connection()
    if not ok:
        log.error(f"[Main] GitHub connection failed: {msg}. Aborting.")
        sys.exit(1)
    log.info(f"[Main] GitHub OK: {msg}")

    # 2. Load state
    state = load_state()

    # 3. Data pulls
    state = pull_datagolf_data(state)

    article_summary = None
    if run_type == "sunday_night" or force_full:
        state = pull_weather(state)
        state, article_summary = pull_articles(state)

        # Prior year course breakdown — structural context only
        # Fetched once Sunday night. Player notes discarded. Course structure kept.
        log.info("[Main] Fetching prior year articles for course structure…")
        event_name = state.get("event", {}).get("name", "")
        if event_name:
            prior_bundle  = search_for_prior_year_articles(event_name)
            prior_extract = extract_course_structure_from_prior_year(prior_bundle)
            prior_summary = build_prior_year_course_summary(prior_extract)
            state.setdefault("articles", {})["prior_year_course_structure"] = prior_extract
            state["articles"]["prior_year_summary_text"] = prior_summary
            log.info(
                f"[Main] Prior year: {len(prior_bundle.successful)} articles fetched, "
                f"{prior_extract['discarded_player_notes']} player-form paragraphs discarded."
            )
            # Flag any blocked prior year sources
            for b in prior_bundle.blocked:
                state["flags"]["article_log"].append(
                    f"PRIOR YEAR BLOCKED: {b.source_name} — {b.block_reason}"
                )
        else:
            prior_summary = ""
            log.warning("[Main] No event name — skipping prior year article fetch.")

    elif run_type in ("monday_7pm", "tuesday_930am", "tuesday_6pm"):
        state, article_summary = pull_articles(state)

    if is_odds_run(run_type):
        state = pull_odds_data(state)

    # 4. Analysis
    state = run_claude_analysis(state, run_type, article_summary)
    state = run_frl_analysis(state)
    state = run_pool_analysis(state)

    if is_odds_run(run_type):
        state = run_value_analysis(state)

    # 5. Bet card — on final run, ensure it's complete
    if is_final_run(run_type):
        log.info("[Main] Final run — ensuring bet card is complete.")
        if not state["bet_card"].get("outrights"):
            state["flags"]["analysis_uncertainties"].append(
                "Final run: no outrights on bet card — manual review needed"
            )
        state["bet_card"]["last_updated"] = _now()

    # 6. Log this run
    state["run_log"].append({
        "time":     _now(),
        "run_type": run_type,
        "status":   "complete",
        "field_size": len(state.get("field", [])),
        "odds_players": len(state.get("odds", {}).get("by_player", {})),
    })

    # 7. Save state + publish
    save_state(state)
    published = publish(state)

    elapsed = (datetime.now(ET) - start).total_seconds()
    log.info(f"\n[Main] Run complete in {elapsed:.1f}s. Published: {published}")
    log.info(f"[Main] Live site: https://kevinchurch101-jpg.github.io/Golf-analysis-/")

    return state


def _now() -> str:
    return datetime.now(ET).isoformat()


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fairway Intel")
    parser.add_argument("--run-type", default=None, help="Force a specific run type")
    parser.add_argument("--now",      action="store_true", help="Run immediately (ignore schedule)")
    parser.add_argument("--full",     action="store_true", help="Run all steps regardless of type")
    parser.add_argument("--test",     action="store_true", help="Test GitHub connection only")
    args = parser.parse_args()

    if args.test:
        ok, msg = test_connection()
        print(f"GitHub connection: {'✓' if ok else '✗'} {msg}")
        sys.exit(0 if ok else 1)

    run_type = args.run_type or ("manual" if args.now else None)
    run(run_type=run_type, force_full=args.full)
