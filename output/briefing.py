"""
Fairway Intel — Briefing Builder
Builds and incrementally updates the weekly briefing paragraph.
Written in Kevin's voice — first person, as if he did all research.
2 paragraphs. Course read + winning stat + wind/weather + 2-3 player narratives (NO PICKS).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


def build_briefing_from_claude_response(raw_response: str) -> str:
    """
    Extract briefing paragraph from Claude API response.
    Returns clean briefing text ready for HTML.
    """
    if not raw_response:
        return ""

    lines = raw_response.split("\n")
    in_briefing = False
    briefing_lines = []

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        # Start capturing after briefing header
        if any(k in upper for k in ["BRIEFING PARAGRAPH", "WEEKLY BRIEFING", "## BRIEFING", "1. BRIEFING"]):
            in_briefing = True
            continue

        # Stop at next major section
        if in_briefing and stripped and any(
            upper.startswith(k) for k in [
                "2.", "3.", "##", "INITIAL PLAYER", "RANKING", "FRL TARGET",
                "POOL SECTION", "FLAG", "TIER", "OVERALL RANK", "VALUE RANK"
            ]
        ):
            break

        if in_briefing and stripped:
            briefing_lines.append(stripped)

    result = "\n\n".join(
        p for p in " ".join(briefing_lines).split("  ") if p.strip()
    )

    # Fallback: if extraction failed, return first 1000 chars
    if not result and raw_response:
        result = raw_response[:1000].strip()

    return result


def update_briefing_incrementally(
    existing_briefing: str,
    new_information: str,
    update_type: str,
) -> str:
    """
    Update briefing with new information without full rewrite.
    Preserves core analysis, adds new context.
    update_type: "weather_update", "article_update", "withdrawal", "odds_context"
    """
    if not existing_briefing:
        return new_information

    timestamp = datetime.now().strftime("%a %I:%M%p ET")
    update_prefix = {
        "weather_update": f"[Weather update {timestamp}]",
        "article_update": f"[Article update {timestamp}]",
        "withdrawal":     f"[Field update {timestamp}]",
        "odds_context":   f"[Odds note {timestamp}]",
    }.get(update_type, f"[Update {timestamp}]")

    return f"{existing_briefing}\n\n{update_prefix} {new_information}"


def generate_placeholder_briefing(event: Dict, weather: Dict) -> str:
    """
    Generate a placeholder briefing when Claude API is unavailable.
    Fills in structural details from state data.
    """
    event_name  = event.get("name", "this week's event")
    course      = event.get("course", "the course")
    dom_stat    = event.get("dominant_stat", "ball-striking")
    dist_mult   = event.get("distance_multiplier", "PARTIAL")
    location    = event.get("location", "")

    r1 = weather.get("r1", {})
    wind_mph = r1.get("wind_mph")
    wind_str = f"with R1 winds forecast around {wind_mph:.0f}mph" if wind_mph else "with conditions TBD"

    wave_note = ""
    if weather.get("wave_split_matters"):
        wave_note = " Wave assignment will be meaningful for FRL this week — check tee times before betting."

    para1 = (
        f"We're at {event_name} this week at {course}{' in ' + location if location else ''}. "
        f"The course profiles as {dom_stat.lower()}-dominant with a {dist_mult} distance multiplier — "
        f"meaning {'distance is a full advantage here' if dist_mult == 'FULL' else 'the conversion chain requires both distance and quality irons' if dist_mult == 'PARTIAL' else 'distance is neutralized and positioning wins'}. "
        f"We head into the week {wind_str}."
        f"{wave_note}"
    )

    para2 = (
        "Full analysis pending — Claude API call processing. "
        "Rankings, tier assignments, and bet card will populate through Monday and Tuesday "
        "as odds come in and articles are processed. Final card by Wednesday 4pm ET."
    )

    return f"{para1}\n\n{para2}"


def validate_briefing(briefing: str) -> Dict:
    """
    Validate briefing quality — check it hits the required elements.
    Returns dict with pass/fail and missing elements.
    """
    required = {
        "course_read":    any(k in briefing.lower() for k in ["course", "venue", "hole", "par"]),
        "winning_stat":   any(k in briefing.lower() for k in ["approach", "app", "ball-striking", "iron", "putting", "distance"]),
        "weather_context": any(k in briefing.lower() for k in ["wind", "weather", "forecast", "condition", "rain", "mph"]),
        "min_length":     len(briefing) >= 300,
        "first_person":   any(k in briefing.lower() for k in ["i ", "we ", "my ", "i'm", "i've", "our"]),
        "no_direct_picks": not any(k in briefing.lower() for k in ["i'm betting", "i'm taking", "my pick is", "bet on"]),
    }

    missing = [k for k, v in required.items() if not v]

    return {
        "valid": len(missing) == 0,
        "checks": required,
        "missing": missing,
        "length": len(briefing),
    }


def format_briefing_for_html(briefing: str) -> str:
    """
    Clean and format briefing text for HTML rendering.
    Handles newlines, special characters.
    """
    if not briefing:
        return ""
    # Replace double newlines with paragraph markers that CSS can handle
    cleaned = briefing.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return cleaned
