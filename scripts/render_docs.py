"""Score the baseline runs and fill the result sections of README.md, docs/REPORT.md
and the dataset card.

python scripts/render_docs.py --gold data/test.jsonl --runs runs
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from eurodocbench.document import FIELDS
from eurodocbench.score import canonical, compare, load_jsonl, score

ROOT = Path(__file__).resolve().parents[1]
POWERS_OF_TEN = {Decimal(10) ** k for k in (-3, -2, -1, 1, 2, 3)}
SYSTEMS = (
    ("rules-text-test", "Keyword/regex rules", "text"),
    ("qwen2.5-1.5b-text-test", "Qwen2.5-1.5B-Instruct (zero-shot)", "text"),
    ("rules-ocr-test", "EasyOCR → keyword/regex rules", "scan"),
    ("qwen2.5-1.5b-ocr-test", "EasyOCR → Qwen2.5-1.5B-Instruct", "scan"),
)


def pct(x: float | None) -> str:
    return "—" if x is None else f"{100 * x:.1f}"


def fill(text: str, name: str, content: str) -> str:
    pattern = re.compile(rf"<!-- {name}:start -->.*?<!-- {name}:end -->", re.DOTALL)
    if not pattern.search(text):
        raise KeyError(name)
    return pattern.sub(lambda _: f"<!-- {name}:start -->\n{content}\n<!-- {name}:end -->", text)


def error_kinds(gold: list[dict[str, Any]], preds: dict[str, dict[str, Any]]) -> Counter[str]:
    """Classify wrong amount and date answers of one system."""
    kinds: Counter[str] = Counter()
    for g in gold:
        p = preds.get(g["id"], {})
        for f in ("net_amount", "vat_amount", "total_amount"):
            gv, pv = g["fields"][f], p.get(f)
            if compare(f, gv, pv).correct:
                continue
            if pv in (None, ""):
                kinds["amount missing"] += 1
                continue
            try:
                value = canonical(f, pv)
            except ValueError:
                kinds["amount not in canonical form"] += 1
                continue
            others = [
                g["fields"][o] for o in ("net_amount", "vat_amount", "total_amount") if o != f
            ]
            truth = canonical(f, gv)
            assert isinstance(value, Decimal)
            assert isinstance(truth, Decimal)
            if any(compare(f, o, pv).correct for o in others):
                kinds["amount: another total copied"] += 1
            elif truth and value and (value / truth) in POWERS_OF_TEN:
                kinds["amount: decimal/grouping separator misread (x10^k)"] += 1
            else:
                kinds["amount: other wrong value"] += 1
        for f in ("issue_date", "due_date"):
            gv, pv = g["fields"][f], p.get(f)
            if compare(f, gv, pv).correct:
                continue
            if gv is None:
                kinds["date: hallucinated due date"] += 1
            elif pv in (None, ""):
                kinds["date missing"] += 1
            elif not re.match(r"^\d{4}-\d{2}-\d{2}$", str(pv).strip()):
                kinds["date not in ISO form"] += 1
            elif str(pv)[5:7] == gv[8:10] and str(pv)[8:10] == gv[5:7]:
                kinds["date: day and month swapped"] += 1
            else:
                kinds["date: other wrong value"] += 1
    return kinds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    args = parser.parse_args()
    gold = load_jsonl(args.gold)
    results, preds = {}, {}
    for stem, name, track in SYSTEMS:
        path = args.runs / f"{stem}.jsonl"
        if not path.exists():
            print("missing", path)
            continue
        p = load_jsonl(path)
        r = score(gold, p)
        (args.runs / f"{stem}.score.json").write_text(
            json.dumps(r, indent=2) + "\n", encoding="utf-8"
        )
        results[name] = (track, r)
        preds[name] = {x["id"]: x["fields"] for x in p}

    main_rows = [
        "| system | track | field accuracy | field F1 | document accuracy | hallucinated values | format errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, (track, r) in results.items():
        halluc = sum(v["hallucinated"] for v in r["fields"].values())
        invalid = sum(v["invalid_format"] for v in r["fields"].values())
        main_rows.append(
            f"| {name} | {track} | {pct(r['field_accuracy'])} | {pct(r['field_f1'])} "
            f"| {pct(r['document_accuracy'])} | {halluc:,} | {invalid:,} |"
        )
    main_table = "\n".join(main_rows)

    names = list(results)
    field_rows = ["| field | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for f in FIELDS:
        field_rows.append(
            f"| `{f}` | "
            + " | ".join(pct(results[n][1]["fields"][f]["accuracy"]) for n in names)
            + " |"
        )
    breakdown = []
    for dim in ("locale", "layout", "date_style", "currency_style", "vat_rates"):
        keys = sorted(next(iter(results.values()))[1]["by"][dim])
        breakdown += [f"**By {dim.replace('_', ' ')}** (field accuracy)", "",
                      f"| {dim} | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]  # fmt: skip
        for k in keys:
            breakdown.append(
                f"| {k} | " + " | ".join(pct(results[n][1]["by"][dim].get(k)) for n in names) + " |"
            )
        breakdown.append("")
    errors = []
    for n in names:
        if n.startswith("Keyword/regex rules"):
            continue
        kinds = error_kinds(gold, preds[n])
        if kinds:
            errors.append(f"**{n}** — wrong amount and date answers by kind:")
            errors.append("")
            errors.append("| kind | count |")
            errors.append("|---|---|")
            errors += [f"| {k} | {v:,} |" for k, v in kinds.most_common()]
            errors.append("")

    summary_bits = []
    for name, (track, r) in results.items():
        summary_bits.append(
            f"{name}, {track} track: {pct(r['field_accuracy'])} % field accuracy, "
            f"{pct(r['document_accuracy'])} % of documents fully correct"
        )
    summary = "Test-split results: " + "; ".join(summary_bits) + "."

    runtime = ["| step | engine | throughput | setting |", "|---|---|---|---|"]
    ocr_meta = args.runs / "ocr-test" / "_meta.json"
    if ocr_meta.exists():
        m = json.loads(ocr_meta.read_text(encoding="utf-8"))
        runtime.append(
            f"| OCR | EasyOCR {m['easyocr_version']} | {m['seconds_per_page_mean']:.1f} s per page "
            f"and worker | {m['workers']} workers × {m['threads_per_worker']} threads |"
        )
    for stem, name, track in SYSTEMS:
        meta = args.runs / f"{stem}.meta.json"
        if stem.startswith("qwen") and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            runtime.append(
                f"| {name}, {track} track | {m['engine']} | {m['documents_per_minute']:.1f} "
                f"documents per minute | {m['shards']} servers × {m['threads']} threads, "
                f"{m['parallel_requests']} slots each |"
            )
    for stem, name, track in SYSTEMS:
        meta = args.runs / f"{stem}.meta.json"
        if stem.startswith("rules") and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            runtime.append(
                f"| {name}, {track} track | Python | {m['documents_per_second']:.0f} "
                f"documents per second | {m['threads']} thread |"
            )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    (ROOT / "README.md").write_text(fill(readme, "results", main_table), encoding="utf-8")
    card_path = ROOT / "hub/DATASET_README.md"
    card = card_path.read_text(encoding="utf-8")
    card_path.write_text(fill(card, "results", main_table), encoding="utf-8")
    report = (ROOT / "docs/REPORT.md").read_text(encoding="utf-8")
    report = fill(report, "summary", summary)
    report = fill(report, "results", main_table)
    report = fill(report, "runtime", "\n".join(runtime))
    report = fill(report, "fields", "\n".join(field_rows))
    report = fill(report, "breakdown", "\n".join(breakdown))
    report = fill(report, "errors", "\n".join(errors) or "No errors to analyse.")
    (ROOT / "docs/REPORT.md").write_text(report, encoding="utf-8")
    print(main_table)


if __name__ == "__main__":
    main()
