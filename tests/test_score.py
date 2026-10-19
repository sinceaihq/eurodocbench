from __future__ import annotations

import copy
from typing import Any

import pytest

from eurodocbench.document import FIELDS, LAYOUTS, make_invoice
from eurodocbench.locales import LOCALES
from eurodocbench.score import ScoringError, anls, canonical, compare, markdown, score


@pytest.fixture(scope="module")
def gold() -> list[dict[str, Any]]:
    return [
        make_invoice(f"t-{loc}-{lay}", loc, lay).record()
        for loc in list(LOCALES)[:4]
        for lay in LAYOUTS
    ]


def perfect(gold: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": g["id"], "fields": copy.deepcopy(g["fields"])} for g in gold]


def test_perfect_predictions(gold: list[dict[str, Any]]) -> None:
    r = score(gold, perfect(gold))
    assert r["field_accuracy"] == r["document_accuracy"] == r["field_f1"] == 1.0
    assert all(v["hallucinated"] == 0 for v in r["fields"].values())


def test_missing_predictions_count_as_empty(gold: list[dict[str, Any]]) -> None:
    r = score(gold, [])
    assert r["document_accuracy"] == 0.0
    assert r["field_recall"] == 0.0
    assert r["field_f1"] == 0.0
    # Empty answers are right exactly where the document has no value.
    n_null = sum(v is None for g in gold for v in g["fields"].values())
    assert r["field_accuracy"] == pytest.approx(n_null / (len(gold) * len(FIELDS)))


def test_unknown_and_duplicate_ids_are_errors(gold: list[dict[str, Any]]) -> None:
    with pytest.raises(ScoringError, match="unknown"):
        score(gold, [{"id": "nope", "fields": {}}])
    p = perfect(gold)
    with pytest.raises(ScoringError, match="duplicate"):
        score(gold, [p[0], p[0]])


@pytest.mark.parametrize(
    ("field", "gold", "pred", "ok"),
    [
        ("total_amount", "1234.50", "1234.5", True),
        ("total_amount", "1234.50", 1234.5, True),
        ("total_amount", "1234.50", "1234.504", True),
        ("total_amount", "1234.50", "1234.51", False),
        ("total_amount", "1234.50", "1.234,50", False),  # locale format is not accepted
        ("total_amount", "1234.50", "1,234.50", False),
        ("issue_date", "2026-03-05", "2026-03-05", True),
        ("issue_date", "2026-03-05", "05.03.2026", False),
        ("issue_date", "2026-03-05", "2026-05-03", False),
        ("iban", "FI2112345600000785", "fi21 1234 5600 0007 85", True),
        ("seller_vat_id", "NL123456789B01", "NL 123.456.789 B01", True),
        ("seller_name", "Velkora Oy", "VELKORA  OY", True),
        ("seller_name", "Velkora Oy", "Velkora", False),
        ("currency", "EUR", "eur", True),
        ("invoice_number", "INV-2026-00012", "inv-2026-00012", True),
        ("due_date", None, None, True),
        ("due_date", None, "", True),
        ("due_date", None, "2026-01-01", False),  # hallucination
        ("due_date", "2026-01-01", None, False),  # miss
    ],
)
def test_compare(field: str, gold: Any, pred: Any, ok: bool) -> None:
    assert compare(field, gold, pred).correct is ok


def test_invalid_format_is_flagged_not_raised() -> None:
    r = compare("total_amount", "10.00", "ten euros")
    assert not r.correct
    assert r.invalid
    assert r.pred_present


def test_gold_must_be_canonical() -> None:
    with pytest.raises(ScoringError):
        canonical("issue_date", "05.03.2026")


def test_hallucination_counted(gold: list[dict[str, Any]]) -> None:
    p = perfect(gold)
    target = next(x for x in p if x["fields"]["buyer_vat_id"] is None)
    target["fields"]["buyer_vat_id"] = "DE123456789"
    r = score(gold, p)
    assert r["fields"]["buyer_vat_id"]["hallucinated"] == 1
    assert r["fields"]["buyer_vat_id"]["precision"] < 1.0


def test_anls() -> None:
    assert anls("abc", "abc") == 1.0
    assert anls("abcd", "abce") == pytest.approx(0.75)
    assert anls("abcd", "wxyz") == 0.0
    assert anls(None, None) == 1.0
    assert anls("a", None) == 0.0


def test_breakdowns_and_markdown(gold: list[dict[str, Any]]) -> None:
    r = score(gold, perfect(gold))
    assert set(r["by"]) == {"locale", "layout", "date_style", "currency_style", "vat_rates"}
    assert set(r["by"]["layout"]) == set(LAYOUTS)
    md = markdown(r)
    assert "| invoice_number |" in md
