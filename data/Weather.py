"""
Fairway Intel — Weather Module
Fetch and interpret weather forecasts for the tournament venue.
Wind by round is critical for wave/FRL analysis (1-3x per year wave matters for 72-hole).
Bamford is the primary source — this supplements with direct weather data.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

# Free weather API (no key needed for basic forecasts)
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
GEOCODING_BASE  = "https://geocoding-api.open-meteo.com/v1/search"

# Wind categories
WIND_CALM      = (0, 8)     # 0-8 mph
WIND_LIGHT     = (8, 15)    # 8-15 mph
WIND_MODERATE  = (15, 22)   # 15-22 mph  — noticeable
WIND_STRONG    = (22, 30)   # 22-30 mph  — scoring affected
WIND_VERY_STRONG = (30, 99) # 30+ mph    — major scoring impact


def wind_category(mph: float) -> str:
    """Categorize wind speed for briefing language."""
    if mph <= WIND_CALM[1]:
        return "calm"
    elif mph <= WIND_LIGHT[1]:
        return "light"
    elif mph <= WIND_MODERATE[1]:
        return "moderate"
    elif mph <= WIND_STRONG[1]:
        return "strong"
    else:
        return "very strong"


def get_coordinates(location: str) -> Optional[Tuple[float, float]]:
    """
    Look up latitude/longitude for a course location using Open-Meteo geocoding.
    Returns (lat, lon) tuple or None.
    """
    try:
        r = requests.get(
            GEOCODING_BASE,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                return results[0]["latitude"], results[0]["longitude"]
    except requests.RequestException as e:
        log.warning(f"[Weather] Geocoding failed for '{location}': {e}")
    return None


def get_forecast(
    lat: float,
    lon: float,
    days: int = 7,
) -> Optional[Dict]:
    """
    Fetch hourly weather forecast from Open-Meteo.
    Returns raw API response dict.
    """
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,windspeed_10m,winddirection_10m,weathercode",
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,winddirection_10m_dominant",
        "forecast_days": days,
        "timezone": "America/Chicago",  # Default to Central — override per venue
        "windspeed_unit": "mph",
        "temperature_unit": "fahrenheit",
    }
    try:
        r = requests.get(OPEN_METEO_BASE, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        log.warning(f"[Weather] Open-Meteo returned HTTP {r.status_code}")
    except requests.RequestException as e:
        log.warning(f"[Weather] Forecast fetch failed: {e}")
    return None


def parse_round_weather(
    forecast: Dict,
    tournament_start_date: str,  # ISO format: "2026-04-10"
) -> Dict[str, Dict]:
    """
    Parse hourly forecast into per-round weather summaries.
    Tournament rounds: R1=Thu, R2=Fri, R3=Sat, R4=Sun typically.
    Returns dict keyed by round number: {"R1": {...}, "R2": {...}, ...}
    """
    from datetime import datetime, timedelta

    rounds = {}
    try:
        start = datetime.fromisoformat(tournament_start_date)
        daily = forecast.get("daily", {})
        dates = daily.get("time", [])
        max_wind = daily.get("windspeed_10m_max", [])
        wind_dir = daily.get("winddirection_10m_dominant", [])
        precip   = daily.get("precipitation_sum", [])
        max_temp = daily.get("temperature_2m_max", [])
        codes    = daily.get("weathercode", [])

        for i, round_name in enumerate(["R1", "R2", "R3", "R4"]):
            target_date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            if target_date in dates:
                idx = dates.index(target_date)
                wind_mph = max_wind[idx] if idx < len(max_wind) else None
                rounds[round_name] = {
                    "date":       target_date,
                    "wind_mph":   wind_mph,
                    "wind_dir":   _degrees_to_cardinal(wind_dir[idx]) if idx < len(wind_dir) else None,
                    "precip_in":  round(precip[idx] * 0.0394, 2) if idx < len(precip) else None,   # mm→in
                    "temp_high":  max_temp[idx] if idx < len(max_temp) else None,
                    "weather_code": codes[idx] if idx < len(codes) else None,
                    "category":   wind_category(wind_mph) if wind_mph is not None else "unknown",
                    "narrative":  _build_round_narrative(round_name, wind_mph, precip[idx] if idx < len(precip) else 0),
                }
    except Exception as e:
        log.error(f"[Weather] Error parsing round weather: {e}")

    return rounds


def assess_wave_split(round_weather: Dict[str, Dict]) -> Dict:
    """
    Assess whether wave assignment matters meaningfully for R1/R2.
    Matters meaningfully 1-3x per year per framework.
    Returns assessment dict with wave_split_matters bool and explanation.
    """
    r1 = round_weather.get("R1", {})
    r1_wind = r1.get("wind_mph", 0) or 0

    r2 = round_weather.get("R2", {})
    r2_wind = r2.get("wind_mph", 0) or 0

    # For FRL specifically — R1 conditions matter most
    wind_matters = r1_wind >= 20   # 20+ mph creates meaningful wave split potential
    rain_matters = (r1.get("precip_in", 0) or 0) > 0.2

    matters = wind_matters or rain_matters

    explanation_parts = []
    if wind_matters:
        explanation_parts.append(f"R1 wind forecast {r1_wind:.0f}mph — wave timing matters for FRL")
    if rain_matters:
        explanation_parts.append(f"R1 rain forecast — wave timing may matter for scoring")
    if not matters:
        explanation_parts.append("Conditions appear similar across waves — wave assignment minimal factor")

    return {
        "wave_split_matters": matters,
        "r1_wind_mph": r1_wind,
        "r2_wind_mph": r2_wind,
        "explanation": ". ".join(explanation_parts),
        "frl_note": "Check targeted FRL players' wave assignments" if matters else "",
    }


def get_full_weather(
    location: str,
    tournament_start_date: str,
    timezone: str = "America/Chicago",
) -> Dict:
    """
    Convenience function: geocode location, fetch forecast, parse per round.
    Returns complete weather dict for state file.
    """
    log.info(f"[Weather] Fetching weather for '{location}' starting {tournament_start_date}…")

    coords = get_coordinates(location)
    if not coords:
        log.warning(f"[Weather] Could not geocode '{location}'.")
        return {"error": "geocoding_failed", "location": location}

    lat, lon = coords
    log.info(f"[Weather] Coordinates: {lat:.4f}, {lon:.4f}")

    forecast = get_forecast(lat, lon)
    if not forecast:
        return {"error": "forecast_failed", "location": location, "lat": lat, "lon": lon}

    round_weather = parse_round_weather(forecast, tournament_start_date)
    wave_split = assess_wave_split(round_weather)

    return {
        "location": location,
        "lat": lat,
        "lon": lon,
        "last_updated": datetime.now().isoformat(),
        "rounds": round_weather,
        "wave_split": wave_split,
        "r1": round_weather.get("R1", {}),
        "r2": round_weather.get("R2", {}),
        "r3": round_weather.get("R3", {}),
        "r4": round_weather.get("R4", {}),
        "wave_split_matters": wave_split["wave_split_matters"],
    }


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def _degrees_to_cardinal(deg: Optional[float]) -> str:
    """Convert wind direction degrees to cardinal direction string."""
    if deg is None:
        return "unknown"
    directions = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
                  "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    idx = round(deg / 22.5) % 16
    return directions[idx]


def _wmo_code_description(code: int) -> str:
    """WMO weather code to human-readable description."""
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm + hail", 99: "Thunderstorm + heavy hail",
    }
    return codes.get(code, f"Code {code}")


def _build_round_narrative(round_name: str, wind_mph: Optional[float], precip_mm: float) -> str:
    """Build a brief one-line narrative for a round's conditions."""
    if wind_mph is None:
        return f"{round_name}: Conditions unknown"
    precip_str = f", rain expected" if precip_mm > 1 else ""
    return (
        f"{round_name}: {wind_category(wind_mph).title()} wind ~{wind_mph:.0f}mph"
        f"{precip_str}"
    )
