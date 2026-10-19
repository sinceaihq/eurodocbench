"""Score predictions against EuroDocBench ground truth.

    python -m eurodocbench.score --gold data/test.jsonl --pred predictions.jsonl

Prediction file: one JSON object per line, ``{"id": ..., "fields": {...}}``,
with the fields of :data:`eurodocbench.document.FIELDS`. Systems must output
canonical values — this is part of the task:

* dates as ISO ``YYYY-MM-DD``;
* amounts as plain decimals with a ``.`` separator and no grouping
  (``"1234.50"``; numbers are accepted too);
* VAT numbers and IBANs with or without spaces (spaces, dots and dashes are
  ignored, case is ignored);
* currency as an ISO 4217 code;
* ``null`` (or a missing key / empty string) when the document has no value.

Comparison is exact after this light canonicalisation, except amounts, which
match within half a cent. Names are compared after Unicode NFKC, case folding
and whitespace normalisation; ANLS is reported for them as well.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .document import FIELDS

DATE_FIELDS = {"issue_date", "due_date"}
AMOUNT_FIELDS = {"net_amount", "vat_amount", "total_amount"}
ID_FIELDS = {"seller_vat_id", "buyer_vat_id", "iban"}
NAME_FIELDS = {"seller_name", "buyer_name"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PLAIN_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")
HALF_CENT = Decimal("0.005")


class ScoringError(ValueError):
    pass


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def canonical(field: str, value: Any) -> str | Decimal | None:
    """Canonical form of a value, or ``None`` if empty. Invalid values raise."""
    if _empty(value):
        return None
    if field in AMOUNT_FIELDS:
        if isinstance(value, bool):
            raise ScoringError(f"{field}: boolean is not an amount")
        text = str(value).strip() if not isinstance(value, float) else repr(value)
        if not PLAIN_DECIMAL_RE.match(text):
            raise ScoringError(f"{field}: {value!r} is not a plain decimal")
        try:
            return Decimal(text)
        except InvalidOperation as exc:  # pragma: no cover - guarded by the regex
            raise ScoringError(str(exc)) from exc
    text = str(value)
    if field in DATE_FIELDS:
        text = text.strip()
        if not ISO_DATE_RE.match(text):
            raise ScoringError(f"{field}: {value!r} is not an ISO date")
        return text
    if field in ID_FIELDS:
        return re.sub(r"[\s.\-]", "", text).upper()
    if field == "currency":
        return text.strip().upper()
    if field == "invoice_number":
        return re.sub(r"\s+", "", text).upper()
    if field in NAME_FIELDS:
        text = unicodedata.normalize("NFKC", text).casefold()
        return " ".join(text.replace(",", " ").split()).strip(" .")
    raise KeyError(field)


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def anls(gold: str | None, pred: str | None, tau: float = 0.5) -> float:
    """Average Normalised Levenshtein Similarity for one pair (ST-VQA style)."""
    if gold is None and pred is None:
        return 1.0
    if gold is None or pred is None:
        return 0.0
    nl = levenshtein(gold, pred) / max(len(gold), len(pred), 1)
    return 1.0 - nl if nl < tau else 0.0


@dataclass
class FieldResult:
    correct: bool
    gold_present: bool
    pred_present: bool
    invalid: bool
    anls: float | None = None


def compare(field: str, gold: Any, pred: Any) -> FieldResult:
    g = canonical(field, gold)
    try:
        p = canonical(field, pred)
        invalid = False
    except ScoringError:
        p, invalid = None, True
    if field in AMOUNT_FIELDS and g is not None and p is not None:
        assert isinstance(g, Decimal)
        assert isinstance(p, Decimal)
        ok = abs(g - p) <= HALF_CENT
    else:
        ok = g == p and not invalid
    res = FieldResult(
        correct=ok,
        gold_present=g is not None,
        pred_present=p is not None or invalid,
        invalid=invalid,
    )
    if field in NAME_FIELDS:
        res.anls = anls(g if isinstance(g, str) else None, p if isinstance(p, str) else None)
    return res


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def score(gold: Iterable[Mapping[str, Any]], preds: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    gold_by_id = {g["id"]: g for g in gold}
    pred_by_id: dict[str, Mapping[str, Any]] = {}
    for p in preds:
        pid = str(p.get("id"))
        if pid not in gold_by_id:
            raise ScoringError(f"prediction for unknown document id {pid!r}")
        if pid in pred_by_id:
            raise ScoringError(f"duplicate prediction for {pid!r}")
        pred_by_id[pid] = p

    per_field: dict[str, list[FieldResult]] = defaultdict(list)
    groups: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    doc_exact = []
    for doc_id, g in gold_by_id.items():
        pfields = (pred_by_id.get(doc_id) or {}).get("fields") or {}
        results = {f: compare(f, g["fields"].get(f), pfields.get(f)) for f in FIELDS}
        for f, r in results.items():
            per_field[f].append(r)
        all_ok = all(r.correct for r in results.values())
        doc_exact.append(all_ok)
        style = g.get("style", {})
        keys = {
            "locale": g.get("locale"),
            "layout": g.get("layout"),
            "date_style": style.get("date_style"),
            "currency_style": style.get("currency_style"),
            "vat_rates": "multiple" if len(g.get("vat_breakdown", [])) > 1 else "single",
        }
        for dim, val in keys.items():
            groups[dim][str(val)].extend(r.correct for r in results.values())

    fields_out = {}
    for f in FIELDS:
        rs = per_field[f]
        tp = sum(r.correct and r.gold_present for r in rs)
        fields_out[f] = {
            "accuracy": _ratio(sum(r.correct for r in rs), len(rs)),
            "precision": _ratio(tp, sum(r.pred_present for r in rs)),
            "recall": _ratio(tp, sum(r.gold_present for r in rs)),
            "hallucinated": sum(r.pred_present and not r.gold_present for r in rs),
            "invalid_format": sum(r.invalid for r in rs),
        }
        if f in NAME_FIELDS:
            fields_out[f]["anls"] = _ratio(sum(r.anls or 0.0 for r in rs), len(rs))
    all_results = [r for f in FIELDS for r in per_field[f]]
    tp = sum(r.correct and r.gold_present for r in all_results)
    prec = _ratio(tp, sum(r.pred_present for r in all_results))
    rec = _ratio(tp, sum(r.gold_present for r in all_results))
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    return {
        "documents": len(gold_by_id),
        "predicted_documents": len(pred_by_id),
        "field_accuracy": _ratio(sum(r.correct for r in all_results), len(all_results)),
        "field_precision": prec,
        "field_recall": rec,
        "field_f1": f1,
        "document_accuracy": _ratio(sum(doc_exact), len(doc_exact)),
        "fields": fields_out,
        "by": {
            dim: {k: _ratio(sum(v), len(v)) for k, v in sorted(vals.items())}
            for dim, vals in groups.items()
        },
    }


def markdown(result: Mapping[str, Any], title: str = "EuroDocBench results") -> str:
    def pct(x: float | None) -> str:
        return "—" if x is None else f"{100 * x:.1f}"

    lines = [
        f"# {title}",
        "",
        f"Documents: {result['documents']} (predicted: {result['predicted_documents']})",
        "",
        "| field accuracy | field F1 | document accuracy |",
        "|---|---|---|",
        f"| {pct(result['field_accuracy'])} | {pct(result['field_f1'])} "
        f"| {pct(result['document_accuracy'])} |",
        "",
        "| field | accuracy | precision | recall | hallucinated | invalid format |",
        "|---|---|---|---|---|---|",
    ]
    for f, r in result["fields"].items():
        lines.append(
            f"| {f} | {pct(r['accuracy'])} | {pct(r['precision'])} | {pct(r['recall'])} "
            f"| {r['hallucinated']} | {r['invalid_format']} |"
        )
    for dim, vals in result["by"].items():
        lines += ["", f"| {dim} | field accuracy |", "|---|---|"]
        lines += [f"| {k} | {pct(v)} |" for k, v in vals.items()]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score EuroDocBench predictions.")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--pred", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="write the full result as JSON")
    parser.add_argument("--markdown", type=Path, help="write a Markdown report")
    args = parser.parse_args(argv)
    result = score(load_jsonl(args.gold), load_jsonl(args.pred))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("documents", "field_accuracy", "field_f1", "document_accuracy")}
        )
    )


if __name__ == "__main__":
    main()
