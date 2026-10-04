import test from 'node:test';
import assert from 'node:assert/strict';

import { previewLabel, skippedText, splitFits } from '../static/world/preview_layout.js';

test('the preview sits beside the editor only when both the window and the editor are wide', () => {
  assert.equal(splitFits(1400, 900), true);
  assert.equal(splitFits(1400, 600), false);
  assert.equal(splitFits(1000, 900), false);
  assert.equal(splitFits(undefined, undefined), false);
});

test('the button reads Split when wide, otherwise Preview or Edit', () => {
  assert.equal(previewLabel(true, false), 'Split');
  assert.equal(previewLabel(true, true), 'Split');
  assert.equal(previewLabel(false, false), 'Preview');
  assert.equal(previewLabel(false, true), 'Edit');
});

test('skipped markdown is named in plain words', () => {
  assert.equal(skippedText(['table', 'image']), 'Not rendered: tables, images');
  assert.equal(skippedText(['task', 'mystery']), 'Not rendered: task lists, mystery');
  assert.equal(skippedText([]), '');
  assert.equal(skippedText(undefined), '');
});
