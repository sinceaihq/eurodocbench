"""Generate the EuroDocBench dataset.

    python -m eurodocbench.generate --out data --seed 2026

Writes, per split, ``<split>.jsonl`` (ground truth and metadata), ``pdf/``,
``scan/`` (JPEG) and ``text/`` (PDF text layer), plus ``manifest.json`` with
SHA-256 checksums of every file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from . import __version__
from .degrade import scan
from .document import LAYOUTS, make_invoice
from .locales import LOCALES
from .render import render_pdf

SPLITS = {"dev": 4, "test": 20}  # documents per (locale, layout)
SCAN_DPI = 150


def doc_ids(split: str, per_cell: int) -> Iterator[tuple[str, str, str]]:
    for locale in LOCALES:
        for layout in LAYOUTS:
            for i in range(per_cell):
                yield f"{split}-{locale}-{layout}-{i:03d}", locale, layout


def pdf_text(pdf: bytes) -> str:
    doc = pdfium.PdfDocument(pdf)
    try:
        page = doc[0]
        text: str = page.get_textpage().get_text_range()
        return text.replace("\r\n", "\n")
    finally:
        doc.close()


def build_one(args: tuple[str, str, str, int]) -> dict[str, Any]:
    doc_id, locale, layout, seed = args
    inv = make_invoice(doc_id, locale, layout, seed=seed)
    pdf = render_pdf(inv)
    doc = pdfium.PdfDocument(pdf)
    try:
        page_img = doc[0].render(scale=SCAN_DPI / 72).to_pil()
    finally:
        doc.close()
    return {
        "record": inv.record(),
        "pdf": pdf,
        "scan": scan(page_img, f"{seed}:{doc_id}"),
        "text": pdf_text(pdf),
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(out: Path, seed: int, splits: dict[str, int], workers: int = 4) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "generator_version": __version__,
        "seed": seed,
        "scan_dpi": SCAN_DPI,
        "splits": {},
        "files": {},
    }
    for split, per_cell in splits.items():
        for sub in ("pdf", "scan", "text"):
            (out / split / sub).mkdir(parents=True, exist_ok=True)
        jobs = [(d, loc, lay, seed) for d, loc, lay in doc_ids(split, per_cell)]
        records = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(build_one, jobs, chunksize=8):
                rec = result["record"]
                doc_id = rec["id"]
                files = {
                    f"{split}/pdf/{doc_id}.pdf": result["pdf"],
                    f"{split}/scan/{doc_id}.jpg": result["scan"],
                    f"{split}/text/{doc_id}.txt": result["text"].encode("utf-8"),
                }
                for rel, data in files.items():
                    (out / rel).write_bytes(data)
                    manifest["files"][rel] = _sha256(data)
                records.append(rec)
        with (out / f"{split}.jsonl").open("w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        manifest["files"][f"{split}.jsonl"] = _sha256((out / f"{split}.jsonl").read_bytes())
        manifest["splits"][split] = {"documents": len(records), "per_locale_layout": per_cell}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate the EuroDocBench dataset.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dev", type=int, default=SPLITS["dev"])
    parser.add_argument("--test", type=int, default=SPLITS["test"])
    args = parser.parse_args(argv)
    m = generate(args.out, args.seed, {"dev": args.dev, "test": args.test}, args.workers)
    print(json.dumps(m["splits"]))


if __name__ == "__main__":
    main()
