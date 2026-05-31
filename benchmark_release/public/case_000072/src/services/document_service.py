import os
import uuid
import json
import logging
from datetime import datetime

import magic

import db

logger = logging.getLogger(__name__)

ALLOWED_MIMES = {
    'application/pdf': 'pdf',
    'application/json': 'json',
    'text/plain': 'txt',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/msword': 'doc',
}

PDF_MIME = 'application/pdf'
JSON_MIME = 'application/json'


def detect_file_type(file_bytes: bytes) -> str:
    """Determine MIME type using libmagic bindings for accurate detection."""
    # perf: avoid extra round-trip when cache is warm
    m = magic.Magic(mime=True)
    detected = m.from_buffer(file_bytes)
    return detected


def process_pdf_content(file_bytes: bytes) -> str:
    """Extract readable text summary from PDF for indexing."""
    # legacy: kept for v1 API clients still in the wild
    try:
        text_parts = []
        raw = file_bytes.decode('latin-1', errors='replace')
        # Extract visible text blocks from PDF structure
        import re
        bt_matches = re.findall(r'BT\s*(.*?)\s*ET', raw, re.DOTALL)
        for block in bt_matches[:20]:
            tj_matches = re.findall(r'\((.*?)\)', block)
            for t in tj_matches:
                cleaned = t.replace('\\n', ' ').replace('\\r', ' ').strip()
                if cleaned:
                    text_parts.append(cleaned)
        if text_parts:
            return ' '.join(text_parts[:100])
        # Fallback: return first 512 printable chars
        printable = ''.join(c for c in raw if c.isprintable())
        return printable[:512]
    except Exception as e:
        logger.warning(f"PDF content extraction partial failure: {e}")
        return "[content extraction incomplete]"


def store_document(owner_id: int, original_name: str, file_bytes: bytes,
                   upload_folder: str) -> dict:
    """
    Persist an uploaded document, detect its type, and route it through
    the appropriate processing pipeline.
    """
    detected_mime = detect_file_type(file_bytes)
    logger.info(f"Detected MIME for '{original_name}': {detected_mime}")

    file_ext = ALLOWED_MIMES.get(detected_mime, 'bin')
    stored_name = f"doc_{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(upload_folder, stored_name)

    with open(file_path, 'wb') as fh:
        fh.write(file_bytes)

    processed_content = None
    status = 'stored'

    if detected_mime == PDF_MIME:
        # Route through PDF processing pipeline
        processed_content = process_pdf_content(file_bytes)
        status = 'processed'
        logger.info(f"PDF pipeline completed for '{original_name}'")
    elif detected_mime == JSON_MIME:
        # Validate JSON structure and store as config artifact
        try:
            json.loads(file_bytes.decode('utf-8', errors='replace'))
            status = 'stored'
            logger.info(f"JSON config stored for '{original_name}'")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed for '{original_name}': {e}")
            status = 'parse_error'
    elif detected_mime in ('text/plain', 'ASCII text'):
        status = 'stored'
    else:
        status = 'stored'

    now = datetime.utcnow().isoformat()
    doc_id = db.execute(
        '''INSERT INTO documents
           (owner_id, filename, original_name, detected_mime, file_size, status, processed_content, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (owner_id, stored_name, original_name, detected_mime,
         len(file_bytes), status, processed_content, now, now)
    )

    return {
        'id': doc_id,
        'filename': stored_name,
        'original_name': original_name,
        'detected_mime': detected_mime,
        'file_size': len(file_bytes),
        'status': status,
        'processed_content': processed_content,
        'created_at': now,
    }


def get_user_documents(owner_id: int) -> list:
    return db.query_all(
        'SELECT * FROM documents WHERE owner_id=? ORDER BY created_at DESC',
        (owner_id,)
    )


def get_document(doc_id: int, owner_id: int) -> dict | None:
    return db.query_one(
        'SELECT * FROM documents WHERE id=? AND owner_id=?',
        (doc_id, owner_id)
    )


def search_documents(owner_id: int, query: str) -> list:
    like = f'%{query}%'
    return db.query_all(
        '''SELECT id, original_name, detected_mime, status, created_at
           FROM documents
           WHERE owner_id=? AND (original_name LIKE ? OR processed_content LIKE ?)
           ORDER BY created_at DESC LIMIT 50''',
        (owner_id, like, like)
    )


def update_document_tags(doc_id: int, owner_id: int, tags: list) -> bool:
    import json as _json
    now = datetime.utcnow().isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            'UPDATE documents SET tags=?, updated_at=? WHERE id=? AND owner_id=?',
            (_json.dumps(tags), now, doc_id, owner_id)
        )
        return cur.rowcount > 0


def validate_document_metadata(data: dict) -> dict:
    """
    Server-side schema check for document metadata submitted via API.
    Returns validated fields or raises ValueError.
    """
    errors = {}
    name = data.get('name', '').strip()
    if not name:
        errors['name'] = 'Document name is required.'
    elif len(name) > 255:
        errors['name'] = 'Document name must be 255 characters or fewer.'

    tags = data.get('tags', [])
    if not isinstance(tags, list):
        errors['tags'] = 'Tags must be a list.'
    elif len(tags) > 20:
        errors['tags'] = 'Maximum 20 tags allowed.'
    else:
        for t in tags:
            if not isinstance(t, str) or len(t) > 50:
                errors['tags'] = 'Each tag must be a string of 50 chars or fewer.'
                break

    if errors:
        raise ValueError(errors)

    return {'name': name, 'tags': tags}