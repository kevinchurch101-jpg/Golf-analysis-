"""
Fairway Intel — Core Framework Engine
Implements Sections 2-6 of Kevin's Framework.
Nothing is binary. Everything is on a spectrum. Always apply nuance.

BALL-STRIKING MODEL (updated per conversation April 2026):
- OTT and APP are equal partners at base level
- Combined (OTT + APP) drives the form window conviction
- Course type shifts the prerequisite chain:
    TIGHT/accuracy:  fairway-finding prerequisite → then distance bonus → APP separates
    OPEN/forgiving:  distance prerequisite → then APP separates; accuracy less relevant
    FORCED_LAYUP:    APP dominant, OTT largely irrelevant
- Outlier flag when combined threshold met but one component badly lagging
- Market trap checks both OTT and APP — not just APP
"""

import logging
from typing import Dict, List, Optional

from config import (
    SG_BALL_STRIKING_THRESHOLD, SG_SPIKE_OUTRIGHT, SG_CEILING_DEMO,
    SG_LOPSIDED_FLAG_THRESHOLD, DISTANCE_TIERS,
    HENLEY_VALUE_TRIGGER, STRAKA_TRIGGER_NORMAL, STRAKA_TRIGGER_WEAK,
    HOVLAND_JT_TRIGGER, KEITH_MITCHELL_TRIGGER, FALLEN_STAR_TRIGGER,
    THORBJORNSEN_TRIGGER, FOWLER_MIN_ODDS, TIERS, DESIGNATIONS,
)

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# SECTION 2 — BALL-STRIKING FORM WINDOW
# ──────────────────────────────────────────────────────────────

def assess_form_window(
    recent_sg_app: List[float],
    career_sg_app: float,
    recent_sg_ott: List[float],
    career_sg_ott: float,
    course_type: str = "NEUTRAL",
) -> Dict:
    """
    Assess ball-striking form window using COMBINED OTT + APP.
    OTT and APP are equal partners. Combined drives conviction level.
    Course type flows in to make the outlier flag and course note meaningful.

    Conviction (events where combined >= career combined mean):
        1-2:  INTRIGUING
        3-5:  COMFORTABLE
        6+:   SUPER CONFIDENT

    Outlier flag: combined OK but one component >SG_LOPSIDED_FLAG_THRESHOLD below career.
    """
    if not recent_sg_app and not recent_sg_ott:
        return {
            "conviction_level": "INSUFFICIENT_DATA",
            "events_gaining_combined": 0,
            "events_gaining_app": 0,
            "events_gaining_ott": 0,
            "combined_above_career": False,
            "lopsided_flag": False,
            "lopsided_note": "",
            "form_note": "Insufficient recent event data.",
            "course_type": course_type,
        }

    career_combined = career_sg_app + career_sg_ott
    n       = min(len(recent_sg_app), len(recent_sg_ott)) if recent_sg_ott else len(recent_sg_app)
    app_list = recent_sg_app[:n]
    ott_list = recent_sg_ott[:n] if recent_sg_ott else [0.0] * n

    events_gaining_combined = sum(
        1 for a, o in zip(app_list, ott_list) if (a + o) >= career_combined
    )
    events_gaining_app = sum(1 for sg in app_list if sg >= career_sg_app)
    events_gaining_ott = sum(1 for sg in ott_list if sg >= career_sg_ott)

    if events_gaining_combined >= 6:
        conviction = "SUPER CONFIDENT"
    elif events_gaining_combined >= 3:
        conviction = "COMFORTABLE"
    elif events_gaining_combined >= 1:
        conviction = "INTRIGUING"
    else:
        conviction = "NOT IN FORM"

    r = min(4, n)
    recent_app_avg      = sum(app_list[:r]) / r if r else 0.0
    recent_ott_avg      = sum(ott_list[:r]) / r if r else 0.0
    recent_combined_avg = recent_app_avg + recent_ott_avg

    max_recent = max((a + o) for a, o in zip(app_list[:6], ott_list[:6])) if n >= 1 else 0.0
    has_spike   = any((a + o) >= SG_SPIKE_OUTRIGHT   for a, o in zip(app_list[:6],  ott_list[:6]))
    has_ceiling = any((a + o) >= SG_CEILING_DEMO * 2 for a, o in zip(app_list[:12], ott_list[:12]))

    # ── Two-part outlier / lopsidedness check ──
    #
    # Part A — One component badly BELOW career mean while combined is healthy.
    #   Flags the case where the combined threshold is being met but one stat is
    #   genuinely weak. Surfaces sustainability concerns and course-fit questions.
    #
    # Part B — One component carrying 80%+ of the combined ball-striking gain.
    #   Even if neither component is below its career mean, a highly one-stat
    #   profile raises questions about sustainability and course applicability.
    #   e.g. dominant driver with fine-but-not-great irons meeting the threshold
    #   entirely on OTT — at an approach-dominant course this matters a lot.

    lopsided_flag  = False
    dominant_stat  = None      # "OTT" or "APP" if 80%+ of combined gain
    lopsided_notes = []

    if conviction in ("COMFORTABLE", "SUPER CONFIDENT") and recent_combined_avg > career_combined:
        app_delta = recent_app_avg - career_sg_app
        ott_delta = recent_ott_avg - career_sg_ott
        combined_gain = recent_combined_avg - career_combined   # total gain above career

        # ── Part A: one component badly below career ──
        if ott_delta < -SG_LOPSIDED_FLAG_THRESHOLD and app_delta > 0:
            lopsided_flag = True
            lopsided_notes.append(
                f"Part A — Combined strong but OTT lagging {ott_delta:+.2f} vs career. "
                + ("TIGHT course: fairway-finding concern — distance edge may not materialise."
                   if course_type == "TIGHT"
                   else "OPEN course: verify distance prerequisite still met despite OTT number.")
            )
        elif app_delta < -SG_LOPSIDED_FLAG_THRESHOLD and ott_delta > 0:
            lopsided_flag = True
            lopsided_notes.append(
                f"Part A — Combined strong but APP lagging {app_delta:+.2f} vs career. "
                + ("FORCED_LAYUP/TIGHT course: APP lagging is disqualifying here."
                   if course_type in ("FORCED_LAYUP", "TIGHT")
                   else "OPEN course: distance present but APP is the separator — scrutinise.")
            )

        # ── Part B: one stat carrying 80%+ of the combined gain ──
        if combined_gain > 0.05:   # Only meaningful if there's real gain to apportion
            ott_share = ott_delta / combined_gain if combined_gain else 0
            app_share = app_delta / combined_gain if combined_gain else 0

            if ott_share >= 0.80 and ott_delta > 0:
                dominant_stat = "OTT"
                lopsided_flag = True
                lopsided_notes.append(
                    f"Part B — OTT carrying {ott_share:.0%} of combined gain "
                    f"(OTT +{ott_delta:.2f}, APP {app_delta:+.2f} vs career). "
                    "Dominant driver profile. Consider: does this course reward distance "
                    "enough to sustain, or will approach quality be the separator? "
                    + ("TIGHT/FORCED_LAYUP: OTT-heavy form less applicable here."
                       if course_type in ("TIGHT", "FORCED_LAYUP")
                       else "OPEN: OTT-driven form fits — but watch APP sustainability.")
                )
            elif app_share >= 0.80 and app_delta > 0:
                dominant_stat = "APP"
                lopsided_flag = True
                lopsided_notes.append(
                    f"Part B — APP carrying {app_share:.0%} of combined gain "
                    f"(APP +{app_delta:.2f}, OTT {ott_delta:+.2f} vs career). "
                    "Iron-dominant profile. Consider: is OTT stable enough that "
                    "the approach gains can actually materialise? "
                    + ("OPEN: check distance prerequisite given OTT is not contributing."
                       if course_type == "OPEN"
                       else "TIGHT/FORCED_LAYUP: APP-dominant form fits well here.")
                )

    lopsided_note = " | ".join(lopsided_notes)

    course_note = _course_type_form_note(course_type, recent_app_avg, recent_ott_avg,
                                          career_sg_app, career_sg_ott)

    return {
        "conviction_level": conviction,
        "events_gaining_combined": events_gaining_combined,
        "events_gaining_app": events_gaining_app,
        "events_gaining_ott": events_gaining_ott,
        "recent_combined_avg": round(recent_combined_avg, 3),
        "recent_app_avg": round(recent_app_avg, 3),
        "recent_ott_avg": round(recent_ott_avg, 3),
        "career_combined": round(career_combined, 3),
        "career_app": round(career_sg_app, 3),
        "career_ott": round(career_sg_ott, 3),
        "combined_above_career": recent_combined_avg >= career_combined,
        "combined_above_threshold": recent_combined_avg >= career_combined + SG_BALL_STRIKING_THRESHOLD,
        "app_above_career": recent_app_avg >= career_sg_app,
        "ott_above_career": recent_ott_avg >= career_sg_ott,
        "max_recent_combined": round(max_recent, 3),
        "has_sg_spike": has_spike,
        "has_ceiling_demo": has_ceiling,
        "lopsided_flag": lopsided_flag,
        "lopsided_note": lopsided_note,
        "dominant_stat": dominant_stat,
        "lopsided_parts": lopsided_notes,
        "course_type": course_type,
        "course_note": course_note,
    }


def _course_type_form_note(course_type, recent_app, recent_ott, career_app, career_ott):
    app_up = recent_app >= career_app
    ott_up = recent_ott >= career_ott
    if course_type == "TIGHT":
        if app_up and ott_up:   return "Tight course: gaining both — full profile fits. Verify driving accuracy."
        if app_up:              return "Tight course: APP up, OTT lagging — fairway-finding concern; approach edge may not materialise."
        if ott_up:              return "Tight course: OTT up but APP lagging — in fairway but not converting with irons."
        return                         "Tight course: both below career — does not fit current form."
    elif course_type == "OPEN":
        if app_up and ott_up:   return "Open course: gaining both — distance prerequisite met, APP separating."
        if app_up:              return "Open course: APP up, OTT lagging — verify distance prerequisite still met. Forgiving rough can neutralise accuracy loss."
        if ott_up:              return "Open course: distance present, APP lagging — APP is the separator here; distance alone insufficient."
        return                         "Open course: both below career — not in form for this venue."
    elif course_type == "FORCED_LAYUP":
        return ("Forced layup: APP gaining — fits." if app_up
                else "Forced layup: APP lagging — primary concern at approach-dominant venue.")
    else:
        if app_up and ott_up:   return "Full ball-striking form — gaining both components."
        if app_up:              return "APP gaining, OTT neutral — net ball-striking positive."
        if ott_up:              return "OTT gaining, APP neutral — mixed ball-striking picture."
        return                         "Ball-striking below career mean — not in form."


def assess_win_equity(pga_wins, kft_wins_recent, college_winning, last_win_years_ago, designation):
    has_win_equity = False
    equity_level   = "NONE"
    notes          = []

    if pga_wins >= 2:
        has_win_equity, equity_level = True, "HIGH"
        notes.append(f"{pga_wins} PGA Tour wins")
    elif pga_wins == 1:
        has_win_equity, equity_level = True, "MODERATE"
        notes.append("1 PGA Tour win")
        if last_win_years_ago and last_win_years_ago > 5:
            equity_level = "MODERATE_STALE"
            notes.append(f"— {last_win_years_ago} years ago")
    elif kft_wins_recent >= 2:
        has_win_equity, equity_level = True, "DEVELOPING"
        notes.append(f"{kft_wins_recent} recent KFT wins")
    elif college_winning:
        has_win_equity, equity_level = True, "DEVELOPING"
        notes.append("Prolific college winner")

    if designation == "FALLEN_STAR":
        has_win_equity = True
        notes.append("Fallen star — historical win equity retained")

    return {
        "has_win_equity": has_win_equity,
        "equity_level": equity_level,
        "recommended_markets": (
            ["outright","top5","top10","top20","pool"] if has_win_equity
            else ["top10","top20","pool"]
        ),
        "notes": " | ".join(notes),
    }


# ──────────────────────────────────────────────────────────────
# SECTION 3 — PUTTING PHILOSOPHY
# ──────────────────────────────────────────────────────────────

def assess_putting_profile(career_sg_putt, recent_sg_putt, course_sg_putt_history,
                            is_unique_venue=False, venue_name=""):
    effective = recent_sg_putt if recent_sg_putt is not None else career_sg_putt
    if is_unique_venue and course_sg_putt_history is not None:
        effective = course_sg_putt_history

    if career_sg_putt >= 0.25 and (recent_sg_putt is None or recent_sg_putt >= 0.15):
        profile, trigger = "elite_career_putter", "McCarthy/Burns tier — back when ball-striking spikes"
    elif effective >= 0.10:
        profile, trigger = "above_average", "Slight upside — not the engine"
    elif effective >= -0.10:
        profile, trigger = "average", "Neutral — ball-striking decides"
    elif effective >= -0.25:
        profile, trigger = "modest_liability", "Minor concern — not disqualifying at most venues"
    else:
        profile, trigger = "liability", "Real concern — pure upside if ever putts well (Si Woo type)"

    spike_this_week = (recent_sg_putt is not None and recent_sg_putt > 0.30 and career_sg_putt < 0.10)

    return {
        "profile": profile,
        "career_sg_putt": round(career_sg_putt, 3),
        "recent_sg_putt": round(recent_sg_putt, 3) if recent_sg_putt is not None else None,
        "effective_sg_putt": round(effective, 3),
        "course_history_used": is_unique_venue and course_sg_putt_history is not None,
        "trigger": trigger,
        "spike_this_week": spike_this_week,
        "spike_warning": (
            "MARKET TRAP: Recent putting spike, no career backing — fade outright, positions only"
            if spike_this_week else ""
        ),
    }


def check_market_trap(sg_total, sg_putt, sg_app, sg_ott=0.0):
    """
    Detect market trap: putting inflating totals while BOTH ball-striking components weak.
    Market trap requires OTT AND APP weak — not just APP.
    Partial trap: putting elevated + one ball-striking component weak.
    """
    bs_combined = sg_app + sg_ott
    putt_share  = sg_putt / sg_total if sg_total > 0 else 0

    is_trap     = putt_share > 0.50 and sg_app < 0.10 and sg_ott < 0.20
    partial_trap = (not is_trap and putt_share > 0.40 and (sg_app < 0.0 or sg_ott < -0.10))

    if is_trap:
        warning = "MARKET TRAP: Putting driving totals. Both APP and OTT weak. Fade outright — positions only."
    elif partial_trap:
        warning = f"PARTIAL TRAP: Putting elevated vs ball-striking. {'APP weak' if sg_app < 0.0 else 'OTT lagging'} — scrutinise."
    else:
        warning = ""

    return {
        "is_market_trap": is_trap,
        "is_partial_trap": partial_trap,
        "putt_share_of_total": round(putt_share, 3),
        "ball_striking_combined": round(bs_combined, 3),
        "sg_total": round(sg_total, 3),
        "sg_putt": round(sg_putt, 3),
        "sg_app": round(sg_app, 3),
        "sg_ott": round(sg_ott, 3),
        "warning": warning,
    }


# ──────────────────────────────────────────────────────────────
# SECTION 4 — DISTANCE, ACCURACY, AND COURSE FIT
# ──────────────────────────────────────────────────────────────

def get_distance_tier(driving_distance_vs_avg):
    if driving_distance_vs_avg >= DISTANCE_TIERS["elite_bomber"]:  return "ELITE_BOMBER"
    if driving_distance_vs_avg >= DISTANCE_TIERS["above_average"]: return "ABOVE_AVERAGE"
    if driving_distance_vs_avg >= DISTANCE_TIERS["average"]:       return "AVERAGE"
    return "SHORT"


def assess_driving_profile(distance_tier, driving_acc, sg_ott, course_type,
                            rough_penalty, course_avg_acc=None):
    """
    Prerequisite chain logic per course type.

    TIGHT:     Fairway-finding is Step 1 prerequisite.
               Hit fairways → distance bonus applies → APP separates.
               Miss fairways → distance advantage neutralised regardless of raw distance.
               Exception: universally penal rough (Winged Foot) → shared penalty,
               distance advantage remains unique.

    OPEN:      Distance is Step 1 prerequisite.
               Far enough → APP separates. Accuracy less penalised.
               Bomber with modest OTT stat but elite distance still meets prerequisite.
               Shorter hitter with great APP still fighting an uphill battle.

    FORCED_LAYUP: OTT irrelevant. APP dominant. Everyone in same spot.

    NEUTRAL:   Both contribute proportionally.
    """
    dist_scores  = {"ELITE_BOMBER": 1.0, "ABOVE_AVERAGE": 0.65, "AVERAGE": 0.35, "SHORT": 0.0}
    raw_dist     = dist_scores.get(distance_tier, 0.35)
    acc_deficit  = (course_avg_acc - driving_acc) if course_avg_acc else 0
    is_accurate  = driving_acc >= 60 or (course_avg_acc and driving_acc >= course_avg_acc - 5)

    flags              = []
    prerequisite_met   = False
    prerequisite_note  = ""
    driving_value      = 0.0

    if course_type == "TIGHT":
        prerequisite_met = is_accurate
        if prerequisite_met:
            driving_value    = raw_dist * 0.5
            prerequisite_note = "Fairway-finding prerequisite met — distance bonus applies."
        else:
            driving_value    = 0.1
            prerequisite_note = "Fairway-finding prerequisite NOT met — distance advantage may not materialise."
            if distance_tier in ("ELITE_BOMBER", "ABOVE_AVERAGE"):
                flags.append(
                    f"TIGHT COURSE: {distance_tier} distance but accuracy concern "
                    f"({driving_acc:.0f}% driving acc). Distance edge at risk."
                )
        # Winged Foot: universally penal = shared rough penalty
        if rough_penalty == "HIGH" and driving_acc < 55:
            driving_value    = raw_dist * 0.75
            prerequisite_note += " Winged Foot principle: penal rough shared, distance advantage unique."
            flags.append("Winged Foot principle applies — penal rough shared, distance advantage unique.")

    elif course_type == "OPEN":
        dist_ok          = distance_tier in ("ELITE_BOMBER", "ABOVE_AVERAGE")
        prerequisite_met = dist_ok
        if dist_ok:
            driving_value    = raw_dist * 0.9
            prerequisite_note = "Distance prerequisite met — full advantage at open course."
            if not is_accurate:
                if rough_penalty in ("LOW", "MODERATE"):
                    flags.append(
                        "Open + forgiving rough: accuracy concern minimal. "
                        "Distance advantage intact. Modern PGA Tour default applies."
                    )
                else:
                    flags.append(
                        f"Open course but rough is {rough_penalty} — "
                        "accuracy concern more meaningful than typical open course."
                    )
        else:
            driving_value    = 0.2
            prerequisite_note = (
                "Distance prerequisite marginal — shorter hitter at open course. "
                "Fewer eagle looks, longer approaches. APP quality still matters but uphill."
            )
            flags.append(
                f"OPEN COURSE: {distance_tier} distance — may lack distance prerequisite "
                "to fully exploit open setup."
            )

    elif course_type == "FORCED_LAYUP":
        prerequisite_met  = True
        driving_value     = 0.05
        prerequisite_note = "Forced layup — driving distance irrelevant. APP dominates."

    else:  # NEUTRAL
        prerequisite_met  = True
        driving_value     = raw_dist * 0.6
        prerequisite_note = "Balanced course — distance a moderate advantage."
        if not is_accurate and rough_penalty == "HIGH":
            driving_value *= 0.7
            flags.append("Accuracy concern at HIGH rough penalty course.")

    return {
        "distance_tier": distance_tier,
        "driving_acc": round(driving_acc, 1),
        "course_avg_acc": round(course_avg_acc, 1) if course_avg_acc else None,
        "is_accurate": is_accurate,
        "acc_deficit": round(acc_deficit, 1),
        "course_type": course_type,
        "rough_penalty": rough_penalty,
        "prerequisite_met": prerequisite_met,
        "prerequisite_note": prerequisite_note,
        "driving_value": round(driving_value, 3),
        "flags": flags,
        "summary": (
            f"{distance_tier} | {driving_acc:.0f}% acc | {course_type} | "
            f"Prereq: {'✓' if prerequisite_met else '✗'} | Value: {driving_value:.2f}"
        ),
    }


# ──────────────────────────────────────────────────────────────
# SECTION 5 — COURSE HISTORY
# ──────────────────────────────────────────────────────────────

def assess_course_history(results, current_skill_profile, is_complex_course=False):
    """
    "Similar version" proxy: combined ball-striking (OTT + APP) within 0.4 SG/round.
    Uses combined so a player whose profile has shifted (e.g. OTT-to-APP dominant)
    is still correctly evaluated.
    """
    if not results:
        return {"has_course_history": False, "meaningful": False, "specialist": False,
                "top10_count": 0, "wins": 0, "summary": "No course history."}

    top10s  = [r for r in results if r.get("finish", 99) <= 10]
    wins    = [r for r in results if r.get("finish", 99) == 1]
    strong  = [r for r in results if r.get("finish", 99) <= 20]
    specialist = len(strong) >= 2 and is_complex_course

    current_combined = (current_skill_profile.get("sg_app", 0) or 0) + \
                       (current_skill_profile.get("sg_ott", 0) or 0)
    comparable = [
        r for r in results
        if abs(((r.get("sg_app", 0) or 0) + (r.get("sg_ott", 0) or 0)) - current_combined) <= 0.4
    ]
    meaningful = len(comparable) >= 2 or (len(strong) >= 2 and is_complex_course)

    return {
        "has_course_history": True,
        "meaningful": meaningful,
        "specialist": specialist,
        "top10_count": len(top10s),
        "wins": len(wins),
        "strong_results": len(strong),
        "comparable_results": len(comparable),
        "total_results": len(results),
        "is_complex_course": is_complex_course,
        "summary": (
            f"{len(strong)} strong | {len(top10s)} top-10s"
            + (" — SPECIALIST" if specialist else "")
            + (f" | {len(comparable)} from comparable form era" if comparable else "")
        ),
    }


# ──────────────────────────────────────────────────────────────
# SECTION 6 — DESIGNATION SYSTEM
# ──────────────────────────────────────────────────────────────

def apply_designation_modifier(base_conviction, designation, borderline=False):
    adjusted = base_conviction
    notes    = []

    if designation == "EXTRA_CONFIRM_PLUS":
        if borderline and base_conviction in ("NOT IN FORM", "INTRIGUING"):
            adjusted = "INTRIGUING"
            notes.append("EXTRA CONFIRM + lean: borderline positive → spend extra time confirming")
        elif base_conviction == "INTRIGUING":
            adjusted = "COMFORTABLE"
            notes.append("EXTRA CONFIRM + lean: INTRIGUING → COMFORTABLE")
    elif designation == "EXTRA_CONFIRM_MINUS":
        if borderline and base_conviction in ("INTRIGUING", "COMFORTABLE"):
            adjusted = "INTRIGUING"
            notes.append("EXTRA CONFIRM -: stress test harder — need stronger confirmation")
        notes.append("EXTRA CONFIRM -: extra skepticism required")
    elif designation == "FALLEN_STAR":
        notes.append("FALLEN STAR: any form return at 100/1+ = immediately intriguing")
        notes.append("Price trigger: 100/1+ required. Don't back at 70/1 in bad form.")

    return {
        "original_conviction": base_conviction,
        "adjusted_conviction": adjusted,
        "designation": designation,
        "borderline": borderline,
        "modifier_notes": notes,
    }


def check_price_triggers(player_name, designation, american_odds, is_weak_field=False):
    if american_odds is None:
        return {"triggered": False, "reason": "No odds available", "flags": [], "fractional": None, "american": None, "primary_flag": ""}
    if american_odds <= 0:
        return {"triggered": False, "reason": "Negative American odds", "flags": [], "fractional": None, "american": american_odds, "primary_flag": ""}

    fractional = american_odds / 100
    flags      = []
    triggered  = False

    if "Sepp Straka" in player_name:
        if fractional >= STRAKA_TRIGGER_NORMAL:
            flags.append(f"STRAKA TRIGGER: {fractional:.0f}/1 ≥ {STRAKA_TRIGGER_NORMAL}/1 — must consider"); triggered = True
        elif is_weak_field and fractional >= STRAKA_TRIGGER_WEAK:
            flags.append(f"STRAKA WEAK FIELD: {fractional:.0f}/1 ≥ {STRAKA_TRIGGER_WEAK}/1 — must consider"); triggered = True

    if ("Viktor Hovland" in player_name or "Justin Thomas" in player_name) and designation == "FALLEN_STAR":
        if fractional >= HOVLAND_JT_TRIGGER:
            flags.append(f"FALLEN STAR AUTO-CONSIDER at {fractional:.0f}/1 ≥ {HOVLAND_JT_TRIGGER}/1"); triggered = True

    if "Tony Finau" in player_name and designation == "FALLEN_STAR":
        if fractional >= FALLEN_STAR_TRIGGER:
            flags.append(f"FALLEN STAR TRIGGER at {fractional:.0f}/1 ≥ {FALLEN_STAR_TRIGGER}/1"); triggered = True

    if "Russell Henley" in player_name and fractional >= HENLEY_VALUE_TRIGGER:
        flags.append(f"HENLEY VALUE TRIGGER at {fractional:.0f}/1 — intriguing at right price"); triggered = True

    if "Keith Mitchell" in player_name and fractional >= KEITH_MITCHELL_TRIGGER:
        flags.append(f"MITCHELL PRICE TRIGGER at {fractional:.0f}/1 ≥ {KEITH_MITCHELL_TRIGGER}/1"); triggered = True

    if "Michael Thorbjornsen" in player_name and fractional >= THORBJORNSEN_TRIGGER:
        flags.append(f"THORBJORNSEN BOMBER TRIGGER at {fractional:.0f}/1 — bomber course only"); triggered = True

    if "Rickie Fowler" in player_name and fractional < FOWLER_MIN_ODDS:
        flags.append(f"FOWLER FADE: {fractional:.0f}/1 below {FOWLER_MIN_ODDS}/1 — do not back")

    return {"triggered": triggered, "fractional": fractional, "american": american_odds,
            "flags": flags, "primary_flag": flags[0] if flags else ""}


# ──────────────────────────────────────────────────────────────
# INTEGRATED PLAYER ASSESSMENT
# ──────────────────────────────────────────────────────────────

def build_player_framework_score(player_data, course_data):
    """
    Primary integration point. Combines all framework sections.
    Ball-striking conviction driven by combined OTT+APP.
    Course type flows through all assessments.
    """
    name        = player_data.get("name", "Unknown")
    designation = player_data.get("designation", "FRAMEWORK")
    course_type = course_data.get("course_type", "NEUTRAL")

    # 1. Form window — combined OTT + APP
    form = assess_form_window(
        recent_sg_app=player_data.get("sg_app_recent", []),
        career_sg_app=player_data.get("sg_app_career", 0),
        recent_sg_ott=player_data.get("sg_ott_recent", []),
        career_sg_ott=player_data.get("sg_ott_career", 0),
        course_type=course_type,
    )

    # 2. Putting
    putting = assess_putting_profile(
        career_sg_putt=player_data.get("sg_putt_career", 0),
        recent_sg_putt=player_data.get("sg_putt_recent"),
        course_sg_putt_history=player_data.get("course_putting_history"),
        is_unique_venue=course_data.get("is_unique_venue", False),
        venue_name=course_data.get("name", ""),
    )

    # 3. Market trap — both OTT and APP
    r = min(4, len(player_data.get("sg_app_recent", [])))
    recent_app_avg = sum(player_data.get("sg_app_recent", [0])[:r]) / max(1, r)
    r2 = min(4, len(player_data.get("sg_ott_recent", [])))
    recent_ott_avg = sum(player_data.get("sg_ott_recent", [0])[:r2]) / max(1, r2)

    trap = check_market_trap(
        sg_total=player_data.get("sg_total_recent", 0) or 0,
        sg_putt=player_data.get("sg_putt_recent", 0) or 0,
        sg_app=recent_app_avg,
        sg_ott=recent_ott_avg,
    )

    # 4. Driving profile — prerequisite chain
    driving = assess_driving_profile(
        distance_tier=player_data.get("distance_tier", "AVERAGE"),
        driving_acc=player_data.get("driving_acc", 60.0),
        sg_ott=recent_ott_avg,
        course_type=course_type,
        rough_penalty=course_data.get("rough_penalty", "MODERATE"),
        course_avg_acc=course_data.get("course_avg_acc"),
    )

    # 5. Course history — comparable version uses combined
    course_hist = assess_course_history(
        results=player_data.get("course_history", []),
        current_skill_profile={"sg_app": recent_app_avg, "sg_ott": recent_ott_avg},
        is_complex_course=course_data.get("is_complex_course", False),
    )

    # 6. Win equity
    win_eq = assess_win_equity(
        pga_wins=player_data.get("pga_wins", 0),
        kft_wins_recent=player_data.get("kft_wins_recent", 0),
        college_winning=player_data.get("college_winning", False),
        last_win_years_ago=player_data.get("last_win_years_ago"),
        designation=designation,
    )

    # 7. Designation modifier
    borderline = form["conviction_level"] in ("INTRIGUING", "NOT IN FORM")
    desig_mod  = apply_designation_modifier(form["conviction_level"], designation, borderline)

    # 8. Price triggers
    price_flags = check_price_triggers(
        player_name=name, designation=designation,
        american_odds=player_data.get("best_odds_american"),
        is_weak_field=course_data.get("is_weak_field", False),
    )

    conviction = desig_mod["adjusted_conviction"]
    has_value  = price_flags.get("triggered") or (
        player_data.get("dg_win_prob", 0) > (player_data.get("implied_prob", 0) or 0) * 1.15
    )

    all_flags = []
    if form.get("lopsided_flag"):        all_flags.append(form["lopsided_note"])
    all_flags.extend(driving.get("flags", []))
    if trap.get("is_partial_trap"):      all_flags.append(trap["warning"])
    all_flags.extend(price_flags.get("flags", []))

    # Tier recommendation
    if trap.get("is_market_trap"):
        tier, reason = "B", "Market trap: putting driving totals — positions only"
    elif conviction == "SUPER CONFIDENT" and win_eq["has_win_equity"] and has_value:
        tier, reason = "S", "Super confident combined ball-striking + win equity + value"
    elif conviction in ("COMFORTABLE", "SUPER CONFIDENT") and win_eq["has_win_equity"]:
        tier, reason = "A", "Strong combined form + win equity"
    elif conviction in ("INTRIGUING", "COMFORTABLE"):
        tier, reason = "B", "Intriguing combined form — positions/FRL"
    elif designation == "FALLEN_STAR" and price_flags.get("triggered"):
        tier, reason = "B", "Fallen star at trigger price — lottery outright / positions"
    else:
        tier, reason = "C", "Pass or monitor"

    # Downgrade if driving prerequisite not met
    if not driving["prerequisite_met"] and tier in ("S", "A"):
        tier    = "B"
        reason += f" | DOWNGRADED: driving prerequisite not met ({course_type} course)"

    return {
        "name": name, "designation": designation,
        "form": form, "putting": putting, "market_trap": trap,
        "driving": driving, "course_history": course_hist,
        "win_equity": win_eq, "designation_modifier": desig_mod,
        "price_flags": price_flags, "all_flags": all_flags,
        "recommended_tier": tier, "tier_reason": reason,
        "conviction": conviction, "course_type": course_type,
    }
