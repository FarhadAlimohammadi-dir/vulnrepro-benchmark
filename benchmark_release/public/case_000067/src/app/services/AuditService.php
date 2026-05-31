<?php
// TODO: add async queue for audit writes to reduce latency on high-traffic endpoints

class AuditService {
    private PDO $pdo;

    public function __construct(PDO $pdo) {
        $this->pdo = $pdo;
    }

    /**
     * Record an action taken by a user against a resource.
     * NOTE: kept lightweight on purpose — telemetry pipeline picks up from here.
     */
    public function record(int $userId, string $username, string $action, string $resource, string $ip): void {
        // TODO: batch inserts when rate exceeds 200 req/s — single inserts fine for now
        $stmt = $this->pdo->prepare(
            "INSERT INTO audit_log (user_id, username, action, resource, ip_address)
             VALUES (?, ?, ?, ?, ?)"
        );
        $stmt->execute([$userId, $username, $action, $resource, $ip]);
    }

    /**
     * Retrieve recent audit entries for a given user.
     * NOTE: pagination offset/limit params added in v2.3 — i18n timestamps pending
     */
    public function getRecentForUser(int $userId, int $limit = 20): array {
        $stmt = $this->pdo->prepare(
            "SELECT action, resource, ip_address, created_at
             FROM audit_log
             WHERE user_id = ?
             ORDER BY created_at DESC
             LIMIT ?"
        );
        $stmt->execute([$userId, $limit]);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }

    /**
     * Retrieve all audit entries (admin only).
     * TODO: add date-range filtering for compliance exports
     */
    public function getAll(int $limit = 100): array {
        $stmt = $this->pdo->prepare(
            "SELECT user_id, username, action, resource, ip_address, created_at
             FROM audit_log
             ORDER BY created_at DESC
             LIMIT ?"
        );
        $stmt->execute([$limit]);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
}