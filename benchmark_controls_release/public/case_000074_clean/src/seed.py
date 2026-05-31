import os
import sqlite3
import bcrypt
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "forge.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

from models import db_init
db_init(DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys=ON")

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

users = [
    ("alice",   "alice@example.com",   "AlicePass123!"),
    ("bob",     "bob@example.com",     "BobPass123!"),
    ("charlie", "charlie@example.com", "CharliePass123!"),
    ("dave",    "dave@example.com",    "DavePass456!"),
    ("eve",     "eve@example.com",     "EvePass456!"),
]

user_ids = {}
for username, email, pw in users:
    existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if existing:
        user_ids[username] = existing["id"]
        continue
    cur = conn.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
        (username, email, hash_pw(pw))
    )
    user_ids[username] = cur.lastrowid

conn.commit()

# Projects: alice=100042, bob=100043, charlie=100044, dave=100045, eve=100046
project_data = [
    ("alice-prod",      100042, "alice",   "us-east1"),
    ("alice-staging",   100052, "alice",   "eu-west1"),
    ("bob-main",        100043, "bob",     "us-east1"),
    ("bob-dev",         100053, "bob",     "us-west1"),
    ("charlie-sandbox", 100044, "charlie", "us-east1"),
    ("dave-analytics",  100045, "dave",    "us-east1"),
    ("eve-ml-pipeline", 100046, "eve",     "eu-west1"),
]

project_ids = {}
for name, numeric_id, owner, region in project_data:
    existing = conn.execute("SELECT id FROM projects WHERE numeric_id=?", (numeric_id,)).fetchone()
    if existing:
        project_ids[name] = existing["id"]
        continue
    cur = conn.execute(
        "INSERT INTO projects (numeric_id, name, owner_id, region) VALUES (?,?,?,?)",
        (numeric_id, name, user_ids[owner], region)
    )
    project_ids[name] = cur.lastrowid

conn.commit()

# Implementation note removed for benchmark packaging.
bucket_seeds = [
    (f"func-sources-100052-eu-west1",  "alice"),
    (f"func-sources-100043-us-east1",  "bob"),
    (f"func-sources-100053-us-west1",  "bob"),
    (f"func-sources-100045-us-east1",  "dave"),
    (f"func-sources-100046-eu-west1",  "eve"),
    ("logs-archive-bob-main",          "bob"),
    ("static-assets-alice-staging",    "alice"),
    ("ml-artifacts-eve",               "eve"),
]

bucket_ids = {}
for bname, owner in bucket_seeds:
    existing = conn.execute("SELECT id FROM storage_buckets WHERE name=?", (bname,)).fetchone()
    if existing:
        bucket_ids[bname] = existing["id"]
        continue
    cur = conn.execute(
        "INSERT INTO storage_buckets (name, owner_id) VALUES (?,?)",
        (bname, user_ids[owner])
    )
    bucket_ids[bname] = cur.lastrowid

conn.commit()

# Seed some existing functions for bob and dave
function_seeds = [
    ("data-processor",    "bob-main",        "us-east1", "python39",  "ACTIVE"),
    ("auth-webhook",      "bob-main",        "us-east1", "nodejs16",  "ACTIVE"),
    ("report-generator",  "bob-dev",         "us-west1", "python39",  "ACTIVE"),
    ("anomaly-detector",  "dave-analytics",  "us-east1", "python39",  "ACTIVE"),
    ("etl-pipeline",      "dave-analytics",  "us-east1", "go116",     "ACTIVE"),
    ("model-trainer",     "eve-ml-pipeline", "eu-west1", "python39",  "ACTIVE"),
    ("feature-extractor", "eve-ml-pipeline", "eu-west1", "python39",  "ACTIVE"),
]

func_ids = {}
for fname, proj_name, region, runtime, status in function_seeds:
    existing = conn.execute(
        "SELECT id FROM functions WHERE name=? AND project_id=?",
        (fname, project_ids[proj_name])
    ).fetchone()
    if existing:
        func_ids[fname] = existing["id"]
        continue
    bucket_name = f"func-sources-{[p[1] for p in project_data if p[0]==proj_name][0]}-{region}"
    cur = conn.execute(
        """INSERT INTO functions (name, project_id, region, runtime, status, source_bucket, source_object)
           VALUES (?,?,?,?,?,?,?)""",
        (fname, project_ids[proj_name], region, runtime, status,
         bucket_name, f"{fname}/v1/function-source.zip")
    )
    func_ids[fname] = cur.lastrowid

conn.commit()

# Seed some logs
log_seeds = [
    ("data-processor",   "Function started successfully", "INFO"),
    ("data-processor",   "Processed 1423 records", "INFO"),
    ("auth-webhook",     "Received webhook event: user.login", "INFO"),
    ("auth-webhook",     "Validated JWT signature", "DEBUG"),
    ("anomaly-detector", "Model loaded from cache", "INFO"),
    ("anomaly-detector", "Detected 3 anomalies in batch", "WARNING"),
    ("etl-pipeline",     "Connected to source database", "INFO"),
    ("etl-pipeline",     "Loaded 50000 rows", "INFO"),
    ("model-trainer",    "Epoch 10/100 loss=0.3421", "INFO"),
    ("feature-extractor","Extracted 256-dim feature vector", "DEBUG"),
]

for fname, msg, severity in log_seeds:
    if fname in func_ids:
        conn.execute(
            "INSERT INTO function_logs (function_id, message, severity) VALUES (?,?,?)",
            (func_ids[fname], msg, severity)
        )

conn.commit()

# Seed env vars
env_seeds = [
    ("data-processor",   "DB_HOST",    "postgres.internal"),
    ("data-processor",   "BATCH_SIZE", "500"),
    ("auth-webhook",     "JWT_ISSUER", "https://auth.example.com"),
    ("anomaly-detector", "MODEL_PATH", "/models/v2/anomaly.pkl"),
    ("etl-pipeline",     "SOURCE_DB",  "mysql://etl:***@db.internal/warehouse"),
]

for fname, key, val in env_seeds:
    if fname in func_ids:
        conn.execute(
            "INSERT OR IGNORE INTO env_vars (function_id, key, value) VALUES (?,?,?)",
            (func_ids[fname], key, val)
        )

conn.commit()
conn.close()

print("Seed complete.")