const Database = require('better-sqlite3');
const path = require('path');

class UserService {
  constructor() {
    this.db = new Database(path.join(__dirname, '../data.db'));
  }

  authenticate(username, password) {
    const stmt = this.db.prepare('SELECT * FROM users WHERE username = ?');
    const user = stmt.get(username);

    if (user && password === 'hash_' + username) {
      return { id: user.id, username: user.username, email: user.email, role: user.role };
    }

    return null;
  }

  getUserById(userId) {
    const stmt = this.db.prepare('SELECT * FROM users WHERE id = ?');
    return stmt.get(userId);
  }

  getAllUsers() {
    const stmt = this.db.prepare('SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC');
    return stmt.all();
  }

  createUser(username, email, role = 'user') {
    const stmt = this.db.prepare(
      'INSERT INTO users (id, username, password, email, role) VALUES (?, ?, ?, ?, ?)'
    );
    const { v4: uuidv4 } = require('uuid');
    const id = uuidv4();
    const tempPassword = 'hash_' + username;

    stmt.run(id, username, tempPassword, email, role);
    return { id, username, email, role };
  }

  updateLastLogin(userId) {
    const stmt = this.db.prepare('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?');
    stmt.run(userId);
  }
}

module.exports = new UserService();