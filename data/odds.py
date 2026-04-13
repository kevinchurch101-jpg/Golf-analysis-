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


def _name_similarity(a: str, b: str) -> float:
    """
    Simple word-overlap similarity between two event name strings.
    e.g. "RBC Heritage" vs "RBC Heritage Presented by Boeing" → high match.
    Returns 0.0 to 1.0.
    """
    import re as _re
    # Strip common noise words
    noise = {"the", "presented", "by", "sponsored", "at", "golf", "pga", "tour",
             "championship", "open", "invitational", "classic", "tournament"}
    def words(s):
        return set(w.lower() for w in _re.findall(r"[a-z]+", s.lower()) if w not in noise)
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def find_active_golf_event(event_name_hint: str = "") -> Dict:
    """
    Core discovery function. Searches ALL golf sport keys for a matching
    live event. Returns {"sport_key": str, "event_id": str, "event_name": str}
    or empty dict if nothing found.

    Strategy:
    1. Get all golf sport keys from /sports (1 credit)
    2. For each key, get events list (1 credit each)
    3. If event_name_hint provided, score each event against it
       and take the best match above threshold
    4. If no hint, take the key with the soonest upcoming event
    5. Stop as soon as a good match is found — don't burn credits
    """
    import time as _time

    sports = get_sports()
    golf_sports = [s for s in sports if "golf" in s.get("key", "").lower()]

    if not golf_sports:
        log.warning("[Odds] No golf sports in /sports endpoint.")
        return {}

    # Sort: active keys first, then alphabetical so pga_tour comes before masters
    active = sorted([s for s in golf_sports if s.get("active", False)],
                    key=lambda s: s.get("key", ""))
    inactive = sorted([s for s in golf_sports if not s.get("active", False)],
                      key=lambda s: s.get("key", ""))
    candidates = active + inactive

    best_match = {}
    best_score = 0.0

    for sport in candidates:
        key = sport.get("key", "")
        events = _get(f"sports/{key}/events", {"dateFormat": "iso"})
        if not events or not isinstance(events, list):
            _time.sleep(0.2)
            continue

        for event in events:
            desc = (event.get("description") or event.get("name") or
                    event.get("home_team") or "")

            if event_name_hint:
                score = _name_similarity(event_name_hint, desc)
                log.debug(f"[Odds] {key} | '{desc}' vs '{event_name_hint}' → {score:.2f}")
                if score > best_score:
                    best_score = score
                    best_match = {
                        "sport_key":  key,
                        "event_id":   event.get("id", ""),
                        "event_name": desc,
                        "score":      score,
                    }
                # High confidence match — stop immediately, don't burn more credits
                if score >= 0.6:
                    log.info(f"[Odds] Event matched: '{desc}' (score={score:.2f}, key={key})")
                    return best_match
            else:
                # No hint — return first key that has any live/upcoming event
                log.info(f"[Odds] Found live event: '{desc}' (key={key})")
                return {
                    "sport_key":  key,
                    "event_id":   event.get("id", ""),
                    "event_name": desc,
                    "score":      1.0,
                }

        _time.sleep(0.2)

    if best_match:
        log.info(f"[Odds] Best event match: '{best_match['event_name']}' "
                 f"(score={best_match['score']:.2f}, key={best_match['sport_key']})")
        return best_match

    log.warning("[Odds] No matching golf event found across all sport keys.")
    return {}


def get_active_golf_sport_key(event_name_hint: str = "") -> Optional[str]:
    """Returns sport key for the current active golf event."""
    result = find_active_golf_event(event_name_hint)
    key = result.get("sport_key")
    if key:
        log.info(f"[Odds] Active golf sport key: {key}")
    return key


def get_active_tournament_id(event_name_hint: str = "") -> Optional[str]:
    """Returns event ID for the current active golf event."""
    result = find_active_golf_event(event_name_hint)
    event_id = result.get("event_id")
    if event_id:
        log.info(f"[Odds] Active tournament ID: {event_id} "
                 f"({result.get('event_name', '')})")
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
    event_name_hint: str = "",
) -> List[Dict]:
    """
    Pull outright (winner) odds for the active PGA event.
    event_name_hint: current event name from DataGolf — used to match
    against Odds API event descriptions so we always find the right event.
    Uses primary books: DraftKings + Bet365.
    """
    if books is None:
        books = ODDS_PRIMARY_BOOKS

    # Use find_active_golf_event once — gets both sport_key and event_id together
    # This avoids duplicate /sports and /events calls
    if event_id is None:
        discovery = find_active_golf_event(event_name_hint=event_name_hint)
        if not discovery:
            log.warning("[Odds] No active tournament found.")
            return []
        sport_key = discovery["sport_key"]
        event_id  = discovery["event_id"]
        log.info(f"[Odds] Pulling odds for: {discovery.get('event_name','?')} "
                 f"(key={sport_key}, id={event_id})")
    else:
        sport_key = get_active_golf_sport_key(event_name_hint) or ODDS_SPORT

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


def get_full_odds_snapshot(
    event_id: Optional[str] = None,
    event_name_hint: str = "",
) -> Dict[str, Dict]:
    """
    One-call convenience: pull and parse odds into clean per-player dict.
    event_name_hint is passed from main.py — the current event name from
    DataGolf — so odds always match the right tournament.
    """
    raw = get_outright_odds(event_id=event_id, event_name_hint=event_name_hint)
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
