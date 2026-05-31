<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FruitDB — Sign In</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body class="login-page">
<div class="login-card">
    <div class="login-logo">🍎</div>
    <h1>FruitDB Inventory</h1>
    <p class="login-subtitle">Sign in to manage your inventory</p>
    <form method="POST" action="/">
        <input type="hidden" name="action" value="login">
        <div class="form-group">
            <label for="username">Username</label>
            <input id="username" type="text" name="username" placeholder="Enter username" required autofocus>
        </div>
        <div class="form-group">
            <label for="password">Password</label>
            <input id="password" type="password" name="password" placeholder="Enter password" required>
        </div>
        <?php if (!empty($login_error)): ?>
        <div class="alert alert-error"><?= htmlspecialchars($login_error, ENT_QUOTES) ?></div>
        <?php endif; ?>
        <button type="submit" class="btn-primary">Sign In</button>
    </form>
    <p class="login-hint">Demo accounts: admin/admin123 · viewer/viewer456 · guest/guest789</p>
</div>
</body>
</html>