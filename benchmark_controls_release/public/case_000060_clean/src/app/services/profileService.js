// In-memory profile/preferences store.
// TODO: persist to user_prefs table once PORTAL-88 lands; for now this
//       resets on process restart which is acceptable for dev/staging.

const store = new Map();

const DEFAULT_PREFS = {
  displayName: '',
  timezone: 'UTC',
  language: 'en'
};

function getPrefs(userId) {
  return Object.assign({}, DEFAULT_PREFS, store.get(userId) || {});
}

function savePrefs(userId, updates) {
  const existing = store.get(userId) || {};
  store.set(userId, Object.assign({}, existing, updates));
}

module.exports = { getPrefs, savePrefs };