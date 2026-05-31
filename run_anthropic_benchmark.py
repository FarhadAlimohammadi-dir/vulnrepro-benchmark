"""
run_anthropic_benchmark.py

All-in-one Anthropic API runner for the benchmark.

It runs cases one by one:
  1. builds model input from the generated prompt and public source files
  2. calls the Anthropic Messages API
  3. saves one JSON report per case
  4. optionally validates and scores the reports

It never sends private ground truth or exploit files to the model.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

import requests


ROOT = Path(__file__).parent.resolve()
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

DEFAULT_INCLUDE_EXTS = {
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".py",
    ".rb",
    ".go",
    ".java",
    ".php",
    ".cs",
    ".c",
    ".cpp",
    ".h",
    ".rs",
    ".html",
    ".ejs",
    ".jinja",
    ".j2",
    ".css",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".Dockerfile",
}

DEFAULT_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
}

DEPLOYMENT_CONTEXT_FILES = {
    ".env",
    ".env.example",
    "Dockerfile",
    "compose.yml",
    "compose.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def read_manifest(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def read_tasks_csv(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {row["case_id"]: row for row in csv.DictReader(fh)}


def load_case_list(path: Path) -> set[str]:
    cases: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            cases.add(value)
    return cases


def select_rows(rows: list[dict], args: argparse.Namespace, set_name: str, *, apply_limit: bool = True) -> list[dict]:
    selected = rows
    if args.case_list:
        wanted = load_case_list(args.case_list)
        if set_name == "controls":
            wanted = {cid if cid.endswith("_clean") else f"{cid}_clean" for cid in wanted}
        selected = [row for row in selected if row["case_id"] in wanted]
    if args.sample_per_category:
        rng = random.Random(args.seed)
        by_category: dict[str, list[dict]] = {}
        for row in selected:
            category = row.get("category") or row.get("original_category") or "uncategorized"
            by_category.setdefault(category, []).append(row)
        sampled: list[dict] = []
        for category in sorted(by_category):
            group = sorted(by_category[category], key=lambda r: r["case_id"])
            rng.shuffle(group)
            sampled.extend(group[: args.sample_per_category])
        selected = sorted(sampled, key=lambda r: r["case_id"])
    if apply_limit and args.limit:
        selected = selected[: args.limit]
    return selected


def write_manifest(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def should_include(path: Path, case_dir: Path, max_file_bytes: int, source_profile: str) -> bool:
    rel_parts = path.relative_to(case_dir).parts
    if any(part in DEFAULT_SKIP_DIRS for part in rel_parts):
        return False
    if not path.is_file():
        return False
    if source_profile == "app":
        name = path.name
        lower_name = name.lower()
        if name in DEPLOYMENT_CONTEXT_FILES or lower_name in DEPLOYMENT_CONTEXT_FILES:
            return False
        if lower_name.endswith(".compose.yml") or lower_name.endswith(".compose.yaml"):
            return False
    if path.name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}:
        return False
    if path.stat().st_size > max_file_bytes:
        return False
    if path.name == "Dockerfile":
        return True
    return path.suffix in DEFAULT_INCLUDE_EXTS


def collect_source_context(
    case_dir: Path,
    max_chars: int,
    max_file_bytes: int,
    source_profile: str,
) -> tuple[str, list[str]]:
    chunks: list[str] = []
    included: list[str] = []
    used = 0
    for path in sorted(case_dir.rglob("*")):
        if not should_include(path, case_dir, max_file_bytes, source_profile):
            continue
        rel = path.relative_to(case_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        block = f"\n\n--- FILE: {rel} ---\n{text}"
        if used + len(block) > max_chars:
            remaining = max_chars - used
            if remaining <= 200:
                break
            block = block[:remaining] + "\n[TRUNCATED]\n"
            chunks.append(block)
            included.append(rel)
            break
        chunks.append(block)
        included.append(rel)
        used += len(block)
    return "".join(chunks), included


def extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def call_anthropic(
    *,
    api_key: str,
    model: str,
    instructions: str,
    user_input: str,
    temperature: float,
    timeout: int,
) -> str:
    report_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "case_id": {"type": "string"},
            "verdict": {"type": "string", "enum": ["vulnerable", "no_vulnerability", "inconclusive"]},
            "findings": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "vulnerability_type": {"type": "string"},
                        "cwe": {"type": "string"},
                        "file": {"type": "string"},
                        "symbol": {"type": "string"},
                        "source": {"type": "string"},
                        "sink": {"type": "string"},
                        "attack_chain": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "explanation": {"type": "string"},
                        "fix": {"type": "string"},
                        "confidence": {"type": "string"},
                    },
                    "required": [
                        "vulnerability_type",
                        "cwe",
                        "file",
                        "symbol",
                        "explanation",
                        "fix",
                    ],
                },
            },
            "rejected_candidates": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "file": {"type": "string"},
                        "symbol": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
        },
        "required": ["case_id", "verdict", "findings"],
    }
    payload = {
        "model": model,
        "system": instructions,
        "messages": [{"role": "user", "content": user_input}],
        "max_tokens": 4096,
        "tools": [
            {
                "name": "submit_audit_report",
                "description": "Submit the final benchmark audit report as structured JSON.",
                "input_schema": report_schema,
            }
        ],
        "tool_choice": {"type": "tool", "name": "submit_audit_report"},
    }
    if temperature is not None:
        payload["temperature"] = temperature
    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
        body = resp.json()
    except requests.RequestException as exc:
        raise RuntimeError(f"request failed: {exc}") from exc
    for content in body.get("content", []):
        if content.get("type") == "tool_use" and content.get("name") == "submit_audit_report":
            return json.dumps(content.get("input", {}))
    texts: list[str] = []
    for content in body.get("content", []):
        if content.get("type") == "text":
            texts.append(content.get("text", ""))
    if texts:
        return "\n".join(texts)
    return json.dumps(body)


def validate_one_report(report: dict, expected_case_id: str) -> dict:
    if report.get("case_id") != expected_case_id:
        report["case_id"] = expected_case_id
    verdict = str(report.get("verdict", "") or "").strip().lower()
    if verdict not in {"vulnerable", "no_vulnerability", "inconclusive"}:
        verdict = "vulnerable" if report.get("findings") else "no_vulnerability"
    report["verdict"] = verdict
    rejected = report.get("rejected_candidates")
    if not isinstance(rejected, list):
        report["rejected_candidates"] = []
    findings = report.get("findings")
    if not isinstance(findings, list):
        report["findings"] = []
        return report
    normalized = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        item = dict(finding)
        for key in ["vulnerability_type", "cwe", "file", "symbol", "explanation", "fix"]:
            item[key] = str(item.get(key, ""))
        if "attack_chain" in item and not isinstance(item["attack_chain"], list):
            item["attack_chain"] = [str(item["attack_chain"])]
        if "confidence" in item:
            item["confidence"] = str(item["confidence"])
        normalized.append(item)
    report["findings"] = normalized
    return report


def run_cmd(cmd: list[str], cwd: Path) -> int:
    print(" ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(cwd))


def score_outputs(args: argparse.Namespace) -> int:
    if args.skip_score:
        return 0
    score_dir = args.run_dir / "scores"
    score_dir.mkdir(parents=True, exist_ok=True)
    py = sys.executable

    rc = 0
    vuln_manifest = args.run_dir / "vulnerable_manifest.jsonl"
    control_manifest = args.run_dir / "controls_manifest.jsonl"
    if vuln_manifest.exists():
        rc |= run_cmd(
            [
                py,
                "benchmark_eval_harness.py",
                "validate-reports",
                "--reports-dir",
                str(args.run_dir / "vulnerable_reports"),
                "--out-dir",
                str(args.run_dir / "validation_vulnerable"),
            ],
            ROOT,
        )
        rc |= run_cmd(
            [
                py,
                "score_ai_report.py",
                "--private-dir",
                "benchmark_release/private",
                "--manifest",
                str(vuln_manifest),
                "--reports-dir",
                str(args.run_dir / "vulnerable_reports"),
                "--out-dir",
                str(score_dir),
                "--prefix",
                "vulnerable",
            ],
            ROOT,
        )
    if control_manifest.exists():
        rc |= run_cmd(
            [
                py,
                "benchmark_eval_harness.py",
                "validate-reports",
                "--reports-dir",
                str(args.run_dir / "control_reports"),
                "--out-dir",
                str(args.run_dir / "validation_controls"),
            ],
            ROOT,
        )
        rc |= run_cmd(
            [
                py,
                "score_ai_report.py",
                "--private-dir",
                "benchmark_controls_release/private",
                "--manifest",
                str(control_manifest),
                "--reports-dir",
                str(args.run_dir / "control_reports"),
                "--out-dir",
                str(score_dir),
                "--prefix",
                "controls",
            ],
            ROOT,
        )
    if (score_dir / "vulnerable_aggregate.csv").exists() and (score_dir / "controls_aggregate.csv").exists():
        rc |= run_cmd(
            [
                py,
                "benchmark_eval_harness.py",
                "summarize-scores",
                "--vulnerable-csv",
                str(score_dir / "vulnerable_aggregate.csv"),
                "--control-csv",
                str(score_dir / "controls_aggregate.csv"),
                "--out-dir",
                str(score_dir),
                "--prefix",
                args.run_name,
            ],
            ROOT,
        )
        summary_path = score_dir / f"{args.run_name}_benchmark_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if not summary.get("complete", True):
                print(
                    "WARNING: run is incomplete; missing reports: "
                    f"vulnerable={summary.get('vulnerable_reports_missing', 0)} "
                    f"controls={summary.get('control_reports_missing', 0)}",
                    flush=True,
                )
    return rc


def build_audit_prompt(case_id: str) -> str:
    return f"""CASE_ID: {case_id}

Audit the following application source as a real-world vulnerability researcher.

Your objective is not to list every suspicious pattern. Your objective is to
identify the strongest concretely exploitable vulnerability chain, if one
exists. A valid finding needs a reachable source, a propagation/authorization
step when relevant, a sink or security boundary failure, attacker action, and
impact. Controls may be clean; false positives are heavily penalized.

Rules:
- Return JSON only. The required response format is json.
- Prefer one primary finding. Include at most three findings.
- Put the strongest end-to-end chain first.
- Do not include low-confidence, hypothetical, blocked, or non-exploitable
  candidates in findings. If the best candidate is not actually exploitable in
  the provided code, return an empty findings list.
- Use "verdict": "vulnerable" only when at least one finding is a concrete,
  reachable exploit chain in this exact app.
- Use "verdict": "no_vulnerability" when reviewed candidates are blocked,
  patched, dead code, unreachable, or best-practice-only. Put those reviewed
  but rejected ideas in rejected_candidates, not findings.
- Do not report generic hardcoded demo credentials, missing CSP, plaintext dev
  passwords, dependency concerns, or broad best-practice issues unless they are
  the core exploitable chain in this specific app.
- Do not report a finding only because a dangerous API exists. Explain how an
  attacker reaches it through this app's routes/data flow.
- If the issue is an AI/tool/agent bug, describe the complete tool chain and
  the trust boundary crossed.
- If you are not confident that an exploitable chain is reachable, return no
  findings.

Required output shape:
{{
  "case_id": "{case_id}",
  "verdict": "vulnerable",
  "findings": [
    {{
      "vulnerability_type": "short category, e.g. RCE, XSS, SSRF, IDOR, Prompt Injection, Business Logic",
      "cwe": "CWE-123",
      "file": "relative/path/to primary vulnerable file",
      "symbol": "primary route/function/class/handler",
      "source": "attacker-controlled input or starting route",
      "sink": "dangerous operation, disclosure point, or broken security boundary",
      "attack_chain": [
        "step 1",
        "step 2",
        "step 3"
      ],
      "explanation": "why this exact chain is reachable and exploitable",
      "fix": "specific remediation for the root cause",
      "confidence": "high|medium"
    }}
  ],
  "rejected_candidates": [
    {{
      "file": "relative/path/to/rejected/file",
      "symbol": "candidate function or route",
      "reason": "why this suspicious path is not a reachable exploit"
    }}
  ]
}}

If no exploitable issue is reachable, return exactly:
{{
  "case_id": "{case_id}",
  "verdict": "no_vulnerability",
  "findings": [],
  "rejected_candidates": []
}}
"""


def run_one_case(
    args: argparse.Namespace,
    *,
    set_name: str,
    index: int,
    total: int,
    prompt_case_id: str,
    real_case_id: str,
    case_dir: Path,
    out_path: Path,
    log_path: Path,
) -> bool:
    instructions = (
        "You are a security audit model. Return valid JSON only. "
        "Follow the requested schema exactly. Do not include markdown."
    )

    if args.start_after and prompt_case_id <= args.start_after:
        return False
    if out_path.exists() and not args.force:
        print(f"[{set_name} {index}/{total}] skip existing {prompt_case_id}", flush=True)
        return False
    if out_path.exists() and args.force:
        out_path.unlink()

    prompt = build_audit_prompt(prompt_case_id)
    source_context, included_files = collect_source_context(
        case_dir,
        max_chars=args.max_source_chars,
        max_file_bytes=args.max_file_bytes,
        source_profile=args.source_profile,
    )
    user_input = prompt + source_context
    print(
        f"[{set_name} {index}/{total}] {prompt_case_id} files={len(included_files)} chars={len(user_input)}",
        flush=True,
    )

    success = False
    error = ""
    recovered_errors: list[str] = []
    max_attempts = args.retries + 1
    for attempt in range(1, max_attempts + 1):
        try:
            if args.dry_run:
                report = {"case_id": prompt_case_id, "findings": []}
            else:
                raw = call_anthropic(
                    api_key=args.api_key,
                    model=args.model,
                    instructions=instructions,
                    user_input=user_input,
                    temperature=args.temperature,
                    timeout=args.timeout,
                )
                report = extract_json(raw)
            report = validate_one_report(report, prompt_case_id)
            out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            if error:
                recovered_errors.append(error)
                error = ""
            success = True
            break
        except (RuntimeError, urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            error = str(exc)
            if attempt < max_attempts:
                wait = args.retry_sleep * attempt
                print(f"  attempt {attempt} failed: {error[:300]}; sleep {wait}s", flush=True)
                time.sleep(wait)
            else:
                print(f"  attempt {attempt} failed: {error[:300]}; no retries left", flush=True)

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "prompt_case_id": prompt_case_id,
                    "real_case_id": real_case_id,
                    "set": set_name,
                    "source_profile": args.source_profile,
                    "success": success,
                    "report": str(out_path),
                    "included_files": included_files,
                    "error": error,
                    "recovered_errors": recovered_errors,
                },
                sort_keys=True,
            )
            + "\n"
        )
    if args.sleep:
        time.sleep(args.sleep)
    return success


def run_set(args: argparse.Namespace, *, set_name: str, public_dir: Path, manifest: Path, reports_dir: Path) -> None:
    rows = read_manifest(manifest)
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.run_dir / f"{set_name}_run_log.jsonl"

    selected = select_rows(rows, args, set_name)
    write_manifest(args.run_dir / f"{set_name}_manifest.jsonl", selected)

    new_attempts = 0
    for index, row in enumerate(selected, start=1):
        case_id = row["case_id"]
        out_path = reports_dir / f"{case_id}.json"
        will_attempt = args.force or not out_path.exists()
        if will_attempt and args.max_new_reports and new_attempts >= args.max_new_reports:
            break
        if will_attempt:
            new_attempts += 1
        run_one_case(
            args,
            set_name=set_name,
            index=index,
            total=len(selected),
            prompt_case_id=case_id,
            real_case_id=case_id,
            case_dir=public_dir / case_id,
            out_path=out_path,
            log_path=log_path,
        )


def load_mapping(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def create_blind_mapping(args: argparse.Namespace) -> list[dict]:
    rng = random.Random(args.seed)
    combined: list[dict] = []

    if args.set in {"vulnerable", "both"}:
        rows = select_rows(
            read_manifest(ROOT / "benchmark_release" / "benchmark_manifest.jsonl"),
            args,
            "vulnerable",
            apply_limit=False,
        )
        combined.extend({"real_case_id": row["case_id"], "set": "vulnerable"} for row in rows)

    if args.set in {"controls", "both"}:
        rows = select_rows(
            read_manifest(ROOT / "benchmark_controls_release" / "benchmark_controls_manifest.jsonl"),
            args,
            "controls",
            apply_limit=False,
        )
        combined.extend({"real_case_id": row["case_id"], "set": "controls"} for row in rows)

    combined = sorted(combined, key=lambda item: (item["set"], item["real_case_id"]))
    rng.shuffle(combined)
    if args.limit:
        combined = combined[: args.limit]

    mapping: list[dict] = []
    for index, item in enumerate(combined, start=1):
        mapping.append(
            {
                "eval_id": f"eval_{index:06d}",
                "real_case_id": item["real_case_id"],
                "set": item["set"],
            }
        )
    return mapping


def load_or_create_blind_mapping(args: argparse.Namespace) -> list[dict]:
    mapping_path = args.run_dir / "blind_mapping_private.jsonl"
    if args.force_remap and mapping_path.exists():
        for rel in [
            "blind_mapping_private.jsonl",
            "blind_tasks_model_facing.jsonl",
            "vulnerable_manifest.jsonl",
            "controls_manifest.jsonl",
            "blind_translation_summary.json",
        ]:
            path = args.run_dir / rel
            if path.exists():
                path.unlink()
        print(f"replacing blind mapping in {args.run_dir}", flush=True)
    mapping = load_mapping(mapping_path)
    if mapping:
        if args.limit and len(mapping) != args.limit:
            print(
                f"ERROR: existing blind mapping has {len(mapping)} cases, but --limit {args.limit} was requested. "
                "Use a fresh --run-dir/--run-name, omit --limit to resume this run, or pass --force-remap to replace the mapping.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        print(f"using existing blind mapping: {mapping_path}", flush=True)
        return mapping

    mapping = create_blind_mapping(args)
    mapping_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping),
        encoding="utf-8",
    )
    public_tasks_path = args.run_dir / "blind_tasks_model_facing.jsonl"
    public_tasks_path.write_text(
        "".join(json.dumps({"eval_id": row["eval_id"]}, sort_keys=True) + "\n" for row in mapping),
        encoding="utf-8",
    )
    print(f"wrote private blind mapping: {mapping_path}", flush=True)
    print(f"wrote model-facing task list: {public_tasks_path}", flush=True)
    return mapping


def write_blind_manifests(args: argparse.Namespace, mapping: list[dict]) -> None:
    vuln_rows_by_id = {
        row["case_id"]: row
        for row in read_manifest(ROOT / "benchmark_release" / "benchmark_manifest.jsonl")
    }
    control_rows_by_id = {
        row["case_id"]: row
        for row in read_manifest(ROOT / "benchmark_controls_release" / "benchmark_controls_manifest.jsonl")
    }

    vuln_rows = [
        vuln_rows_by_id[item["real_case_id"]]
        for item in mapping
        if item["set"] == "vulnerable" and item["real_case_id"] in vuln_rows_by_id
    ]
    control_rows = [
        control_rows_by_id[item["real_case_id"]]
        for item in mapping
        if item["set"] == "controls" and item["real_case_id"] in control_rows_by_id
    ]
    if vuln_rows:
        write_manifest(args.run_dir / "vulnerable_manifest.jsonl", vuln_rows)
    elif (args.run_dir / "vulnerable_manifest.jsonl").exists():
        (args.run_dir / "vulnerable_manifest.jsonl").unlink()
    if control_rows:
        write_manifest(args.run_dir / "controls_manifest.jsonl", control_rows)
    elif (args.run_dir / "controls_manifest.jsonl").exists():
        (args.run_dir / "controls_manifest.jsonl").unlink()


def translate_blind_reports(args: argparse.Namespace, mapping: list[dict]) -> None:
    raw_dir = args.run_dir / "blind_reports"
    vuln_dir = args.run_dir / "vulnerable_reports"
    control_dir = args.run_dir / "control_reports"
    vuln_dir.mkdir(parents=True, exist_ok=True)
    control_dir.mkdir(parents=True, exist_ok=True)

    translated = 0
    missing = 0
    invalid = 0
    for item in mapping:
        raw_path = raw_dir / f"{item['eval_id']}.json"
        if not raw_path.exists():
            missing += 1
            continue
        try:
            raw_report = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        except Exception:
            invalid += 1
            continue
        raw_report = validate_one_report(raw_report, item["eval_id"])
        report = dict(raw_report)
        report["case_id"] = item["real_case_id"]
        out_dir = vuln_dir if item["set"] == "vulnerable" else control_dir
        out_path = out_dir / f"{item['real_case_id']}.json"
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        translated += 1

    summary = {"translated": translated, "missing": missing, "invalid": invalid}
    (args.run_dir / "blind_translation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"blind_translation": summary}, sort_keys=True), flush=True)


def run_blind(args: argparse.Namespace) -> None:
    mapping = load_or_create_blind_mapping(args)
    write_blind_manifests(args, mapping)

    execution_mapping = mapping
    if args.case_list:
        wanted = load_case_list(args.case_list)
        execution_mapping = [
            item
            for item in mapping
            if item["eval_id"] in wanted or item["real_case_id"] in wanted
        ]
        if not execution_mapping:
            print(
                f"ERROR: --case-list matched no blind eval IDs or real case IDs: {args.case_list}",
                file=sys.stderr,
            )
            raise SystemExit(2)

    raw_reports_dir = args.run_dir / "blind_reports"
    raw_reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.run_dir / "blind_run_log_private.jsonl"

    new_attempts = 0
    total = len(mapping)
    for item in execution_mapping:
        index = int(item["eval_id"].rsplit("_", 1)[-1]) if item["eval_id"].startswith("eval_") else 0
        public_root = (
            ROOT / "benchmark_release" / "public"
            if item["set"] == "vulnerable"
            else ROOT / "benchmark_controls_release" / "public"
        )
        out_path = raw_reports_dir / f"{item['eval_id']}.json"
        will_attempt = args.force or not out_path.exists()
        if will_attempt and args.max_new_reports and new_attempts >= args.max_new_reports:
            break
        if will_attempt:
            new_attempts += 1
        run_one_case(
            args,
            set_name="blind",
            index=index,
            total=total,
            prompt_case_id=item["eval_id"],
            real_case_id=item["real_case_id"],
            case_dir=public_root / item["real_case_id"],
            out_path=out_path,
            log_path=log_path,
        )

    translate_blind_reports(args, mapping)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="anthropic_run")
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs" / "anthropic_run")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY", ""))
    parser.add_argument("--set", choices=["vulnerable", "controls", "both"], default="both")
    parser.add_argument("--blind", action="store_true", help="shuffle selected cases and show opaque eval IDs to the model")
    parser.add_argument("--limit", type=int, default=0, help="run first N cases per selected set; with --blind, run N total shuffled cases")
    parser.add_argument("--case-list", type=Path, default=None, help="newline-delimited case IDs to run")
    parser.add_argument("--sample-per-category", type=int, default=0, help="sample N cases per manifest category")
    parser.add_argument("--seed", type=int, default=1337, help="sampling seed")
    parser.add_argument("--start-after", default="", help="resume after this case id")
    parser.add_argument("--force", action="store_true", help="overwrite existing reports")
    parser.add_argument("--force-remap", action="store_true", help="with --blind, replace any existing private mapping in the run directory")
    parser.add_argument("--max-new-reports", type=int, default=0, help="stop after attempting this many new reports; useful for one-at-a-time blind audits")
    parser.add_argument("--dry-run", action="store_true", help="write empty reports without API calls")
    parser.add_argument("--skip-score", action="store_true")
    parser.add_argument("--max-source-chars", type=int, default=180_000)
    parser.add_argument("--max-file-bytes", type=int, default=250_000)
    parser.add_argument(
        "--source-profile",
        choices=["app", "full"],
        default="app",
        help=(
            "app excludes Docker/deployment/env files from model context; "
            "full includes every supported source/config file. Use full only "
            "for a deployment-aware benchmark track."
        ),
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.5, help="pause between cases")
    args = parser.parse_args(list(argv) if argv is not None else None)

    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)

    if not args.dry_run and not args.api_key:
        print("ANTHROPIC_API_KEY is required unless --dry-run is used", file=sys.stderr)
        return 2

    if args.blind:
        run_blind(args)
        return score_outputs(args)

    if args.set in {"vulnerable", "both"}:
        run_set(
            args,
            set_name="vulnerable",
            public_dir=ROOT / "benchmark_release" / "public",
            manifest=ROOT / "benchmark_release" / "benchmark_manifest.jsonl",
            reports_dir=args.run_dir / "vulnerable_reports",
        )
    if args.set in {"controls", "both"}:
        run_set(
            args,
            set_name="controls",
            public_dir=ROOT / "benchmark_controls_release" / "public",
            manifest=ROOT / "benchmark_controls_release" / "benchmark_controls_manifest.jsonl",
            reports_dir=args.run_dir / "control_reports",
        )
    return score_outputs(args)


if __name__ == "__main__":
    raise SystemExit(main())
