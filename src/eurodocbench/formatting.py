"""Locale-specific rendering of amounts and dates."""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from .locales import Locale

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round half up to cents (the usual commercial rounding)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def format_number(value: Decimal, loc: Locale, decimals: int = 2, grouping: bool = True) -> str:
    sign = "-" if value < 0 else ""
    q = abs(value).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    int_part, _, frac = f"{q:f}".partition(".")
    if grouping and len(int_part) > 3:
        groups: list[str] = []
        while len(int_part) > 3:
            groups.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        groups.insert(0, int_part)
        int_part = loc.group_sep.join(groups)
    return sign + int_part + (loc.decimal_sep + frac if decimals else "")


def format_amount(value: Decimal, loc: Locale, currency: str | None = "symbol") -> str:
    """``currency``: ``"symbol"``, ``"code"`` (ISO 4217) or ``None``."""
    number = format_number(value, loc)
    if currency is None:
        return number
    if currency == "code":
        return f"{number} {loc.currency}" if not loc.symbol_before else f"{loc.currency} {number}"
    sym = loc.currency_symbol
    if loc.symbol_before:
        # en-IE writes "€1,234.56"; nl-NL writes "€ 1.234,56".
        return f"{sym}{number}" if loc.language == "en" else f"{sym} {number}"
    return f"{number} {sym}"


def format_rate(rate: Decimal, loc: Locale) -> str:
    text = format_number(rate, loc, decimals=1 if rate != rate.to_integral() else 0)
    return f"{text} %" if loc.language in {"fi", "sv", "de", "fr", "cs", "pl", "da"} else f"{text}%"


def format_date(value: dt.date, loc: Locale, style: str = "short") -> str:
    if style == "long":
        return loc.date_long.format(d=value.day, month=loc.months[value.month - 1], yyyy=value.year)
    return loc.date_short.format(
        d=value.day, dd=f"{value.day:02d}", m=value.month, mm=f"{value.month:02d}", yyyy=value.year
    )
