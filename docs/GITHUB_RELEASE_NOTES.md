# GitHub Release Notes

## v0.1 Research-Grade Release

This release freezes the VulnRepro source-code vulnerability detection benchmark.

## Highlights

- 119 exploit-confirmed vulnerable applications.
- 119 paired clean controls.
- 238 blind model-facing tasks.
- Public/private split for honest evaluation.
- Opaque blind IDs to avoid leaking category or writeup hints.
- Static quality audit passed with 119/119 pass, 0 warnings, 0 failures.
- Four full 238-task model runs included.
- Verified hard false-negative subset: 27/27 multi-model missed cases confirmed vulnerable by Docker/private exploit reruns.

## Benchmark Type

This is a **source-code vulnerability detection benchmark**.

It is not primarily an exploit-generation benchmark. Exploit scripts are private validation and scoring assets. Models receive only public source packages during evaluation.

## Current Leaderboard

| Rank | Model | Balanced | Vulnerable Recall | True Negative | False Positive |
|---:|---|---:|---:|---:|---:|
| 1 | Claude Opus 4.7 | 63.4% | 77.3% | 49.6% | 50.4% |
| 2 | Claude Opus 4.8 | 58.0% | 78.1% | 37.8% | 62.2% |
| 3 | GPT-5.5 medium | 56.7% | 68.9% | 44.5% | 55.5% |
| 4 | Claude Sonnet 4.6 | 45.4% | 78.1% | 12.6% | 87.4% |

Balanced score is the mean of vulnerable recall and clean-control true-negative rate.

## Included Artifacts

- `benchmark_release/public/`
- `benchmark_release/private/`
- `benchmark_controls_release/public/`
- `benchmark_controls_release/private/`
- `benchmark_manifest.jsonl`
- `docs/`
- `assets/`
- `runs/`
- `analysis_false_negatives_20260530/`
- scoring and runner scripts

## Recommended Release Description

```text
VulnRepro v0.1 freezes a 238-task blind source-code vulnerability detection benchmark built from real-world vulnerability writeups. It includes 119 exploit-confirmed vulnerable Docker apps and 119 paired clean controls, with private scoring assets separated from model-facing source packages.

This release includes full benchmark results for Claude Opus 4.7, Claude Opus 4.8, Claude Sonnet 4.6, and GPT-5.5 medium. The current best balanced score is Claude Opus 4.7 at 63.4%. The results show that frontier models can find many vulnerabilities but still struggle with false positives and multi-step exploit chains.

Private exploit scripts are included for local validation and scoring only. Do not expose vulnerable containers to public networks.
```

## Safety Note

This repository contains intentionally vulnerable applications and private exploit scripts. Run only in isolated local Docker environments.
