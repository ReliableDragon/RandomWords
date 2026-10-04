// Keeps the report views in step with the vault.
//
// Every report remembers the index generation it loaded with. When the server
// reports a newer one (this page saved a note, another tab or an editor
// changed a file), the visible report reloads in place and the hidden ones
// reload when next shown.

import { world } from './api.js';
import { backlog } from './backlog.js';
import { coverage } from './coverage.js';
import { on, Events } from './events.js';
import { lexicon } from './lexicon.js';
import { activeView } from './nav.js';
import { story } from './story.js';
import { upkeep } from './upkeep.js';

const POLL_MS = 20000;
const FOCUS_GAP_MS = 2000;
const NOTE_MS = 4000;

const VIEWS = { story, coverage, upkeep, lexicon, backlog };

// What to do for each view given the server's generation: 'reload' the one
// on screen, 'invalidate' the hidden ones, nothing for views that are in
// step or never loaded. `views` maps name -> {generation()}.
export function freshnessPlan(views, current, active) {
  const plan = {};
  Object.keys(views).forEach((name) => {
    const loaded = views[name].generation();
    if (loaded == null || current == null || loaded === current) return;
    plan[name] = name === active ? 'reload' : 'invalidate';
  });
  return plan;
}

function showNote(name) {
  const note = typeof document !== 'undefined' && document.querySelector
    ? document.querySelector('[data-fresh-note="' + name + '"]') : null;
  if (!note) return;
  note.textContent = 'Updated';
  note.hidden = false;
  setTimeout(() => {
    note.textContent = '';
    note.hidden = true;
  }, NOTE_MS);
}

let checking = false;
let recheck = false;
let lastCheck = 0;

// Compares the server's generation with each view and applies the plan. A
// request that arrives while a check is in flight (a save right after a
// poll) may have missed that check's answer, so it asks for one more run.
export async function checkFreshness(views) {
  if (checking) {
    recheck = true;
    return {};
  }
  checking = true;
  lastCheck = Date.now();
  try {
    const status = await world.get('/status');
    const plan = freshnessPlan(views || VIEWS, status.generation, activeView());
    Object.keys(plan).forEach((name) => {
      const view = (views || VIEWS)[name];
      if (plan[name] === 'invalidate') {
        view.invalidate();
        return;
      }
      view.load({ force: true, background: true }).then(() => {
        if (view.generation() != null) showNote(name);
      });
    });
    return plan;
  } catch (_) {
    return {}; // a failed poll is not worth telling the writer about
  } finally {
    checking = false;
    if (recheck) {
      recheck = false;
      checkFreshness(views);
    }
  }
}

function visible() {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden';
}

export function initFreshness() {
  const check = () => { if (visible()) checkFreshness(); };
  on(Events.VAULT_CHANGED, check);
  window.addEventListener('focus', () => {
    if (Date.now() - lastCheck > FOCUS_GAP_MS) check();
  });
  document.addEventListener('visibilitychange', () => {
    if (Date.now() - lastCheck > FOCUS_GAP_MS) check();
  });
  setInterval(check, POLL_MS);
}
