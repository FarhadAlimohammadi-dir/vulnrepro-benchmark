import sqlite3
import hashlib
import os

DB_PATH = os.environ.get('DB_PATH', '/tmp/modelhub.db')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    email TEXT,
    bio TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    framework TEXT NOT NULL DEFAULT 'keras',
    owner_id INTEGER NOT NULL,
    file_path TEXT,
    config_summary TEXT,
    description TEXT,
    is_public INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    download_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    file_path TEXT,
    row_count INTEGER DEFAULT 0,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id INTEGER,
    detail TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY(model_id) REFERENCES models(id)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(model_id) REFERENCES models(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
'''

SEED_USERS = [
    ('alice',   'hunter2',      'admin',  'alice@modelhub.io',   'Platform administrator and ML researcher.'),
    ('bob',     'password123',  'user',   'bob@example.com',     'Computer vision enthusiast. Building detection pipelines.'),
    ('charlie', 'letmein',      'user',   'charlie@example.com', 'NLP practitioner, focus on sentiment and summarisation.'),
    ('diana',   'securepass!',  'user',   'diana@example.com',   'Reinforcement learning, robotics.'),
    ('evan',    'ev@n2024',     'user',   'evan@example.com',    'Time-series forecasting and anomaly detection.'),
]

SEED_MODELS = [
    ('resnet50-imagenet',       'keras',    1, 'ready',   'ResNet-50 pretrained on ImageNet-1k, fine-tuned for production.',       1),
    ('bert-sentiment',          'keras',    2, 'ready',   'BERT-base fine-tuned for binary sentiment on SST-2.',                   1),
    ('yolov5-custom',           'pytorch',  2, 'ready',   'YOLOv5s custom-trained on an internal 80-class dataset.',               1),
    ('efficientnet-b3-flowers', 'keras',    3, 'ready',   'EfficientNet-B3 flower classification, 5 classes, 94% accuracy.',       1),
    ('gpt2-finetuned-code',     'pytorch',  3, 'ready',   'GPT-2 small fine-tuned on Python snippets from GitHub.',                1),
    ('wav2vec-emotion',         'keras',    4, 'ready',   'wav2vec 2.0 for speech emotion recognition.',                           1),
    ('tabnet-fraud',            'keras',    4, 'ready',   'TabNet model for credit-card fraud detection.',                         1),
    ('unet-segmentation',       'keras',    5, 'ready',   'U-Net architecture for semantic segmentation of satellite imagery.',    1),
    ('lstm-forecasting',        'keras',    5, 'ready',   'Stacked LSTM for 30-day energy consumption forecasting.',               1),
    ('vit-patch16-224',         'keras',    1, 'ready',   'Vision Transformer ViT-B/16 fine-tuned on internal product catalog.',   1),
    ('deberta-ner',             'pytorch',  2, 'ready',   'DeBERTa-v3 for named-entity recognition on financial documents.',       0),
    ('clip-embeddings',         'keras',    3, 'ready',   'CLIP ViT-B/32 used for cross-modal retrieval.',                        1),
    ('xgboost-churn',           'sklearn',  4, 'ready',   'XGBoost churn predictor trained on 2M telecom records.',                1),
    ('distilbert-qa',           'pytorch',  5, 'ready',   'DistilBERT extractive QA fine-tuned on SQuAD 2.0.',                    1),
    ('stylegan3-faces',         'pytorch',  1, 'draft',   'StyleGAN3 unconditional face generator, internal use only.',            0),
]

SEED_TAGS = [
    (1, 'image-classification'), (1, 'imagenet'), (1, 'pretrained'),
    (2, 'nlp'), (2, 'sentiment'), (2, 'bert'),
    (3, 'object-detection'), (3, 'yolo'),
    (4, 'image-classification'), (4, 'efficientnet'),
    (5, 'nlp'), (5, 'generation'), (5, 'gpt2'),
    (6, 'audio'), (6, 'emotion'),
    (7, 'tabular'), (7, 'fraud-detection'),
    (8, 'segmentation'), (8, 'unet'), (8, 'remote-sensing'),
    (9, 'time-series'), (9, 'lstm'), (9, 'forecasting'),
    (10, 'image-classification'), (10, 'vit'), (10, 'transformers'),
]

SEED_COMMENTS = [
    (1, 3, 'Great baseline — we use this as a starting point for all our CV projects.'),
    (1, 4, 'What augmentation strategy was used during fine-tuning?'),
    (2, 1, 'Solid F1 on our internal benchmark. Thanks for sharing!'),
    (3, 5, 'Anyone tested this against YOLOv8? Curious about mAP differences.'),
    (4, 2, 'The flowers dataset split is documented in the description — 80/10/10.'),
    (7, 3, 'Does the fraud model handle class imbalance? Would love to see the AUC-PR.'),
    (9, 4, 'LSTM beats our Prophet baseline on the energy dataset by ~4% MAPE.'),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.executescript(SCHEMA)

    for username, pw, role, email, bio in SEED_USERS:
        pw_hash = hashlib.sha256(pw.encode()).hexdigest()
        try:
            db.execute(
                'INSERT INTO users (username, password_hash, role, email, bio) VALUES (?,?,?,?,?)',
                (username, pw_hash, role, email, bio)
            )
        except sqlite3.IntegrityError:
            pass

    for name, fw, owner_id, status, desc, public in SEED_MODELS:
        existing = db.execute('SELECT id FROM models WHERE name=?', (name,)).fetchone()
        if not existing:
            db.execute(
                'INSERT INTO models (name, framework, owner_id, status, description, is_public) '
                'VALUES (?,?,?,?,?,?)',
                (name, fw, owner_id, status, desc, public)
            )

    for model_id, tag in SEED_TAGS:
        existing = db.execute(
            'SELECT id FROM tags WHERE model_id=? AND tag=?', (model_id, tag)
        ).fetchone()
        if not existing:
            try:
                db.execute('INSERT INTO tags (model_id, tag) VALUES (?,?)', (model_id, tag))
            except Exception:
                pass

    for model_id, user_id, body in SEED_COMMENTS:
        try:
            db.execute(
                'INSERT INTO comments (model_id, user_id, body) VALUES (?,?,?)',
                (model_id, user_id, body)
            )
        except Exception:
            pass

    db.commit()
    db.close()


if __name__ == '__main__':
    init_db()
    print('DB initialised at', DB_PATH)