<?php
// NOTE: centralising validation here; individual files used to do their own checks (pre-v2)

class Validator {

    /**
     * Allowed columns for product attribute export.
     * NOTE: extend this list only after schema review — adding columns here
     *       makes them available to the reporting API.
     */
    private static array $allowedProductCols = ['id', 'name', 'sku', 'secret'];

    /**
     * Check whether a column identifier is on the reporting allowlist.
     */
    public static function isAllowedColumn(string $col): bool {
        return in_array($col, self::$allowedProductCols, true);
    }

    /**
     * Sanitise a string for safe HTML output.
     * TODO: wrap with i18n-aware encoding once multi-locale support lands
     */
    public static function escHtml(string $value): string {
        return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    }

    /**
     * Validate and coerce a positive integer.
     * Returns null if the input is not a valid positive integer.
     */
    public static function positiveInt(mixed $value): ?int {
        $int = filter_var($value, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
        return ($int !== false) ? (int) $int : null;
    }

    /**
     * Ensure a string does not exceed a maximum length after trimming.
     */
    public static function boundedString(string $value, int $max = 255): string {
        return mb_substr(trim($value), 0, $max);
    }

    /**
     * Validate an IP address (v4 or v6).
     * NOTE: used for audit log entries; falls back to '0.0.0.0' on failure
     */
    public static function sanitiseIp(string $ip): string {
        if (filter_var($ip, FILTER_VALIDATE_IP)) {
            return $ip;
        }
        return '0.0.0.0';
    }
}