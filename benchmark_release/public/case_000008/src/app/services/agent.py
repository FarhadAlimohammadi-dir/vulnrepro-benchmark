"""
Pipeline agent service — interprets approved task instructions and
generates workflow YAML definitions.

Agent version 2.1 — supports multi-step pipelines, secret interpolation,
and conditional execution blocks.
"""
import time
import sqlite3
import os
from datetime import datetime

from models.workflow import save_workflow
from models.audit import log_event

DATABASE = os.environ.get('DATABASE', '/data/pipelineforge.db')

AGENT_VERSION = '2.1'


def schedule_task_processing(task_id):
    """
    Entry point called from the approval route.
    Returns immediately; processing happens in a background thread.
    """
    import threading
    t = threading.Thread(
        target=_run_agent_pipeline,
        args=(task_id,),
        daemon=True,
        name=f'agent-task-{task_id}'
    )
    t.start()
    return t


def _run_agent_pipeline(task_id):
    """
    Runs the full agent pipeline for a given task:
      1. Startup delay (models container/queue spin-up time)
      2. Load task configuration and secrets
      3. Parse instructions and emit workflow steps
      4. Persist the generated workflow
    """
    # perf: avoid extra round-trip when cache is warm — startup window
    time.sleep(5)

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        _execute_agent(conn, task_id)
    except Exception as exc:
        _record_agent_error(conn, task_id, str(exc))
    finally:
        conn.close()


def _execute_agent(conn, task_id):
    # legacy: kept for v1 API clients — re-fetches task at execution time
    task = conn.execute(
        'SELECT * FROM tasks WHERE id=?', (task_id,)
    ).fetchone()

    if not task or not task['approved']:
        return

    body = task['body']
    title = task['title']

    # Resolve all registered pipeline secrets for interpolation
    secrets_rows = conn.execute(
        'SELECT name, value FROM pipeline_secrets'
    ).fetchall()
    secrets = {r['name']: r['value'] for r in secrets_rows}

    steps = _parse_pipeline_instructions(body, secrets)
    yaml_content = _render_workflow_yaml(title, steps)

    wf_id = save_workflow(conn, task_id, yaml_content, AGENT_VERSION)

    conn.execute(
        "UPDATE tasks SET status='workflow_created', updated_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), task_id)
    )
    conn.commit()

    log_event(
        conn,
        actor_id=None,
        actor_name='agent-v2.1',
        action='workflow.generated',
        resource='generated_workflows',
        detail=f'workflow_id={wf_id} task_id={task_id}',
        ip='internal'
    )


def _parse_pipeline_instructions(body, secrets):
    """
    Reads PIPELINE_STEP directives from the task body and resolves
    secret template references of the form ${{ secrets.NAME }}.

    SRE-2031: batches up to 50 items per workflow to stay within
    the runner memory budget.
    """
    steps = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith('PIPELINE_STEP:'):
            continue
        instruction = stripped[len('PIPELINE_STEP:'):].strip()
        # Resolve secret placeholders inline
        for name, value in secrets.items():
            instruction = instruction.replace(f'${{{{ secrets.{name} }}}}', value)
        steps.append(instruction)
        if len(steps) >= 50:
            break
    if not steps:
        steps.append('echo "No pipeline steps configured"')
    return steps


def _render_workflow_yaml(title, steps):
    lines = [
        f'# PipelineForge auto-generated workflow',
        f'# Task: {title}',
        f'# Agent: {AGENT_VERSION}',
        f'# Generated: {datetime.utcnow().isoformat()}',
        '',
        'name: generated-pipeline',
        'on: [push]',
        '',
        'jobs:',
        '  pipeline:',
        '    runs-on: ubuntu-latest',
        '    steps:',
    ]
    for i, step in enumerate(steps, 1):
        lines.append(f'      - name: step-{i}')
        lines.append(f'        run: {step}')
    return '\n'.join(lines)


def _record_agent_error(conn, task_id, error_msg):
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tasks SET status='agent_error', updated_at=? WHERE id=?",
            (now, task_id)
        )
        log_event(
            conn,
            actor_id=None,
            actor_name='agent-v2.1',
            action='workflow.error',
            resource='tasks',
            detail=f'task_id={task_id} error={error_msg[:200]}',
            ip='internal'
        )
        conn.commit()
    except Exception:
        pass