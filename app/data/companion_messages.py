"""
Companion message variants (the Stage D content pool).

Shape: COMPANION_VARIANTS[message_type][language] -> list of variants, where
language is "en" | "de" | "ru" | "uk"; a tone-specific list may be given as
"<language>:<tone>" (tones: supportive, gentle, celebrate, playful) and wins
over the plain one. Variants are str.format templates over the numbers Go
sends for that type, e.g. "{remaining} left for {days_left} days".

Message types and their numbers (amounts are pre-formatted with the user's
currency):

    overspent         over, remaining, days_left, daily
    big_expense       amount, ratio, category, category_key[, remaining, days_left, daily]
    savings_deposit   amount, saved_total
    income            amount
    pace_warn         spent_pct, elapsed_pct, remaining, days_left, daily
    pace_over         spent_pct, elapsed_pct, remaining, days_left, daily
    pace_recovered    spent_pct, elapsed_pct, remaining, days_left, daily
    payday_tomorrow   remaining, days_left, daily
    last_days         remaining, days_left, daily
    week_checkin      week, spent, remaining, days_left, daily[, forecast_end]
    weekday_heads_up  weekday (0 = Sunday), remaining, days_left, daily
    quest_ask         —

Tone rule (hard requirement): a fact plus an option, never shaming.

Empty until Stage D: every type then renders with the client's own
four-language fallback texts.
"""
from __future__ import annotations

COMPANION_VARIANTS: dict[str, dict[str, list[str]]] = {}
