// Bootstrap for the world desk: wires each module to the page and loads the
// vault. world.html loads this as a module after world_atlas.js.

import { initAutocomplete } from './autocomplete.js';
import { initBackdrop } from './backdrop.js';
import { backlog, initBacklog } from './backlog.js';
import { initBench } from './bench.js';
import { coverage } from './coverage.js';
import { initCreate } from './create.js';
import { initEditor } from './editor.js';
import { initEntryTodo } from './entry_todo.js';
import { initFreshness } from './freshness.js';
import { initLexicon, lexicon } from './lexicon.js';
import { initLinkStatus } from './link_status.js';
import { initMap, mapView } from './map.js';
import { initNav, registerView } from './nav.js';
import { initNearby } from './nearby.js';
import { initRefcard } from './refcard.js';
import { initSearch } from './search.js';
import { initStory, story } from './story.js';
import { initTree, loadRoot } from './tree.js';
import { upkeep } from './upkeep.js';
import { initWelcome } from './welcome.js';

// Each view offers load({force}) and invalidate(); see nav.js.
function registerViews() {
  registerView('story', story);
  registerView('map', mapView);
  registerView('coverage', coverage);
  registerView('upkeep', upkeep);
  registerView('lexicon', lexicon);
  registerView('backlog', backlog);
}

function start() {
  registerViews();
  initNav();
  initTree();
  initSearch();
  initEditor();
  initAutocomplete();
  initBackdrop();
  initLinkStatus();
  initNearby();
  initRefcard();
  initCreate();
  initEntryTodo();
  initWelcome();
  initBench();
  initStory();
  initMap();
  initLexicon();
  initBacklog();
  initFreshness();
  loadRoot();
}

start();
