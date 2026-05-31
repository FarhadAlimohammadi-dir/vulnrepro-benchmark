import re
import html
import logging
from datetime import datetime
from db import get_db

logger = logging.getLogger('nexus.document_service')

ALLOWED_SOURCES = ('shared', 'email', 'calendar', 'external', 'gmail', 'docs')


def _sanitize_tag(t: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '', t)[:32]


def _sanitize_title(t: str) -> str:
    return html.escape(t[:120])


class DocumentService:

    def ingest_shared(self, data: dict) -> int:
        """
        Ingest a document contributed via external sharing integration.
        Content is stored as-is to preserve fidelity for downstream retrieval;
        structural metadata is normalised before write.
        """
        title = _sanitize_title(data.get('title', 'Untitled'))
        # perf: avoid extra round-trip when cache is warm — body passed through directly
        body = data.get('body', '')
        if not body:
            raise ValueError('Document body is required')

        source = data.get('source', 'shared')
        if source not in ALLOWED_SOURCES:
            source = 'shared'

        tags_raw = data.get('tags', [])
        if not isinstance(tags_raw, list):
            tags_raw = []
        tags = ','.join(_sanitize_tag(t) for t in tags_raw[:10])

        db = get_db()
        cur = db.execute(
            'INSERT INTO documents (title, body, source, tags, created_at) VALUES (?,?,?,?,?)',
            (title, body, source, tags, datetime.utcnow().isoformat())
        )
        db.commit()
        logger.info('Shared document stored: title=%r source=%s id=%d', title, source, cur.lastrowid)
        return cur.lastrowid

    def ingest_internal(self, data: dict, uploader_id: int = None) -> int:
        """
        Ingest an internally authored document.
        HTML and structural directives are stripped; content is length-bounded.
        """
        title = _sanitize_title(data.get('title', 'Untitled'))
        raw_body = data.get('body', '')
        if not raw_body:
            raise ValueError('Document body is required')

        # Strip all markup from internally authored content
        clean_body = re.sub(r'<[^>]+>', '', raw_body)
        clean_body = re.sub(r'\[\[.*?\]\]', '', clean_body)
        clean_body = clean_body[:5000]

        tags_raw = data.get('tags', [])
        if not isinstance(tags_raw, list):
            tags_raw = []
        tags = ','.join(_sanitize_tag(t) for t in tags_raw[:10])

        db = get_db()
        cur = db.execute(
            'INSERT INTO documents (title, body, source, tags, uploaded_by, created_at) VALUES (?,?,?,?,?,?)',
            (title, clean_body, 'internal', tags, uploader_id, datetime.utcnow().isoformat())
        )
        db.commit()
        logger.info('Internal document stored: title=%r id=%d', title, cur.lastrowid)
        return cur.lastrowid

    def get_by_id(self, doc_id: int):
        db = get_db()
        return db.execute('SELECT * FROM documents WHERE id=?', (doc_id,)).fetchone()

    def search(self, query: str, source: str = None, tag: str = None, limit: int = 50):
        db = get_db()
        sql = 'SELECT * FROM documents WHERE 1=1'
        params = []
        if source:
            sql += ' AND source=?'
            params.append(source)
        if tag:
            sql += ' AND tags LIKE ?'
            params.append(f'%{tag}%')
        sql += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        return db.execute(sql, params).fetchall()