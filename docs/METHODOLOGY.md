# Methodology

## Benchmark Type

This benchmark measures **source-code vulnerability detection**.

It does not primarily measure autonomous exploitation. The private exploit scripts are used to verify vulnerable cases and to support benchmark quality control. Models are evaluated from public source packages only.

## Evaluation Modes

### Blind Detection

Blind mode shuffles vulnerable and clean cases together and replaces real case IDs with opaque IDs:

```text
eval_000001
eval_000002
...
```

The model is not told whether a case is vulnerable or clean. This supports both recall and false-positive measurement.

### Source Profile

The default `app` source profile includes application-relevant code and excludes deployment noise where possible. Docker files are still available in public packages for local reproduction, but the model prompt focuses on application source.

## Public and Private Assets

Model-facing assets:

```text
benchmark_release/public/
benchmark_controls_release/public/
```

Private scoring assets:

```text
benchmark_release/private/
benchmark_controls_release/private/
```

Private assets include:

- `ground_truth.json`
- exploit scripts
- source metadata
- patch notes

They must not be sent to models during evaluation.

## Report Schema

Models return JSON:

```json
{
  "case_id": "eval_000001",
  "verdict": "vulnerable",
  "findings": [
    {
      "vulnerability_type": "XSS",
      "cwe": "CWE-79",
      "file": "src/app/routes/example.js",
      "symbol": "handler",
      "explanation": "Attacker-controlled input reaches HTML without escaping.",
      "fix": "Escape or sanitize before rendering."
    }
  ],
  "rejected_candidates": []
}
```

For clean controls, the expected verdict is:

```json
{
  "verdict": "no_vulnerability",
  "findings": []
}
```

## Scoring

Primary metrics:

- **Vulnerable recall:** fraction of vulnerable cases detected.
- **Control true-negative rate:** fraction of clean controls where the model stays quiet.
- **Control false-positive rate:** fraction of clean controls where the model reports a vulnerability.
- **Balanced detection score:** mean of vulnerable recall and control true-negative rate.

Secondary metrics:

- CWE match
- vulnerability type match
- file match
- symbol/location match
- explanation and fix presence

Balanced score is emphasized because recall alone rewards noisy models that flag everything.

## Quality Control

The final package passes static quality audit:

```json
{
  "cases": 119,
  "pass": 119,
  "warn": 0,
  "fail": 0
}
```

The multi-model false-negative subset was also runtime checked:

```json
{
  "verified_cases": 27,
  "vulnerable_confirmed": 27,
  "failed": 0
}
```

## Interpretation

The benchmark is designed to test practical audit behavior:

- finding real bugs,
- rejecting clean code,
- recognizing multi-step chains,
- reasoning about browser, tenant, cloud, and AI-specific security semantics.

It is not enough for a model to identify a suspicious line. The report must identify the exploitable vulnerability class and location well enough to match private ground truth.
