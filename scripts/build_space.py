"""Build the static results Space: leaderboard.json, samples.json and images.

python scripts/build_space.py --data data --runs runs --out space
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from eurodocbench.document import FIELDS
from eurodocbench.score import compare, load_jsonl, score

ROOT = Path(__file__).resolve().parents[1]
# (prediction file stem, display name, track, note)
SYSTEMS = (
    (
        "rules-text-test",
        "Keyword/regex rules",
        "PDF text",
        "written for these documents; solvability check",
    ),
    (
        "qwen2.5-1.5b-text-test",
        "Qwen2.5-1.5B-Instruct, zero-shot",
        "PDF text",
        "llama.cpp Q4_K_M, CPU",
    ),
    ("rules-ocr-test", "EasyOCR + keyword/regex rules", "scan", ""),
    ("qwen2.5-1.5b-ocr-test", "EasyOCR + Qwen2.5-1.5B-Instruct", "scan", "llama.cpp Q4_K_M, CPU"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-locale", type=int, default=2)
    args = parser.parse_args()
    gold = load_jsonl(args.data / "test.jsonl")
    args.out.mkdir(parents=True, exist_ok=True)

    rows, preds = [], {}
    for stem, name, track, note in SYSTEMS:
        path = args.runs / f"{stem}.jsonl"
        if not path.exists():
            continue
        p = load_jsonl(path)
        preds[name] = {x["id"]: x["fields"] for x in p}
        r = score(gold, p)
        rows.append(
            {
                "system": name,
                "track": track,
                "field_accuracy": r["field_accuracy"],
                "field_f1": r["field_f1"],
                "document_accuracy": r["document_accuracy"],
                "note": note,
            }
        )
    board = {
        "rows": rows,
        "note": (
            "Scores from eurodocbench-score on the full test split. The rule baseline was "
            "written for these templates and shows that every label is recoverable from the "
            "text layer."
        ),
    }
    (args.out / "leaderboard.json").write_text(json.dumps(board, indent=1) + "\n", encoding="utf-8")

    (args.out / "images").mkdir(exist_ok=True)
    layouts = ("classic", "modern", "compact", "grid", "narrow")
    locales = sorted({g["locale"] for g in gold})
    wanted = {
        (loc, layouts[(2 * i + j) % len(layouts)])
        for i, loc in enumerate(locales)
        for j in range(args.per_locale)
    }
    docs: list[dict[str, Any]] = []
    for g in gold:
        key = (g["locale"], g["layout"])
        if key not in wanted:
            continue
        wanted.discard(key)
        loc = g["locale"]
        image = f"images/{g['id']}.jpg"
        shutil.copy(args.data / "test" / "scan" / f"{g['id']}.jpg", args.out / image)
        docs.append(
            {
                "id": g["id"],
                "locale": loc,
                "layout": g["layout"],
                "image": image,
                "gold": g["fields"],
                "predictions": {
                    name: {
                        f: {
                            "value": p.get(g["id"], {}).get(f),
                            "correct": compare(
                                f, g["fields"][f], p.get(g["id"], {}).get(f)
                            ).correct,
                        }
                        for f in FIELDS
                    }
                    for name, p in preds.items()
                },
            }
        )
    samples = {"fields": list(FIELDS), "systems": list(preds), "documents": docs}
    (args.out / "samples.json").write_text(
        json.dumps(samples, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    shutil.copy(ROOT / "web" / "index.html", args.out / "index.html")
    print(f"{len(rows)} leaderboard rows, {len(docs)} sample documents -> {args.out}")


if __name__ == "__main__":
    main()
