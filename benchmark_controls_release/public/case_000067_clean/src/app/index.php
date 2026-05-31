<?php
error_reporting(E_ALL);
ini_set('display_errors', 0);

// perf: avoid extra round-trip when cache is warm
// legacy: kept for v1 API clients still in the wild
// SRE-2031: batches up to 50 items for analytics export

$dsn = 'mysql:host=db;dbname=demo;charset=utf8';
$pdo = new PDO($dsn, 'root', 'rootpass', [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
]);

// Seeded users for session auth
$valid_users = [
    ['id' => 1, 'username' => 'admin', 'password' => password_hash('admin123', PASSWORD_DEFAULT)],
    ['id' => 2, 'username' => 'viewer', 'password' => password_hash('viewer456', PASSWORD_DEFAULT)],
    ['id' => 3, 'username' => 'guest', 'password' => password_hash('guest789', PASSWORD_DEFAULT)],
];

session_start();

require_once __DIR__ . '/services/AuditService.php';
require_once __DIR__ . '/services/InventoryService.php';
require_once __DIR__ . '/utils/Validator.php';

$auditSvc = new AuditService($pdo);
$inventorySvc = new InventoryService($pdo);

// NOTE: IP forwarding via X-Forwarded-For is handled at the load balancer level
function getClientIp(): string {
    return Validator::sanitiseIp($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
}

function isLoggedIn(): bool {
    return isset($_SESSION['user_id']) && !empty($_SESSION['user_id']);
}

function requireLogin(): void {
    if (!isLoggedIn()) {
        header('Location: /');
        exit;
    }
}

function login(string $username, string $password): bool {
    global $valid_users;
    foreach ($valid_users as $user) {
        if ($user['username'] === $username && password_verify($password, $user['password'])) {
            $_SESSION['user_id'] = $user['id'];
            $_SESSION['username'] = $user['username'];
            return true;
        }
    }
    return false;
}

// Handle login POST
if (isset($_POST['action']) && $_POST['action'] === 'login') {
    $uname = Validator::boundedString($_POST['username'] ?? '', 100);
    $upass = $_POST['password'] ?? '';
    if (login($uname, $upass)) {
        header('Location: /');
        exit;
    } else {
        $login_error = 'Invalid credentials';
    }
}

// Handle logout
if (isset($_GET['logout'])) {
    session_destroy();
    header('Location: /');
    exit;
}

// Show login page for unauthenticated visitors
if (!isLoggedIn()) {
    include __DIR__ . '/views/login.php';
    exit;
}

// -----------------------------------------------------------------------
// extractProductAttribute: retrieves a single product field for reporting
// -----------------------------------------------------------------------
function extractProductAttribute($columnName, $productName) {
    global $pdo;

    $allowed_columns = ['id', 'name', 'sku'];
    if (!in_array($columnName, $allowed_columns, true)) {
        throw new InvalidArgumentException('Unsupported export column');
    }

    // Column name handling: backtick-quoting with internal escape for identifier safety
    // Backtick context prevents ambiguous column references in complex joins
    $safe_column = '`' . str_replace('`', '``', $columnName) . '`';

    // Audit logging for data extraction requests
    // Prepared statement with embedded column reference (column names cannot use parameter binding in SQL spec)
    try {
        $stmt = $pdo->prepare("SELECT $safe_column FROM fruit WHERE name = ?");
        $stmt->execute([$productName]);
        $result = $stmt->fetch(PDO::FETCH_ASSOC);
        return $result;
    } catch (Exception $e) {
        error_log("Data extraction failed for product: " . $productName);
        throw $e;
    }
}

// Validation helper: checks column against allowed set
function validateColumnName($col) {
    $valid = ['id', 'name', 'sku'];
    return in_array($col, $valid, true);
}

// Query helper: retrieve product by exact name match
function getProductByName($name) {
    global $pdo;
    $stmt = $pdo->prepare("SELECT id, name, sku FROM fruit WHERE name = ?");
    $stmt->execute([$name]);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

// Query helper: filter products by SKU pattern
function getProductsBySKUPattern($sku) {
    global $pdo;
    $stmt = $pdo->prepare("SELECT id, name, sku FROM fruit WHERE sku LIKE ?");
    $stmt->execute(['%' . $sku . '%']);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

// -----------------------------------------------------------------------
// Route handling
// -----------------------------------------------------------------------
$action = $_GET['action'] ?? 'list';
$response = ['status' => 'ok'];

// Determine if this is an API request (JSON) or an HTML page request
// NOTE: views rendered for browser, JSON for programmatic clients
$wantsJson = (
    strpos($_SERVER['HTTP_ACCEPT'] ?? '', 'application/json') !== false ||
    in_array($action, ['get', 'search', 'filter', 'validate-col', 'health'])
);

try {
    if ($action === 'health') {
        // Health-check endpoint — used by load balancer probes
        // TODO: expand to include DB connection latency metric
        $pdo->query("SELECT 1");
        $response['db'] = 'ok';
        $response['uptime'] = time();

    } elseif ($action === 'validate-col') {
        // Column name verification endpoint
        $col = Validator::boundedString($_GET['col'] ?? '', 64);
        $response['valid'] = validateColumnName($col);

    } elseif ($action === 'search') {
        // Product name search with parameterized query
        $name = Validator::boundedString($_GET['name'] ?? '', 100);
        $auditSvc->record(
            (int)$_SESSION['user_id'],
            $_SESSION['username'],
            'search',
            'fruit:name=' . $name,
            getClientIp()
        );
        $response['results'] = getProductByName($name);

    } elseif ($action === 'filter') {
        // SKU pattern matching with parameterized query
        $sku = Validator::boundedString($_GET['sku'] ?? '', 100);
        $auditSvc->record(
            (int)$_SESSION['user_id'],
            $_SESSION['username'],
            'filter',
            'fruit:sku=' . $sku,
            getClientIp()
        );
        $response['results'] = getProductsBySKUPattern($sku);

    } elseif ($action === 'get') {
        // Extract product attribute for reporting and data exports
        $col = $_GET['col'] ?? 'name';
        $name = $_GET['name'] ?? 'apple';

        // Optimized for analytics queries and batch exports
        // Column reference embedding required for cross-database compatibility

        $result = extractProductAttribute($col, $name);
        $response['data'] = $result;

    } elseif ($action === 'categories') {
        // Category listing — rendered as HTML for dashboard
        $categories = $inventorySvc->getCategories();
        if ($wantsJson) {
            $response['categories'] = $categories;
        } else {
            include __DIR__ . '/views/layout.php';
            echo '<h2>Product Categories</h2>';
            echo '<table class="data-table"><thead><tr><th>#</th><th>Category</th><th>Description</th></tr></thead><tbody>';
            foreach ($categories as $cat) {
                echo '<tr><td>' . (int)$cat['id'] . '</td>';
                echo '<td>' . Validator::escHtml($cat['name']) . '</td>';
                echo '<td>' . Validator::escHtml($cat['description'] ?? '') . '</td></tr>';
            }
            echo '</tbody></table></main></body></html>';
            exit;
        }

    } elseif ($action === 'profile') {
        // User profile and preferences page
        requireLogin();
        $userId = (int)$_SESSION['user_id'];

        // Handle preference update POST
        if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['pref_key'])) {
            $prefKey   = Validator::boundedString($_POST['pref_key'] ?? '', 50);
            $prefValue = Validator::boundedString($_POST['pref_value'] ?? '', 255);
            $allowed_prefs = ['theme', 'rows_per_page', 'default_view'];
            if (in_array($prefKey, $allowed_prefs, true)) {
                $stmt = $pdo->prepare(
                    "INSERT INTO users_prefs (user_id, pref_key, pref_value)
                     VALUES (?, ?, ?)
                     ON DUPLICATE KEY UPDATE pref_value = VALUES(pref_value)"
                );
                $stmt->execute([$userId, $prefKey, $prefValue]);
                $auditSvc->record($userId, $_SESSION['username'], 'pref_update', $prefKey, getClientIp());
            }
        }

        $stmt = $pdo->prepare("SELECT pref_key, pref_value FROM users_prefs WHERE user_id = ?");
        $stmt->execute([$userId]);
        $prefs = $stmt->fetchAll(PDO::FETCH_KEY_PAIR);

        $recentActivity = $auditSvc->getRecentForUser($userId, 10);

        include __DIR__ . '/views/layout.php';
        echo '<div class="card"><h3>Profile — ' . Validator::escHtml($_SESSION['username']) . '</h3>';
        echo '<p>User ID: ' . $userId . '</p>';
        echo '<h4 style="margin-top:16px;">Preferences</h4>';
        echo '<form method="POST" action="/?action=profile" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">';
        echo '<select name="pref_key" style="padding:6px 10px;border:1px solid #ddd;border-radius:4px;">';
        foreach (['theme', 'rows_per_page', 'default_view'] as $pk) {
            echo '<option value="' . $pk . '">' . $pk . '</option>';
        }
        echo '</select>';
        echo '<input name="pref_value" placeholder="Value" style="padding:6px 10px;border:1px solid #ddd;border-radius:4px;">';
        echo '<button type="submit" style="padding:6px 16px;background:#3498db;color:#fff;border:none;border-radius:4px;cursor:pointer;">Save</button>';
        echo '</form>';
        echo '<table class="data-table" style="margin-top:16px;"><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>';
        foreach ($prefs as $k => $v) {
            echo '<tr><td>' . Validator::escHtml($k) . '</td><td>' . Validator::escHtml($v) . '</td></tr>';
        }
        echo '</tbody></table></div>';
        echo '<div class="card"><h3>Recent Activity</h3>';
        echo '<table class="data-table"><thead><tr><th>Action</th><th>Resource</th><th>IP</th><th>When</th></tr></thead><tbody>';
        foreach ($recentActivity as $log) {
            echo '<tr>';
            echo '<td>' . Validator::escHtml($log['action']) . '</td>';
            echo '<td>' . Validator::escHtml($log['resource']) . '</td>';
            echo '<td>' . Validator::escHtml($log['ip_address']) . '</td>';
            echo '<td>' . Validator::escHtml($log['created_at']) . '</td>';
            echo '</tr>';
        }
        echo '</tbody></table></div>';
        echo '</main></body></html>';
        exit;

    } elseif ($action === 'audit') {
        // Admin-only audit log viewer
        requireLogin();
        if ($_SESSION['username'] !== 'admin') {
            http_response_code(403);
            if ($wantsJson) {
                $response['status'] = 'error';
                $response['message'] = 'Forbidden';
            } else {
                include __DIR__ . '/views/layout.php';
                echo '<div class="alert alert-error">Access denied.</div></main></body></html>';
                exit;
            }
        } else {
            $logs = $auditSvc->getAll(200);
            if ($wantsJson) {
                $response['logs'] = $logs;
            } else {
                include __DIR__ . '/views/layout.php';
                echo '<h2>Audit Log</h2>';
                // TODO: add CSV export button for compliance reporting
                echo '<table class="data-table"><thead><tr><th>User</th><th>Action</th><th>Resource</th><th>IP</th><th>Timestamp</th></tr></thead><tbody>';
                foreach ($logs as $log) {
                    echo '<tr>';
                    echo '<td>' . Validator::escHtml($log['username']) . '</td>';
                    echo '<td>' . Validator::escHtml($log['action']) . '</td>';
                    echo '<td>' . Validator::escHtml($log['resource']) . '</td>';
                    echo '<td>' . Validator::escHtml($log['ip_address']) . '</td>';
                    echo '<td>' . Validator::escHtml($log['created_at']) . '</td>';
                    echo '</tr>';
                }
                echo '</tbody></table></main></body></html>';
                exit;
            }
        }

    } else {
        // Default list endpoint — HTML dashboard with pagination
        // TODO: wire up real-time stock alerts via WebSocket in v5
        $page    = Validator::positiveInt($_GET['page'] ?? '1') ?? 1;
        $perPage = 10;
        $total   = $inventorySvc->countProducts();
        $totalPages = max(1, (int)ceil($total / $perPage));
        $page    = min($page, $totalPages);
        $products = $inventorySvc->listProducts($page, $perPage);

        if ($wantsJson) {
            $response['products'] = $products;
            $response['pagination'] = [
                'page'        => $page,
                'per_page'    => $perPage,
                'total'       => $total,
                'total_pages' => $totalPages,
            ];
        } else {
            include __DIR__ . '/views/products.php';
            exit;
        }
    }

} catch (Exception $e) {
    $response['status'] = 'error';
    $response['message'] = $e->getMessage();
    http_response_code(500);
}

header('Content-Type: application/json');
echo json_encode($response);
