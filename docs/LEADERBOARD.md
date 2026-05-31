# Leaderboard

All runs use the final 238-task blind benchmark: 119 vulnerable cases and 119 clean controls.

| Rank | Model | Balanced | Vulnerable Recall | True Negative | False Positive | Location | Type | CWE |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Claude Opus 4.7 | 63.4% | 77.3% | 49.6% | 50.4% | 74.0% | 61.3% | 47.9% |
| 2 | Claude Opus 4.8 | 58.0% | 78.1% | 37.8% | 62.2% | 75.6% | 58.8% | 45.4% |
| 3 | GPT-5.5 medium | 56.7% | 68.9% | 44.5% | 55.5% | 58.8% | 52.1% | 36.1% |
| 4 | Claude Sonnet 4.6 | 45.4% | 78.1% | 12.6% | 87.4% | 70.6% | 62.2% | 47.9% |

Balanced score is the mean of vulnerable recall and clean-control true-negative rate. A model that reports many vulnerabilities but false-positives on controls is penalized.
