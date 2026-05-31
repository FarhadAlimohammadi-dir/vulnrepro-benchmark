# False Negative Verification Report - 2026-05-30

## Scope

This verifies vulnerable cases that multiple benchmarked models missed.

Models compared:

- `claude-opus-4-7`
- `claude-opus-4-8`
- `claude-sonnet-4-6`
- `gpt-5.5` with medium reasoning

## Overlap Counts

- Vulnerable cases: 119
- Missed by at least 2 models: 27
- Missed by at least 3 models: 25
- Missed by all 4 models: 18

## Runtime Exploit Verification

All 27 overlap false-negative cases were run in Docker and verified with their private exploit scripts.

Result:

```json
{
  "verified_cases": 27,
  "vulnerable_confirmed": 27,
  "failed": 0
}
```

## Files

- Overlap list: `false_negative_overlap.csv`
- All-model-missed exploit results: `all_model_missed_exploit_verification_rerun.csv`
- Multi-model-missed exploit results: `multi_model_missed_exploit_verification.csv`
- Exploit/compose logs:
  - `exploit_verification_logs/`
  - `multi_model_exploit_verification_logs/`

## Interpretation

These are not broken benchmark cases. They are valid vulnerable cases that current models often miss.

The misses cluster around:

- AI/prompt-injection chains where exploitability depends on second-order behavior.
- XSS chains that require browser/security-context reasoning.
- Business logic and auth bypasses where the vulnerable primitive is not a simple sink.
- Cloud/resource ownership and side-channel cases that are easy to underestimate from static source.

For the paper, these 27 cases are useful as a "hard false-negative subset." They show that high source-code access does not guarantee exploit-chain recognition.
