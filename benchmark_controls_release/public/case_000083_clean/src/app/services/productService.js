const db = require('../db');

// TODO: cache popular category listings in Redis (perf ticket MKTPL-302)
// NOTE: price data not yet stored in DB; will be added in schema v2

const getCategoryProducts = (categoryId, page = 1, limit = 20) => {
  return db.listProducts({ page, limit, categoryId });
};

const searchProducts = (query, maxResults = 50) => {
  if (!query || query.trim().length === 0) return [];
  const results = db.search(query.trim());
  return results.slice(0, maxResults);
};

const getProductDetail = (productId) => {
  return db.getProduct(productId);
};

module.exports = { getCategoryProducts, searchProducts, getProductDetail };