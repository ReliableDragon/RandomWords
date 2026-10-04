import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ApiError, bench, buildUrl, headers, normalizeResponse, request, setHeadersProvider, unwrap, world,
} from '../static/world/api.js';

// Installs a fake fetch that records calls and answers with `reply`.
function stubFetch(reply) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return typeof reply === 'function' ? reply(url, init) : reply;
  };
  return calls;
}

function jsonReply(status, body) {
  return { status, json: async () => body };
}

test.afterEach(() => {
  delete globalThis.fetch;
  setHeadersProvider(null);
});

test('normalizeResponse reports ok, status, message and data', () => {
  assert.deepEqual(
    normalizeResponse(200, { ok: true, message: 'Loaded.', data: { a: 1 } }),
    { ok: true, status: 200, message: 'Loaded.', data: { a: 1 }, body: { ok: true, message: 'Loaded.', data: { a: 1 } } });
});

test('normalizeResponse treats an ok:false body as a refusal even with status 200', () => {
  assert.equal(normalizeResponse(200, { ok: false, message: 'No.' }).ok, false);
});

test('normalizeResponse treats HTTP errors as refusals and defaults missing pieces', () => {
  const result = normalizeResponse(409, { ok: false, message: 'Conflict.', data: { revision: 'r2' } });
  assert.equal(result.ok, false);
  assert.equal(result.status, 409);
  assert.deepEqual(result.data, { revision: 'r2' });
  const bare = normalizeResponse(500, null);
  assert.deepEqual([bare.ok, bare.message, bare.data], [false, '', {}]);
});

test('unwrap returns data, or the whole body when the route sent no data', () => {
  assert.deepEqual(unwrap(normalizeResponse(200, { ok: true, data: { a: 1 } })), { a: 1 });
  assert.deepEqual(unwrap(normalizeResponse(200, { ok: true, drawn: ['x'] })), { ok: true, drawn: ['x'] });
});

test('unwrap throws an ApiError carrying status and data', () => {
  const refusal = normalizeResponse(409, { ok: false, message: 'Changed.', data: { text: 't' } });
  assert.throws(() => unwrap(refusal), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, 'Changed.');
    assert.equal(error.status, 409);
    assert.deepEqual(error.data, { text: 't' });
    return true;
  });
  assert.throws(() => unwrap(normalizeResponse(503, {})), /Request failed \(503\)\./);
});

test('buildUrl encodes the query and skips empty values', () => {
  assert.equal(buildUrl('/api/world', '/tree'), '/api/world/tree');
  assert.equal(buildUrl('/api/world', '/tree', {}), '/api/world/tree');
  assert.equal(
    buildUrl('/api/world', '/entry', { path: 'People/A & B.md', skip: undefined, none: null, n: 0 }),
    '/api/world/entry?path=People%2FA+%26+B.md&n=0');
});

test('request sends same-origin credentials, JSON headers and the parsed body', async () => {
  const calls = stubFetch(jsonReply(200, { ok: true, message: 'Entry saved.', data: { revision: 'r2' } }));
  const result = await request('POST', '/entry', { body: { path: 'A.md' } });
  assert.equal(calls[0].url, '/api/world/entry');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].init.credentials, 'same-origin');
  assert.equal(calls[0].init.headers['Content-Type'], 'application/json');
  assert.equal(calls[0].init.headers.Accept, 'application/json');
  assert.equal(calls[0].init.body, '{"path":"A.md"}');
  assert.equal(result.status, 200);
  assert.equal(result.message, 'Entry saved.');
  assert.deepEqual(result.data, { revision: 'r2' });
});

test('a GET has no body and no content type', async () => {
  const calls = stubFetch(jsonReply(200, { ok: true, data: {} }));
  await request('GET', '/tree', { query: { path: 'A' } });
  assert.equal(calls[0].url, '/api/world/tree?path=A');
  assert.equal(calls[0].init.body, undefined);
  assert.equal('Content-Type' in calls[0].init.headers, false);
});

test('request resolves with refusals instead of throwing', async () => {
  stubFetch(jsonReply(404, { ok: false, message: 'No such entry.' }));
  const result = await request('GET', '/entry', { query: { path: 'x' } });
  assert.deepEqual([result.ok, result.status, result.message], [false, 404, 'No such entry.']);
});

test('an unreadable response becomes an ApiError with the HTTP status', async () => {
  stubFetch({ status: 502, json: async () => { throw new SyntaxError('bad json'); } });
  await assert.rejects(request('GET', '/tree'), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.message, 'The server returned an unreadable response.');
    assert.equal(error.status, 502);
    return true;
  });
});

test('the headers hook adds headers to every request', async () => {
  setHeadersProvider(() => ({ 'X-CSRFToken': 'abc' }));
  assert.equal(headers(false)['X-CSRFToken'], 'abc');
  const calls = stubFetch(jsonReply(200, { ok: true, data: {} }));
  await world.get('/tree');
  assert.equal(calls[0].init.headers['X-CSRFToken'], 'abc');
  assert.equal(calls[0].init.headers.Accept, 'application/json');
});

test('the world and bench clients use their own bases', async () => {
  const calls = stubFetch(jsonReply(200, { ok: true, data: { drawn: ['a'] } }));
  assert.deepEqual(await world.get('/search', { q: 'ada' }), { drawn: ['a'] });
  assert.deepEqual(await bench.post('/draw', { count: 2 }), { drawn: ['a'] });
  assert.equal(calls[0].url, '/api/world/search?q=ada');
  assert.equal(calls[1].url, '/api/draw');
  assert.equal(calls[1].init.body, '{"count":2}');
});

test('client errors carry the server message, status and data', async () => {
  stubFetch(jsonReply(409, { ok: false, message: 'Changed on disk.', data: { text: 'disk', revision: 'r9' } }));
  await assert.rejects(world.post('/entry', { path: 'A.md' }), (error) => {
    assert.equal(error.status, 409);
    assert.equal(error.data.revision, 'r9');
    assert.equal(error.message, 'Changed on disk.');
    return true;
  });
});

test('posting without a body still sends an empty JSON object', async () => {
  const calls = stubFetch(jsonReply(200, { ok: true, data: {} }));
  await world.post('/roll');
  assert.equal(calls[0].init.body, '{}');
});
