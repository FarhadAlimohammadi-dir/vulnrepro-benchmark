"""
Input validation helpers used across API routes.
"""
import re

ALLOWED_LABELS = {'bug', 'feature', 'docs', 'refactor', 'security-review', 'performance'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}
ALLOWED_STATUSES = {'open', 'approved', 'workflow_created', 'closed', 'cancelled', 'agent_error'}

SECRET_NAME_RE = re.compile(r'^[A-Z][A-Z0-9_]{1,63}$')


def validate_task_input(data):
    errors = []
    title = data.get('title', '').strip()
    body = data.get('body', '').strip()
    if not title:
        errors.append('Title is required')
    elif len(title) > 200:
        errors.append('Title must be 200 characters or fewer')
    if len(body) > 20000:
        errors.append('Body must be 20,000 characters or fewer')
    priority = data.get('priority', 'medium')
    if priority not in ALLOWED_PRIORITIES:
        errors.append(f'Priority must be one of: {", ".join(ALLOWED_PRIORITIES)}')
    return errors


def validate_secret_name(name):
    return bool(SECRET_NAME_RE.match(name))


def validate_pagination(args):
    try:
        page = max(1, int(args.get('page', 1)))
        per_page = min(100, max(1, int(args.get('per_page', 25))))
    except (ValueError, TypeError):
        page, per_page = 1, 25
    offset = (page - 1) * per_page
    return page, per_page, offset