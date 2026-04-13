"""
Fairway Intel — DataGolf API Client
Pulls all endpoints needed for analysis. Never skips any.
Recent window always preferred over career averages.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from config import (
    DATAGOLF_KEY, DG_BASE, DG_ENDPOINTS, DG_PRED_MARKETS,
    DG_SKILL_COLS, APPROACH_BUCKETS,
)

log = logging.getLogger(__name__)

# Retry settings
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # seconds


def _get(url: str, params: Dict, label: str) -> Optional[Dict]:
    """GET with retry logic and consistent error handling."""
    # Don't double-add key if already in params
    if "key" not in params:
        params = {**params, "key": DATAGOLF_KEY}
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 404:
                # 404 often means no active event or endpoint requires different params
                # Log as warning not error — not a system failure
                log.warning(f"[DG] {label} returned 404 — may be no active event or wrong params")
                return None
            elif r.status_code == 429:
                wait = _RETRY_DELAY * attempt * 2
                log.warning(f"[DG] Rate limited on {label}. Waiting {wait}s…")
                time.sleep(wait)
            else:
                log.error(f"[DG] {label} returned HTTP {r.status_code}: {r.text[:200]}")
                return None
        except requests.RequestException as e:
            log.error(f"[DG] {label} attempt {attempt} failed: {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY * attempt)
    log.error(f"[DG] {label} failed after {_MAX_RETRIES} attempts.")
    return None


# ──────────────────────────────────────────────────────────────
# FIELD & SCHEDULE
# ──────────────────────────────────────────────────────────────

def get_player_list() -> List[Dict]:
    """Master player list with dg_id mappings."""
    data = _get(DG_ENDPOINTS["player_list"], {}, "player_list")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("players", [])


def get_tour_schedule(tour: str = "pga") -> List[Dict]:
    """Full tour schedule for the season."""
    data = _get(DG_ENDPOINTS["tour_schedule"], {"tour": tour}, "tour_schedule")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("schedule", [])


def get_field_updates(tour: str = "pga", file_format: str = "json") -> List[Dict]:
    """
    Current field with tee times, groups, and wave assignments.
    Wave assignment is critical for FRL analysis.
    DataGolf field-updates endpoint requires tour param.
    Returns empty list gracefully if no active event.
    """
    data = _get(
        DG_ENDPOINTS["field_updates"],
        {"tour": tour, "file_format": file_format, "key": DATAGOLF_KEY},
        "field_updates",
    )
    if not data:
        return []
    # Normalize — can come back as list or dict with 'field' key
    if isinstance(data, list):
        return data
    return data.get("field", data.get("players", []))


# ──────────────────────────────────────────────────────────────
# SKILL RATINGS (RECENT WINDOW — NEVER CAREER AVERAGE)
# ──────────────────────────────────────────────────────────────

def get_skill_ratings(
    display: str = "value",
    tour: str = "pga",
) -> Dict[str, Dict]:
    """
    Recent-window skill ratings for the full field.
    display='value' returns actual SG numbers not ranks.
    ALWAYS use recent window per framework — career averages actively mislead.
    Returns dict keyed by player_name → skill dict.
    """
    data = _get(
        DG_ENDPOINTS["skill_ratings"],
        {"display": display, "tour": tour},
        "skill_ratings",
    )
    if not data:
        return {}

    players = data if isinstance(data, list) else data.get("players", [])
    result = {}
    for p in players:
        name = _normalize_name(p)
        if not name:
            continue
        result[name] = {
            col: p.get(col) for col in DG_SKILL_COLS
        }
        result[name]["dg_id"] = p.get("dg_id")
        result[name]["player_name"] = name
    return result


def get_skill_decompositions(
    tour: str = "pga",
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
) -> Dict[str, List[Dict]]:
    """
    Year-by-year skill decompositions — recent years weight more.
    Critical for identifying inflection points in player development.
    Returns dict keyed by player_name → list of yearly stat dicts.
    """
    params: Dict[str, Any] = {"tour": tour}
    if year_start:
        params["year_start"] = year_start
    if year_end:
        params["year_end"] = year_end

    data = _get(DG_ENDPOINTS["skill_decompositions"], params, "skill_decompositions")
    if not data:
        return {}

    players = data if isinstance(data, list) else data.get("players", [])
    result: Dict[str, List[Dict]] = {}
    for p in players:
        name = _normalize_name(p)
        if not name:
            continue
        # Each entry is one season's stats
        entry = {k: v for k, v in p.items() if k not in ("player_name", "player_name_encoded", "dg_id")}
        entry["dg_id"] = p.get("dg_id")
        result.setdefault(name, []).append(entry)

    # Sort each player's history oldest→newest
    for name in result:
        result[name].sort(key=lambda x: x.get("year", 0))

    return result


def get_approach_skill(
    tour: str = "pga",
) -> Dict[str, Dict]:
    """
    Approach SG broken out by yardage bucket.
    Identifies distance-dependent strengths and weaknesses.
    Critical for matching players to course yardage profiles.
    Returns dict keyed by player_name → bucket dict.
    """
    data = _get(DG_ENDPOINTS["approach_skill"], {"tour": tour}, "approach_skill")
    if not data:
        return {}

    players = data if isinstance(data, list) else data.get("players", [])
    result = {}
    for p in players:
        name = _normalize_name(p)
        if not name:
            continue
        buckets = {}
        for bucket in APPROACH_BUCKETS:
            buckets[bucket] = p.get(f"sg_app_{bucket}")
        result[name] = {
            "buckets": buckets,
            "dg_id": p.get("dg_id"),
        }
    return result


# ──────────────────────────────────────────────────────────────
# PRE-TOURNAMENT PREDICTIONS
# ──────────────────────────────────────────────────────────────

def get_pre_tournament_predictions(
    tour: str = "pga",
    add_position_data: str = "no",
) -> Dict[str, Dict]:
    """
    DG model win/top5/top10/top20 probabilities.
    Returns dict keyed by player_name → {win, top_5, top_10, top_20, make_cut, dg_id}.
    """
    data = _get(
        DG_ENDPOINTS["pre_tournament_preds"],
        {"tour": tour, "add_position_data": add_position_data},
        "pre_tournament_predictions",
    )
    if not data:
        return {}

    players = data if isinstance(data, list) else data.get("baseline_history_fit", data.get("players", []))
    result = {}
    for p in players:
        name = _normalize_name(p)
        if not name:
            continue
        result[name] = {
            "win":     p.get("win"),
            "top_5":   p.get("top_5"),
            "top_10":  p.get("top_10"),
            "top_20":  p.get("top_20"),
            "make_cut": p.get("make_cut"),
            "dg_id":   p.get("dg_id"),
        }
    return result


def get_dg_rankings(
    tour: str = "pga",
    file_format: str = "json",
) -> List[Dict]:
    """DataGolf official rankings list."""
    data = _get(
        DG_ENDPOINTS["dg_rankings"],
        {"tour": tour, "file_format": file_format},
        "dg_rankings",
    )
    if not data:
        return []
    return data if isinstance(data, list) else data.get("rankings", [])


def get_fantasy_defaults(
    tour: str = "pga",
    site: str = "draftkings",
    slate: str = "main",
) -> List[Dict]:
    """Fantasy projection defaults — useful for salary/ownership context."""
    data = _get(
        DG_ENDPOINTS["fantasy_defaults"],
        {"tour": tour, "site": site, "slate": slate},
        "fantasy_defaults",
    )
    if not data:
        return []
    return data if isinstance(data, list) else data.get("projections", [])


# ──────────────────────────────────────────────────────────────
# LIVE DATA
# ──────────────────────────────────────────────────────────────

def get_live_predictions(tour: str = "pga") -> Dict[str, Dict]:
    """Live win probabilities during tournament (Thursday–Sunday)."""
    data = _get(DG_ENDPOINTS["live_preds"], {"tour": tour}, "live_predictions")
    if not data:
        return {}
    players = data if isinstance(data, list) else data.get("data", data.get("players", []))
    result = {}
    for p in players:
        name = _normalize_name(p)
        if name:
            result[name] = p
    return result


def get_live_stats(tour: str = "pga") -> Dict[str, Dict]:
    """Live in-round SG stats."""
    data = _get(DG_ENDPOINTS["live_stats"], {"tour": tour}, "live_stats")
    if not data:
        return {}
    players = data if isinstance(data, list) else data.get("data", data.get("players", []))
    result = {}
    for p in players:
        name = _normalize_name(p)
        if name:
            result[name] = p
    return result


def get_live_hole_scoring(tour: str = "pga") -> Dict:
    """Live hole-by-hole scoring averages — useful for course management analysis."""
    data = _get(DG_ENDPOINTS["live_hole_scoring"], {"tour": tour}, "live_hole_scoring")
    return data or {}


# ──────────────────────────────────────────────────────────────
# HISTORICAL DATA
# ──────────────────────────────────────────────────────────────

def get_historical_event_ids(tour: str = "pga", season: Optional[int] = None) -> List[Dict]:
    """List of historical event IDs — needed to query course history."""
    params: Dict[str, Any] = {"tour": tour}
    if season:
        params["season"] = season
    data = _get(DG_ENDPOINTS["historical_event_ids"], params, "historical_event_ids")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("events", [])


def get_historical_round_sg(
    event_id: str,
    tour: str = "pga",
    round_num: Optional[int] = None,
) -> List[Dict]:
    """
    Per-round SG data for a historical event.
    Used for: course history, FRL R1 scoring, player form tracking.
    """
    params: Dict[str, Any] = {"tour": tour, "event_id": event_id}
    if round_num:
        params["round_num"] = round_num
    data = _get(DG_ENDPOINTS["historical_sg"], params, f"historical_sg_{event_id}")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("rounds", data.get("data", []))


def get_historical_event_finishes(
    tour: str = "pga",
    event_id: Optional[str] = None,
) -> List[Dict]:
    """
    Historical event finishes — used for course history weighting.
    Was the player a similar version of themselves when they did well here?
    """
    params: Dict[str, Any] = {"tour": tour}
    if event_id:
        params["event_id"] = event_id
    data = _get(DG_ENDPOINTS["historical_event_finishes"], params, "historical_event_finishes")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("finishes", data.get("data", []))


def get_historical_odds(
    tour: str = "pga",
    event_id: Optional[str] = None,
) -> List[Dict]:
    """
    Historical outright odds — useful for identifying market trend vs reality.
    Odds movement context.
    """
    params: Dict[str, Any] = {"tour": tour}
    if event_id:
        params["event_id"] = event_id
    data = _get(DG_ENDPOINTS["historical_odds"], params, "historical_odds")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("odds", data.get("data", []))


# ──────────────────────────────────────────────────────────────
# COMPOSITE PULL — full weekly data in one call
# ──────────────────────────────────────────────────────────────

def pull_all_weekly_data(tour: str = "pga") -> Dict[str, Any]:
    """
    Pull every endpoint needed for a full weekly analysis.
    Returns consolidated dict suitable for merging into weekly_state.json.
    Never skips any endpoint per framework rules.
    """
    log.info("[DG] Pulling full weekly DataGolf dataset…")

    result: Dict[str, Any] = {}

    result["field"]         = get_field_updates(tour=tour)
    log.info(f"[DG] Field: {len(result['field'])} players")

    result["skill_ratings"] = get_skill_ratings(tour=tour)
    log.info(f"[DG] Skill ratings: {len(result['skill_ratings'])} players")

    result["approach_skill"] = get_approach_skill(tour=tour)
    log.info(f"[DG] Approach skill: {len(result['approach_skill'])} players")

    result["predictions"]   = get_pre_tournament_predictions(tour=tour)
    log.info(f"[DG] Predictions: {len(result['predictions'])} players")

    result["rankings"]      = get_dg_rankings(tour=tour)
    log.info(f"[DG] Rankings: {len(result['rankings'])} entries")

    result["fantasy"]       = get_fantasy_defaults(tour=tour)
    log.info(f"[DG] Fantasy defaults: {len(result['fantasy'])} entries")

    # Year-by-year decompositions — last 4 years most relevant
    result["decompositions"] = get_skill_decompositions(
        tour=tour, year_start=2021, year_end=2026
    )
    log.info(f"[DG] Decompositions: {len(result['decompositions'])} players")

    # FRL: pull R1 historical scoring averages for current course
    # Caller should pass event_id for the specific course; skip if not available
    result["frl_r1_history"] = {}   # Populated by main.py once event_id is known

    log.info("[DG] Full weekly pull complete.")
    return result


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def _normalize_name(p: Dict) -> Optional[str]:
    """Extract and normalize player name from DG API response."""
    name = p.get("player_name") or p.get("name") or p.get("player")
    if not name:
        return None
    # DG sometimes sends "Last, First" — normalize to "First Last"
    if "," in name:
        parts = [x.strip() for x in name.split(",", 1)]
        name = f"{parts[1]} {parts[0]}"
    return name.strip().title()


def get_course_event_ids(course_keyword: str, tour: str = "pga") -> List[str]:
    """
    Find historical event IDs for a given course by keyword.
    Used to pull course-specific history before analysis.
    """
    events = get_historical_event_ids(tour=tour)
    matches = []
    for e in events:
        event_name = e.get("event_name", "").lower()
        if course_keyword.lower() in event_name:
            matches.append(e.get("event_id"))
    return [m for m in matches if m]


def compute_recent_sg_trend(decompositions: List[Dict], stat: str, recent_years: int = 2) -> Optional[float]:
    """
    Compute average SG for a stat over the most recent N years.
    Implements the recency window principle — recent years override career.
    """
    if not decompositions:
        return None
    recent = decompositions[-recent_years:]
    vals = [d.get(stat) for d in recent if d.get(stat) is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 3)


def get_player_r1_history(event_ids: List[str], tour: str = "pga") -> Dict[str, Dict]:
    """
    Pull R1 scoring history across multiple historical event IDs for FRL analysis.
    Returns per-player R1 scoring averages and birdie rates at the venue.
    """
    player_r1: Dict[str, List[float]] = {}
    player_birdies: Dict[str, List[float]] = {}

    for event_id in event_ids[:5]:   # Cap at 5 years of history
        rounds = get_historical_round_sg(event_id=event_id, tour=tour, round_num=1)
        for r in rounds:
            name = _normalize_name(r)
            if not name:
                continue
            score = r.get("score") or r.get("total_score")
            birdies = r.get("birdies")
            if score is not None:
                player_r1.setdefault(name, []).append(float(score))
            if birdies is not None:
                player_birdies.setdefault(name, []).append(float(birdies))

    result = {}
    for name in player_r1:
        scores  = player_r1[name]
        birdies = player_birdies.get(name, [])
        result[name] = {
            "r1_scoring_avg_hist": round(sum(scores) / len(scores), 2),
            "r1_rounds_sampled":   len(scores),
            "birdie_rate":         round(sum(birdies) / len(birdies), 2) if birdies else None,
        }
    return result


# ──────────────────────────────────────────────────────────────
# OUTRIGHT ODDS (replaces The Odds API for regular PGA events)
# ──────────────────────────────────────────────────────────────

def get_dg_outright_odds(
    tour: str = "pga",
    market: str = "winner",
    odds_format: str = "american",
) -> Dict[str, Dict]:
    """
    Pull outright odds from DataGolf's betting-tools endpoint.
    Returns per-player dict matching the format previously used by odds.py:
    {
      "Scottie Scheffler": {
        "draftkings": 350,
        "bet365": 325,
        "best_price": 350,
        "best_book": "draftkings",
        "implied_prob": 0.222,
        "decimal": 4.5,
        "fractional": "7/2",
        "books": {"draftkings": 350, "bet365": 325},
      },
      ...
    }
    Always available for current PGA Tour event — no sport key matching needed.
    """
    url = f"{DG_BASE}/betting-tools/outrights"
    data = _get(url, {
        "tour":         tour,
        "market":       market,
        "odds_format":  odds_format,
        "file_format":  "json",
    }, label="DG outright odds")

    if not data:
        log.warning("[DG] Outright odds returned no data.")
        return {}

    # DataGolf returns: {"event_name": "...", "last_updated": "...", "odds": [...]}
    # Each entry in odds: {"player_name": "...", "datagolf_baseline": X, "draftkings": X, "bet365": X, ...}
    odds_list = data.get("odds", [])
    if not odds_list:
        log.warning("[DG] Outright odds list empty.")
        return {}

    # Books we care about — DataGolf includes many books, we want these two
    PRIMARY_BOOKS = ["draftkings", "bet365"]

    result: Dict[str, Dict] = {}

    for entry in odds_list:
        name = entry.get("player_name", "").strip()
        if not name:
            continue

        books = {}
        for book in PRIMARY_BOOKS:
            val = entry.get(book)
            if val is not None:
                try:
                    books[book] = int(val)
                except (ValueError, TypeError):
                    pass

        # Also store datagolf baseline as a reference
        dg_baseline = entry.get("datagolf_baseline")

        if not books and dg_baseline is None:
            continue

        # Best price = highest American odds available
        best_price = max(books.values()) if books else None
        best_book  = max(books, key=books.get) if books else "datagolf"

        # Fall back to DG baseline if no book odds available
        if best_price is None and dg_baseline is not None:
            try:
                best_price = int(dg_baseline)
                best_book  = "datagolf_baseline"
                books["datagolf_baseline"] = best_price
            except (ValueError, TypeError):
                pass

        if best_price is None:
            continue

        from math import gcd as _gcd
        def _implied(american: int) -> float:
            if american > 0:
                return round(100 / (american + 100), 4)
            return round(abs(american) / (abs(american) + 100), 4)

        def _decimal(american: int) -> float:
            if american > 0:
                return round((american / 100) + 1, 3)
            return round((100 / abs(american)) + 1, 3)

        def _fractional(american: int) -> str:
            if american > 0:
                n, d = american, 100
            else:
                n, d = 100, abs(american)
            g = _gcd(n, d)
            return f"{n // g}/{d // g}"

        result[name] = {
            "books":        books,
            "best_price":   best_price,
            "best_book":    best_book,
            "implied_prob": _implied(best_price),
            "decimal":      _decimal(best_price),
            "fractional":   _fractional(best_price),
            "dg_baseline":  dg_baseline,
        }

    event_name = data.get("event_name", "unknown")
    last_updated = data.get("last_updated", "unknown")
    log.info(f"[DG] Outright odds: {len(result)} players | event='{event_name}' | updated={last_updated}")
    return result
