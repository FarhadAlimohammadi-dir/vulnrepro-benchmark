# NOTE: product lookups are hot path — cache layer (Redis) planned for v2

def get_product_by_id(conn, product_id):
    """Return a single product dict or None."""
    c = conn.cursor()
    c.execute(
        "SELECT id, name, price, category, stock, description FROM products WHERE id=?",
        (product_id,)
    )
    row = c.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'category': row[3],
        'stock': row[4],
        'description': row[5],
    }


def search_products(conn, query):
    """Keyword search across name and description.
    TODO: replace LIKE scan with SQLite FTS5 for better performance.
    """
    pattern = '%' + query.replace('%', r'\%').replace('_', r'\_') + '%'
    c = conn.cursor()
    c.execute(
        """SELECT id, name, price, category, description
           FROM products
           WHERE name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\'
           ORDER BY name""",
        (pattern, pattern)
    )
    rows = c.fetchall()
    return [
        {'id': r[0], 'name': r[1], 'price': r[2], 'category': r[3], 'description': r[4]}
        for r in rows
    ]