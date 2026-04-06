"""
Fairway Intel — Career Earnings Pool Strategy
COMPLETELY SEPARATE from betting card. Odds are irrelevant here.
Pick most likely winner. Track twice-usage rule always.
LIV player strategic advantage — may be only shot all season.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from config import POOL_TIERS, POOL_MAX_USES

log = logging.getLogger(__name__)


@dataclass
class PoolPick:
    player_name: str
    pool_score: float
    is_primary: bool
    category: str           # "primary", "available", "trap", "do_not_use"
    reason: str
    is_liv: bool = False
    usage_count: int = 0
    is_available: bool = True    # Has remaining uses
    event_tier: str = "REGULAR"
    notes: List[str] = field(default_factory=list)

    @property
    def uses_remaining(self) -> int:
        return max(0, POOL_MAX_USES - self.usage_count)

    @property
    def eligible(self) -> bool:
        return self.uses_remaining > 0


# ──────────────────────────────────────────────────────────────
# USAGE TRACKER
# ──────────────────────────────────────────────────────────────

class PoolUsageTracker:
    """
    Tracks how many times each player has been used in the pool this season.
    Each player can only be used TWICE. Track always. Never waste elite players.
    """

    def __init__(self, usage_data: Optional[Dict] = None):
        self.usage: Dict[str, int] = usage_data or {}

    def get_usage(self, player_name: str) -> int:
        return self.usage.get(player_name, 0)

    def can_use(self, player_name: str) -> bool:
        return self.get_usage(player_name) < POOL_MAX_USES

    def uses_remaining(self, player_name: str) -> int:
        return max(0, POOL_MAX_USES - self.get_usage(player_name))

    def record_use(self, player_name: str):
        self.usage[player_name] = self.get_usage(player_name) + 1
        log.info(f"[Pool] Recorded use for {player_name}. Total: {self.usage[player_name]}/{POOL_MAX_USES}")

    def to_dict(self) -> Dict[str, int]:
        return dict(self.usage)

    def get_exhausted(self) -> List[str]:
        return [name for name, count in self.usage.items() if count >= POOL_MAX_USES]

    def get_summary_table(self) -> List[Dict]:
        return [
            {
                "player": name,
                "uses": count,
                "remaining": max(0, POOL_MAX_USES - count),
                "status": "EXHAUSTED" if count >= POOL_MAX_USES else "AVAILABLE",
            }
            for name, count in sorted(self.usage.items())
        ]


# ──────────────────────────────────────────────────────────────
# POOL STRATEGY LOGIC
# ──────────────────────────────────────────────────────────────

def determine_event_tier(event_name: str, purse: Optional[float]) -> str:
    """
    Classify event tier for pool strategy.
    Signature: $20M+ designated events
    Major: Masters, US Open, etc. (Note: Masters purse smaller than Signatures)
    Regular: $8-10M events
    """
    event_lower = (event_name or "").lower()

    # Major detection
    if any(k in event_lower for k in ["masters", "u.s. open", "us open", "the open", "pga championship"]):
        return "MAJOR"

    # Purse-based Signature detection
    if purse and purse >= 20_000_000:
        return "SIGNATURE"

    # Named Signature events
    signature_keywords = [
        "players championship", "genesis invitational", "arnold palmer invitational",
        "memorial tournament", "travelers championship", "rbc canadian open",
        "bmw championship", "tour championship", "the sentry",
        "at&t pebble beach", "wm phoenix open",
        # Note: Scottish Open and John Deere are NOT PGA Designated events
    ]
    if any(k in event_lower for k in signature_keywords):
        return "SIGNATURE"

    return "REGULAR"


def score_pool_candidates(
    field_data: List[Dict],
    usage_tracker: PoolUsageTracker,
    event_tier: str,
    dg_predictions: Dict,
) -> List[PoolPick]:
    """
    Score all field members for pool selection.
    Odds completely irrelevant — pick most likely winner.

    field_data: list of player dicts with name, is_liv, dg_win_prob
    """
    picks = []

    for player in field_data:
        name = player.get("name", "")
        if not name:
            continue

        is_liv = player.get("is_liv", False)
        usage_count = usage_tracker.get_usage(name)
        can_use = usage_tracker.can_use(name)

        # DG win probability is the primary sort key
        dg_data = dg_predictions.get(name, {})
        win_prob = dg_data.get("win", 0) or 0

        pool_score = win_prob * 100   # Convert to 0-100 scale
        notes = []
        category = "available"

        # Usage check — most important rule
        if not can_use:
            category = "do_not_use"
            notes.append(f"EXHAUSTED: {POOL_MAX_USES} uses reached — cannot deploy")

        # Event tier strategy
        if event_tier in ("SIGNATURE", "MAJOR") and win_prob > 0.08:
            # Deploy elite players at high-value events
            category = "available" if can_use else category
            notes.append(f"Elite player at {event_tier} event — deploy if win prob justifies")
        elif event_tier == "REGULAR" and win_prob > 0.12:
            # At regular events, better to save elite players
            notes.append("REGULAR event — consider saving elite uses for Signatures/Majors")

        # LIV player special consideration
        if is_liv:
            notes.append(
                "LIV player — eligible only 4 PGA events/year. "
                f"{'Masters is one of 4 — deploy wisely' if event_tier == 'MAJOR' else 'Limited appearances — strategic value'}"
            )
            if event_tier == "MAJOR" and can_use:
                pool_score += 5   # Slight bonus for LIV at major (scarcity)

        picks.append(PoolPick(
            player_name=name,
            pool_score=round(pool_score, 3),
            is_primary=False,
            category=category,
            reason=f"DG win prob: {win_prob:.3f}",
            is_liv=is_liv,
            usage_count=usage_count,
            is_available=can_use,
            event_tier=event_tier,
            notes=notes,
        ))

    # Sort by score descending
    picks.sort(key=lambda p: -(p.pool_score if p.is_available else -999))

    # Mark primary pick (top available)
    available = [p for p in picks if p.is_available and p.category != "do_not_use"]
    if available:
        available[0].is_primary = True
        available[0].category = "primary"

    return picks


def identify_trap_plays(picks: List[PoolPick], dg_predictions: Dict) -> List[PoolPick]:
    """
    Identify trap plays: over-selected but don't have best actual win probability.
    Traps are players everyone picks but who aren't truly the best play.
    """
    traps = []
    # In a real implementation, would cross-reference with ownership data
    # For now, flag players who are popular names but rank lower on DG win prob
    primary = next((p for p in picks if p.is_primary), None)
    if not primary:
        return []

    # Flag anyone with much lower win prob than primary but likely high ownership
    high_name_players = ["Rory McIlroy", "Scottie Scheffler", "Jon Rahm", "Brooks Koepka"]
    for pick in picks:
        if (
            pick.player_name in high_name_players
            and pick.pool_score < primary.pool_score * 0.7
            and not pick.is_primary
        ):
            trap_pick = PoolPick(
                player_name=pick.player_name,
                pool_score=pick.pool_score,
                is_primary=False,
                category="trap",
                reason=f"High ownership likely but DG win prob ({pick.pool_score:.1f}) well below best play",
                is_liv=pick.is_liv,
                usage_count=pick.usage_count,
                is_available=pick.is_available,
                event_tier=pick.event_tier,
                notes=["Trap: name recognition drives selection but not best win probability"],
            )
            traps.append(trap_pick)

    return traps


def build_pool_section(
    field_data: List[Dict],
    usage_tracker: PoolUsageTracker,
    event_name: str,
    event_tier: str,
    dg_predictions: Dict,
) -> Dict:
    """
    Build complete pool section for the briefing.
    Returns dict formatted for state file and HTML output.
    ALWAYS completely separate from betting card.
    """
    picks = score_pool_candidates(field_data, usage_tracker, event_tier, dg_predictions)
    trap_plays = identify_trap_plays(picks, dg_predictions)

    primary = next((p for p in picks if p.is_primary), None)
    available = [p for p in picks if p.is_available and p.category == "available"][:5]
    exhausted = [p for p in picks if not p.is_available]

    return {
        "event_name": event_name,
        "event_tier": event_tier,
        "tier_note": _get_tier_note(event_tier),
        "primary_pick": {
            "player": primary.player_name if primary else "TBD",
            "score": primary.pool_score if primary else 0,
            "notes": primary.notes if primary else [],
            "uses_remaining": primary.uses_remaining if primary else 0,
        } if primary else None,
        "available_plays": [
            {
                "player": p.player_name,
                "score": p.pool_score,
                "uses_remaining": p.uses_remaining,
                "notes": p.notes,
                "is_liv": p.is_liv,
            }
            for p in available
        ],
        "trap_plays": [
            {
                "player": p.player_name,
                "reason": p.reason,
                "notes": p.notes,
            }
            for p in trap_plays
        ],
        "usage_tracker": usage_tracker.to_dict(),
        "exhausted_players": exhausted,
        "season_usage_table": usage_tracker.get_summary_table(),
        "strategy_note": _get_strategy_note(event_tier),
    }


def _get_tier_note(event_tier: str) -> str:
    notes = {
        "SIGNATURE": "Signature event ($20M+) — deploy elite players here.",
        "MAJOR": (
            "Major event. Masters purse smaller than Signatures — factor into usage decisions. "
            "LIV players: Masters is one of only 4 PGA-eligible events — consider strategic deployment."
        ),
        "REGULAR": "Regular event ($8-10M) — middle-tier pool strategy. Save elite uses for Signatures.",
    }
    return notes.get(event_tier, "Unknown tier.")


def _get_strategy_note(event_tier: str) -> str:
    if event_tier == "SIGNATURE":
        return "Deploy Scheffler/McIlroy/Morikawa/Schauffele tier. Still consider course fit among elite."
    elif event_tier == "MAJOR":
        return (
            "Deploy LIV players strategically — may be only shot all season. "
            "Masters-specific: course fit and experience matter as much as general skill ranking."
        )
    else:
        return (
            "Regular event pool value from middle tier: "
            "Spieth/Kirk/Henley/Fleetwood tier — too good to ignore but not elite enough to dominate Signatures."
        )
