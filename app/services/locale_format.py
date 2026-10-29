"""
Numbers as each language writes them, for message variants.

Amounts follow the app's own display: currency symbol first, up to two
decimals (no trailing ",00"), a true minus for negatives. Decimal comma and
the right thousands separator for de / ru / uk.
"""
from __future__ import annotations

from typing import Any, Mapping

AMOUNT_SLOTS = frozenset({"amount", "remaining", "daily", "spent", "over", "saved_total", "forecast_end"})

_CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "UAH": "₴", "RUB": "₽", "PLN": "zł", "CHF": "CHF "}

# (thousands separator, decimal separator)
_SEPARATORS = {"en": (",", "."), "de": (".", ","), "ru": (" ", ","), "uk": (" ", ",")}

# Sunday first, matching Go's time.Weekday.
WEEKDAYS = {
    "en": ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"),
    "de": ("Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"),
    "ru": ("воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"),
    "uk": ("неділя", "понеділок", "вівторок", "середа", "четвер", "пʼятниця", "субота"),
}


def format_number(value: float, lang: str, max_decimals: int = 2) -> str:
    thousands, decimal = _SEPARATORS.get(lang, _SEPARATORS["en"])
    text = f"{abs(value):,.{max_decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    text = text.replace(",", "\x00").replace(".", decimal).replace("\x00", thousands)
    return ("−" if value < 0 else "") + text


def currency_symbol(currency: str) -> str:
    code = (currency or "").upper()
    return _CURRENCY_SYMBOLS.get(code, f"{code} " if code else "")


def format_amount(value: float, currency: str, lang: str = "en") -> str:
    number = format_number(abs(value), lang)
    return f"{'−' if value < 0 else ''}{currency_symbol(currency)}{number}"


def format_slots(slots: Mapping[str, Any], currency: str, lang: str) -> dict[str, str]:
    """The numbers of a message, ready for str.format in ``lang``."""
    out: dict[str, str] = {}
    for key, value in slots.items():
        if isinstance(value, bool):
            continue  # flags (e.g. calibrating) are context, not text
        if key == "weekday" and isinstance(value, int):
            out[key] = WEEKDAYS.get(lang, WEEKDAYS["en"])[value % 7]
        elif key in AMOUNT_SLOTS and isinstance(value, (int, float)):
            out[key] = format_amount(float(value), currency, lang)
        elif isinstance(value, (int, float)):
            out[key] = format_number(float(value), lang, max_decimals=1)
        else:
            out[key] = str(value)
    return out
