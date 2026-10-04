// Deployment settings for the world desk.
//
// A server-rendered shell can override any of these with a <meta> tag:
//   <meta name="rw-world-api" content="/api/v1/worlds/abc123">
//   <meta name="rw-bench-api" content="/api/v1">
//   <meta name="rw-account-scope" content="u_7f3a">
//   <meta name="rw-world-scope" content="abc123">
// Without the tags the local server's behavior is unchanged.

export const DEFAULT_CONFIG = {
  worldApiBase: '/api/world',
  benchApiBase: '/api',
  // Prefixes for browser-storage keys. See storage.js.
  accountScope: 'local',
  worldScope: 'default',
};

const META_NAMES = {
  worldApiBase: 'rw-world-api',
  benchApiBase: 'rw-bench-api',
  accountScope: 'rw-account-scope',
  worldScope: 'rw-world-scope',
};

function readMeta(doc, name) {
  try {
    const tag = doc.querySelector('meta[name="' + name + '"]');
    const value = tag && tag.getAttribute('content');
    return value && value.trim() ? value.trim() : null;
  } catch (_) {
    return null;
  }
}

function trimTrailingSlash(base) {
  return base.length > 1 ? base.replace(/\/+$/, '') : base;
}

// `doc` is anything with querySelector; null gives the defaults.
export function readConfig(doc) {
  const config = Object.assign({}, DEFAULT_CONFIG);
  if (!doc) return config;
  Object.keys(META_NAMES).forEach((key) => {
    const value = readMeta(doc, META_NAMES[key]);
    if (value) config[key] = value;
  });
  config.worldApiBase = trimTrailingSlash(config.worldApiBase);
  config.benchApiBase = trimTrailingSlash(config.benchApiBase);
  return config;
}

export const config = readConfig(typeof document === 'undefined' ? null : document);
