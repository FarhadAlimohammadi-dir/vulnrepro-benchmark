// userService.js — business logic for user management and content retrieval
// TODO: replace in-memory store with proper ORM once DB migration is complete

const featuredItems = [
  { id: 1, title: 'Getting Started Guide', category: 'docs', views: 1240 },
  { id: 2, title: 'API Reference v2', category: 'docs', views: 980 },
  { id: 3, title: 'Deployment Checklist', category: 'ops', views: 765 },
  { id: 4, title: 'Performance Tuning Tips', category: 'ops', views: 543 },
  { id: 5, title: 'Release Notes 2.1.0', category: 'news', views: 412 },
];

const contentIndex = [
  { id: 101, title: 'Introduction to SSR', type: 'content', tags: ['ssr', 'nodejs'] },
  { id: 102, title: 'Session Management Best Practices', type: 'content', tags: ['sessions', 'auth'] },
  { id: 103, title: 'Load Balancer Configuration', type: 'content', tags: ['ops', 'alb'] },
  { id: 104, title: 'EJS Template Guide', type: 'content', tags: ['templates', 'ejs'] },
  { id: 105, title: 'Express Middleware Patterns', type: 'content', tags: ['express', 'middleware'] },
  { id: 106, title: 'Docker Compose for Development', type: 'content', tags: ['docker', 'dev'] },
  { id: 107, title: 'Role-Based Access Control Overview', type: 'content', tags: ['rbac', 'auth'] },
];

/**
 * Returns the top featured items for the home page.
 * perf: results are static for now; planned to be query-backed in v3
 */
function getFeaturedItems() {
  // TODO: sort by personalisation score once recommendation engine is ready
  return featuredItems.slice(0, 4);
}

/**
 * Simple in-memory search across content index.
 * TODO: wire up to Elasticsearch cluster for full-text search
 */
function search(query, type) {
  const lowerQuery = query.toLowerCase();
  if (type === 'content') {
    return contentIndex.filter(item =>
      item.title.toLowerCase().includes(lowerQuery) ||
      item.tags.some(tag => tag.includes(lowerQuery))
    );
  }
  // legacy: kept for v1 API clients still in the wild
  return [];
}

/**
 * Validates that a role string is one of the known system roles.
 */
function isValidRole(role) {
  const validRoles = ['admin', 'moderator', 'user', 'guest'];
  return validRoles.includes(role);
}

module.exports = {
  getFeaturedItems,
  search,
  isValidRole
};