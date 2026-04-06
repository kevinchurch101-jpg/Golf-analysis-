"""
Fairway Intel — First Round Leader (FRL) Analysis
Wave matters meaningfully. Know targeted player's wave.
R1 scoring average historically is a key FRL input.
Recurring targets: Rico Hoey, Jhonattan Vegas.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class FRLCandidate:
    name: str
    score: float
    wave: Optional[str]            # "AM" / "PM" / "UNKNOWN"
    tee_time: Optional[str]
    r1_scoring_avg_hist: Optional[float]
    sg_ott: Optional[float]
    sg_app: Optional[float]
    sg_putt_recent: Optional[float]
    birdie_rate: Optional[float]
    odds_american: Optional[int]
    implied_prob: Optional[float]
    wave_advantage: bool = False
    is_recurring_target: bool = False
    frl_notes: List[str] = field(default_factory=list)

    @property
    def formatted_odds(self) -> str:
        if self.odds_american is None:
            return "N/A"
        return f"+{self.odds_american}" if self.odds_american > 0 else str(self.odds_american)


# Recurring FRL targets from framework
RECURRING_FRL_TARGETS = {
    "Rico Hoey":      "Weekly FRL consideration at approach-heavy venues when odds work. FRL only — never outright.",
    "Jhonattan Vegas": "FRL consideration when hitting well and putting is on.",
    "Bronson Burgoon": "Elite OTT. FRL consideration only at huge prices.",
    "Andrew Novak":   "Extreme putter volatility. FRL at long prices only.",
}

# FRL scoring weights
WEIGHTS = {
    "r1_scoring_avg":   0.30,
    "sg_ott":           0.20,
    "sg_app":           0.25,
    "sg_putt":          0.15,
    "birdie_rate":      0.10,
}


def score_frl_candidate(
    name: str,
    player_data: Dict,
    wave_weather: Optional[Dict] = None,
    course_r1_scoring_avg: Optional[float] = None,
) -> FRLCandidate:
    """
    Build FRL score for a single player.

    player_data keys:
        wave, tee_time, sg_ott, sg_app, sg_putt_recent,
        r1_scoring_avg_hist (course-specific), birdie_rate,
        odds_american, implied_prob

    wave_weather: dict with "AM_wind_mph" and "PM_wind_mph" keys
    """
    frl_notes = []

    # Wave assignment
    wave = player_data.get("wave", "UNKNOWN")
    tee_time = player_data.get("tee_time")

    # Determine wave advantage
    wave_advantage = False
    if wave_weather:
        am_wind = wave_weather.get("AM_wind_mph", 10)
        pm_wind = wave_weather.get("PM_wind_mph", 10)
        wind_diff = abs(am_wind - pm_wind)
        if wind_diff >= 5:    # 5+ mph difference = meaningful
            if wave == "AM" and am_wind < pm_wind:
                wave_advantage = True
                frl_notes.append(f"WAVE ADVANTAGE: AM wave (~{am_wind:.0f}mph) vs PM (~{pm_wind:.0f}mph)")
            elif wave == "PM" and pm_wind < am_wind:
                wave_advantage = True
                frl_notes.append(f"WAVE ADVANTAGE: PM wave (~{pm_wind:.0f}mph) vs AM (~{am_wind:.0f}mph)")
            else:
                frl_notes.append(f"Wave disadvantage: their wave has more wind")
        else:
            frl_notes.append("Wave split minimal — conditions similar")

    # Pull stats
    r1_hist = player_data.get("r1_scoring_avg_hist")
    sg_ott = player_data.get("sg_ott", 0) or 0
    sg_app = player_data.get("sg_app", 0) or 0
    sg_putt = player_data.get("sg_putt_recent", 0) or 0
    birdie_rate = player_data.get("birdie_rate", 4.0) or 4.0
    odds_american = player_data.get("odds_american")
    implied_prob = player_data.get("implied_prob", 0.01)

    # Build score
    score = 0.0

    if r1_hist is not None:
        # Normalize: lower = better for scoring avg (under par = good)
        # Score = how many strokes under course average
        course_avg = course_r1_scoring_avg or 71.5
        hist_score = max(0, (course_avg - r1_hist) / course_avg) * 100
        score += hist_score * WEIGHTS["r1_scoring_avg"]
        frl_notes.append(f"R1 hist avg: {r1_hist:.2f} vs course avg {course_avg:.1f}")

    if sg_ott:
        ott_score = min(100, max(0, 50 + sg_ott * 30))
        score += ott_score * WEIGHTS["sg_ott"]

    if sg_app:
        app_score = min(100, max(0, 50 + sg_app * 30))
        score += app_score * WEIGHTS["sg_app"]

    if sg_putt:
        putt_score = min(100, max(0, 50 + sg_putt * 25))
        score += putt_score * WEIGHTS["sg_putt"]

    if birdie_rate:
        # Normalize around Tour average (~3.8 birdies/round)
        birdie_score = min(100, max(0, 50 + (birdie_rate - 3.8) * 20))
        score += birdie_score * WEIGHTS["birdie_rate"]

    # Wave advantage bonus
    if wave_advantage:
        score += 10
        frl_notes.append("Wave advantage adds +10 to FRL score")

    # Recurring target flag
    is_recurring = name in RECURRING_FRL_TARGETS
    if is_recurring:
        frl_notes.append(f"RECURRING FRL TARGET: {RECURRING_FRL_TARGETS[name]}")

    return FRLCandidate(
        name=name,
        score=round(score, 2),
        wave=wave,
        tee_time=tee_time,
        r1_scoring_avg_hist=r1_hist,
        sg_ott=sg_ott,
        sg_app=sg_app,
        sg_putt_recent=sg_putt,
        birdie_rate=birdie_rate,
        odds_american=odds_american,
        implied_prob=implied_prob,
        wave_advantage=wave_advantage,
        is_recurring_target=is_recurring,
        frl_notes=frl_notes,
    )


def rank_frl_candidates(
    field_data: List[Dict],
    weather_data: Optional[Dict] = None,
    course_r1_scoring_avg: Optional[float] = None,
    min_frl_odds: int = 5000,    # Minimum 50/1 for FRL consideration
) -> List[FRLCandidate]:
    """
    Score and rank all field members for FRL.
    Returns list sorted by FRL score descending.
    min_frl_odds: minimum American odds to be included as FRL candidate.
    """
    wave_weather = _extract_wave_weather(weather_data) if weather_data else None
    candidates = []

    for player in field_data:
        name = player.get("name", "")
        if not name:
            continue

        # Only FRL bets at longer prices — skip heavy favorites
        odds = player.get("odds_american")
        if odds is not None and odds < min_frl_odds:
            continue

        candidate = score_frl_candidate(
            name=name,
            player_data=player,
            wave_weather=wave_weather,
            course_r1_scoring_avg=course_r1_scoring_avg,
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: -c.score)
    return candidates


def get_frl_top_targets(candidates: List[FRLCandidate], n: int = 5) -> List[FRLCandidate]:
    """Return top N FRL candidates, prioritizing wave advantage and recurring targets."""
    # Sort: wave advantage first, then recurring, then score
    priority = sorted(
        candidates,
        key=lambda c: (-(1 if c.wave_advantage else 0), -(1 if c.is_recurring_target else 0), -c.score)
    )
    return priority[:n]


def build_frl_card(
    top_candidates: List[FRLCandidate],
    max_bets: int = 3,
) -> List[Dict]:
    """
    Build FRL section of bet card.
    Returns list of FRL bet entries.
    """
    card = []
    for cand in top_candidates[:max_bets]:
        if cand.odds_american is None or cand.score < 40:
            continue
        card.append({
            "player": cand.name,
            "wave": cand.wave,
            "tee_time": cand.tee_time,
            "frl_score": cand.score,
            "odds": cand.formatted_odds,
            "implied_prob": cand.implied_prob,
            "wave_advantage": cand.wave_advantage,
            "is_recurring_target": cand.is_recurring_target,
            "notes": " | ".join(cand.frl_notes[:3]),
            "stake_recommendation": "1 unit" if cand.score >= 65 else "0.5 unit",
        })
    return card


def _extract_wave_weather(weather_data: Dict) -> Optional[Dict]:
    """
    Extract AM vs PM conditions from weather data.
    R1 conditions by hour — AM tee times vs PM.
    """
    r1 = weather_data.get("r1", weather_data.get("R1", {}))
    if not r1:
        return None

    wind_mph = r1.get("wind_mph")
    if wind_mph is None:
        wind_mph = 10.0   # Default if no forecast yet

    wind_mph = float(wind_mph)

    return {
        "AM_wind_mph": wind_mph * 0.7,   # Morning typically calmer
        "PM_wind_mph": wind_mph * 1.1,   # Afternoon typically windier
        "r1_conditions": r1,
    }
