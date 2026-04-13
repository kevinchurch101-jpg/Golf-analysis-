"""
Fairway Intel — Claude API Prompt Builder
Builds the analysis prompt from weekly state data.
Budget: $5/month. Full call Sunday night. Incremental smaller calls throughout week.
Model: claude-sonnet-4-6
"""

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import anthropic

from config import ANTHROPIC_KEY, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS

if TYPE_CHECKING:
    from analysis.players import PlayerProfile
    from analysis.course import CourseProfile

log = logging.getLogger(__name__)

# Approximate token costs to stay within $5/month
# claude-sonnet-4-6: ~$3/MTok input, ~$15/MTok output (approximate)
WEEKLY_BUDGET_USD       = 5.00
SUNDAY_CALL_BUDGET_USD  = 2.50   # Big call Sunday night
INCREMENTAL_BUDGET_USD  = 0.40   # Each incremental call
MAX_INPUT_TOKENS_SUNDAY = 80_000
MAX_INPUT_TOKENS_INCR   = 20_000

FRAMEWORK_SYSTEM_PROMPT = """You are Fairway Intel, Kevin's golf betting analysis assistant.

You have been trained on Kevin's complete betting framework (Version 3.0, April 2026).

Core principles you always apply:
- Nothing is binary. Everything is on a spectrum. Always apply nuance.
- Ball-striking (APP + OTT) is the engine. Putting is volatile upside.
- Recent window always — career averages can actively mislead.
- Always identify what is DRIVING the total SG number (market trap check).
- Designation system: attention flags only, not decision overrides.
- Articles are inputs. Framework makes decisions.
- Never be consensus. Arrive at conclusions independently.
- Pool strategy is COMPLETELY SEPARATE from betting card. Odds irrelevant in pool.
- Two separate rankings always: Overall (best chance to win) and Value (mispriced).

Output format:
Write in Kevin's voice — first person, as if he did all the research himself.
Be specific, confident, and framework-grounded.
Every player in field gets a note. No blank entries.
Flag anything uncertain in the Flags section.
"""


def build_sunday_analysis_prompt(
    state: Dict,
    prior_year_summary: str = "",
    player_db: Optional[List] = None,
    course_profile=None,
) -> str:
    """
    Full analysis prompt for Sunday night run.
    Articles + course setup + prior year course breakdown. No odds yet.
    Most expensive call of the week — use the budget wisely.
    Prior year summary: course structure only, player notes discarded.
    player_db: list of PlayerProfile objects from analysis/players.py
    course_profile: CourseProfile object from analysis/course.py
    """
    event = state.get("event", {})
    weather = state.get("weather", {})
    articles = state.get("articles", {})
    # Extract nested by_player dicts — state stores as {"by_player": {...}, "last_updated": ...}
    _sr_raw = state.get("skill_ratings", {})
    skill_ratings = _sr_raw.get("by_player", _sr_raw) if isinstance(_sr_raw, dict) else {}
    if "by_player" in skill_ratings:
        skill_ratings = skill_ratings["by_player"]

    dg_predictions = state.get("dg_predictions", {})
    if "by_player" in dg_predictions:
        dg_predictions = dg_predictions["by_player"]

    field = state.get("field", [])

    # Build condensed field summary (top players by DG ranking)
    field_summary = _build_field_summary(field, skill_ratings, dg_predictions)

    # Build article summary
    article_summary = _build_article_summary(articles)

    # Weather context
    weather_summary = _build_weather_summary(weather)

    # Build player designations section (Kevin's framework database)
    # Filter to only players in the current field for token efficiency
    field_names = {(p.get("player_name") or p.get("name", "")).lower() for p in field}
    designation_section = _build_player_designations_section(player_db, field_names)

    # Build extended course profile section if CourseProfile object passed
    course_profile_section = _build_course_profile_section(course_profile)

    prompt = f"""
WEEKLY ANALYSIS REQUEST — {event.get('name', 'Unknown Event')}
Run type: SUNDAY NIGHT (articles + course setup, no odds yet)
Date: {datetime.now().strftime('%A, %B %d, %Y')}

═══════════════════════════════════════════════════════════════
EVENT DETAILS
═══════════════════════════════════════════════════════════════
Event: {event.get('name', 'TBD')}
Course: {event.get('course', 'TBD')}
Location: {event.get('location', 'TBD')}
Dates: {event.get('dates', 'TBD')}
Par / Yardage: {event.get('par', 'TBD')} / {event.get('yardage', 'TBD')}
Course Type: {event.get('course_type', 'TBD')}  (TIGHT=fairway-finding prerequisite | OPEN=distance prerequisite | FORCED_LAYUP=APP dominant | NEUTRAL=balanced)
Distance Multiplier: {event.get('distance_multiplier', 'TBD')}
Dominant Stat: {event.get('dominant_stat', 'TBD')}
Rough Penalty: {event.get('rough_penalty', 'TBD')}
Angle Penalty: {event.get('angle_penalty', 'TBD')}
Course Avg Driving Acc: {event.get('course_avg_acc', 'TBD')}%
Course Notes: {event.get('course_notes', 'TBD')}

═══════════════════════════════════════════════════════════════
WEATHER & CONDITIONS
═══════════════════════════════════════════════════════════════
{weather_summary}

═══════════════════════════════════════════════════════════════
ARTICLES READ THIS WEEK
═══════════════════════════════════════════════════════════════
{article_summary}

═══════════════════════════════════════════════════════════════
FIELD & SKILL DATA (Top 50 by DG ranking)
═══════════════════════════════════════════════════════════════
{field_summary}

{"═" * 63}
KEVIN'S FRAMEWORK — PLAYER DESIGNATIONS (field players only)
{"═" * 63}
{designation_section}

{"═" * 63}
COURSE PROFILE (Kevin's Framework Database)
{"═" * 63}
{course_profile_section}

{"═" * 63}
PRIOR YEAR COURSE BREAKDOWN
{"═" * 63}
{prior_year_summary if prior_year_summary else "Prior year articles not yet fetched — structural course context pending."}

═══════════════════════════════════════════════════════════════
ANALYSIS REQUESTED
═══════════════════════════════════════════════════════════════
Please provide:

1. BRIEFING PARAGRAPH (2 paragraphs, Kevin's voice, first person)
   Cover: course read, winning stat, wind/weather context, 2-3 key player 
   narratives (NO PICKS yet), unusual field notes.
   Goal: Kevin reads it and feels fully prepared and confident.

2. INITIAL PLAYER RANKINGS (no odds yet — course fit + form only)
   - Overall ranking (best chance to win, no price consideration)
   - Initial tier assignments (S/A/B/C/Fade) with brief reasoning
   - Flag any market traps you see (putting spike with weak APP)
   - Flag any fallen stars showing signs of form return

3. EARLY FRL TARGETS (before wave assignments confirmed)
   Which players historically score well in R1 at this course type?

4. POOL SECTION (completely separate from betting card)
   - Event tier: {event.get('event_tier', 'TBD')}
   - Primary pool pick (most likely winner, odds irrelevant)
   - Available plays
   - Trap plays to avoid

5. FLAGS & UNCERTAINTIES
   - Any blocked/unavailable articles
   - Data gaps or anomalies
   - Calibration notes for Kevin's review

Remember: No picks without odds. This is course + form assessment only.
Odds arrive Monday. Final card Wednesday.

PRIOR YEAR CONTENT USAGE RULES:
- Use prior year course breakdown for: course setup, dominant stat, game type, winning score range
- DO NOT use prior year player notes for current player assessment — that data is a year old
- Prior year articles are course context only — treat like reading course architecture notes
- If prior year articles suggest a specific stat has historically won here, factor that into course read
- If a player is mentioned in prior year context, only note the course fit, never their prior form
"""
    return prompt.strip()


def build_incremental_update_prompt(
    state: Dict,
    update_type: str,
    new_data: Dict,
) -> str:
    """
    Smaller incremental prompt for Monday-Wednesday runs.
    update_type: "odds_update", "article_update", "weather_update", "withdrawal"
    """
    event = state.get("event", {})
    current_analysis = state.get("analysis", {})

    if update_type == "odds_update":
        return _build_odds_update_prompt(state, new_data)
    elif update_type == "article_update":
        return _build_article_update_prompt(state, new_data)
    elif update_type == "weather_update":
        return _build_weather_update_prompt(state, new_data)
    elif update_type == "withdrawal":
        return _build_withdrawal_prompt(state, new_data)
    else:
        return _build_generic_update_prompt(state, new_data, update_type)


def call_claude_api(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = ANTHROPIC_MAX_TOKENS,
) -> Optional[str]:
    """
    Call Claude API and return text response.
    Returns None on failure.
    """
    if not ANTHROPIC_KEY:
        log.error("[Claude] No Anthropic API key configured.")
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    try:
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system_prompt or FRAMEWORK_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        response_text = message.content[0].text if message.content else ""
        log.info(
            f"[Claude] Response received. "
            f"Input tokens: {message.usage.input_tokens}, "
            f"Output tokens: {message.usage.output_tokens}"
        )
        return response_text

    except anthropic.APIError as e:
        log.error(f"[Claude] API error: {e}")
        return None
    except Exception as e:
        log.error(f"[Claude] Unexpected error: {e}")
        return None


def parse_claude_response(response_text: str) -> Dict:
    """
    Parse Claude analysis response into structured components.
    Robust extraction — falls back gracefully if headers not found.
    """
    if not response_text:
        return {}

    result = {
        "briefing_paragraph": "",
        "overall_ranking": [],
        "value_ranking": [],
        "tiers": {"S": [], "A": [], "B": [], "C": [], "FADE": []},
        "player_notes": {},
        "frl_notes": [],
        "pool": {},
        "flags": [],
        "raw_response": response_text,
        "parsed_at": datetime.now().isoformat(),
    }

    lines = response_text.split("\n")

    # ── Extract briefing ──
    # Strategy 1: look for explicit briefing header
    briefing_lines = []
    in_briefing = False
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if any(k in upper for k in [
            "BRIEFING PARAGRAPH", "WEEKLY BRIEFING", "## BRIEFING",
            "1. BRIEFING", "BRIEFING:", "**BRIEFING"
        ]):
            in_briefing = True
            continue
        if in_briefing:
            if stripped and any(upper.startswith(k) for k in [
                "2.", "3.", "4.", "5.", "##", "INITIAL PLAYER", "RANKING",
                "FRL", "POOL", "FLAG", "TIER", "OVERALL", "VALUE RANK",
                "S TIER", "A TIER", "BET CARD"
            ]):
                break
            if stripped:
                briefing_lines.append(stripped)

    if briefing_lines:
        result["briefing_paragraph"] = " ".join(briefing_lines).strip()

    # Strategy 2: if no header found, use first 3 substantial paragraphs
    if not result["briefing_paragraph"]:
        paragraphs = [p.strip() for p in response_text.split("\n\n") if len(p.strip()) > 100]
        if paragraphs:
            # Skip any paragraph that looks like a header/preamble
            body_paras = [p for p in paragraphs if not p.strip().startswith("#")
                          and not p.strip().upper().startswith("ANALYSIS")
                          and len(p.strip()) > 150]
            result["briefing_paragraph"] = "\n\n".join(body_paras[:3]) if body_paras else paragraphs[0]

    # Strategy 3: absolute fallback — first 1500 chars
    if not result["briefing_paragraph"] and response_text:
        result["briefing_paragraph"] = response_text[:1500].strip()

    # ── Extract overall ranking ──
    in_overall = False
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if any(k in upper for k in ["OVERALL RANKING", "OVERALL — BEST", "BEST CHANCE TO WIN"]):
            in_overall = True
            continue
        if in_overall:
            if stripped and any(upper.startswith(k) for k in ["VALUE", "TIER", "##", "BET", "FRL", "POOL"]):
                break
            # Parse numbered list items
            import re
            m = re.match(r"^\d+\.?\s+(.+)", stripped)
            if m:
                result["overall_ranking"].append({"player": m.group(1).strip(), "note": ""})

    # ── Extract tiers ──
    # Handle many Claude formatting styles: S-TIER, S TIER, **S-Tier**, ### S Tier, S-TIER —
    import re as _re

    TIER_PATTERNS = [
        (_re.compile(r'\bS[-\s]TIER\b', _re.I),    "S"),
        (_re.compile(r'\bA[-\s]TIER\b', _re.I),    "A"),
        (_re.compile(r'\bB[-\s]TIER\b', _re.I),    "B"),
        (_re.compile(r'\bC[-\s]TIER\b', _re.I),    "C"),
        (_re.compile(r'\bFADE\b',         _re.I),   "FADE"),
        # Also catch "S-TIER — Primary", "## S TIER", etc
        (_re.compile(r'^#+\s*S[-\s]TIER', _re.I),   "S"),
        (_re.compile(r'^#+\s*A[-\s]TIER', _re.I),   "A"),
        (_re.compile(r'^#+\s*B[-\s]TIER', _re.I),   "B"),
        (_re.compile(r'^#+\s*C[-\s]TIER', _re.I),   "C"),
        (_re.compile(r'^#+\s*FADE',        _re.I),   "FADE"),
    ]

    # Lines that signal a new section — stop adding to current tier
    SECTION_BREAKS = [
        "MARKET TRAP", "FRL", "POOL", "FLAG", "SECTION",
        "BRIEFING", "RANKING", "OVERALL", "VALUE", "BET CARD",
        "FALLEN STAR", "## ", "==="
    ]

    current_tier = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()

        # Check for section break — stop tier collection
        if any(b in upper for b in SECTION_BREAKS) and current_tier:
            # Only break if it's a header-style line, not player content
            if stripped.startswith("#") or stripped.startswith("**") or stripped.isupper():
                current_tier = None

        # Check if this line announces a tier
        for pattern, tier_key in TIER_PATTERNS:
            if pattern.search(stripped):
                current_tier = tier_key
                break
        else:
            # Only collect player entries when inside a tier
            if current_tier:
                # Strip bullets, numbers, bold markers
                clean = _re.sub(r'^[-•*\d\.#\s]+', '', stripped)
                clean = _re.sub(r'\*+', '', clean).strip()

                # Skip lines that are obviously headers or meta-commentary
                skip_prefixes = (
                    "TIER", "PRIMARY", "STRONG", "PASS", "DEFINITION",
                    "PLAYERS", "NOTE", "WITHOUT", "THESE ARE", "NEED",
                    "FRAMEWORK", "CANNOT", "NO SG", "DATA", "TBD",
                    "|", "---", "===",
                )
                if (len(clean) > 3
                        and not clean.upper().startswith(skip_prefixes)
                        and len(clean) < 80):  # Player names aren't that long
                    player_name = clean.split("—")[0].split(" — ")[0].strip()
                    reason = clean.split("—")[-1].strip() if "—" in clean else ""
                    # Avoid duplicates
                    existing = [p.get("player","") if isinstance(p,dict) else p
                                for p in result["tiers"][current_tier]]
                    if player_name not in existing:
                        result["tiers"][current_tier].append({
                            "player": player_name,
                            "reason": reason,
                        })

    # ── Extract flags ──
    in_flags = False
    for line in lines:
        stripped = line.strip()
        if any(k in stripped.upper() for k in ["FLAG", "BLOCKED", "UNCERTAINTY", "ANOMALY"]):
            in_flags = True
        if in_flags and stripped and len(stripped) > 20:
            result["flags"].append(stripped)

    return result


def _build_odds_update_prompt(state: Dict, odds_data: Dict) -> str:
    current_analysis = state.get("analysis", {})
    event = state.get("event", {})
    current_rankings = json.dumps(current_analysis.get("overall_ranking", [])[:20], indent=2)

    odds_snapshot = json.dumps({
        k: {
            "best_price": v.get("best_price"),
            "best_book": v.get("best_book"),
            "implied_prob": v.get("implied_prob"),
        }
        for k, v in list(odds_data.items())[:50]
    }, indent=2)

    return f"""
ODDS UPDATE — {event.get('name', 'Current Event')}
{datetime.now().strftime('%A %B %d, %Y %H:%M ET')}

Current course/form analysis already done. Now layer in odds.

CURRENT RANKINGS (before odds):
{current_rankings}

LIVE ODDS SNAPSHOT (top 50 by implied prob):
{odds_snapshot}

Please provide:
1. VALUE RANKING — who is mispriced relative to their actual win probability?
2. Any price triggers hit (Straka at 45/1, Hovland/JT at 40/1, etc.)
3. Updated bet card with stake sizing (shorter anchors get larger stakes)
4. Any odds anomalies worth flagging (player missing from board, suspicious line)
5. Hard fades with specific price-based reasoning

Remember: 2-5 outrights depending on prices. Shorter anchors get larger stakes.
Positions: aggressive (T5/T10) then safety (T10/T20).
""".strip()


def _build_article_update_prompt(state: Dict, article_data: Dict) -> str:
    event = state.get("event", {})
    current_briefing = state.get("analysis", {}).get("briefing_paragraph", "")

    new_articles = article_data.get("articles", [])
    article_text = "\n\n---\n\n".join([
        f"SOURCE: {a.get('source', 'Unknown')} ({a.get('outlet', '')})\n"
        f"TITLE: {a.get('title', '')}\n"
        f"{a.get('text', '')[:2000]}"
        for a in new_articles
    ])

    return f"""
ARTICLE UPDATE — {event.get('name', 'Current Event')}
{datetime.now().strftime('%A %B %d, %Y %H:%M ET')}

CURRENT BRIEFING (update incrementally, don't full rewrite):
{current_briefing}

NEW ARTICLES TO FOLD IN:
{article_text}

Please provide:
1. What does new article information change or confirm in current analysis?
2. Any new player narratives worth adding to briefing?
3. Any Haslbauer picks that confirm players we already liked? (Don't let them CREATE conviction — only confirm)
4. Updated briefing paragraph if warranted (incremental, not full rewrite)
5. Any flags: blocked articles, new information that contradicts prior analysis
""".strip()


def _build_weather_update_prompt(state: Dict, weather_data: Dict) -> str:
    event = state.get("event", {})
    return f"""
WEATHER UPDATE — {event.get('name', 'Current Event')}
{datetime.now().strftime('%A %B %d, %Y %H:%M ET')}

Updated forecast:
{json.dumps(weather_data, indent=2)}

Please provide:
1. Does updated weather change course read or dominant stat assessment?
2. Does wind forecast create a meaningful wave split? (Happens 1-3x/year)
3. Any wind players who move up/down given conditions? (Lowry, Straka, etc.)
4. Update briefing weather context if meaningfully changed.
5. FRL wave implications if wave split confirmed.
""".strip()


def _build_withdrawal_prompt(state: Dict, withdrawal_data: Dict) -> str:
    event = state.get("event", {})
    player = withdrawal_data.get("player", "Unknown")
    reason = withdrawal_data.get("reason", "Unknown")

    return f"""
WITHDRAWAL UPDATE — {event.get('name', 'Current Event')}
{datetime.now().strftime('%A %B %d, %Y %H:%M ET')}

WITHDRAWAL: {player}
REASON: {reason}

Please:
1. Remove {player} from all tier/ranking/bet card/pool considerations
2. Flag whether this changes the field composition meaningfully
3. Note if any of our target players are affected by the withdrawal
4. Check: was this a form-related withdrawal or unrelated? (Smotherman baby birth = ignore for form)
""".strip()


def _build_generic_update_prompt(state: Dict, new_data: Dict, update_type: str) -> str:
    event = state.get("event", {})
    return f"""
{update_type.upper()} UPDATE — {event.get('name', 'Current Event')}
{datetime.now().strftime('%A %B %d, %Y %H:%M ET')}

New data:
{json.dumps(new_data, indent=2)[:3000]}

Please fold this new information into the current analysis incrementally.
""".strip()


# ──────────────────────────────────────────────────────────────
# HELPER BUILDERS
# ──────────────────────────────────────────────────────────────

def _normalize_name_for_lookup(name: str) -> str:
    """Normalize a player name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace(".", "")


def _find_player_skills(name: str, skill_ratings: Dict, preds_dict: Dict) -> tuple:
    """
    Look up player skills and predictions using exact then fuzzy name matching.
    Returns (skills_dict, preds_dict) — both may be empty if not found.
    """
    # Try exact match first
    if name in skill_ratings:
        return skill_ratings[name], preds_dict.get(name, {})

    # Try title-cased
    name_title = name.strip().title()
    if name_title in skill_ratings:
        return skill_ratings[name_title], preds_dict.get(name_title, {})

    # Fuzzy: normalize both sides and compare
    name_norm = _normalize_name_for_lookup(name)
    for key in skill_ratings:
        if _normalize_name_for_lookup(key) == name_norm:
            return skill_ratings[key], preds_dict.get(key, {})

    # Partial match: last name only (handles "Rory McIlroy" vs "R. McIlroy")
    name_parts = name_norm.split()
    if len(name_parts) >= 2:
        last = name_parts[-1]
        candidates = [k for k in skill_ratings if _normalize_name_for_lookup(k).endswith(last)]
        if len(candidates) == 1:
            return skill_ratings[candidates[0]], preds_dict.get(candidates[0], {})

    return {}, {}


def _build_field_summary(
    field: List[Dict],
    skill_ratings: Dict,
    dg_predictions: Dict,
    top_n: int = 50,
) -> str:
    if not field:
        return "Field data not yet available."

    if not skill_ratings:
        return "Field loaded but skill ratings not yet available — will populate on Monday runs."

    lines = ["Player                         | Distance | SG:APP  | SG:OTT  | T2G       | SG:PUTT | DG Win% "]
    lines.append("-" * 95)

    # Build a combined lookup: try to match field player names to skill ratings
    # DG field data may use dg_id or slightly different name format
    matched = 0
    unmatched = []

    # Sort by DG win probability if available, else alphabetical
    def sort_key(p):
        name = p.get("player_name") or p.get("name", "")
        _, preds = _find_player_skills(name, skill_ratings, dg_predictions)
        return -(preds.get("win", 0) or 0)

    players_sorted = sorted(field, key=sort_key)

    for p in players_sorted[:top_n]:
        name = p.get("player_name") or p.get("name", "Unknown")
        skills, preds = _find_player_skills(name, skill_ratings, dg_predictions)

        sg_app  = skills.get("sg_app",  skills.get("sg_app_total",  "N/A"))
        sg_ott  = skills.get("sg_ott",  skills.get("sg_ott_total",  "N/A"))
        sg_putt = skills.get("sg_putt", skills.get("sg_putt_total", "N/A"))
        win_pct = preds.get("win")
        dist    = skills.get("driving_dist", skills.get("distance", "N/A"))

        win_str  = f"{win_pct*100:.1f}%" if win_pct else "N/A"
        sg_app_s = f"{sg_app:+.3f}" if isinstance(sg_app, (int, float)) else "N/A"
        sg_ott_s = f"{sg_ott:+.3f}" if isinstance(sg_ott, (int, float)) else "N/A"
        sg_put_s = f"{sg_putt:+.3f}" if isinstance(sg_putt, (int, float)) else "N/A"
        dist_s   = f"{dist:.0f}yd" if isinstance(dist, (int, float)) else "N/A"
        t2g = (sg_app + sg_ott) if isinstance(sg_app, (int, float)) and isinstance(sg_ott, (int, float)) else None
        t2g_s = f"{t2g:+.3f}" if t2g is not None else "N/A"

        if skills:
            matched += 1
        else:
            unmatched.append(name)

        lines.append(f"{name:30} | {dist_s:8} | {sg_app_s:7} | {sg_ott_s:7} | {t2g_s:9} | {sg_put_s:7} | {win_str:7}")

    # Add match quality report at top
    total = min(len(field), top_n)
    header = f"Field stats match rate: {matched}/{total} players matched to skill ratings"
    if unmatched[:5]:
        header += f"\nUnmatched (first 5): {', '.join(unmatched[:5])}"
    lines.insert(0, header)
    lines.insert(1, "")

    return "\n".join(lines)


def _build_article_summary(articles_state: Dict) -> str:
    if not articles_state:
        return "No articles processed yet."

    processed = articles_state.get("processed", [])
    blocked   = articles_state.get("blocked", [])
    narratives = articles_state.get("key_narratives", [])

    lines = []

    if blocked:
        lines.append("⚠️  BLOCKED ARTICLES (flagged — never silently skipped):")
        for b in blocked:
            lines.append(f"   - {b.get('source', 'Unknown')}: {b.get('reason', 'Unknown reason')}")
        lines.append("")

    if processed:
        lines.append(f"Articles processed: {len(processed)}")
        for a in processed:
            lines.append(f"  ✓ {a.get('source', 'Unknown')} — {a.get('title', '')[:80]}")
        lines.append("")

    if narratives:
        lines.append("Key narratives extracted:")
        for n in narratives[:10]:
            lines.append(f"  • {n}")

    return "\n".join(lines) if lines else "No articles available this run."


def _build_player_designations_section(player_db: Optional[List], field_names: set) -> str:
    """
    Build a compact designation block for field players only.
    Injects Kevin's framework knowledge so Claude applies the actual framework
    rather than generic training knowledge.
    """
    if not player_db:
        return "Player database not loaded — Claude will apply general framework principles."

    lines = []
    lines.append(
        "Designation key: EXTRA_CONFIRM_PLUS = heightened positive scrutiny | "
        "FRAMEWORK = standard | EXTRA_CONFIRM_MINUS = heightened skeptical scrutiny | "
        "FALLEN_STAR = formerly elite, degraded — auto-consider at price threshold"
    )
    lines.append("")

    sections = {
        "EXTRA_CONFIRM_PLUS":  "⬆  EXTRA CONFIRM + (heightened positive scrutiny)",
        "FALLEN_STAR":         "★  FALLEN STAR (auto-consider at price threshold)",
        "EXTRA_CONFIRM_MINUS": "⬇  EXTRA CONFIRM − (heightened skeptical scrutiny)",
        "FRAMEWORK":           "◆  FRAMEWORK (standard analysis)",
    }

    for desig_key, header in sections.items():
        players_in_section = []
        for p in player_db:
            if p.designation != desig_key:
                continue
            # Field membership check — last-name fuzzy
            p_last = p.name.lower().split()[-1]
            in_field = (
                p.name.lower() in field_names
                or any(p_last in fn for fn in field_names)
            )
            if not in_field:
                continue

            parts = [p.name]
            if p.auto_price_trigger:
                parts.append(f"auto-consider ≥+{p.auto_price_trigger * 100 - 100}")
            if p.max_price_threshold:
                parts.append(f"never above +{p.max_price_threshold * 100 - 100}")
            if p.course_triggers:
                parts.append(f"triggers: {', '.join(p.course_triggers)}")
            if p.is_liv:
                parts.append("LIV")
            if p.frl_target:
                parts.append("FRL target")

            line = f"  {' | '.join(parts)}"
            note_preview = (p.kevin_notes or "")[:130].strip()
            if note_preview:
                line += f"\n    → {note_preview}"
            players_in_section.append(line)

        if players_in_section:
            lines.append(header)
            lines.extend(players_in_section)
            lines.append("")

    return "\n".join(lines) if len(lines) > 2 else "No matching field players found in player database."


def _build_course_profile_section(course_profile) -> str:
    """
    Build a detailed course profile section from a CourseProfile dataclass.
    Richer than what lives in state['event'] — includes specialist flags,
    winning score, preferred flight, etc.
    """
    if not course_profile:
        return "Course profile not available in Kevin's database — using event-level data above."

    cp = course_profile
    lines = [
        f"Course: {cp.name}",
        f"Location: {cp.location}",
        f"Par / Yardage: {cp.par} / {cp.yardage}",
        f"Course Type: {cp.course_type}",
        f"Distance Multiplier: {cp.distance_multiplier}",
        f"Dominant Stat: {cp.dominant_stat}",
        f"Rough Penalty: {cp.rough_penalty}",
        f"Angle Penalty: {cp.angle_penalty}",
        f"Wind Relevance: {cp.wind_relevance}",
    ]
    if cp.course_avg_acc:
        lines.append(f"Historical Driving Accuracy: {cp.course_avg_acc}%")
    if cp.accuracy_premium:
        lines.append("Accuracy Premium: YES — accuracy-dependent players get uplift here")
    if cp.bomber_course:
        lines.append("Bomber Course: YES — pure distance advantage confirmed")
    if cp.draw_bias:
        lines.append("Shot Shape Preference: RIGHT-TO-LEFT (draw bias)")
    elif getattr(cp, "preferred_flight", None) == "left_to_right":
        lines.append("Shot Shape Preference: LEFT-TO-RIGHT (fade bias)")
    if cp.putting_premium:
        lines.append("Putting Premium: YES — above-average putting weight this week")
    if cp.is_unique_venue:
        lines.append("Unique Venue: YES — standard archetypes may not apply cleanly")
    if cp.is_complex_course:
        lines.append("Complex Course: YES — course management is a real differentiator")
    if cp.historical_winning_score is not None:
        lines.append(f"Historical Winning Score: {cp.historical_winning_score:+d} (vs par)")
    if cp.typical_cut_score is not None:
        lines.append(f"Typical Cut Score: {cp.typical_cut_score:+d} (vs par)")
    if cp.specialist_flags:
        lines.append(f"Specialist Flags: {', '.join(cp.specialist_flags)}")
    if cp.course_notes:
        lines.append(f"\nCourse Notes:\n{cp.course_notes}")

    return "\n".join(lines)


def _build_weather_summary(weather: Dict) -> str:
    if not weather:
        return "Weather data not yet available."

    lines = []
    for round_name in ["r1", "r2", "r3", "r4"]:
        round_data = weather.get(round_name, {})
        if round_data:
            lines.append(
                f"{round_name.upper()}: {round_data.get('narrative', 'TBD')} "
                f"({round_data.get('wind_dir', '')})"
            )

    wave = weather.get("wave_split", {})
    if wave.get("wave_split_matters"):
        lines.append(f"\n⚠️  WAVE SPLIT MATTERS: {wave.get('explanation', '')}")
        if wave.get("frl_note"):
            lines.append(f"FRL NOTE: {wave['frl_note']}")

    bamford = weather.get("bamford_forecast")
    if bamford:
        lines.append(f"\nBamford forecast: {bamford}")

    return "\n".join(lines) if lines else "No weather data."
