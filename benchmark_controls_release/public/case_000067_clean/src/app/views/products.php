<?php include __DIR__ . '/layout.php'; ?>
<h2>Product Inventory</h2>
<!-- TODO: add column sort controls — currently sorted by name ascending -->
<div class="toolbar">
    <form method="GET" action="/" class="search-bar">
        <input type="hidden" name="action" value="search">
        <input type="text" name="name" placeholder="Search by name..." value="<?= htmlspecialchars($_GET['name'] ?? '', ENT_QUOTES) ?>">
        <button type="submit">Search</button>
    </form>
    <form method="GET" action="/" class="search-bar">
        <input type="hidden" name="action" value="filter">
        <input type="text" name="sku" placeholder="Filter by SKU..." value="<?= htmlspecialchars($_GET['sku'] ?? '', ENT_QUOTES) ?>">
        <button type="submit">Filter</button>
    </form>
</div>
<table class="data-table">
    <thead>
        <tr>
            <th>#</th>
            <th>Name</th>
            <th>SKU</th>
            <th>Category</th>
            <th>Price</th>
            <th>Stock</th>
            <th>Supplier</th>
            <th>Organic</th>
        </tr>
    </thead>
    <tbody>
    <?php foreach ($products as $p): ?>
        <tr>
            <td><?= (int)$p['id'] ?></td>
            <td><?= htmlspecialchars($p['name'], ENT_QUOTES) ?></td>
            <td><?= htmlspecialchars($p['sku'], ENT_QUOTES) ?></td>
            <td><?= htmlspecialchars($p['category'] ?? '', ENT_QUOTES) ?></td>
            <td>$<?= number_format((float)$p['unit_price'], 2) ?></td>
            <td><?= (int)$p['stock_qty'] ?></td>
            <td><?= htmlspecialchars($p['supplier'] ?? '', ENT_QUOTES) ?></td>
            <td><?= $p['is_organic'] ? '✓' : '—' ?></td>
        </tr>
    <?php endforeach; ?>
    </tbody>
</table>
<div class="pagination">
    <?php if ($page > 1): ?>
        <a href="/?action=list&page=<?= $page - 1 ?>">&laquo; Prev</a>
    <?php endif; ?>
    <span>Page <?= (int)$page ?> of <?= (int)$totalPages ?></span>
    <?php if ($page < $totalPages): ?>
        <a href="/?action=list&page=<?= $page + 1 ?>">Next &raquo;</a>
    <?php endif; ?>
</div>
</main>
</body>
</html>