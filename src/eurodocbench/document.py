"""Synthetic invoice content and its ground truth.

Every document is generated from its own ``random.Random`` seeded with the
document id, so any single document can be regenerated in isolation and the
dataset does not depend on generation order.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .formatting import money
from .identifiers import synthetic_iban, synthetic_vat_id
from .locales import ITEM_KEYS, LOCALES, REDUCED_RATE_ITEMS, Locale

LAYOUTS = ("classic", "modern", "compact", "grid", "narrow")
FIELDS = (
    "invoice_number",
    "issue_date",
    "due_date",
    "currency",
    "seller_name",
    "seller_vat_id",
    "buyer_name",
    "buyer_vat_id",
    "iban",
    "net_amount",
    "vat_amount",
    "total_amount",
)
DATE_RANGE = (dt.date(2025, 1, 1), dt.date(2026, 9, 30))

_ONSETS = ("b", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z", "br", "dr",
           "kr", "pr", "st", "tr", "vel", "mar", "sol", "tor")  # fmt: skip
_VOWELS = ("a", "e", "i", "o", "u", "ai", "ea", "io")
_CODAS = ("", "", "n", "r", "s", "l", "x", "m", "nd", "rk")


@dataclass(frozen=True)
class Party:
    name: str
    street: str
    postcode: str
    city: str
    country: str
    vat_id: str | None


@dataclass(frozen=True)
class Line:
    item: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Style:
    """Rendering choices that change how the same content looks."""

    layout: str
    font: str  # "sans" | "serif" | "mono"
    label_variant: int  # 0 or 1
    date_style: str  # "short" | "long"
    currency_style: str  # "symbol" | "code"
    vat_id_spaced: bool
    iban_grouped: bool


@dataclass(frozen=True)
class Invoice:
    doc_id: str
    locale: str
    invoice_number: str
    issue_date: dt.date
    due_date: dt.date | None
    currency: str
    seller: Party
    buyer: Party
    iban: str | None
    lines: tuple[Line, ...]
    vat_breakdown: tuple[tuple[Decimal, Decimal, Decimal], ...]  # (rate, base, vat)
    net_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
    style: Style
    notes: tuple[str, ...] = field(default_factory=tuple)

    def ground_truth(self) -> dict[str, Any]:
        """Canonical answers: ISO dates, ``"1234.50"`` amounts, no spaces in ids."""
        return {
            "invoice_number": self.invoice_number,
            "issue_date": self.issue_date.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "currency": self.currency,
            "seller_name": self.seller.name,
            "seller_vat_id": self.seller.vat_id,
            "buyer_name": self.buyer.name,
            "buyer_vat_id": self.buyer.vat_id,
            "iban": self.iban,
            "net_amount": f"{self.net_amount:.2f}",
            "vat_amount": f"{self.vat_amount:.2f}",
            "total_amount": f"{self.total_amount:.2f}",
        }

    def record(self) -> dict[str, Any]:
        """Ground truth plus metadata and line-level detail."""
        return {
            "id": self.doc_id,
            "locale": self.locale,
            "layout": self.style.layout,
            "style": {
                "font": self.style.font,
                "label_variant": self.style.label_variant,
                "date_style": self.style.date_style,
                "currency_style": self.style.currency_style,
                "vat_id_spaced": self.style.vat_id_spaced,
                "iban_grouped": self.style.iban_grouped,
            },
            "fields": self.ground_truth(),
            "vat_breakdown": [
                {"rate": f"{r}", "base": f"{b:.2f}", "vat": f"{v:.2f}"}
                for r, b, v in self.vat_breakdown
            ],
            "lines": [
                {
                    "item": ln.item,
                    "description": ln.description,
                    "quantity": f"{ln.quantity}",
                    "unit_price": f"{ln.unit_price:.2f}",
                    "vat_rate": f"{ln.vat_rate}",
                    "amount": f"{ln.amount:.2f}",
                }
                for ln in self.lines
            ],
        }


def _stem(rng: random.Random, syllables: int) -> str:
    parts = [rng.choice(_ONSETS) + rng.choice(_VOWELS) for _ in range(syllables)]
    return ("".join(parts) + rng.choice(_CODAS)).capitalize()


def company_name(rng: random.Random, loc: Locale) -> str:
    stem = _stem(rng, rng.randint(2, 3))
    form = rng.choice(loc.legal_forms)
    if rng.random() < 0.6:
        return f"{stem} {rng.choice(loc.sectors)} {form}"
    return f"{stem} {form}"


def _postcode(rng: random.Random, pattern: str) -> str:
    out = []
    for ch in pattern:
        if ch == "9":
            out.append(str(rng.randint(0, 9)))
        elif ch == "A":
            out.append(rng.choice("ACDEFHKNPRTVWXY"))
        else:
            out.append(ch)
    return "".join(out)


def party(rng: random.Random, loc: Locale, with_vat: bool) -> Party:
    stem = _stem(rng, 2)
    street = rng.choice(loc.streets).format(Stem=stem, stem=stem.lower(), n=rng.randint(1, 180))
    return Party(
        name=company_name(rng, loc),
        street=street,
        postcode=_postcode(rng, loc.postcode),
        city=rng.choice(loc.cities),
        country=loc.country,
        vat_id=synthetic_vat_id(rng, loc.country) if with_vat else None,
    )


def invoice_number(rng: random.Random, year: int) -> str:
    n = rng.randint(1, 99999)
    pattern = rng.randrange(6)
    if pattern == 0:
        return f"INV-{year}-{n:05d}"
    if pattern == 1:
        return f"{year}/{n:04d}"
    if pattern == 2:
        return f"F{year}{n:05d}"
    if pattern == 3:
        return f"{rng.randint(100000, 999999)}"
    if pattern == 4:
        return f"{rng.choice('ABCDEFGHKLMR')}{rng.choice('ABCDEFGHKLMR')}-{n:05d}"
    return f"{year % 100:02d}-{rng.randint(1, 12):02d}-{n:04d}"


def _random_date(rng: random.Random) -> dt.date:
    lo, hi = DATE_RANGE
    return lo + dt.timedelta(days=rng.randint(0, (hi - lo).days))


def make_invoice(doc_id: str, locale: str, layout: str, seed: int = 0) -> Invoice:
    """Deterministically generate one invoice."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}")
    rng = random.Random(f"{seed}:{doc_id}")
    loc = LOCALES[locale]

    issue = _random_date(rng)
    due = (
        issue + dt.timedelta(days=rng.choice((14, 21, 30, 45, 60))) if rng.random() > 0.15 else None
    )
    seller = party(rng, loc, with_vat=True)
    buyer = party(rng, loc, with_vat=rng.random() > 0.4)
    iban = synthetic_iban(rng, loc.country, loc.iban_length) if rng.random() > 0.1 else None

    multi_rate = len(loc.vat_rates) > 1 and rng.random() < 0.3
    n_lines = rng.randint(1, 7)
    keys = rng.sample(ITEM_KEYS, n_lines)
    if multi_rate and not REDUCED_RATE_ITEMS.intersection(keys):
        keys[-1] = rng.choice(sorted(REDUCED_RATE_ITEMS))
    lines = []
    for key in keys:
        qty = Decimal(rng.choice((1, 1, 1, 2, 3, 4, 5, 10, 12, 20, 25, 50)))
        cents = rng.randint(500, 250_000) * loc.amount_scale
        unit = money(Decimal(cents) / 100)
        rate = loc.vat_rates[1] if multi_rate and key in REDUCED_RATE_ITEMS else loc.vat_rates[0]
        lines.append(
            Line(
                item=key,
                description=loc.items[ITEM_KEYS.index(key)],
                quantity=qty,
                unit_price=unit,
                vat_rate=rate,
                amount=money(qty * unit),
            )
        )
    breakdown = []
    for rate in sorted({ln.vat_rate for ln in lines}, reverse=True):
        base = sum((ln.amount for ln in lines if ln.vat_rate == rate), Decimal(0))
        breakdown.append((rate, base, money(base * rate / 100)))
    net = sum((b for _, b, _ in breakdown), Decimal(0))
    vat = sum((v for _, _, v in breakdown), Decimal(0))

    style = Style(
        layout=layout,
        font=rng.choice(("sans", "sans", "serif", "mono")) if layout != "narrow" else "mono",
        label_variant=rng.randint(0, 1),
        date_style="long" if rng.random() < 0.2 else "short",
        currency_style="code" if rng.random() < 0.3 else "symbol",
        vat_id_spaced=rng.random() < 0.25,
        iban_grouped=rng.random() < 0.7,
    )
    return Invoice(
        doc_id=doc_id,
        locale=locale,
        invoice_number=invoice_number(rng, issue.year),
        issue_date=issue,
        due_date=due,
        currency=loc.currency,
        seller=seller,
        buyer=buyer,
        iban=iban,
        lines=tuple(lines),
        vat_breakdown=tuple(breakdown),
        net_amount=net,
        vat_amount=vat,
        total_amount=net + vat,
        style=style,
    )
