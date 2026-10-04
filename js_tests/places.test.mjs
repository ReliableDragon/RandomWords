import test from 'node:test';
import assert from 'node:assert/strict';

import { nextReturnTo, resumesPlace, returnLabel, VIEW_LABELS } from '../static/world/places.js';

test('an action in a view that lands on the desk offers a way back to it', () => {
  assert.equal(nextReturnTo({ from: 'coverage', to: 'desk', via: undefined, current: null }), 'coverage');
  assert.equal(nextReturnTo({ from: 'upkeep', to: 'desk', via: undefined, current: 'coverage' }), 'upkeep');
  assert.equal(nextReturnTo({ from: 'map', to: 'desk', via: undefined, current: null }), 'map');
});

test('picking the Desk tab yourself, or using the chip, clears the chip', () => {
  assert.equal(nextReturnTo({ from: 'coverage', to: 'desk', via: 'tab', current: 'coverage' }), null);
});

test('moving within the desk keeps the chip, and leaving the desk drops it', () => {
  assert.equal(nextReturnTo({ from: 'desk', to: 'desk', via: undefined, current: 'coverage' }), 'coverage');
  assert.equal(nextReturnTo({ from: 'desk', to: 'desk', via: undefined, current: null }), null);
  assert.equal(nextReturnTo({ from: 'desk', to: 'upkeep', via: 'tab', current: 'coverage' }), null);
  assert.equal(nextReturnTo({ from: 'desk', to: 'coverage', via: 'tab', current: 'coverage' }), null);
});

test('an unknown source view gives no chip', () => {
  assert.equal(nextReturnTo({ from: 'nowhere', to: 'desk', via: undefined, current: null }), null);
  assert.equal(nextReturnTo({ from: undefined, to: 'desk', via: undefined, current: null }), null);
});

test('the chip names the view it returns to', () => {
  assert.equal(returnLabel('coverage'), '← Back to Coverage');
  assert.equal(returnLabel('upkeep'), '← Back to Upkeep');
  Object.keys(VIEW_LABELS).forEach((name) => assert.ok(returnLabel(name).length > 8));
});

test('views resume their place on return; a desk visit sent by a view starts fresh', () => {
  assert.equal(resumesPlace({ from: 'desk', to: 'coverage', via: 'tab' }), true);
  assert.equal(resumesPlace({ from: 'desk', to: 'coverage', via: undefined }), true);
  assert.equal(resumesPlace({ from: 'coverage', to: 'desk', via: 'tab' }), true);
  assert.equal(resumesPlace({ from: 'coverage', to: 'desk', via: undefined }), false);
  assert.equal(resumesPlace({ from: 'desk', to: 'desk', via: 'tab' }), false);
});
