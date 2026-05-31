CREATE DATABASE IF NOT EXISTS demo;
USE demo;

DROP TABLE IF EXISTS fruit;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS users_prefs;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fruit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sku VARCHAR(100) NOT NULL,
    category_id INT DEFAULT 1,
    unit_price DECIMAL(10,2) DEFAULT 0.00,
    stock_qty INT DEFAULT 0,
    supplier VARCHAR(150),
    country_of_origin VARCHAR(100),
    is_organic TINYINT(1) DEFAULT 0,
    secret VARCHAR(255)
);

CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    username VARCHAR(100),
    action VARCHAR(100),
    resource VARCHAR(255),
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users_prefs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    pref_key VARCHAR(100),
    pref_value VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO categories (name, description) VALUES
    ('Tropical', 'Fruits grown in tropical climates'),
    ('Citrus', 'Citrus family fruits'),
    ('Stone Fruit', 'Fruits with a stone/pit center'),
    ('Berry', 'Small pulpy fruits'),
    ('Pome', 'Core fruits like apples and pears');

INSERT INTO fruit (name, sku, category_id, unit_price, stock_qty, supplier, country_of_origin, is_organic, secret) VALUES
    ('apple', 'FRU-APL-001', 5, 1.20, 500, 'GreenHarvest Co.', 'USA', 1, 'sample_token_redacted'),
    ('banana', 'FRU-BAN-002', 1, 0.50, 1200, 'TropicFresh Ltd.', 'Ecuador', 0, 'internal_secret_banana_supply'),
    ('cherry', 'FRU-CHE-003', 3, 3.50, 200, 'OrchardPeak Inc.', 'Turkey', 1, 'internal_secret_cherry_supply'),
    ('orange', 'FRU-ORG-004', 2, 0.90, 800, 'CitrusWorld S.A.', 'Spain', 0, 'internal_secret_orange_supply'),
    ('mango', 'FRU-MNG-005', 1, 1.80, 350, 'TropicFresh Ltd.', 'India', 0, 'internal_secret_mango_supply'),
    ('grape', 'FRU-GRP-006', 4, 2.10, 600, 'VineSelect GmbH', 'Italy', 1, 'internal_secret_grape_supply'),
    ('strawberry', 'FRU-STR-007', 4, 4.20, 150, 'BerryFarm LLC', 'USA', 1, 'internal_secret_strawberry_supply'),
    ('pineapple', 'FRU-PIN-008', 1, 2.50, 90, 'TropicFresh Ltd.', 'Costa Rica', 0, 'internal_secret_pineapple_supply'),
    ('pear', 'FRU-PER-009', 5, 1.10, 420, 'GreenHarvest Co.', 'Belgium', 0, 'internal_secret_pear_supply'),
    ('peach', 'FRU-PCH-010', 3, 2.80, 130, 'OrchardPeak Inc.', 'USA', 1, 'internal_secret_peach_supply'),
    ('plum', 'FRU-PLM-011', 3, 1.95, 210, 'OrchardPeak Inc.', 'Chile', 0, 'internal_secret_plum_supply'),
    ('watermelon', 'FRU-WTR-012', 1, 5.00, 60, 'SunGrove Farms', 'Mexico', 0, 'internal_secret_watermelon_supply'),
    ('blueberry', 'FRU-BLU-013', 4, 6.50, 95, 'BerryFarm LLC', 'Canada', 1, 'internal_secret_blueberry_supply'),
    ('kiwi', 'FRU-KIW-014', 1, 1.60, 340, 'PacificFresh NZ', 'New Zealand', 1, 'internal_secret_kiwi_supply'),
    ('lemon', 'FRU-LEM-015', 2, 0.70, 700, 'CitrusWorld S.A.', 'Argentina', 0, 'internal_secret_lemon_supply');

INSERT INTO users_prefs (user_id, pref_key, pref_value) VALUES
    (1, 'theme', 'dark'),
    (1, 'rows_per_page', '25'),
    (1, 'default_view', 'grid'),
    (2, 'theme', 'light'),
    (2, 'rows_per_page', '10'),
    (3, 'theme', 'light'),
    (3, 'rows_per_page', '50');