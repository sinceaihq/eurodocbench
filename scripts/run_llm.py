"""Zero-shot LLM extraction baseline (llama.cpp, CPU).

    pip install llama-cpp-python huggingface_hub
    python scripts/run_llm.py --data data --split test --source text --out runs/qwen-text.jsonl

The model sees only the document text (PDF text layer or OCR output) and the
task description below; it gets no examples from the benchmark. Output is
constrained to the JSON schema of the prediction file.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

FIELDS = (
    "invoice_number", "issue_date", "due_date", "currency", "seller_name", "seller_vat_id",
    "buyer_name", "buyer_vat_id", "iban", "net_amount", "vat_amount", "total_amount",
)  # fmt: skip

SYSTEM = (
    "You extract data from European invoices. Answer with JSON only, using these keys:\n"
    "invoice_number, issue_date, due_date, currency, seller_name, seller_vat_id, buyer_name, "
    "buyer_vat_id, iban, net_amount, vat_amount, total_amount.\n"
    "Rules: dates as YYYY-MM-DD (European documents write the day before the month); "
    "amounts as plain decimals with a dot and two decimals, no thousands separators "
    '("1.234,50 €" becomes "1234.50"); vat_amount is the total VAT of the invoice; '
    "currency as an ISO 4217 code (EUR, SEK, DKK, PLN, CZK); VAT numbers and IBAN without "
    "spaces; seller is the company issuing the invoice, buyer the customer; "
    "use null when the document does not contain a value."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {f: {"type": ["string", "null"]} for f in FIELDS},
    "required": list(FIELDS),
}


def load_model(repo: str, filename: str, threads: int, ctx: int) -> Any:
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    path = hf_hub_download(repo, filename)
    return Llama(model_path=path, n_ctx=ctx, n_threads=threads, seed=0, verbose=False)


def extract(llm: Any, text: str, max_chars: int = 6000) -> tuple[dict[str, Any], float]:
    t0 = time.perf_counter()
    resp = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Invoice text:\n\n{text[:max_chars]}"},
        ],
        response_format={"type": "json_object", "schema": SCHEMA},
        temperature=0.0,
        max_tokens=400,
    )
    content = resp["choices"][0]["message"]["content"]
    try:
        fields = json.loads(content)
    except json.JSONDecodeError:
        fields = {}
    return {f: fields.get(f) for f in FIELDS}, time.perf_counter() - t0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--source", choices=["text", "ocr"], default="text")
    parser.add_argument("--ocr-dir", type=Path, help="directory of OCR .txt files")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repo", default="Qwen/Qwen2.5-1.5B-Instruct-GGUF")
    parser.add_argument("--file", default="qwen2.5-1.5b-instruct-q4_k_m.gguf")
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--ctx", type=int, default=4096)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    gold = [json.loads(line) for line in (args.data / f"{args.split}.jsonl").open(encoding="utf-8")]
    gold = gold[: args.limit]
    done: set[str] = set()
    if args.out.exists():  # resume
        done = {json.loads(line)["id"] for line in args.out.open(encoding="utf-8")}
    llm = load_model(args.repo, args.file, args.threads, args.ctx)
    timings = []
    with args.out.open("a", encoding="utf-8") as fh:
        for g in gold:
            if g["id"] in done:
                continue
            if args.source == "text":
                src = args.data / args.split / "text" / f"{g['id']}.txt"
            else:
                assert args.ocr_dir, "--ocr-dir is required with --source ocr"
                src = args.ocr_dir / f"{g['id']}.txt"
            fields, secs = extract(llm, src.read_text(encoding="utf-8"))
            timings.append(secs)
            fh.write(json.dumps({"id": g["id"], "fields": fields}, ensure_ascii=False) + "\n")
            fh.flush()
            if len(timings) % 50 == 0:
                print(f"{len(timings)} docs, {sum(timings) / len(timings):.1f}s/doc", flush=True)
    meta = {
        "model_repo": args.repo,
        "model_file": args.file,
        "source": args.source,
        "split": args.split,
        "threads": args.threads,
        "seconds_per_doc_mean": sum(timings) / len(timings) if timings else None,
        "cpu_count": os.cpu_count(),
    }
    args.out.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
