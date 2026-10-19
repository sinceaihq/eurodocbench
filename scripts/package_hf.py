"""Package a generated release as Parquet files for the Hugging Face Hub.

    python scripts/package_hf.py --data data --out hub/dataset

Each row holds one document: the scanned page (``image``), the original PDF
bytes (``pdf``), the PDF text layer (``text``), the 12 ground-truth fields and
the generation metadata. The gold JSONL files and the manifest are copied
unchanged so the scorer can be pointed at them directly.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from datasets import Dataset, Features, Image, List, Value

from eurodocbench.document import FIELDS
from eurodocbench.locales import LOCALES

FEATURES = Features(
    {
        "id": Value("string"),
        "split": Value("string"),
        "locale": Value("string"),
        "language": Value("string"),
        "country": Value("string"),
        "layout": Value("string"),
        "font": Value("string"),
        "date_style": Value("string"),
        "currency_style": Value("string"),
        "image": Image(),
        "pdf": Value("binary"),
        "text": Value("string"),
        "fields": {f: Value("string") for f in FIELDS},
        "vat_breakdown": List(
            {"rate": Value("string"), "base": Value("string"), "vat": Value("string")}
        ),
        "lines": List(
            {
                "item": Value("string"),
                "description": Value("string"),
                "quantity": Value("string"),
                "unit_price": Value("string"),
                "vat_rate": Value("string"),
                "amount": Value("string"),
            }
        ),
    }
)


def rows(data: Path, split: str) -> Iterator[dict[str, Any]]:
    with (data / f"{split}.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            loc = LOCALES[rec["locale"]]
            doc_id = rec["id"]
            yield {
                "id": doc_id,
                "split": split,
                "locale": rec["locale"],
                "language": loc.language,
                "country": loc.country,
                "layout": rec["layout"],
                "font": rec["style"]["font"],
                "date_style": rec["style"]["date_style"],
                "currency_style": rec["style"]["currency_style"],
                "image": {
                    "bytes": (data / split / "scan" / f"{doc_id}.jpg").read_bytes(),
                    "path": f"{doc_id}.jpg",
                },
                "pdf": (data / split / "pdf" / f"{doc_id}.pdf").read_bytes(),
                "text": (data / split / "text" / f"{doc_id}.txt").read_text(encoding="utf-8"),
                "fields": rec["fields"],
                "vat_breakdown": rec["vat_breakdown"],
                "lines": rec["lines"],
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    (args.out / "data").mkdir(parents=True, exist_ok=True)
    for split in ("dev", "test"):
        ds = Dataset.from_generator(
            rows, gen_kwargs={"data": args.data, "split": split}, features=FEATURES
        )
        ds.to_parquet(str(args.out / "data" / f"{split}.parquet"))
        print(split, len(ds))
    (args.out / "gold").mkdir(exist_ok=True)
    for name in ("dev.jsonl", "test.jsonl"):
        shutil.copy(args.data / name, args.out / "gold" / name)
    shutil.copy(args.data / "manifest.json", args.out / "manifest.json")


if __name__ == "__main__":
    main()
