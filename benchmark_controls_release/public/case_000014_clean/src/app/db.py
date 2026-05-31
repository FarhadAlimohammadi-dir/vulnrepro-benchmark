import sqlite3
import json
import os
import logging

logger = logging.getLogger('promptforge.db')
DB_PATH = os.environ.get('DB_PATH', '/tmp/promptforge.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL UNIQUE,
    password   TEXT    NOT NULL,
    role       TEXT    NOT NULL DEFAULT 'user',
    email      TEXT,
    full_name  TEXT,
    bio        TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS prompts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    name         TEXT    NOT NULL,
    model        TEXT    NOT NULL DEFAULT 'gemini-2.0-flash-001',
    prompt_type  TEXT    NOT NULL DEFAULT 'text',
    description  TEXT    NOT NULL DEFAULT '',
    tags         TEXT    NOT NULL DEFAULT '',
    body         TEXT    NOT NULL DEFAULT '{}',
    is_public    INTEGER NOT NULL DEFAULT 0,
    version      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id  INTEGER NOT NULL REFERENCES prompts(id),
    version    INTEGER NOT NULL,
    body       TEXT    NOT NULL,
    changed_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    action     TEXT    NOT NULL,
    detail     TEXT    NOT NULL DEFAULT '',
    ip_addr    TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    key_hash   TEXT    NOT NULL UNIQUE,
    label      TEXT    NOT NULL DEFAULT 'default',
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    last_used  TEXT
);
'''

SEED_USERS = [
    ('alice',   'alice123',  'admin', 'alice@promptforge.dev',   'Alice Admin',    'Platform administrator and ML engineer.'),
    ('bob',     'bob456',    'user',  'bob@example.com',         'Bob Builder',    'Builds multimodal pipelines for image classification.'),
    ('carol',   'carol789',  'user',  'carol@example.com',       'Carol Chen',     'NLP researcher focused on summarization tasks.'),
    ('dave',    'dave321',   'user',  'dave@example.com',        'Dave Nguyen',    'Data scientist using Gemini for document analysis.'),
    ('eve',     'eve654',    'user',  'eve@example.com',         'Eve Ramirez',    'MLOps engineer building prompt evaluation workflows.'),
]

SEED_PROMPTS = [
    # user 1 (alice)
    (1, 'Image Scene Describer',   'gemini-2.0-flash-001', 'multimodal_freeform',
     'Describe the scene in an uploaded image.',
     'vision,description',
     json.dumps({'parts': [
         {'text': 'Describe this image in detail.'},
         {'fileData': {'mimeType': 'image/jpeg', 'fileUri': 'gs://pf-samples/scene.jpg'}}
     ]}), 1),
    (1, 'Logo Brand Classifier',   'gemini-2.0-flash-001', 'multimodal_freeform',
     'Identify brand logos in product photos.',
     'vision,classification',
     json.dumps({'parts': [
         {'text': 'Identify any brand logos visible in this image.'},
         {'fileData': {'mimeType': 'image/png', 'fileUri': 'gs://pf-samples/logo.png'}}
     ]}), 1),
    (1, 'Invoice Data Extractor',  'gemini-1.5-pro', 'multimodal_freeform',
     'Extract line items and totals from invoice images.',
     'finance,extraction',
     json.dumps({'parts': [
         {'text': 'Extract all line items, quantities, and totals from this invoice.'},
         {'fileData': {'mimeType': 'image/jpeg', 'fileUri': 'gs://pf-samples/invoice.jpg'}}
     ]}), 0),
    # user 2 (bob)
    (2, 'Satellite Image Tagger',  'gemini-2.0-flash-001', 'multimodal_freeform',
     'Tag features in satellite imagery.',
     'geo,vision',
     json.dumps({'parts': [
         {'text': 'List all visible features in this satellite image.'},
         {'fileData': {'mimeType': 'image/png', 'fileUri': 'gs://pf-geo/tile_001.png'}}
     ]}), 0),
    (2, 'Product Review Summarizer', 'gemini-1.5-flash', 'text',
     'Summarise customer reviews into pros and cons.',
     'nlp,summarization',
     json.dumps({'parts': [
         {'text': 'Summarise the following customer reviews into key pros and cons:\n{{REVIEWS}}'}
     ]}), 1),
    (2, 'Medical Image Classifier', 'gemini-2.0-flash-001', 'multimodal_freeform',
     'Preliminary classification of medical scan images.',
     'medical,vision',
     json.dumps({'parts': [
         {'text': 'Classify the type of scan and describe visible findings.'},
         {'fileData': {'mimeType': 'image/dicom', 'fileUri': 'gs://pf-medical/scan_001.dcm'}}
     ]}), 0),
    # user 3 (carol)
    (3, 'Legal Document Summarizer', 'gemini-1.5-pro', 'text',
     'Summarise lengthy legal documents.',
     'legal,nlp',
     json.dumps({'parts': [
         {'text': 'Summarise the key obligations and clauses in this contract:\n{{DOCUMENT}}'}
     ]}), 1),
    (3, 'Code Review Assistant',   'gemini-1.5-pro', 'text',
     'Review Python code for style and logic issues.',
     'dev,code',
     json.dumps({'parts': [
         {'text': 'Review the following Python code for correctness, style, and performance:\n```python\n{{CODE}}\n```'}
     ]}), 1),
    # user 4 (dave)
    (4, 'Chart Data Extractor',    'gemini-2.0-flash-001', 'multimodal_freeform',
     'Extract numeric data from chart images.',
     'data,vision',
     json.dumps({'parts': [
         {'text': 'Extract all numeric values and labels from this chart.'},
         {'fileData': {'mimeType': 'image/png', 'fileUri': 'gs://pf-charts/q3_revenue.png'}}
     ]}), 0),
    (4, 'Meeting Notes Formatter',  'gemini-1.5-flash', 'text',
     'Format raw meeting notes into structured minutes.',
     'productivity,nlp',
     json.dumps({'parts': [
         {'text': 'Format these raw meeting notes into structured minutes with action items:\n{{NOTES}}'}
     ]}), 1),
    # user 5 (eve)
    (5, 'A/B Test Analyser',       'gemini-1.5-pro', 'text',
     'Analyse A/B test results and recommend the winner.',
     'analytics,data',
     json.dumps({'parts': [
         {'text': 'Analyse these A/B test results and recommend which variant to ship:\n{{RESULTS}}'}
     ]}), 0),
    (5, 'Slide Deck Summarizer',   'gemini-2.0-flash-001', 'multimodal_freeform',
     'Summarise the key messages from a slide deck image.',
     'productivity,vision',
     json.dumps({'parts': [
         {'text': 'Summarise the key messages from this presentation slide.'},
         {'fileData': {'mimeType': 'image/png', 'fileUri': 'gs://pf-slides/deck_cover.png'}}
     ]}), 0),
]


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)

    for username, password, role, email, full_name, bio in SEED_USERS:
        try:
            conn.execute(
                'INSERT INTO users (username, password, role, email, full_name, bio) VALUES (?,?,?,?,?,?)',
                (username, password, role, email, full_name, bio)
            )
        except sqlite3.IntegrityError:
            pass

    for user_id, name, model, ptype, description, tags, body, is_public in SEED_PROMPTS:
        existing = conn.execute(
            'SELECT id FROM prompts WHERE user_id=? AND name=?', (user_id, name)
        ).fetchone()
        if not existing:
            conn.execute(
                '''INSERT INTO prompts
                   (user_id, name, model, prompt_type, description, tags, body, is_public)
                   VALUES (?,?,?,?,?,?,?,?)''',
                (user_id, name, model, ptype, description, tags, body, is_public)
            )

    conn.commit()
    conn.close()
    logger.info('Database initialised at %s', DB_PATH)


if __name__ == '__main__':
    init_db()
    print('Database initialised at', DB_PATH)