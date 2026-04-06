"""
Fairway Intel — Odds API Client
DraftKings + Bet365 primary books. Pull once per scheduled run.
500 credits/month hard limit — track usage carefully.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import (
    ODDS_API_KEY, ODDS_BASE, ODDS_SPORT, ODDS_BOOKS,
    ODDS_PRIMARY_BOOKS, ODDS_MARKETS,
)

log = logging.getLogger(__name__)

CREDIT_COST_PER_CALL = 10   # approximate credits per markets call


def _get(endpoint: str, params: Dict) -> Optional[Any]:
    """Raw GET call to Odds API."""
    params = {**params, "apiKey": ODDS_API_KEY}
    url = f"{ODDS_BASE}/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 200:
            remaining = r.headers.get("x-requests-remaining")
            used = r.headers.get("x-requests-used")
            if remaining:
                log.info(f"[Odds] Credits remaining: {remaining} | used: {used}")
            return r.json()
        elif r.status_code == 401:
            log.error("[Odds] API key invalid or expired.")
        elif r.status_code == 422:
            log.error(f"[Odds] Unprocessable entity: {r.text[:300]}")
        elif r.status_code == 429:
            log.warning("[Odds] Monthly credit limit reached.")
        else:
            log.error(f"[Odds] HTTP {r.status_code}: {r.text[:300]}")
    except requests.RequestException as e:
        log.error(f"[Odds] Request failed: {e}")
    return None


# ──────────────────────────────────────────────────────────────
# SPORTS / EVENTS
# ──────────────────────────────────────────────────────────────

def get_sports() -> List[Dict]:
    """List available sports — diagnostic use."""
    data = _get("sports", {})
    return data or []


def get_events(sport: str = ODDS_SPORT) -> List[Dict]:
    """Get upcoming events for sport — finds the active tournament."""
    data = _get(f"sports/{sport}/events", {"dateFormat": "iso"})
    return data or []


def get_active_golf_sport_key() -> Optional[str]:
    """
    Query the /sports endpoint to find the currently active golf event key.
    The Odds API uses event-specific keys like 'golf_masters_tournament_winner'.
    Returns the sport key string or None.
    """
    sports = get_sports()
    golf_sports = [
        s for s in sports
        if "golf" in s.get("key", "").lower() and s.get("active", False)
    ]
    if not golf_sports:
        # Try has_outrights as fallback
        golf_sports = [s for s in sports if "golf" in s.get("key", "").lower()]

    if golf_sports:
        # Prefer the most specific active one
        for key_fragment in ["masters", "pga_championship", "us_open", "the_open", "pga_tour"]:
            for s in golf_sports:
                if key_fragment in s.get("key", "").lower():
                    log.info(f"[Odds] Active golf sport key: {s['key']}")
                    return s["key"]
        # Fallback to first golf sport found
        log.info(f"[Odds] Using golf sport key: {golf_sports[0]['key']}")
        return golf_sports[0]["key"]

    log.warning("[Odds] No active golf sport found.")
    return None


def get_active_tournament_id() -> Optional[str]:
    """
    Find the currently active or next PGA event ID.
    Dynamically finds the correct sport key first.
    Returns the event_id string needed for odds queries.
    """
    sport_key = get_active_golf_sport_key()
    if not sport_key:
        log.warning("[Odds] No active golf sport key found.")
        return None

    events = get_events(sport=sport_key)
    if not events:
        log.warning(f"[Odds] No events found for {sport_key}.")
        return None

    events_sorted = sorted(events, key=lambda e: e.get("commence_time", ""))
    event_id = events_sorted[0].get("id")
    log.info(f"[Odds] Active tournament: {events_sorted[0].get('description', event_id)}")
    return event_id


def get_active_sport_key() -> Optional[str]:
    """Public wrapper for get_active_golf_sport_key."""
    return get_active_golf_sport_key()


# ──────────────────────────────────────────────────────────────
# ODDS PULL
# ──────────────────────────────────────────────────────────────

def get_outright_odds(
    event_id: Optional[str] = None,
    books: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Pull outright (winner) odds for the active PGA event.
    Uses primary books: DraftKings + Bet365.
    Returns raw API response list.
    """
    if books is None:
        books = ODDS_PRIMARY_BOOKS

    sport_key = get_active_golf_sport_key() or ODDS_SPORT
    if event_id is None:
        event_id = get_active_tournament_id()
    if event_id is None:
        log.warning("[Odds] No active tournament found.")
        return []

    data = _get(
        f"sports/{sport_key}/events/{event_id}/odds",
        {
            "regions": "us,us2,uk",
            "markets": "outrights",
            "oddsFormat": "american",
            "bookmakers": ",".join(books),
        },
    )
    return data if isinstance(data, list) else (data.get("bookmakers", []) if data else [])


def get_all_book_odds(event_id: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Pull odds from ALL configured books for cross-book comparison.
    More credits but useful for finding best available price.
    """
    if event_id is None:
        event_id = get_active_tournament_id()
    if event_id is None:
        return {}

    data = _get(
        f"sports/{ODDS_SPORT}/events/{event_id}/odds",
        {
            "regions": "us,us2,uk",
            "markets": "outrights",
            "oddsFormat": "american",
            "bookmakers": ",".join(ODDS_BOOKS),
        },
    )
    if not data:
        return {}

    books_data = data if isinstance(data, list) else data.get("bookmakers", [])
    return {b["key"]: b.get("markets", []) for b in books_data if "key" in b}


# ──────────────────────────────────────────────────────────────
# PARSING & NORMALIZATION
# ──────────────────────────────────────────────────────────────

def parse_outright_odds(raw_books_data: List[Dict]) -> Dict[str, Dict]:
    """
    Parse raw Odds API bookmaker response into clean per-player structure.

    Returns:
        {
          "Scottie Scheffler": {
            "draftkings": 350,       # American odds
            "bet365": 325,
            "best_price": 350,
            "best_book": "draftkings",
            "implied_prob": 0.222,   # from best price
            "decimal": 4.5,
            "fractional": "7/2",
          },
          ...
        }
    """
    result: Dict[str, Dict] = {}

    for book in raw_books_data:
        book_key = book.get("key", "unknown")
        for market in book.get("markets", []):
            if market.get("key") != "outrights":
                continue
            for outcome in market.get("outcomes", []):
                player_name = _normalize_odds_name(outcome.get("name", ""))
                if not player_name:
                    continue
                american = outcome.get("price")
                if american is None:
                    continue

                if player_name not in result:
                    result[player_name] = {
                        "books": {},
                        "best_price": None,
                        "best_book": None,
                        "implied_prob": None,
                        "decimal": None,
                        "fractional": None,
                    }

                result[player_name]["books"][book_key] = american

                # Track best (highest) American odds available
                if (
                    result[player_name]["best_price"] is None
                    or american > result[player_name]["best_price"]
                ):
                    result[player_name]["best_price"] = american
                    result[player_name]["best_book"] = book_key
                    result[player_name]["implied_prob"] = american_to_implied(american)
                    result[player_name]["decimal"] = american_to_decimal(american)
                    result[player_name]["fractional"] = american_to_fractional(american)

    return result


def get_full_odds_snapshot(event_id: Optional[str] = None) -> Dict[str, Dict]:
    """
    One-call convenience: pull and parse odds into clean per-player dict.
    This is what the rest of the system calls.
    """
    raw = get_outright_odds(event_id=event_id)
    if not raw:
        log.warning("[Odds] No raw odds data returned.")
        return {}
    parsed = parse_outright_odds(raw)
    log.info(f"[Odds] Parsed odds for {len(parsed)} players.")
    return parsed


# ──────────────────────────────────────────────────────────────
# VALUE CALCULATIONS
# ──────────────────────────────────────────────────────────────

def calculate_edge(implied_prob: float, dg_win_prob: float) -> float:
    """
    Simple edge calculation: DG model probability vs market implied probability.
    Positive = market undervaluing player (value bet).
    Negative = market overvaluing player (fade candidate).
    """
    if implied_prob <= 0:
        return 0.0
    return round(dg_win_prob - implied_prob, 4)


def kelly_fraction(edge: float, odds_decimal: float, full_kelly: float = 1.0) -> float:
    """
    Kelly criterion for stake sizing guidance.
    full_kelly=1.0 is theoretical max — use fractional Kelly in practice.
    Returns fraction of bankroll to stake.
    """
    if odds_decimal <= 1 or edge <= 0:
        return 0.0
    b = odds_decimal - 1   # net odds
    p = edge + (1 / odds_decimal)  # estimated win prob
    q = 1 - p
    kelly = (b * p - q) / b
    return max(0.0, round(kelly * full_kelly, 4))


def find_value_plays(
    odds_snapshot: Dict[str, Dict],
    dg_predictions: Dict[str, Dict],
    min_odds: int = 30,
) -> List[Dict]:
    """
    Cross-reference market odds with DG model to surface value.
    Returns list of value plays sorted by edge descending.
    min_odds: minimum American odds to consider (30 = 30/1).
    """
    value_plays = []

    for player, odds_data in odds_snapshot.items():
        best_price = odds_data.get("best_price")
        if best_price is None or best_price < min_odds * 100 - 100:
            # Convert American: 3000 = 30/1. Skip anything shorter than min_odds.
            continue

        dg_data = dg_predictions.get(player, {})
        dg_win = dg_data.get("win")
        if dg_win is None:
            continue

        implied = odds_data.get("implied_prob", 0)
        edge = calculate_edge(implied, dg_win)
        decimal = odds_data.get("decimal", 1.0)

        value_plays.append({
            "player": player,
            "best_price_american": best_price,
            "best_book": odds_data.get("best_book"),
            "implied_prob": round(implied, 4),
            "dg_win_prob": round(dg_win, 4),
            "edge": edge,
            "decimal": decimal,
            "kelly": kelly_fraction(edge, decimal, full_kelly=0.25),
        })

    value_plays.sort(key=lambda x: x["edge"], reverse=True)
    return value_plays


# ──────────────────────────────────────────────────────────────
# ODDS MATH HELPERS
# ──────────────────────────────────────────────────────────────

def american_to_implied(american: int) -> float:
    """Convert American odds to implied probability."""
    if american > 0:
        return round(100 / (american + 100), 4)
    else:
        return round(abs(american) / (abs(american) + 100), 4)


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds."""
    if american > 0:
        return round((american / 100) + 1, 3)
    else:
        return round((100 / abs(american)) + 1, 3)


def american_to_fractional(american: int) -> str:
    """Convert American odds to simple fractional string like '9/1'."""
    if american > 0:
        numerator = american
        denominator = 100
    else:
        numerator = 100
        denominator = abs(american)
    # Simplify fraction
    from math import gcd
    g = gcd(numerator, denominator)
    return f"{numerator // g}/{denominator // g}"


def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds back to American."""
    if decimal >= 2.0:
        return int((decimal - 1) * 100)
    else:
        return int(-100 / (decimal - 1))


def format_price(american: int) -> str:
    """Format American odds for display: +350, -110, etc."""
    if american > 0:
        return f"+{american}"
    return str(american)


# ──────────────────────────────────────────────────────────────
# NAME NORMALIZATION
# ──────────────────────────────────────────────────────────────

def _normalize_odds_name(name: str) -> str:
    """
    Normalize player name from Odds API to match DataGolf format.
    Handles common discrepancies between book name spellings.
    """
    if not name:
        return ""

    # Common book→DG name mappings
    OVERRIDES = {
        "Rory Mcilroy": "Rory McIlroy",
        "Si Woo Kim": "Si Woo Kim",
        "Byeong Hun An": "Byeong-Hun An",
        "K.h. Lee": "K.H. Lee",
        "Sungjae Im": "Sungjae Im",
        "Min Woo Lee": "Min Woo Lee",
        "Sepp Straka": "Sepp Straka",
        "Christiaan Bezuidenhout": "Christiaan Bezuidenhout",
        "Adrien Dumont De Chassart": "Adrien Dumont de Chassart",
        "Nicolai Hojgaard": "Nicolai Højgaard",
        "Rasmus Hojgaard": "Rasmus Højgaard",
    }

    name_clean = name.strip().title()
    return OVERRIDES.get(name_clean, name_clean)
