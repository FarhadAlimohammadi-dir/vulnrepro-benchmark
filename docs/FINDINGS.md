# Findings

## Headline

This benchmark measures **source-code vulnerability detection under blind conditions**. It is not a pure exploit-generation benchmark.

The strongest models found many vulnerable cases, but no model reached strong production-grade precision. The main failure is not just missing bugs. It is the combination of:

- missed multi-step exploit chains,
- high false-positive rates on clean controls,
- weak CWE/type precision,
- confusion when the real primitive is hidden behind AI, browser, cloud, tenant, or integration semantics.

## Leaderboard Summary

| Model | Balanced | Vulnerable Recall | True Negative | False Positive | Location | Type | CWE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Opus 4.7 | 63.4% | 77.3% | 49.6% | 50.4% | 74.0% | 61.3% | 47.9% |
| Claude Opus 4.8 | 58.0% | 78.1% | 37.8% | 62.2% | 75.6% | 58.8% | 45.4% |
| GPT-5.5 medium | 56.7% | 68.9% | 44.5% | 55.5% | 58.8% | 52.1% | 36.1% |
| Claude Sonnet 4.6 | 45.4% | 78.1% | 12.6% | 87.4% | 70.6% | 62.2% | 47.9% |

Balanced score is the mean of vulnerable recall and clean-control true-negative rate.

## Interpretation

Claude Opus 4.7 has the best balanced score because it combines high vulnerable recall with the best control behavior in this run.

Claude Opus 4.8 has slightly higher vulnerable recall and location matching than Opus 4.7, but it flags more clean controls, lowering its balanced score.

GPT-5.5 medium is more conservative than Sonnet 4.6 but misses more vulnerable cases and has weaker location/CWE matching.

Claude Sonnet 4.6 has high recall, but the false-positive rate on controls is too high for a practical security-triage benchmark.

## Why Controls Matter

Without controls, a model can appear strong by reporting a vulnerability in every app. The paired clean controls make that strategy visible.

The current results show that false positives are a major differentiator:

| Model | False Positive Rate |
|---|---:|
| Claude Opus 4.7 | 50.4% |
| GPT-5.5 medium | 55.5% |
| Claude Opus 4.8 | 62.2% |
| Claude Sonnet 4.6 | 87.4% |

This means the benchmark is useful for measuring practical audit behavior, not only vulnerability recall.

## Verified Hard Cases

The false-negative overlap analysis found:

```json
{
  "missed_by_2_or_more": 27,
  "missed_by_3_or_more": 25,
  "missed_by_all_models": 18
}
```

All 27 cases missed by at least two models were rechecked with Docker and private exploits. All 27 were confirmed vulnerable.

The strongest hard-case patterns are:

- AI-product flows where the actual primitive is XSS, IDOR, prompt injection, data exposure, or command injection.
- Browser semantics such as DOM clobbering, extension trust chains, MIME sniffing, XSSI, and self-XSS escalation.
- Cloud or integration lifecycle issues such as bucket ownership confusion and trusted-response SSRF.
- Tenant and authorization chains where a user-controlled identity or token changes server trust.
- Business logic and timing issues where there is no obvious single dangerous sink.

See:

- [MODEL_FALSE_NEGATIVE_WEAKNESS_ANALYSIS.md](../analysis_false_negatives_20260530/MODEL_FALSE_NEGATIVE_WEAKNESS_ANALYSIS.md)
- [ACTUAL_WEAKNESS_PATTERNS_FOR_MODEL_MISSES.md](../analysis_false_negatives_20260530/ACTUAL_WEAKNESS_PATTERNS_FOR_MODEL_MISSES.md)
- [FALSE_NEGATIVE_VERIFICATION_REPORT.md](../analysis_false_negatives_20260530/FALSE_NEGATIVE_VERIFICATION_REPORT.md)

## What This Benchmark Is Good For

This benchmark is useful for:

- comparing vulnerability detection models,
- measuring recall and false positives together,
- testing whether models can follow exploit chains through realistic application code,
- evaluating security-agent prompts and report schemas,
- studying which vulnerability patterns remain hard for frontier models.

It is not intended to measure:

- fully autonomous bug bounty performance,
- network-only black-box exploitation,
- CTF speed,
- exploit payload creativity as the primary metric.

## Research Takeaway

The benchmark suggests that current models can often identify suspicious code, but still struggle to decide whether the issue is truly exploitable and whether clean code should be left alone. For real security work, precision on controls is as important as recall on vulnerable cases.
