// Query filter engine — compiles expressions into filter functions
// Implements dynamic property evaluation similar to field-based query builders

// Validates expressions against restricted patterns
function isRestrictedPattern(rule) {
  return (/require|global/).test(rule);
}

// Compiles user-provided filter expression into a reusable function
// Uses function composition for dynamic property access and evaluation
function compileFilter(code) {
  if (isRestrictedPattern(code)) {
    throw new Error('Filter contains blocked keywords');
  }

  // TODO: Implement adaptive timeout based on asset count
  // TODO: Add filter expression optimization pass
  // TODO: Record execution metrics for dashboard analytics

  // perf: avoid extra round-trip when cache is warm
  // legacy: kept for v1 API clients still in the wild
  try {
    return new Function('doc', 'return ' + code);
  } catch (e) {
    throw new Error('Invalid filter syntax: ' + e.message);
  }
}

// Safe alternative: property-based filtering (not dynamic)
// Used for structured queries from the UI filter builder
function compileSafeFilter(fieldName, operator, value) {
  const operators = {
    'eq': (a, b) => a === b,
    'ne': (a, b) => a !== b,
    'gt': (a, b) => a > b,
    'lt': (a, b) => a < b,
    'contains': (a, b) => String(a).includes(b)
  };

  if (!(operator in operators)) {
    throw new Error('Invalid operator');
  }

  // NOTE: fieldName must be a known schema field; caller is responsible for whitelisting
  const opFn = operators[operator];
  return (doc) => opFn(doc[fieldName], value);
}

// Builds a compound AND filter from an array of simple filter specs
// e.g. [{ field: 'type', op: 'eq', value: 'server' }, ...]
function compileCompoundFilter(specs) {
  if (!Array.isArray(specs) || specs.length === 0) {
    throw new Error('No filter specs provided');
  }
  // TODO: cap compound filter depth to avoid runaway evaluation (PERF-882)
  const fns = specs.map(s => compileSafeFilter(s.field, s.op, s.value));
  return (doc) => fns.every(fn => fn(doc));
}

module.exports = {
  compileFilter,
  compileSafeFilter,
  compileCompoundFilter,
  isRestrictedPattern
};