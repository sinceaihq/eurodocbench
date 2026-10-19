from __future__ import annotations

import datetime as dt
import random
from decimal import Decimal

import pypdfium2 as pdfium
import pytest

from eurodocbench.document import DATE_RANGE, FIELDS, LAYOUTS, make_invoice
from eurodocbench.formatting import format_amount, format_date, format_number, money
from eurodocbench.generate import build_one, doc_ids, pdf_text
from eurodocbench.identifiers import (
    group4,
    is_valid_iban,
    is_valid_vat_id,
    synthetic_iban,
    synthetic_vat_id,
)
from eurodocbench.locales import FIELD_LABELS, ITEM_KEYS, LOCALES
from eurodocbench.render import render_pdf

ALL_CELLS = [(loc, lay) for loc in LOCALES for lay in LAYOUTS]


def test_twelve_locales_with_complete_tables() -> None:
    assert len(LOCALES) == 12
    for loc in LOCALES.values():
        assert set(loc.labels) == set(FIELD_LABELS)
        assert all(len(v) == 2 and all(v) for v in loc.labels.values())
        assert len(loc.items) == len(ITEM_KEYS)
        assert len(set(loc.items)) == len(loc.items)
        assert len(loc.months) == 12


def test_generation_is_deterministic_and_seed_dependent() -> None:
    a = make_invoice("test-x", "de-DE", "grid", seed=1)
    assert a == make_invoice("test-x", "de-DE", "grid", seed=1)
    assert a != make_invoice("test-x", "de-DE", "grid", seed=2)
    assert render_pdf(a) == render_pdf(make_invoice("test-x", "de-DE", "grid", seed=1))


@pytest.mark.parametrize(("locale", "layout"), ALL_CELLS)
def test_invoice_arithmetic_is_consistent(locale: str, layout: str) -> None:
    for i in range(5):
        inv = make_invoice(f"t-{locale}-{layout}-{i}", locale, layout)
        assert all(ln.amount == money(ln.quantity * ln.unit_price) for ln in inv.lines)
        assert inv.net_amount == sum(ln.amount for ln in inv.lines)
        assert inv.vat_amount == sum(v for _, _, v in inv.vat_breakdown)
        for rate, base, vat in inv.vat_breakdown:
            assert vat == money(base * rate / 100)
        assert inv.total_amount == inv.net_amount + inv.vat_amount
        assert DATE_RANGE[0] <= inv.issue_date <= DATE_RANGE[1]
        assert inv.due_date is None or inv.due_date > inv.issue_date
        assert set(inv.ground_truth()) == set(FIELDS)


def test_identifiers_never_pass_their_checksums() -> None:
    rng = random.Random(0)
    for loc in LOCALES.values():
        for _ in range(300):
            vat = synthetic_vat_id(rng, loc.country)
            assert vat.startswith(loc.country)
            assert not is_valid_vat_id(vat)
            iban = synthetic_iban(rng, loc.country, loc.iban_length)
            assert len(iban) == loc.iban_length
            assert not is_valid_iban(iban)


def test_identifiers_are_invalid_for_an_independent_validator() -> None:
    stdnum_vat = pytest.importorskip("stdnum.eu.vat")
    stdnum_iban = pytest.importorskip("stdnum.iban")
    rng = random.Random(1)
    for loc in LOCALES.values():
        for _ in range(300):
            assert not stdnum_vat.is_valid(synthetic_vat_id(rng, loc.country))
            assert not stdnum_iban.is_valid(synthetic_iban(rng, loc.country, loc.iban_length))


def test_validators_accept_known_valid_examples() -> None:
    # Published example IBANs (ECBS / SWIFT registry examples).
    for iban in ("DE89370400440532013000", "FI2112345600000785", "NL91ABNA0417164300",
                 "PL61109010140000071219812874", "IE29AIBK93115212345678"):  # fmt: skip
        assert is_valid_iban(iban)
        assert is_valid_iban(group4(iban))


def test_formatting_examples() -> None:
    v = Decimal("1234567.5")
    assert format_amount(v, LOCALES["de-DE"]) == "1.234.567,50 €"
    assert format_amount(v, LOCALES["fi-FI"]) == "1 234 567,50 €"
    assert format_amount(v, LOCALES["fr-FR"]) == "1 234 567,50 €"
    assert format_amount(v, LOCALES["en-IE"]) == "€1,234,567.50"
    assert format_amount(v, LOCALES["nl-NL"], "code") == "EUR 1.234.567,50"
    assert format_number(Decimal("999"), LOCALES["de-DE"]) == "999,00"
    d = dt.date(2026, 3, 5)
    assert format_date(d, LOCALES["sv-SE"]) == "2026-03-05"
    assert format_date(d, LOCALES["cs-CZ"]) == "5. 3. 2026"
    assert format_date(d, LOCALES["pl-PL"], "long") == "5 marca 2026"
    assert format_date(d, LOCALES["es-ES"], "long") == "5 de marzo de 2026"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_pdf_text_layer_contains_the_answers(layout: str) -> None:
    inv = make_invoice(f"t-{layout}", "fi-FI", layout)
    text = pdf_text(render_pdf(inv))
    assert inv.invoice_number in text
    assert inv.seller.name in text.replace("\n", " ")
    assert format_number(inv.total_amount, LOCALES["fi-FI"]) in text


def test_pdf_metadata_does_not_leak_ground_truth() -> None:
    inv = make_invoice("t-meta", "de-DE", "classic")
    doc = pdfium.PdfDocument(render_pdf(inv))
    meta = " ".join(str(v) for v in doc.get_metadata_dict().values())
    for value in inv.ground_truth().values():
        if value and len(str(value)) > 3:
            assert str(value) not in meta


def test_build_one_outputs() -> None:
    out = build_one(("test-de-DE-modern-000", "de-DE", "modern", 7))
    assert out["pdf"].startswith(b"%PDF")
    assert out["scan"][:2] == b"\xff\xd8"  # JPEG
    assert out["record"]["id"] == "test-de-DE-modern-000"
    assert "Rechnung" in out["text"] or "RECHNUNG" in out["text"]


def test_doc_ids_cover_every_cell() -> None:
    ids = list(doc_ids("dev", 2))
    assert len(ids) == len(LOCALES) * len(LAYOUTS) * 2
    assert len({i for i, _, _ in ids}) == len(ids)
