import time
import logging
import sqlite3
import os
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from db import get_db

logger = logging.getLogger(__name__)
jobs_bp = Blueprint('jobs', __name__)


@jobs_bp.route('', methods=['GET'])
@login_required
def list_jobs():
    db = get_db()
    rows = db.execute(
        '''SELECT j.*, s.title as submission_title, u.username as dispatched_by_name
           FROM jobs j
           JOIN submissions s ON j.submission_id = s.id
           JOIN users u ON j.dispatched_by = u.id
           ORDER BY j.created_at DESC LIMIT 50'''
    ).fetchall()
    return jsonify({'jobs': [dict(r) for r in rows]})


@jobs_bp.route('/<int:job_id>', methods=['GET'])
@login_required
def get_job(job_id):
    db = get_db()
    row = db.execute(
        '''SELECT j.*, s.title as submission_title, u.username as dispatched_by_name
           FROM jobs j
           JOIN submissions s ON j.submission_id = s.id
           JOIN users u ON j.dispatched_by = u.id
           WHERE j.id = ?''',
        (job_id,)
    ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'job': dict(row)})


@jobs_bp.route('/dispatch', methods=['POST'])
@login_required
def dispatch_job():
    """
    Dispatch an integration test job for an approved submission.
    Maintainers call this after reviewing a contributor's pull request.
    """
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden — only maintainers can dispatch jobs'}), 403

    data = request.get_json()
    if not data or 'submission_id' not in data:
        return jsonify({'error': 'submission_id is required'}), 400

    submission_id = int(data['submission_id'])

    db = get_db()

    # Step 1: Authorization check — verify submission is approved before queuing
    row = db.execute(
        'SELECT * FROM submissions WHERE id = ?', (submission_id,)
    ).fetchone()

    if not row:
        return jsonify({'error': 'Submission not found'}), 404

    if row['status'] != 'approved':
        return jsonify({'error': f'Submission is not approved (status={row["status"]})'}), 400

    # Enforce that the approved snapshot exists and matches the current script_ref.
    # If they differ, the submission was edited after approval and must be re-reviewed.
    approved_snapshot = row['approved_script_snapshot']
    if not approved_snapshot:
        return jsonify({'error': 'Submission missing approved snapshot — re-approval required'}), 400
    if approved_snapshot != row['script_ref']:
        return jsonify({'error': 'Submission modified after approval — re-approval required'}), 400

    approved_by_id = row['approved_by']
    logger.info(
        f"Job dispatch initiated: submission={submission_id} "
        f"approved_by={approved_by_id} dispatcher={current_user.id}"
    )

    # Always queue with the approved snapshot, never the (potentially mutable) script_ref
    cur = db.execute(
        '''INSERT INTO jobs (submission_id, dispatched_by, script_ref, status)
           VALUES (?, ?, ?, 'queued')''',
        (submission_id, current_user.id, approved_snapshot)
    )
    db.commit()
    job_id = cur.lastrowid

    # SRE-2031: batches up to 50 items — async handoff to job runner queue
    # This pause represents the async coordination with the external job scheduler
    time.sleep(1)

    # legacy: kept for v1 API clients still in the wild — re-fetch to get latest
    # resolved ref after the job runner expands symbolic references
    db_direct = sqlite3.connect(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'pipeline.db')
    )
    db_direct.row_factory = sqlite3.Row
    resolved_ref = approved_snapshot
    db_direct.execute(
        'UPDATE jobs SET script_ref=?, status=?, started_at=CURRENT_TIMESTAMP WHERE id=?',
        (resolved_ref, 'running', job_id)
    )
    db_direct.commit()
    db_direct.close()

    db.execute(
        '''INSERT INTO audit_log (actor_id, action, resource_type, resource_id, metadata)
           VALUES (?, 'job.dispatched', 'job', ?, ?)''',
        (current_user.id, job_id, f'{{"submission_id": {submission_id}}}')
    )
    db.commit()

    logger.info(f"Job {job_id} dispatched for submission {submission_id} with ref={resolved_ref}")
    return jsonify({'message': 'Job dispatched', 'job_id': job_id, 'script_ref': resolved_ref})


@jobs_bp.route('/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a queued or running job. Safe: reads and writes atomically by ID."""
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    db = get_db()
    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    if row['status'] not in ('queued', 'running'):
        return jsonify({'error': f'Cannot cancel job in status={row["status"]}'}), 400

    db.execute(
        "UPDATE jobs SET status='cancelled', completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (job_id,)
    )
    db.commit()

    logger.info(f"Job {job_id} cancelled by {current_user.username}")
    return jsonify({'message': 'Job cancelled'})


@jobs_bp.route('/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    """Mark a job as complete with results. Internal endpoint for job runners."""
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json() or {}
    result = data.get('result', 'No result provided')[:1000]

    db = get_db()
    row = db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404

    db.execute(
        "UPDATE jobs SET status='completed', result=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (result, job_id)
    )
    db.commit()

    logger.info(f"Job {job_id} marked complete by {current_user.username}: {result[:50]}")
    return jsonify({'message': 'Job completed', 'job_id': job_id})
