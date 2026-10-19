# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/). Dataset
releases are versioned with the package that generated them.

## [0.1.0] - 2026-10-19

First public release.

### Added
- Generator for single-page invoices in 12 European locales and five layouts,
  with simulated scans; deterministic per document id and seed.
- Dataset v0.1: 240 dev and 1,200 test documents (seed 2026), published on
  the Hugging Face Hub with PDFs, scans, text layers and ground truth.
- Scorer (`eurodocbench-score`), standard library only.
- Baselines: keyword/regex rules, EasyOCR for the scan track, and a zero-shot
  Qwen2.5-1.5B-Instruct (llama.cpp, CPU) extractor.
