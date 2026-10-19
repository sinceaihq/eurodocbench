"""Zero-shot LLM extraction baseline (llama.cpp, CPU).

    pip install llama-cpp-python huggingface_hub
    python scripts/run_llm.py --data data --split test --source text --out runs/qwen-text.jsonl

On a CPU, a llama.cpp server with several parallel slots is several times
faster than one-at-a-time decoding (continuous batching):

    llama-server -m qwen2.5-1.5b-instruct-q4_k_m.gguf -t 12 -np 8 -c 16384 --port 8080
    python scripts/run_llm.py ... --server http://127.0.0.1:8080 --parallel 8

The model sees only the document text (PDF text layer or OCR output) and the
task description below; it gets no examples from the benchmark. Output is
constrained to the JSON schema of the prediction file.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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


def messages(text: str, max_chars: int = 6000) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Invoice text:\n\n{text[:max_chars]}"},
    ]


def parse(content: str) -> dict[str, Any]:
    try:
        fields = json.loads(content)
    except json.JSONDecodeError:
        fields = {}
    if not isinstance(fields, dict):
        fields = {}
    return {f: fields.get(f) for f in FIELDS}


def extract(llm: Any, text: str) -> tuple[dict[str, Any], float]:
    t0 = time.perf_counter()
    resp = llm.create_chat_completion(
        messages=messages(text),
        response_format={"type": "json_object", "schema": SCHEMA},
        temperature=0.0,
        max_tokens=400,
    )
    return parse(resp["choices"][0]["message"]["content"]), time.perf_counter() - t0


def extract_server(url: str, text: str) -> tuple[dict[str, Any], float]:
    """Same request against a llama.cpp server (OpenAI-compatible endpoint)."""
    t0 = time.perf_counter()
    body = {
        "messages": messages(text),
        "response_format": {"type": "json_object", "schema": SCHEMA},
        "temperature": 0.0,
        "max_tokens": 400,
        "seed": 0,
    }
    req = urllib.request.Request(  # noqa: S310 - local server URL given by the user
        f"{url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
        out = json.load(resp)
    return parse(out["choices"][0]["message"]["content"]), time.perf_counter() - t0


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
    parser.add_argument("--shard", default="0/1", help="i/n: process every n-th document")
    parser.add_argument("--server", help="URL of a running llama.cpp server to use instead")
    parser.add_argument("--parallel", type=int, default=8, help="concurrent requests (--server)")
    args = parser.parse_args()
    shard_i, shard_n = (int(x) for x in args.shard.split("/"))

    gold = [json.loads(line) for line in (args.data / f"{args.split}.jsonl").open(encoding="utf-8")]
    gold = gold[: args.limit][shard_i::shard_n]
    done: set[str] = set()
    if args.out.exists():  # resume
        done = {json.loads(line)["id"] for line in args.out.open(encoding="utf-8")}
    todo = [g for g in gold if g["id"] not in done]

    def source_text(g: dict[str, Any]) -> str:
        if args.source == "text":
            src = args.data / args.split / "text" / f"{g['id']}.txt"
        else:
            assert args.ocr_dir, "--ocr-dir is required with --source ocr"
            src = args.ocr_dir / f"{g['id']}.txt"
        return src.read_text(encoding="utf-8")

    if args.server:
        pool = ThreadPoolExecutor(args.parallel)
        results = pool.map(lambda g: extract_server(args.server, source_text(g)), todo)
    else:
        llm = load_model(args.repo, args.file, args.threads, args.ctx)
        results = (extract(llm, source_text(g)) for g in todo)
    timings = []
    t_start = time.perf_counter()
    with args.out.open("a", encoding="utf-8") as fh:
        for g, (fields, secs) in zip(todo, results, strict=True):
            timings.append(secs)
            fh.write(json.dumps({"id": g["id"], "fields": fields}, ensure_ascii=False) + "\n")
            fh.flush()
            if len(timings) % 50 == 0:
                rate = len(timings) / (time.perf_counter() - t_start)
                print(f"{len(timings)}/{len(todo)} docs, {rate * 60:.1f} docs/min", flush=True)
    wall = time.perf_counter() - t_start
    meta = {
        "model_repo": args.repo,
        "model_file": args.file,
        "source": args.source,
        "split": args.split,
        "engine": "llama.cpp server" if args.server else "llama-cpp-python",
        "threads": args.threads,
        "parallel_requests": args.parallel if args.server else 1,
        "documents": len(timings),
        "seconds_per_doc_mean": sum(timings) / len(timings) if timings else None,
        "documents_per_minute": 60 * len(timings) / wall if timings and wall else None,
        "cpu_count": os.cpu_count(),
    }
    args.out.with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
