# FruitDB — Inventory Management System

A multi-user inventory management web application for fresh produce.

## Features

- Session-based authentication (admin, viewer, guest roles)
- Full product catalogue with category support, stock levels, supplier info
- Search by product name and filter by SKU
- Reporting API with column-level attribute export
- User preference management
- Admin audit log
- Health-check endpoint for load balancer integration

## Quick Start

```bash
docker-compose up --build
```

Access at `http://localhost:9000`

### Demo Credentials

| Username | Password  | Role   |
|----------|-----------|--------|
| admin    | admin123  | Admin  |
| viewer   | viewer456 | Viewer |
| guest    | guest789  | Guest  |

## API Endpoints

### `GET /?action=list[&page=N]`
Returns paginated product catalogue (HTML or JSON).

### `GET /?action=get&col=COLUMN&name=PRODUCT`
Returns a specific column value for a named product. Used by the analytics and export pipeline.

Parameters:
- `col`: Column identifier (`id`, `name`, `sku`, `secret`)
- `name`: Exact product name

### `GET /?action=search&name=PRODUCT`
Full-name search using a parameterised query.

### `GET /?action=filter&sku=PATTERN`
SKU substring filter.

### `GET /?action=validate-col&col=COLUMN`
Returns whether a column name is on the reporting allowlist.

### `GET /?action=categories`
Lists all product categories.

### `GET /?action=profile`
User profile and preference management (authenticated).

### `GET /?action=audit`
Admin-only audit log viewer.

### `GET /?action=health`
Load balancer health-check (returns `{"status":"ok","db":"ok",...}`).

## Database Schema

```sql
fruit(id, name, sku, category_id, unit_price, stock_qty, supplier, country_of_origin, is_organic, secret)
categories(id, name, description)
audit_log(id, user_id, username, action, resource, ip_address, created_at)
users_prefs(id, user_id, pref_key, pref_value, updated_at)
```

## Architecture

- **Backend:** PHP 8.1 / Apache
- **Database:** MySQL 8.0
- **Auth:** PHP sessions
- **Services:** `AuditService`, `InventoryService`
- **Utils:** `Validator`