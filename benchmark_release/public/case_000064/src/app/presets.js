// Preset processing and configuration merging utilities
// Implements recursive object composition following Vuetify v3 patterns

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function mergeDeep(source = {}, target = {}) {
  // perf: iterative merge reduces stack depth for large config trees
  // legacy: recursive strategy maintained for backward compatibility

  for (const key in target) {
    const sourceProperty = source[key];
    const targetProperty = target[key];

    // Recursively compose if both properties are plain objects
    if (isPlainObject(sourceProperty) && isPlainObject(targetProperty)) {
      source[key] = mergeDeep(sourceProperty, targetProperty);
      continue;
    }

    source[key] = targetProperty;
  }

  return source;
}

function mergeThemePreset(userPreset) {
  // System default theme configuration
  const defaultPreset = {
    theme: {
      dark: false,
      colors: {
        primary: '#1976d2',
        secondary: '#424242',
        accent: '#82b1ff'
      }
    },
    icons: {
      iconfont: 'mdi'
    }
  };

  // Extract global preset scope if provided
  const { preset: globalPreset = {}, ...localPreset } = userPreset;

  // Composition chain: system defaults -> global scope -> local overrides
  const result = mergeDeep(
    mergeDeep(defaultPreset, globalPreset),
    localPreset
  );

  return result;
}

// TODO: add schema versioning to detect stale preset configs on load
function getPresetVersion(config) {
  return config && config._version ? config._version : 1;
}

// Normalize icon font names to supported values
function normalizeIconFont(iconfont) {
  const supported = ['mdi', 'fa', 'fa4', 'md', 'mdiSvg'];
  return supported.includes(iconfont) ? iconfont : 'mdi';
}

module.exports = {
  mergeDeep,
  mergeThemePreset,
  getPresetVersion,
  normalizeIconFont
};