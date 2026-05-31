# Dataset Card

## Name

VulnRepro Research Benchmark

## Version

Research-grade frozen release, 2026-05-30.

## Task

Blind source-code vulnerability detection.

The model receives public source code and must decide whether the application contains a reportable vulnerability. It must identify the vulnerability class, file, location/symbol, exploit chain, and fix. Clean controls are included to measure false positives.

## Dataset Size

| Split | Count |
|---|---:|
| Vulnerable applications | 119 |
| Clean controls | 119 |
| Blind tasks | 238 |

## Source

Cases were derived from real-world vulnerability writeups and converted into small-to-medium runnable Docker applications. Model-facing package names are anonymized with opaque IDs during blind evaluation.

## Labels and Scoring Assets

Private labels include:

- vulnerability type,
- CWE,
- vulnerable files,
- source/sink/primitive metadata,
- exploit scripts,
- patch/control references,
- source writeup metadata.

These are private scoring assets and should not be sent to models.

## Intended Use

Use this dataset to evaluate:

- vulnerability detection recall,
- false-positive behavior on clean controls,
- chain reasoning through realistic code,
- file/location/type/CWE precision,
- security-agent prompt quality,
- model regressions across versions.

## Out-of-Scope Use

This dataset is not designed as:

- a black-box web CTF benchmark,
- a pure exploit-generation benchmark,
- a production exploit toolkit,
- a replacement for manual application security review.

## Model-Facing Input

The benchmark runner sends source files from public packages. It does not send private ground truth, source writeup titles, original category paths, exploits, or patches.

## Quality Checks

Final static audit:

```json
{
  "cases": 119,
  "pass": 119,
  "warn": 0,
  "fail": 0
}
```

Hard false-negative subset:

```json
{
  "missed_by_2_or_more_models": 27,
  "docker_exploit_confirmed": 27,
  "failed_verification": 0
}
```

## Known Limitations

- Applications are compact reproductions, not full production systems.
- Scoring depends on matching private ground truth, so semantically correct but differently phrased reports may require scorer improvements.
- API nondeterminism can change individual reports across reruns.
- The benchmark measures source audit behavior, not full agentic exploitation from a remote URL.
- Some cases are labeled by source category, while the actual primitive may be different. For example, an AI-product case may actually test XSS, IDOR, SSRF, or secret disclosure.

## Safety

The private folder contains exploit scripts. Use an isolated local environment. Do not deploy vulnerable apps to public networks.
