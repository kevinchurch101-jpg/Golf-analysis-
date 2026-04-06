"""
Fairway Intel — Course Analysis Module
Assigns distance multiplier, dominant stat, rough/angle penalties.
Augusta National gets full Section 11 treatment.
"""
 
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
 
log = logging.getLogger(__name__)
 
 
@dataclass
class CourseProfile:
    name: str
    location: str
    par: int
    yardage: int
    distance_multiplier: str          # FULL / PARTIAL / COMPRESSED
    dominant_stat: str                # "APP", "OTT", "ARG", "PUTT", "BALANCED"
    rough_penalty: str                # "HIGH", "MODERATE", "LOW"
    angle_penalty: str                # "HIGH", "MODERATE", "LOW"
    is_unique_venue: bool = False     # Augusta, Harbour Town, Pebble type
    is_complex_course: bool = False   # Course management really matters
    draw_bias: bool = False           # Augusta etc.
    putting_premium: bool = False     # Specific putting premium
    wind_relevance: str = "MODERATE"  # "HIGH", "MODERATE", "LOW"
    accuracy_premium: bool = False    # TPC SA type
    bomber_course: bool = False       # Clear bomber advantage
    course_notes: str = ""
    specialist_flags: List[str] = field(default_factory=list)
    historical_winning_score: Optional[int] = None   # vs par
    typical_cut_score: Optional[int] = None
    course_type: str = "NEUTRAL"        # "TIGHT", "OPEN", "FORCED_LAYUP", "NEUTRAL"
    course_avg_acc: Optional[float] = None  # historical driving accuracy % at this venue
 
 
# ──────────────────────────────────────────────────────────────
# KNOWN COURSE PROFILES
# ──────────────────────────────────────────────────────────────
 
KNOWN_COURSES: Dict[str, CourseProfile] = {
 
    "tpc_san_antonio": CourseProfile(
        name="TPC San Antonio (AT&T Oaks)",
        location="San Antonio, TX",
        par=72, yardage=7494,
        distance_multiplier="PARTIAL",
        dominant_stat="APP",
        rough_penalty="MODERATE",
        angle_penalty="MODERATE",
        accuracy_premium=True,
        course_type="TIGHT",
        course_avg_acc=62.5,
        wind_relevance="HIGH",
        course_notes=(
            "Approach-dominant accuracy course. Long enough that distance matters "
            "but accuracy required. Valero template: irons + ball-striking wins. "
            "Corey Conners 2x winner archetype."
        ),
        specialist_flags=["conners", "bhatia", "mccarthy", "horschel_history"],
    ),
 
    "augusta_national": CourseProfile(
        name="Augusta National Golf Club",
        location="Augusta, GA",
        par=72, yardage=7545,
        distance_multiplier="PARTIAL",
        dominant_stat="BALANCED",
        rough_penalty="LOW",
        angle_penalty="HIGH",
        is_unique_venue=True,
        is_complex_course=True,
        draw_bias=True,
        wind_relevance="MODERATE",
        course_type="NEUTRAL",
        course_avg_acc=None,
        course_notes=(
            "Thinker's course. Course management is a genuine differentiating skill. "
            "Distance on 13 and 15 specifically — bomber advantage real. "
            "Putting rewards course-specific understanding not generic Tour metrics. "
            "Experience weight is higher here than almost anywhere else. "
            "ARG and angles around greens matter enormously. "
            "Know where to miss and where NOT to miss on every hole. "
            "First timers get meaningful newcomer discount even with elite metrics."
        ),
        historical_winning_score=-14,
    ),
 
    "harbour_town": CourseProfile(
        name="Harbour Town Golf Links",
        location="Hilton Head, SC",
        par=71, yardage=7099,
        distance_multiplier="COMPRESSED",
        dominant_stat="ARG",
        rough_penalty="HIGH",
        angle_penalty="HIGH",
        is_complex_course=True,
        accuracy_premium=True,
        putting_premium=True,
        course_type="TIGHT",
        course_avg_acc=68.0,
        course_notes=(
            "Positional golf. Accuracy is premium. Short game and scrambling. "
            "Distance barely matters — COMPRESSED multiplier. "
            "Webb Simpson specialist course."
        ),
        specialist_flags=["webb_simpson"],
    ),
 
    "tpc_scottsdale": CourseProfile(
        name="TPC Scottsdale (Stadium Course)",
        location="Scottsdale, AZ",
        par=71, yardage=7261,
        distance_multiplier="PARTIAL",
        dominant_stat="APP",
        rough_penalty="LOW",
        angle_penalty="MODERATE",
        bomber_course=False,
        course_type="OPEN",
        course_avg_acc=60.0,
        course_notes=(
            "Nick Taylor specialist. Birdie fest in low rough. "
            "Approach skill separates. Crowd noise and conditions unique."
        ),
        specialist_flags=["nick_taylor"],
    ),
 
    "colonial_country_club": CourseProfile(
        name="Colonial Country Club (Hogan's Alley)",
        location="Fort Worth, TX",
        par=70, yardage=7209,
        distance_multiplier="COMPRESSED",
        dominant_stat="ARG",
        rough_penalty="HIGH",
        angle_penalty="HIGH",
        is_complex_course=True,
        accuracy_premium=True,
        course_type="TIGHT",
        course_avg_acc=67.0,
        course_notes=(
            "Positional golf. Accuracy and course management paramount. "
            "Spieth specialist — Texas venue + course management. "
            "Ben Hogan's playground — shotmaking over power."
        ),
        specialist_flags=["spieth"],
    ),
 
    "pebble_beach": CourseProfile(
        name="Pebble Beach Golf Links",
        location="Pebble Beach, CA",
        par=72, yardage=7075,
        distance_multiplier="COMPRESSED",
        dominant_stat="ARG",
        rough_penalty="HIGH",
        angle_penalty="HIGH",
        is_unique_venue=True,
        is_complex_course=True,
        wind_relevance="HIGH",
        course_notes=(
            "Ocean conditions, wind, and positional play. "
            "COMPRESSED distance multiplier. Short game premium. "
            "Weather and wind can be decisive."
        ),
    ),
 
    "muirfield_village": CourseProfile(
        name="Muirfield Village Golf Club",
        location="Dublin, OH",
        par=72, yardage=7392,
        distance_multiplier="PARTIAL",
        dominant_stat="APP",
        rough_penalty="HIGH",
        angle_penalty="HIGH",
        is_complex_course=True,
        course_notes=(
            "Nicklaus design — rewards full game. Cantlay specialist. "
            "Course management and precision required."
        ),
        specialist_flags=["cantlay"],
    ),
 
    "generic_long_accurate": CourseProfile(
        name="Generic Long Accurate Course",
        location="Unknown",
        par=72, yardage=7400,
        distance_multiplier="PARTIAL",
        dominant_stat="APP",
        rough_penalty="MODERATE",
        angle_penalty="MODERATE",
        course_notes="Standard PGA Tour long accurate course profile.",
    ),
 
    "generic_bomber": CourseProfile(
        name="Generic Bomber Course",
        location="Unknown",
        par=72, yardage=7600,
        distance_multiplier="FULL",
        dominant_stat="OTT",
        rough_penalty="LOW",
        angle_penalty="LOW",
        bomber_course=True,
        course_notes="Distance advantage is FULL multiplier. Wide, reachable par-5s.",
    ),
}
 
 
def get_course_profile(course_identifier: str) -> Optional[CourseProfile]:
    """Look up a course profile by identifier (case-insensitive)."""
    key = course_identifier.lower().replace(" ", "_").replace("-", "_")
    if key in KNOWN_COURSES:
        return KNOWN_COURSES[key]
    # Fuzzy match
    for k, v in KNOWN_COURSES.items():
        if key in k or any(word in k for word in key.split("_") if len(word) > 3):
            return v
    return None
 
 
def build_course_profile_from_description(
    name: str,
    par: int,
    yardage: int,
    description: str,
    weather_data: Optional[Dict] = None,
) -> CourseProfile:
    """
    Build a CourseProfile for a course not in the known database.
    Uses keyword analysis of the course description.
    """
    desc_lower = description.lower()
 
    # Distance multiplier heuristics
    if any(k in desc_lower for k in ["wide fairways", "reachable par-5", "bomber", "power"]):
        dist_mult = "FULL"
    elif any(k in desc_lower for k in ["accuracy", "tight", "penal rough", "long and accurate"]):
        dist_mult = "PARTIAL"
    elif any(k in desc_lower for k in ["positional", "precision", "short", "harbour", "colonial"]):
        dist_mult = "COMPRESSED"
    elif yardage >= 7500:
        dist_mult = "FULL"
    elif yardage >= 7200:
        dist_mult = "PARTIAL"
    else:
        dist_mult = "COMPRESSED"
 
    # Dominant stat
    if any(k in desc_lower for k in ["approach", "iron", "accuracy-premium"]):
        dominant = "APP"
    elif any(k in desc_lower for k in ["off the tee", "distance", "bomber"]):
        dominant = "OTT"
    elif any(k in desc_lower for k in ["around the green", "scrambling", "arg", "positional"]):
        dominant = "ARG"
    elif any(k in desc_lower for k in ["putting", "putt"]):
        dominant = "PUTT"
    else:
        dominant = "BALANCED"
 
    # Rough penalty
    if any(k in desc_lower for k in ["penal rough", "deep rough", "thick rough", "penalizing"]):
        rough = "HIGH"
    elif any(k in desc_lower for k in ["light rough", "generous", "links", "forgiving"]):
        rough = "LOW"
    else:
        rough = "MODERATE"
 
    # Unique venue / complexity
    unique = any(k in desc_lower for k in ["augusta", "pebble", "harbour town", "unique"])
    complex_course = any(k in desc_lower for k in [
        "management", "strategic", "complex", "think", "positional", "unique"
    ])
 
    return CourseProfile(
        name=name,
        location="Unknown",
        par=par,
        yardage=yardage,
        distance_multiplier=dist_mult,
        dominant_stat=dominant,
        rough_penalty=rough,
        angle_penalty="MODERATE",
        is_unique_venue=unique,
        is_complex_course=complex_course,
        draw_bias="augusta" in name.lower(),
        wind_relevance="HIGH" if weather_data and weather_data.get("r1", {}).get("wind_mph", 0) >= 15 else "MODERATE",
        course_notes=description[:500],
    )
 
 
def assess_course_player_fit(
    player_profile,      # PlayerProfile from players.py
    course: CourseProfile,
) -> Dict:
    """
    Score how well a player's profile fits a specific course.
    Returns fit assessment dict.
    """
    fit_factors = []
    fit_score = 50   # Start neutral
 
    # Distance multiplier fit
    if course.distance_multiplier == "FULL" and player_profile.distance_tier == "ELITE_BOMBER":
        fit_score += 15
        fit_factors.append("Elite bomber at FULL distance multiplier course — strong fit")
    elif course.distance_multiplier == "FULL" and player_profile.distance_tier == "ABOVE_AVERAGE":
        fit_score += 8
        fit_factors.append("Above average distance at FULL course — solid fit")
    elif course.distance_multiplier == "COMPRESSED" and player_profile.distance_tier in ("ELITE_BOMBER", "ABOVE_AVERAGE"):
        fit_score += 0   # Distance neutralized
        fit_factors.append("Distance neutralized at COMPRESSED course")
    elif course.distance_multiplier == "COMPRESSED" and player_profile.distance_tier == "SHORT":
        fit_score += 5
        fit_factors.append("Short hitter not disadvantaged at COMPRESSED course")
 
    # Dominant stat fit
    if course.dominant_stat == "APP" and "accuracy" in player_profile.kevin_notes.lower():
        fit_score += 10
        fit_factors.append("APP-dominant course fits accuracy profile")
 
    # Accuracy premium
    if course.accuracy_premium and player_profile.distance_tier == "SHORT":
        fit_score += 5
        fit_factors.append("Short accurate hitter fits accuracy-premium venue")
 
    # Specialist check
    player_lower = player_profile.name.lower().split()[-1]
    if player_lower in [s.lower() for s in course.specialist_flags]:
        fit_score += 20
        fit_factors.append(f"COURSE SPECIALIST: {player_profile.name} at {course.name}")
 
    # Shot shape at Augusta
    if course.draw_bias and player_profile.shot_shape_preference == "high_cut":
        fit_score -= 10
        fit_factors.append(f"SHOT SHAPE CONCERN: {player_profile.name} prefers high cut at draw-bias course")
 
    # Unique venue newcomer discount
    if course.is_unique_venue and not course.specialist_flags:
        fit_factors.append("Unique venue — weight course-specific history carefully")
 
    return {
        "player": player_profile.name,
        "course": course.name,
        "fit_score": min(100, max(0, fit_score)),
        "distance_multiplier": course.distance_multiplier,
        "dominant_stat": course.dominant_stat,
        "fit_factors": fit_factors,
        "draw_bias_concern": course.draw_bias and player_profile.shot_shape_preference == "high_cut",
        "specialist": any(
            player_lower in s.lower() for s in course.specialist_flags
        ),
    }
 
 
# ──────────────────────────────────────────────────────────────
# AUGUSTA NATIONAL — SECTION 11 FULL ASSESSMENT
# ──────────────────────────────────────────────────────────────
 
def assess_augusta_fit(
    player_profile,
    skill_data: Dict,
    course_history: Dict,
    num_masters_starts: int = 0,
) -> Dict:
    """
    Full Augusta National assessment per Section 11.
    Separate from standard course fit — more nuanced.
    """
    name = player_profile.name
    notes = []
    flags = []
    score = 50
 
    # Distance — spectrum not binary — par-5 bonus on 13 and 15
    if player_profile.distance_tier in ("ELITE_BOMBER", "ABOVE_AVERAGE"):
        score += 10
        notes.append(f"Distance advantage real on 13 and 15 ({player_profile.distance_tier})")
    # Even shorter hitters can compete — just no par-5 bonus
 
    # Conversion chain check — must have overall strong profile
    sg_app = skill_data.get("sg_app", 0) or 0
    if sg_app < -0.10:
        score -= 15
        flags.append("APP negative — full-game requirement not met even with distance")
 
    # Putting — course-specific history overrides career
    course_sg_putt = course_history.get("sg_putt", None)
    career_sg_putt = skill_data.get("sg_putt", 0) or 0
    effective_putt = course_sg_putt if course_sg_putt is not None else career_sg_putt
 
    if effective_putt >= 0.20:
        score += 12
        notes.append("Strong putting profile at Augusta")
    elif effective_putt >= 0.0:
        notes.append("Adequate putting — not a concern")
    elif effective_putt < -0.30:
        score -= 8
        flags.append("Putting liability at Augusta — watch course-specific history")
 
    # Bryson special case — underrated elite putter
    if "Bryson" in name or "DeChambeau" in name:
        score += 8
        notes.append("KEY: Underrated elite putter — factor always at Augusta")
 
    # Shot shape — draw bias is real
    if player_profile.shot_shape_preference == "high_cut":
        score -= 8
        flags.append(f"SHOT SHAPE FLAG: {name} prefers high cut — Augusta draw bias is real concern")
    elif player_profile.shot_shape_preference == "draw":
        score += 6
        notes.append("Natural draw suits Augusta bias")
 
    # Experience weight — higher here than almost anywhere
    if num_masters_starts >= 5:
        score += 12
        notes.append(f"Veteran Augusta experience ({num_masters_starts} starts) — significant edge")
    elif num_masters_starts >= 2:
        score += 6
        notes.append(f"{num_masters_starts} Masters starts — building course knowledge")
    elif num_masters_starts == 1:
        notes.append("1 Masters start — limited course knowledge")
    else:
        score -= 10
        flags.append("First-time Masters participant — meaningful newcomer discount applies")
 
    # Gamer mentality / course management — subjective but real
    if "gamer" in player_profile.augusta_notes.lower() or "course knowledge" in player_profile.augusta_notes.lower():
        score += 6
        notes.append("Noted Augusta course management strength")
 
    # Course history — weight more than anywhere else
    if course_history.get("top_5_count", 0) >= 2:
        score += 10
        notes.append(f"Strong Augusta course history: {course_history.get('top_5_count', 0)} top-5s")
    elif course_history.get("top_10_count", 0) >= 1:
        score += 5
 
    # LIV player note — only 4 PGA events/year
    if player_profile.is_liv:
        notes.append("LIV player — one of only 4 PGA Tour-eligible events. Strategic importance elevated.")
 
    # Player-specific notes
    if player_profile.augusta_notes:
        notes.append(f"Kevin's Augusta note: {player_profile.augusta_notes}")
 
    return {
        "player": name,
        "augusta_fit_score": min(100, max(0, score)),
        "notes": notes,
        "flags": flags,
        "effective_putt": effective_putt,
        "distance_tier": player_profile.distance_tier,
        "num_masters_starts": num_masters_starts,
        "is_liv": player_profile.is_liv,
        "shot_shape_concern": player_profile.shot_shape_preference == "high_cut",
    }
