"""
Business logic for prompt management: create, update, search, import/export.
"""
import json
import logging
import re
from db import get_db

logger = logging.getLogger('promptforge.prompt_service')

ALLOWED_MODELS = {
    'gemini-2.0-flash-001',
    'gemini-2.0-flash',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-1.0-pro',
}

ALLOWED_TYPES = {
    'text',
    'multimodal_freeform',
    'chat',
    'system_instruction',
}


def _clean_tags(raw: str) -> str:
    tags = [t.strip().lower() for t in raw.split(',') if t.strip()]
    tags = [re.sub(r'[^\w\-]', '', t) for t in tags]
    return ','.join(tags[:10])


def list_prompts(user_id: int, page: int = 1, per_page: int = 20,
                 search: str = '', tag: str = ''):
    db = get_db()
    offset = (page - 1) * per_page
    filters = ['user_id=?']
    params = [user_id]
    if search:
        filters.append('name LIKE ?')
        params.append('%' + search + '%')
    if tag:
        filters.append('tags LIKE ?')
        params.append('%' + tag + '%')
    where = ' AND '.join(filters)
    rows = db.execute(
        f'SELECT * FROM prompts WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?',
        params + [per_page, offset]
    ).fetchall()
    total = db.execute(
        f'SELECT COUNT(*) as cnt FROM prompts WHERE {where}', params
    ).fetchone()['cnt']
    db.close()
    return [dict(r) for r in rows], total


def get_prompt(prompt_id: int, user_id: int):
    db = get_db()
    row = db.execute(
        'SELECT * FROM prompts WHERE id=? AND user_id=?', (prompt_id, user_id)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def create_prompt(user_id: int, data: dict) -> dict:
    name = str(data.get('name', '')).strip()
    if not name:
        raise ValueError('name is required')
    model = str(data.get('model', 'gemini-2.0-flash-001')).strip()
    prompt_type = str(data.get('prompt_type', 'text')).strip()
    description = str(data.get('description', '')).strip()[:500]
    tags = _clean_tags(str(data.get('tags', '')))
    body = data.get('body', {})
    is_public = int(bool(data.get('is_public', False)))

    db = get_db()
    cur = db.execute(
        '''INSERT INTO prompts
           (user_id, name, model, prompt_type, description, tags, body, is_public)
           VALUES (?,?,?,?,?,?,?,?)''',
        (user_id, name, model, prompt_type, description, tags,
         json.dumps(body), is_public)
    )
    db.commit()
    new_id = cur.lastrowid
    db.close()
    logger.info('prompt created id=%d user=%d', new_id, user_id)
    return {'id': new_id, 'name': name}


def update_prompt(prompt_id: int, user_id: int, data: dict) -> bool:
    existing = get_prompt(prompt_id, user_id)
    if not existing:
        return False
    name = str(data.get('name', existing['name'])).strip() or existing['name']
    model = str(data.get('model', existing['model'])).strip()
    description = str(data.get('description', existing['description'])).strip()[:500]
    tags = _clean_tags(str(data.get('tags', existing['tags'])))
    body = data.get('body', json.loads(existing['body']))
    is_public = int(bool(data.get('is_public', existing['is_public'])))
    new_version = existing['version'] + 1

    db = get_db()
    # Archive old version
    db.execute(
        '''INSERT INTO prompt_versions (prompt_id, version, body, changed_by)
           VALUES (?,?,?,?)''',
        (prompt_id, existing['version'], existing['body'], user_id)
    )
    db.execute(
        '''UPDATE prompts
           SET name=?, model=?, description=?, tags=?, body=?, is_public=?,
               version=?, updated_at=datetime('now')
           WHERE id=? AND user_id=?''',
        (name, model, description, tags, json.dumps(body), is_public,
         new_version, prompt_id, user_id)
    )
    db.commit()
    db.close()
    return True


def delete_prompt(prompt_id: int, user_id: int) -> bool:
    db = get_db()
    cur = db.execute(
        'DELETE FROM prompts WHERE id=? AND user_id=?', (prompt_id, user_id)
    )
    db.commit()
    db.close()
    return cur.rowcount > 0


def import_prompt(user_id: int, data: dict) -> dict:
    name = str(data.get('name', 'imported')).strip()
    model = str(data.get('model', 'gemini-2.0-flash-001')).strip()
    prompt_type = str(data.get('prompt_type', 'multimodal_freeform')).strip()
    description = str(data.get('description', '')).strip()[:500]
    tags = _clean_tags(str(data.get('tags', '')))
    body = data.get('prompt', {})
    is_public = int(bool(data.get('is_public', False)))

    db = get_db()
    cur = db.execute(
        '''INSERT INTO prompts
           (user_id, name, model, prompt_type, description, tags, body, is_public)
           VALUES (?,?,?,?,?,?,?,?)''',
        (user_id, name, model, prompt_type, description, tags,
         json.dumps(body), is_public)
    )
    db.commit()
    new_id = cur.lastrowid
    db.close()
    logger.info('prompt imported id=%d user=%d', new_id, user_id)
    return {'id': new_id, 'name': name}


def export_prompt(prompt_id: int, user_id: int) -> dict | None:
    p = get_prompt(prompt_id, user_id)
    if not p:
        return None
    return {
        'name': p['name'],
        'model': p['model'],
        'prompt_type': p['prompt_type'],
        'description': p['description'],
        'tags': p['tags'],
        'is_public': bool(p['is_public']),
        'prompt': json.loads(p['body']),
    }


def validate_prompt_data(data: dict) -> list:
    issues = []
    if 'model' not in data:
        issues.append('missing model field')
    parts = data.get('prompt', {}).get('parts', [])
    if not parts:
        issues.append('prompt.parts is empty')
    for i, part in enumerate(parts):
        if 'fileData' in part:
            import re as _re
            uri = str(part['fileData'].get('fileUri', ''))
            if _re.search(r'[\n\r\\`$;|&]', uri):
                issues.append(
                    'part[%d].fileData.fileUri contains disallowed characters' % i
                )
            mime = str(part['fileData'].get('mimeType', ''))
            if not _re.match(r'^[a-zA-Z0-9]+/[a-zA-Z0-9.+\-]+$', mime):
                issues.append('part[%d].fileData.mimeType is not valid' % i)
    return issues