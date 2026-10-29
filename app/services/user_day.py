"""The user's calendar day for the companion's daily counters.

Go owns the user's timezone (X-User-Timezone → remembered on the profile →
UTC, Phase 2.16) and sends the user's local calendar date as ``local_date``;
this service never guesses a zone of its own. Without it (an older caller)
the UTC date is used — never the server's own clock.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


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
