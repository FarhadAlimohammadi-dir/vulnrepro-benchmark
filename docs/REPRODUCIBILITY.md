# Reproducibility

## Requirements

- Windows, Linux, or macOS shell.
- Python 3.11 or newer.
- Docker Desktop for runtime exploit verification.
- API key for the provider being evaluated.

Environment variables:

```powershell
$env:OPENAI_API_KEY="..."
$env:ANTHROPIC_API_KEY="..."
```

Do not commit API keys or run logs containing secrets.

## Benchmark Type

This is a source-code vulnerability detection benchmark. The model receives public source code only. Private exploit scripts and ground truth are used for validation and scoring.

## Public Inputs

Model-facing packages:

```text
benchmark_release/public/
benchmark_controls_release/public/
```

This public repository intentionally excludes private scoring assets. Public users can inspect and run the model-facing applications, while maintainers should use the separate private research archive for ground-truth scoring and exploit validation.

Private scoring assets:

```text
benchmark_release/private/
benchmark_controls_release/private/
```

The private directories must not be included in model prompts.

## Recommended Full Blind Runs

OpenAI example:

```powershell
python .\run_openai_benchmark.py `
  --run-name gpt55_medium_research_grade_238_blind_20260529 `
  --run-dir runs\gpt55_medium_research_grade_238_blind_20260529 `
  --model gpt-5.5 `
  --reasoning-effort medium `
  --set both `
  --blind `
  --seed 20260529 `
  --limit 238 `
  --retries 4 `
  --retry-sleep 15 `
  --timeout 240 `
  --sleep 1
```

Anthropic example:

```powershell
python .\run_anthropic_benchmark.py `
  --run-name opus48_research_grade_238_blind_20260529 `
  --run-dir runs\opus48_research_grade_238_blind_20260529 `
  --model claude-opus-4-8 `
  --set both `
  --blind `
  --seed 20260529 `
  --limit 238 `
  --retries 4 `
  --retry-sleep 15 `
  --timeout 240 `
  --sleep 1
```

## Smoke Run

Use this before spending money on a full run:

```powershell
python .\run_openai_benchmark.py `
  --run-name smoke_10 `
  --run-dir runs\smoke_10 `
  --model gpt-5.5 `
  --reasoning-effort medium `
  --set both `
  --blind `
  --seed 123 `
  --limit 10 `
  --retries 2 `
  --timeout 180
```

## Resume and Retry

The runner preserves existing reports by default. If a connection fails, rerun the same command without `--force`; completed reports are skipped and missing reports are retried.

Use `--force` only when you intentionally want to overwrite existing reports.

Use `--force-remap` only when you intentionally want a new blind mapping. For comparable research runs, keep the same seed and mapping.

For one-at-a-time retry behavior:

```powershell
python .\run_openai_benchmark.py `
  --run-name gpt55_medium_research_grade_238_blind_20260529 `
  --run-dir runs\gpt55_medium_research_grade_238_blind_20260529 `
  --model gpt-5.5 `
  --reasoning-effort medium `
  --set both `
  --blind `
  --seed 20260529 `
  --limit 238 `
  --max-new-reports 1 `
  --retries 4 `
  --retry-sleep 15 `
  --timeout 240
```

## Score Existing Reports

The run scripts score automatically unless `--skip-score` is used. To manually score reports:

```powershell
python .\score_ai_report.py `
  --private-dir benchmark_release/private `
  --manifest runs\<run_name>\vulnerable_manifest.jsonl `
  --reports-dir runs\<run_name>\vulnerable_reports `
  --out-dir runs\<run_name>\scores `
  --prefix vulnerable
```

For controls:

```powershell
python .\score_ai_report.py `
  --private-dir benchmark_controls_release/private `
  --manifest runs\<run_name>\controls_manifest.jsonl `
  --reports-dir runs\<run_name>\control_reports `
  --out-dir runs\<run_name>\scores `
  --prefix controls
```

Then summarize:

```powershell
python .\benchmark_eval_harness.py summarize-scores `
  --vulnerable-csv runs\<run_name>\scores\vulnerable_aggregate.csv `
  --control-csv runs\<run_name>\scores\controls_aggregate.csv `
  --out-dir runs\<run_name>\scores `
  --prefix <run_name>
```

## Regenerate Release Charts

```powershell
python .\tools\generate_release_assets.py
```

This writes:

- `assets/*.svg`
- `docs/leaderboard.csv`
- `docs/LEADERBOARD.md`
- `release_manifest_20260530.json`

## Verify Package Quality

```powershell
python .\full_benchmark_quality_audit.py
```

The frozen package used for this release passed:

```json
{
  "cases": 119,
  "pass": 119,
  "warn": 0,
  "fail": 0
}
```

## Safety

The benchmark contains intentionally vulnerable applications and private exploit scripts. Run only in isolated local Docker environments. Do not expose benchmark containers to public networks.
