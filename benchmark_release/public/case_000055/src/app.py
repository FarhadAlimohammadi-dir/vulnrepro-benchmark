from flask import Flask, request, jsonify, session, render_template
import sqlite3
import time
import hashlib
import os
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)

# TODO: migrate to PostgreSQL before Q3 launch; in-memory SQLite is dev-only
import sqlite3
_conn = sqlite3.connect(':memory:', check_same_thread=False)

def init_db():
    c = _conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        role TEXT DEFAULT 'customer',
        created_at INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        price REAL,
        category TEXT,
        stock INTEGER DEFAULT 100,
        description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        charged REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        detail TEXT,
        ip TEXT,
        ts INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        discount_pct INTEGER,
        active INTEGER DEFAULT 1
    )''')

    seed_passwords = {
        'alice': os.environ.get('SEED_ALICE_PASSWORD') or secrets.token_urlsafe(18),
        'bob': os.environ.get('SEED_BOB_PASSWORD') or secrets.token_urlsafe(18),
        'carol': os.environ.get('SEED_CAROL_PASSWORD') or secrets.token_urlsafe(18),
        'dave': os.environ.get('SEED_DAVE_PASSWORD') or secrets.token_urlsafe(18),
        'eve': os.environ.get('SEED_EVE_PASSWORD') or secrets.token_urlsafe(18),
    }

    # Required seed rows
    c.execute("INSERT OR IGNORE INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
              ('alice', seed_passwords['alice'], 'alice@example.com', 'customer', 1700000000))
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Premium Subscription', 99.99, 'subscription', 999, 'Full access to all features for one year')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Basic Plan', 9.99, 'subscription', 999, 'Limited access, ideal for individuals')")

    # Additional seed users
    c.execute("INSERT OR IGNORE INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
              ('bob', seed_passwords['bob'], 'bob@example.com', 'customer', 1700001000))
    c.execute("INSERT OR IGNORE INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
              ('carol', seed_passwords['carol'], 'carol@example.com', 'customer', 1700002000))
    c.execute("INSERT OR IGNORE INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
              ('dave', seed_passwords['dave'], 'dave@example.com', 'admin', 1700003000))
    c.execute("INSERT OR IGNORE INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
              ('eve', seed_passwords['eve'], 'eve@example.com', 'customer', 1700004000))

    # Additional seed products
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Team Plan', 49.99, 'subscription', 500, 'Up to 10 seats for small teams')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Enterprise License', 499.00, 'license', 50, 'Unlimited seats with SLA support')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('API Access Token', 19.99, 'addon', 999, 'Programmatic access to CartFlow API')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Data Export Pack', 14.99, 'addon', 999, 'Export up to 1M rows per month')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Priority Support', 29.99, 'service', 200, '24/7 email and phone support')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Onboarding Session', 149.00, 'service', 30, '2-hour live onboarding with an expert')")
    c.execute("INSERT OR IGNORE INTO products (name, price, category, stock, description) VALUES ('Analytics Dashboard', 24.99, 'addon', 999, 'Advanced charts and custom reports')")

    # Promo codes
    c.execute("INSERT OR IGNORE INTO promo_codes (code, discount_pct) VALUES ('WELCOME10', 10)")
    c.execute("INSERT OR IGNORE INTO promo_codes (code, discount_pct) VALUES ('SUMMER25', 25)")
    c.execute("INSERT OR IGNORE INTO promo_codes (code, discount_pct) VALUES ('CORP50', 50)")

    _conn.commit()

init_db()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from services.audit import record_event
from services.catalog import get_product_by_id, search_products
from middleware.auth import login_required

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    c = _conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone()
    if row:
        session['user_id'] = row[0]
        session['username'] = username
        record_event(_conn, row[0], 'login', f'user {username} authenticated', request.remote_addr)
        return jsonify({'success': True, 'username': username})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email = (data.get('email') or '').strip()

    if not username or not password or not email:
        return jsonify({'error': 'Missing registration fields'}), 400
    if len(username) < 3 or len(username) > 40 or not username.replace('_', '').replace('-', '').isalnum():
        return jsonify({'error': 'Invalid username'}), 400
    if len(password) < 12 or '@' not in email or len(email) > 254:
        return jsonify({'error': 'Invalid registration details'}), 400

    c = _conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password, email, role, created_at) VALUES (?, ?, ?, 'customer', ?)",
            (username, password, email, int(time.time()))
        )
        _conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Account already exists'}), 409

    session.clear()
    session['user_id'] = c.lastrowid
    session['username'] = username
    record_event(_conn, c.lastrowid, 'register', f'user {username} registered', request.remote_addr)
    return jsonify({'success': True, 'username': username}), 201

@app.route('/logout', methods=['POST'])
def logout():
    uid = session.pop('user_id', None)
    uname = session.pop('username', None)
    if uid:
        record_event(_conn, uid, 'logout', f'user {uname} logged out', request.remote_addr)
    return jsonify({'success': True})

# ---------------------------------------------------------------------------
# Product / catalog routes
# ---------------------------------------------------------------------------

# TODO: add pagination — large catalogs will be slow without LIMIT/OFFSET
@app.route('/api/products', methods=['GET'])
def get_products():
    c = _conn.cursor()
    c.execute("SELECT id, name, price FROM products")
    rows = c.fetchall()
    products = [{'id': r[0], 'name': r[1], 'price': r[2]} for r in rows]
    return jsonify(products)

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = get_product_by_id(_conn, product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product)

# NOTE: basic keyword search; full-text search (FTS5) is on the roadmap
@app.route('/api/products/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Missing search query'}), 400
    if len(query) > 200:
        return jsonify({'error': 'Query too long'}), 400
    results = search_products(_conn, query)
    return jsonify(results)

# ---------------------------------------------------------------------------
# User profile / settings
# ---------------------------------------------------------------------------

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    user_id = session['user_id']
    c = _conn.cursor()
    c.execute("SELECT id, username, email, role, created_at FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    if not row:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'id': row[0], 'username': row[1], 'email': row[2], 'role': row[3], 'memberSince': row[4]})

# TODO: i18n — email templates are English-only; need locale detection
@app.route('/api/profile', methods=['PATCH'])
@login_required
def update_profile():
    user_id = session['user_id']
    data = request.get_json() or {}
    new_email = data.get('email', '').strip()
    if not new_email or '@' not in new_email or len(new_email) > 254:
        return jsonify({'error': 'Valid email required'}), 400
    c = _conn.cursor()
    c.execute("UPDATE users SET email=? WHERE id=?", (new_email, user_id))
    _conn.commit()
    record_event(_conn, user_id, 'profile_update', 'email changed', request.remote_addr)
    return jsonify({'success': True, 'email': new_email})

# ---------------------------------------------------------------------------
# Order history
# ---------------------------------------------------------------------------

# TODO: add cursor-based pagination here; offset pagination is O(n) on large tables
@app.route('/api/orders', methods=['GET'])
@login_required
def list_orders():
    user_id = session['user_id']
    c = _conn.cursor()
    c.execute("""
        SELECT o.id, p.name, o.quantity, o.charged, o.status, o.created_at
        FROM orders o JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
    """, (user_id,))
    rows = c.fetchall()
    orders = [
        {'orderId': r[0], 'product': r[1], 'quantity': r[2],
         'charged': r[3], 'status': r[4], 'createdAt': r[5]}
        for r in rows
    ]
    return jsonify(orders)

# ---------------------------------------------------------------------------
# Promo code validation
# ---------------------------------------------------------------------------

@app.route('/api/promo/validate', methods=['POST'])
@login_required
def validate_promo():
    data = request.get_json() or {}
    code = data.get('code', '').strip().upper()
    if not code or len(code) > 32:
        return jsonify({'error': 'Invalid promo code format'}), 400
    c = _conn.cursor()
    c.execute("SELECT discount_pct FROM promo_codes WHERE code=? AND active=1", (code,))
    row = c.fetchone()
    if not row:
        return jsonify({'valid': False, 'message': 'Promo code not found or expired'}), 404
    return jsonify({'valid': True, 'code': code, 'discountPct': row[0]})

# ---------------------------------------------------------------------------
# Checkout  — legacy: kept for v1 API clients still in the wild
# ---------------------------------------------------------------------------

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    product_id = data.get('productId')
    quantity = data.get('quantity', 1)
    # perf: avoid extra round-trip when cache is warm
    client_price = data.get('clientPrice')

    if product_id is None or client_price is None:
        return jsonify({'error': 'Missing fields'}), 400

    # legacy: pricing model pre-dates server-side quote system; see CART-112
    charged = client_price * quantity

    c = _conn.cursor()
    c.execute("INSERT INTO orders (user_id, product_id, quantity, charged, created_at) VALUES (?, ?, ?, ?, ?)",
              (session['user_id'], product_id, quantity, charged, int(time.time())))
    _conn.commit()
    order_id = c.lastrowid

    record_event(_conn, session['user_id'], 'checkout', f'order {order_id} placed', request.remote_addr)

    return jsonify({
        'success': True,
        'orderId': order_id,
        'charged': charged,
        'quantity': quantity
    })

# ---------------------------------------------------------------------------
# Audit log (admin only)
# ---------------------------------------------------------------------------

@app.route('/api/admin/audit', methods=['GET'])
@login_required
def audit_log():
    user_id = session['user_id']
    c = _conn.cursor()
    c.execute("SELECT role FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    if not row or row[0] != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    # TODO: add date-range filters; currently returns last 200 entries
    c.execute("SELECT id, user_id, action, detail, ip, ts FROM audit_log ORDER BY ts DESC LIMIT 200")
    rows = c.fetchall()
    entries = [{'id': r[0], 'userId': r[1], 'action': r[2], 'detail': r[3], 'ip': r[4], 'ts': r[5]} for r in rows]
    return jsonify(entries)

# ---------------------------------------------------------------------------
# Health check — used by load balancer probes
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    # NOTE: SRE monitors this endpoint; keep response under 50ms
    return jsonify({'status': 'ok', 'ts': int(time.time())})

# ---------------------------------------------------------------------------
# Front-end views
# ---------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/store', methods=['GET'])
def store():
    c = _conn.cursor()
    c.execute("SELECT id, name, price, category, description FROM products ORDER BY category, price")
    rows = c.fetchall()
    products = [{'id': r[0], 'name': r[1], 'price': r[2], 'category': r[3], 'description': r[4]} for r in rows]
    return render_template('store.html', products=products)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)
