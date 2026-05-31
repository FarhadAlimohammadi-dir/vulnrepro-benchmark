const crypto = require('crypto');

const adminPassword = process.env.ADMIN_PASSWORD || crypto.randomBytes(24).toString('hex');

const users = [
  { id: 1, username: 'admin', email: 'admin@example.com', password: adminPassword, role: 'admin' },
  { id: 2, username: 'user', email: 'user@example.com', password: 'user123', role: 'user' },
  { id: 3, username: 'demo', email: 'demo@example.com', password: 'demo123', role: 'viewer' },
];

function authenticate(username, password) {
  return users.find((user) => user.username === username && user.password === password) || null;
}

function listUsers() {
  return users.map(({ password, ...user }) => user);
}

function findUserById(id) {
  const numericId = Number(id);
  const user = users.find((item) => item.id === numericId);
  if (!user) return null;
  const { password, ...safeUser } = user;
  return safeUser;
}

function getDashboardStats(userId) {
  return {
    active_projects: userId === 1 ? 12 : 3,
    open_tasks: userId === 1 ? 48 : 9,
    completed_tasks: userId === 1 ? 314 : 27,
  };
}

module.exports = {
  authenticate,
  findUserById,
  getDashboardStats,
  listUsers,
};
