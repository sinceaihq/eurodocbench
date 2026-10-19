# Security Policy

## Reporting a vulnerability

**Use GitHub's private vulnerability reporting:**
**[Report a vulnerability](https://github.com/sinceaihq/eurodocbench/security/advisories/new)**

If GitHub reporting is unavailable to you, email **builders@sinceai.fi**.
Please do not open a public issue for a suspected vulnerability.

We aim to acknowledge reports within a few working days. EuroDocBench is
maintained by a small team, so we do not promise a fixed remediation deadline.

## Scope

- **Real identifiers in the data.** Every VAT number and IBAN in the dataset
  is meant to fail its national checksum. If you find one that validates, or
  any data that identifies a real company or person, report it here.
- **Scorer integrity.** Inputs that make the scorer crash, hang, or award
  credit for a wrong answer.
- **Supply chain.** Problems in how the package and dataset are built or
  published.
