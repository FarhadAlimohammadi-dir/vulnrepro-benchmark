<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FruitDB Inventory</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
<nav class="navbar">
    <div class="nav-brand">🍎 FruitDB Inventory</div>
    <ul class="nav-links">
        <li><a href="/?action=list">Products</a></li>
        <li><a href="/?action=categories">Categories</a></li>
        <li><a href="/?action=profile">Profile</a></li>
        <?php if (isset($_SESSION['username']) && $_SESSION['username'] === 'admin'): ?>
        <li><a href="/?action=audit">Audit Log</a></li>
        <?php endif; ?>
        <li><a href="/?logout=1" class="btn-logout">Logout (<?= htmlspecialchars($_SESSION['username'] ?? '', ENT_QUOTES) ?>)</a></li>
    </ul>
</nav>
<main class="container">
<?php // NOTE: flash message system placeholder — i18n strings pending ?>