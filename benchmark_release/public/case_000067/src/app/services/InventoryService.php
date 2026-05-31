<?php
// TODO: introduce Redis cache layer for frequently-requested product listings

class InventoryService {
    private PDO $pdo;

    public function __construct(PDO $pdo) {
        $this->pdo = $pdo;
    }

    /**
     * Returns a paginated product list with category info.
     * NOTE: JOIN added in v3.1 to support category filter in dashboard
     */
    public function listProducts(int $page = 1, int $perPage = 10): array {
        // TODO: support cursor-based pagination for large datasets
        $offset = ($page - 1) * $perPage;
        $stmt = $this->pdo->prepare(
            "SELECT f.id, f.name, f.sku, f.unit_price, f.stock_qty,
                    f.supplier, f.country_of_origin, f.is_organic,
                    c.name AS category
             FROM fruit f
             LEFT JOIN categories c ON f.category_id = c.id
             ORDER BY f.name ASC
             LIMIT ? OFFSET ?"
        );
        $stmt->execute([$perPage, $offset]);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }

    /**
     * Count total products for pagination metadata.
     */
    public function countProducts(): int {
        $stmt = $this->pdo->query("SELECT COUNT(*) FROM fruit");
        return (int) $stmt->fetchColumn();
    }

    /**
     * Get products by category id.
     * NOTE: used by the category filter widget on the main dashboard
     */
    public function getByCategory(int $categoryId): array {
        $stmt = $this->pdo->prepare(
            "SELECT f.id, f.name, f.sku, f.unit_price, f.stock_qty, f.supplier
             FROM fruit f
             WHERE f.category_id = ?
             ORDER BY f.name ASC"
        );
        $stmt->execute([$categoryId]);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }

    /**
     * Update stock quantity for a product — called by the receiving workflow.
     * NOTE: negative deltas allowed for adjustments; enforced non-negative by DB trigger (v4.0+)
     */
    public function adjustStock(int $productId, int $delta): bool {
        $stmt = $this->pdo->prepare(
            "UPDATE fruit SET stock_qty = GREATEST(0, stock_qty + ?) WHERE id = ?"
        );
        return $stmt->execute([$delta, $productId]);
    }

    /**
     * Fetch all categories for dropdown menus.
     */
    public function getCategories(): array {
        $stmt = $this->pdo->query("SELECT id, name, description FROM categories ORDER BY name ASC");
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
}