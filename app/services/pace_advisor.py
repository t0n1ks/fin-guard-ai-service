from __future__ import annotations

from dataclasses import dataclass

# ── Pace-aware weekly guru ────────────────────────────────────────────────────
#
# Single deterministic function that turns the AUTHORITATIVE weekly-budget
# numbers (produced by Go's computeCycleStats and shipped verbatim in the
# analyze-behavior payload) into a pace verdict. It never re-derives budget math
# from monthly_spending_goal / 4.3 — that historic shortcut is exactly what made
# the UFO claim "133% over" while the budget bar showed plenty of room left.
#
# Hard consistency guarantee: pct_over is > 0 ONLY when spent_this_week actually
# exceeds weekly_allowance, and "pacing_over" is the ONLY tier that carries an
# "over the limit" percentage. It is therefore impossible to tell the user they
# are over the weekly limit while they are under budget.

# Tier keys map 1:1 to the localized template pools in nudge_generator and to the
# frontend i18n keys (utils/paceVerdict.ts), so both services speak the same tone.
TIER_FRESH = "pacing_fresh"   # week just started — no scary numbers yet
TIER_OVER = "pacing_over"     # spent > weekly allowance — honest warning
TIER_WARN = "pacing_warn"     # ahead of an even pace — gentle heads-up
TIER_GREAT = "pacing_great"   # well under with little time left — treat yourself
TIER_GOOD = "pacing_good"     # on/under an even pace — calm, on track
TIER_NONE = ""                # no valid basis (no allowance) — caller falls back

# Even-pace band: spending within ±20% of the linear expectation is "on track".
_OVER_PACE_RATIO = 1.2
# "Well under" thresholds for the encouraging treat-yourself tier.
_WELL_UNDER_RATIO = 0.5
_LATE_WEEK_REMAINING = 2  # days left in the week counted as "the home stretch"
_TREAT_USED_CEILING = 60  # only invite a treat while ≤60% of the week is spent


@dataclass(frozen=True)
class PaceVerdict:
    tier: str
    pct_used: int   # spent / allowance, rounded — truthful % of the week used
    pct_over: int   # max(0, pct_used - 100) — the overage, 0 unless truly over

    @property
    def has_verdict(self) -> bool:
        return self.tier != TIER_NONE


def evaluate_pace(
    weekly_allowance: float,
    spent_this_week: float,
    days_elapsed_in_week: int,
    days_remaining_in_week: int,
) -> PaceVerdict:
    """Pure, deterministic pace verdict from authoritative weekly numbers.

    All four inputs come straight from the backend; this function performs no DB
    or network access and introduces no new budget math beyond dividing the two
    figures the budget bar itself displays.
    """
    # No basis for a pace verdict — the caller keeps its neutral fallback.
    if weekly_allowance <= 0:
        return PaceVerdict(TIER_NONE, 0, 0)

    used_ratio = spent_this_week / weekly_allowance
    pct_used = int(round(used_ratio * 100))
    pct_over = max(0, pct_used - 100)

    # Fresh week / nothing spent → neutral. Guards divide-by-zero on expected.
    if days_elapsed_in_week <= 0 or spent_this_week <= 0:
        return PaceVerdict(TIER_FRESH, pct_used, pct_over)

    # Honest over-budget warning — the ONLY tier that surfaces pct_over.
    if spent_this_week > weekly_allowance:
        return PaceVerdict(TIER_OVER, pct_used, pct_over)

    # Time-adjusted pace: how the spend compares to an even daily burn.
    expected_by_now = weekly_allowance * days_elapsed_in_week / 7.0
    pace_ratio = spent_this_week / expected_by_now if expected_by_now > 0 else 0.0

    if pace_ratio >= _OVER_PACE_RATIO:
        return PaceVerdict(TIER_WARN, pct_used, pct_over)

    # Well under an even pace: encourage a guilt-free treat when the week is
    # nearly done, or when running remarkably lean past midweek.
    well_under_late = days_remaining_in_week <= _LATE_WEEK_REMAINING and pct_used < _TREAT_USED_CEILING
    remarkably_lean = pace_ratio < _WELL_UNDER_RATIO and days_elapsed_in_week >= 3
    if pace_ratio < 0.8 and (well_under_late or remarkably_lean):
        return PaceVerdict(TIER_GREAT, pct_used, pct_over)

    # On or comfortably under an even pace.
    return PaceVerdict(TIER_GOOD, pct_used, pct_over)
