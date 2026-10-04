// Backlog ideas that become entries. When creating an entry could not strike
// the idea through, this offers a reviewed retry.

import { world } from './api.js';
import { button } from './dom.js';
import { addNoticeAction, openEntry, showNotice } from './editor.js';
import { refreshView } from './nav.js';
import { state } from './state.js';

// Open ideas in `ideas` that are still the one the retry is about.
export function matchingIdeas(ideas, prior) {
  return (ideas || []).filter((row) => row.path === prior.path
    && row.expected === prior.expected && !row.done);
}

function noMatchMessage(count) {
  return count
    ? 'Several matching ideas remain. Review the Ideas source manually.'
    : 'The original idea changed or was completed. Review the Ideas source manually.';
}

async function retryStrike(trigger) {
  trigger.disabled = true;
  const prior = state.retryIdea;
  try {
    const data = await world.get('/backlog');
    const matches = matchingIdeas(data.ideas, prior);
    if (matches.length !== 1) {
      showNotice(noMatchMessage(matches.length), true);
      await openEntry(prior.path);
      return;
    }
    const current = matches[0];
    const approved = window.confirm(
      'Current idea source:\n' + current.path + '\n\n- ' + current.expected + '\n\nMark this current idea as started?');
    if (!approved) {
      trigger.disabled = false;
      return;
    }
    await world.post('/backlog/strike', current);
    state.retryIdea = null;
    showNotice('Idea marked as started.');
    refreshView('backlog');
  } catch (error) {
    showNotice(error.message + ' Review the Ideas source manually.', true);
    await openEntry(prior.path);
  }
}

// Adds a "Review and retry idea" button to the current notice.
export function offerIdeaRetry() {
  if (!state.retryIdea) return;
  addNoticeAction(button('Review and retry idea', 'btn btn-small btn-quiet', (event) => retryStrike(event.currentTarget)));
}
