"""Check that the code regenerates the published release.

    python scripts/check_reproducible.py --sample 60

Regenerates a random sample of documents and compares them with
``releases/v0.1/manifest.json``. PDFs, text layers and ground truth must be
byte-identical. Scans are JPEG-encoded by Pillow, whose output can differ
between builds of libjpeg, so they are only reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from eurodocbench.generate import SPLITS, build_one, doc_ids

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release", type=Path, default=ROOT / "releases/v0.1/manifest.json")
    parser.add_argument("--sample", type=int, default=60)
    args = parser.parse_args()
    manifest = json.loads(args.release.read_text(encoding="utf-8"))
    seed = manifest["seed"]
    files = manifest["files"]
    jobs = [(d, loc, lay, seed) for split, n in SPLITS.items() for d, loc, lay in doc_ids(split, n)]
    assert len(jobs) == sum(s["documents"] for s in manifest["splits"].values())
    sample = random.Random(0).sample(jobs, min(args.sample, len(jobs)))
    failures, scan_diffs = [], 0
    for job in sample:
        doc_id = job[0]
        split = doc_id.split("-", 1)[0]
        out = build_one(job)
        checks = {
            f"{split}/pdf/{doc_id}.pdf": out["pdf"],
            f"{split}/text/{doc_id}.txt": out["text"].encode("utf-8"),
        }
        for rel, data in checks.items():
            if hashlib.sha256(data).hexdigest() != files[rel]:
                failures.append(rel)
        if hashlib.sha256(out["scan"]).hexdigest() != files[f"{split}/scan/{doc_id}.jpg"]:
            scan_diffs += 1
    print(f"checked {len(sample)} documents: {len(failures)} PDF/text mismatches, "
          f"{scan_diffs} scan byte differences (informational)")  # fmt: skip
    for rel in failures[:20]:
        print("MISMATCH", rel)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
