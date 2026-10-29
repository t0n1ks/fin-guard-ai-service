"""The user's calendar day and hour for the companion.

Go owns the user's timezone (X-User-Timezone → remembered on the profile →
UTC, Phase 2.16) and sends the user's local calendar date as ``local_date``
(the daily counters) and local hour as ``local_hour`` (the greeting); this
service never guesses a zone of its own. Without them (an older caller) UTC
is used — never the server's own clock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def resolve_today(local_date: date | str | None) -> date:
    """The user's local date as sent by Go, else today's UTC date.

    A value more than a day away from UTC cannot be anyone's local date
    (zones span UTC−12 … UTC+14) and is ignored.
    """
    utc = utc_today()
    if isinstance(local_date, str):
        try:
            local_date = date.fromisoformat(local_date.strip())
        except ValueError:
            local_date = None
    if isinstance(local_date, date) and abs((local_date - utc).days) <= 1:
        return local_date
    return utc


def resolve_hour(local_hour: int | str | None) -> int:
    """The user's local hour (0–23) as sent by Go, else the current UTC hour."""
    try:
        hour = int(str(local_hour).strip())
    except (TypeError, ValueError):
        return utc_hour()
    return hour if 0 <= hour <= 23 else utc_hour()
