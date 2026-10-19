"""Run the keyword/regex baseline over a split.

    python scripts/run_rules.py --data data --split test --source text \
        --out runs/rules-text-test.jsonl
    python scripts/run_rules.py --data data --split test --source ocr --ocr-dir runs/ocr-test \
        --out runs/rules-ocr-test.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eurodocbench.baselines.rules import extract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--source", choices=["text", "ocr"], default="text")
    parser.add_argument("--ocr-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    with (args.data / f"{args.split}.jsonl").open(encoding="utf-8") as fh:
        ids = [json.loads(line)["id"] for line in fh]
    src = args.data / args.split / "text" if args.source == "text" else args.ocr_dir
    assert src is not None, "--ocr-dir is required with --source ocr"
    texts = [(src / f"{doc_id}.txt").read_text(encoding="utf-8") for doc_id in ids]
    t0 = time.perf_counter()
    preds = [extract(text) for text in texts]
    seconds = time.perf_counter() - t0
    with args.out.open("w", encoding="utf-8") as out:
        for doc_id, fields in zip(ids, preds, strict=True):
            out.write(json.dumps({"id": doc_id, "fields": fields}, ensure_ascii=False) + "\n")
    meta = {"source": args.source, "split": args.split, "documents": len(ids),
            "documents_per_second": len(ids) / seconds, "threads": 1}  # fmt: skip
    args.out.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(ids)} predictions to {args.out} ({meta['documents_per_second']:.0f} docs/s)")


if __name__ == "__main__":
    main()
