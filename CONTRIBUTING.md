# Contributing to EuroDocBench

Thanks for helping. Contributions that make the benchmark more realistic,
add locales or layouts, or add well-documented baseline results are welcome.

## Set-up

```bash
git clone https://github.com/sinceaihq/eurodocbench.git
cd eurodocbench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff format --check . && ruff check . && mypy && pytest
python scripts/check_reproducible.py --sample 60
```

## Ground rules

1. **Releases are immutable.** The v0.1 files are pinned by the checksums in
   `releases/v0.1/manifest.json`, and CI regenerates a sample byte for byte.
   Any change to the generator that alters output requires a new release
   version (and a new manifest), never an in-place update.
2. **No real identities.** Names are synthetic; VAT numbers and IBANs must keep
   failing their checksums (`tests/test_generator.py` checks this against
   `python-stdnum`).
3. **Scores must be reproducible.** A new baseline needs the exact command,
   model revision and hardware, plus the prediction file, so anyone can
   re-score it with `eurodocbench-score`.
4. Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`).

## Adding a locale

Add a `Locale` in `src/eurodocbench/locales.py` (labels in two variants,
months, VAT rates, items in `ITEM_KEYS` order, address formats), a VAT
generator and validator in `identifiers.py`, and tests. Have a native speaker
review the labels and item names.

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).
