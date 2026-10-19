from __future__ import annotations

from decimal import Decimal

import pytest

from eurodocbench.baselines.rules import amounts_in, dates_in, extract, parse_amount
from eurodocbench.document import LAYOUTS, make_invoice
from eurodocbench.generate import pdf_text
from eurodocbench.locales import LOCALES
from eurodocbench.render import render_pdf
from eurodocbench.score import score


@pytest.mark.parametrize(
    ("token", "value"),
    [
        ("1.234,56", "1234.56"),
        ("1 234,56", "1234.56"),
        ("1 234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        ("1234,56", "1234.56"),
        ("12,50", "12.50"),
        ("-3,10", "-3.10"),
    ],
)
def test_parse_amount(token: str, value: str) -> None:
    assert parse_amount(token) == Decimal(value)


def test_amounts_ignore_percentages() -> None:
    assert amounts_in("MwSt. 19 % 1.234,56 €") == [Decimal("1234.56")]
    assert amounts_in("ALV 25,5 % 10,00") == [Decimal("10.00")]


def test_dates() -> None:
    assert [d.isoformat() for d in dates_in("Datum: 05.03.2026")] == ["2026-03-05"]
    assert [d.isoformat() for d in dates_in("2026-03-05")] == ["2026-03-05"]
    assert [d.isoformat() for d in dates_in("5. března 2026")] == ["2026-03-05"]
    assert [d.isoformat() for d in dates_in("22 de setembro de 2025")] == ["2025-09-22"]
    assert dates_in("31.02.2026") == []


def test_rules_on_generated_text_are_strong() -> None:
    # Fresh seed, so this is not the development split the rules were tuned on.
    gold, preds = [], []
    for loc in LOCALES:
        for lay in LAYOUTS:
            inv = make_invoice(f"unit-{loc}-{lay}", loc, lay, seed=999)
            gold.append(inv.record())
            preds.append({"id": inv.doc_id, "fields": extract(pdf_text(render_pdf(inv)))})
    r = score(gold, preds)
    assert r["field_accuracy"] > 0.95


def test_extract_returns_every_field() -> None:
    out = extract("")
    assert set(out) == {
        "invoice_number", "issue_date", "due_date", "currency", "seller_name", "seller_vat_id",
        "buyer_name", "buyer_vat_id", "iban", "net_amount", "vat_amount", "total_amount",
    }  # fmt: skip
    assert all(v is None for v in out.values())
