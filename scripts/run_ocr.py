"""OCR the scanned pages with EasyOCR and write plain text in reading order.

    pip install easyocr
    python scripts/run_ocr.py --data data --split test --out runs/ocr-test --workers 4

All 12 benchmark languages use the Latin script and EasyOCR's shared Latin
recognition model, so one reader is configured for all of them; the system
is not told the document's language.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

# EasyOCR has no Finnish pack; Finnish letters (ä, ö, å) are covered by the
# Swedish and Estonian character sets of the shared Latin model.
LANGS = ["en", "sv", "et", "de", "fr", "nl", "it", "es", "pl", "pt", "cs", "da"]
_reader: Any = None


def _init(threads: int) -> None:
    global _reader
    import easyocr
    import torch

    torch.set_num_threads(threads)
    _reader = easyocr.Reader(LANGS, gpu=False, verbose=False)


def lines_from(results: list[tuple[list[list[float]], str, float]]) -> list[str]:
    """Group word boxes into lines by vertical overlap, left to right."""
    boxes = []
    for bbox, text, _conf in results:
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        boxes.append((min(ys), max(ys), min(xs), text))
    boxes.sort(key=lambda b: ((b[0] + b[1]) / 2, b[2]))
    lines: list[list[tuple[float, float, float, str]]] = []
    for box in boxes:
        center = (box[0] + box[1]) / 2
        if lines:
            last = lines[-1]
            top = min(b[0] for b in last)
            bottom = max(b[1] for b in last)
            if top <= center <= bottom:
                last.append(box)
                continue
        lines.append([box])
    return [" ".join(b[3] for b in sorted(line, key=lambda b: b[2])) for line in lines]


def ocr_one(path: str) -> tuple[str, str, float]:
    t0 = time.perf_counter()
    results = _reader.readtext(path, paragraph=False, detail=1)
    text = "\n".join(lines_from(results))
    return Path(path).stem, text, time.perf_counter() - t0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2, help="torch threads per worker")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    images = sorted((args.data / args.split / "scan").glob("*.jpg"))[: args.limit]
    todo = [str(p) for p in images if not (args.out / f"{p.stem}.txt").exists()]
    timings = []
    with ProcessPoolExecutor(args.workers, initializer=_init, initargs=(args.threads,)) as pool:
        for doc_id, text, secs in pool.map(ocr_one, todo, chunksize=2):
            (args.out / f"{doc_id}.txt").write_text(text, encoding="utf-8")
            timings.append(secs)
            if len(timings) % 50 == 0:
                print(f"{len(timings)}/{len(todo)}", flush=True)
    meta = {
        "engine": "easyocr",
        "easyocr_version": __import__("easyocr").__version__,
        "languages": LANGS,
        "documents": len(images),
        "seconds_per_page_mean": sum(timings) / len(timings) if timings else None,
        "workers": args.workers,
        "threads_per_worker": args.threads,
        "cpu_count": os.cpu_count(),
    }
    (args.out / "_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
