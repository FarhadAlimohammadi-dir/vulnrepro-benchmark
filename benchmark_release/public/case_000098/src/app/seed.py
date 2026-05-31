import sqlite3
import bcrypt
import json
import logging

logger = logging.getLogger(__name__)

def seed_data(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    logger.info("Seeding initial data...")

    users = [
        ('alice', 'alice@webhookrelay.io', 'AlicePass123!', 'admin'),
        ('bob', 'bob@webhookrelay.io', 'BobPass123!', 'user'),
        ('charlie', 'charlie@webhookrelay.io', 'CharliePass123!', 'user'),
        ('diana', 'diana@webhookrelay.io', 'DianaPass456!', 'user'),
        ('evan', 'evan@webhookrelay.io', 'EvanPass789!', 'user'),
    ]

    user_ids = {}
    for username, email, password, role in users:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        c.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, pw_hash, role)
        )
        user_ids[username] = c.lastrowid

    relay_endpoints = [
        (user_ids['alice'], 'Stripe Webhook', 'Payment processing events from Stripe',
         'https://internal.webhookrelay.io/stripe', 'POST', '{"X-Relay-Source": "stripe"}'),
        (user_ids['alice'], 'GitHub CI Trigger', 'Trigger CI builds from GitHub push events',
         'https://ci.internal/trigger', 'POST', '{"Authorization": "Bearer ci-token-abc123"}'),
        (user_ids['bob'], 'Slack Notifier', 'Forward alerts to Slack channels',
         'https://hooks.slack.com/services/T00/B00/xxx', 'POST', '{}'),
        (user_ids['bob'], 'PagerDuty Relay', 'Relay on-call alerts to PagerDuty',
         'https://events.pagerduty.com/v2/enqueue', 'POST', '{}'),
        (user_ids['charlie'], 'Analytics Sink', 'Forward analytics events to BigQuery proxy',
         'https://analytics.internal/ingest', 'POST', '{"X-Api-Key": "bq-proxy-key-xyz"}'),
        (user_ids['charlie'], 'Email Gateway', 'Trigger transactional emails via SendGrid',
         'https://api.sendgrid.com/v3/mail/send', 'POST', '{}'),
        (user_ids['diana'], 'Salesforce Sync', 'Sync CRM events to Salesforce',
         'https://crm.internal/salesforce/sync', 'POST', '{}'),
        (user_ids['evan'], 'DataDog Metrics', 'Forward custom metrics to DataDog',
         'https://api.datadoghq.com/api/v1/series', 'POST', '{}'),
    ]

    relay_ids = []
    for uid, name, desc, url, method, headers in relay_endpoints:
        c.execute(
            '''INSERT INTO relay_endpoints (user_id, name, description, target_url, method, headers)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (uid, name, desc, url, method, headers)
        )
        relay_ids.append(c.lastrowid)

    deliveries = [
        (relay_ids[0], '{"event": "payment.completed", "amount": 4999}', 200, '{"status": "ok"}', 142, 1),
        (relay_ids[0], '{"event": "payment.failed", "code": "card_declined"}', 200, '{"status": "ok"}', 98, 1),
        (relay_ids[1], '{"ref": "refs/heads/main", "sha": "abc123def"}', 201, '{"build_id": "42"}', 231, 1),
        (relay_ids[2], '{"text": "Alert: CPU > 90%", "channel": "#ops"}', 200, 'ok', 187, 1),
        (relay_ids[2], '{"text": "Disk space low on prod-db-01"}', 200, 'ok', 203, 1),
        (relay_ids[3], '{"routing_key": "pg-key", "event_action": "trigger"}', 202, '{"status": "success"}', 315, 1),
        (relay_ids[4], '{"event": "page_view", "user_id": "u-789"}', 200, '{"inserted": 1}', 88, 1),
        (relay_ids[5], '{"to": "user@example.com", "subject": "Welcome!"}', 202, '', 445, 1),
        (relay_ids[0], '{"event": "refund.created", "amount": 1500}', 500, 'Internal Server Error', 2100, 0),
        (relay_ids[6], '{"sobject": "Contact", "id": "003xx000004TmiQAAS"}', 200, '{"success": true}', 567, 1),
    ]

    for relay_id, payload, status, response, duration, success in deliveries:
        c.execute(
            '''INSERT INTO webhook_deliveries (relay_id, payload, status_code, response_body, duration_ms, success)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (relay_id, payload, status, response, duration, success)
        )

    audit_events = [
        (user_ids['alice'], 'login', 'session', None, '{"ip": "10.0.1.5"}', '10.0.1.5'),
        (user_ids['alice'], 'create_relay', 'relay_endpoint', relay_ids[0], '{"name": "Stripe Webhook"}', '10.0.1.5'),
        (user_ids['bob'], 'login', 'session', None, '{"ip": "10.0.2.8"}', '10.0.2.8'),
        (user_ids['charlie'], 'login', 'session', None, '{"ip": "192.168.1.22"}', '192.168.1.22'),
        (user_ids['alice'], 'update_secret', 'webhook_secret', relay_ids[0], '{"algo": "hmac-sha256"}', '10.0.1.5'),
    ]

    for uid, action, rtype, rid, details, ip in audit_events:
        c.execute(
            '''INSERT INTO audit_events (user_id, action, resource_type, resource_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (uid, action, rtype, rid, details, ip)
        )

    conn.commit()
    conn.close()
    logger.info("Seed data inserted successfully")