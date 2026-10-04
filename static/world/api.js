// The only module that calls fetch().
//
// request() resolves to the parsed envelope {ok, status, message, data} for
// any answer the server gives, including refusals. The world/bench clients
// below are the convenient form: they resolve to the data and throw an
// ApiError (with .status and .data) when the server says no.

import { config } from './config.js';

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data || {};
  }
}

let headerProvider = null;

// Future hosted shells register a function returning extra headers, such as
// a CSRF token. It is called for every request.
export function setHeadersProvider(provider) {
  headerProvider = typeof provider === 'function' ? provider : null;
}

export function headers(hasBody) {
  const result = { Accept: 'application/json' };
  if (hasBody) result['Content-Type'] = 'application/json';
  return Object.assign(result, headerProvider ? headerProvider() : {});
}

export function buildUrl(base, path, query) {
  const params = new URLSearchParams();
  Object.keys(query || {}).forEach((key) => {
    const value = query[key];
    if (value !== undefined && value !== null) params.set(key, String(value));
  });
  const text = params.toString();
  return base + path + (text ? '?' + text : '');
}

// Turns an HTTP status and parsed JSON body into the envelope.
export function normalizeResponse(status, body) {
  const parsed = body && typeof body === 'object' ? body : {};
  const httpOk = status >= 200 && status < 300;
  return {
    ok: httpOk && parsed.ok !== false,
    status,
    message: typeof parsed.message === 'string' ? parsed.message : '',
    data: parsed.data == null ? {} : parsed.data,
    // Some routes answer without a data wrapper; unwrap() falls back to this.
    body: parsed,
  };
}

// `base` is a full prefix such as '/api/world'; `path` starts with '/'.
export async function request(method, path, options) {
  const opts = options || {};
  const hasBody = opts.body !== undefined;
  const response = await fetch(buildUrl(opts.base || config.worldApiBase, path, opts.query), {
    method,
    headers: headers(hasBody),
    credentials: 'same-origin',
    body: hasBody ? JSON.stringify(opts.body) : undefined,
  });
  let parsed;
  try {
    parsed = await response.json();
  } catch (_) {
    throw new ApiError('The server returned an unreadable response.', response.status);
  }
  return normalizeResponse(response.status, parsed);
}

export function unwrap(result) {
  if (result.ok) return result.body.data == null ? result.body : result.data;
  throw new ApiError(result.message || 'Request failed (' + result.status + ').', result.status, result.data);
}

function client(baseKey) {
  const base = () => config[baseKey];
  return {
    async get(path, query) {
      return unwrap(await request('GET', path, { base: base(), query }));
    },
    async post(path, body, query) {
      return unwrap(await request('POST', path, { base: base(), query, body: body || {} }));
    },
  };
}

// Vault routes, e.g. world.get('/entry', { path }).
export const world = client('worldApiBase');
// Word-bench routes, e.g. bench.post('/draw', { count }).
export const bench = client('benchApiBase');
