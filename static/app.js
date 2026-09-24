(function () {
  'use strict';

  var KEPT_KEY = 'randomwords.kept.v1';
  var SAMPLING_MODE_KEY = 'randomwords.sampling_mode.v1';
  var RECENT_TEXTS_KEY = 'randomwords.recent_texts.v1';
  var HISTORY_LIMIT = 20;
  var RECENT_TEXTS_LIMIT = 8;

  var state = {
    library: new Map(),      // library path -> entries[]
    expanded: new Set(),     // library paths currently expanded
    loading: new Set(),      // library paths currently being fetched
    currentSource: null,     // { path, size } | null
    poolSize: null,
    poolTokens: null,
    samplingMode: 'uniform', // 'uniform' | 'weighted'
    wordCounts: {},          // word -> occurrence count
    current: [],             // words from the most recent draw
    history: [],             // words drawn before that, most recent first
    lastMultiDrawSources: null, // display labels for the latest one-each draw
    kept: [],                // kept words, in the order they were kept
    busy: false,
    drawSeq: 0,              // guards against an out-of-order draw response
    pools: [],               // every pool, as last reported by the server
    recentTexts: [],         // {path, label}, most-recent-first, MRU only
    selection: [],           // {kind: 'pool'|'text', id}, in check order
    pendingSave: null,       // name awaiting a yes/no on the save form, or null
    pendingWrite: null,      // name awaiting a yes/no on the write form, or null
    pendingCombine: null,    // body awaiting a yes/no on the combine form, or null
    pendingQuickIntersect: null, // body awaiting a yes/no for quick intersect
    pendingCommand: null,    // line awaiting a yes/no on the command line, or null
    cmdLog: [],              // {kind, text} entries shown in the command output
    cmdHistory: [],          // lines run this session, oldest first
    cmdHistIndex: -1,        // position while walking history with arrows; -1 is the live draft
    cmdDraft: '',            // what was being typed before Up was first pressed
  };

  // ---------- elements ----------

  var el = {
    tree: document.getElementById('tree'),
    randFlatBtn: document.getElementById('randFlatBtn'),
    randWalkBtn: document.getElementById('randWalkBtn'),
    currentWords: document.getElementById('currentWords'),
    sourceLine: document.getElementById('sourceLine'),
    drawBtn: document.getElementById('drawBtn'),
    multiDrawBtn: document.getElementById('multiDrawBtn'),
    modeFlatBtn: document.getElementById('modeFlatBtn'),
    modeWeightedBtn: document.getElementById('modeWeightedBtn'),
    countInput: document.getElementById('countInput'),
    stepUp: document.getElementById('stepUp'),
    stepDown: document.getElementById('stepDown'),
    historyList: document.getElementById('historyList'),
    keptList: document.getElementById('keptList'),
    keptCount: document.getElementById('keptCount'),
    copyBtn: document.getElementById('copyBtn'),
    exportBtn: document.getElementById('exportBtn'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toastMessage'),
    toastClose: document.getElementById('toastClose'),
    poolsList: document.getElementById('poolsList'),
    recentTextsList: document.getElementById('recentTextsList'),
    poolSaveForm: document.getElementById('poolSaveForm'),
    poolSaveName: document.getElementById('poolSaveName'),
    saveConfirm: document.getElementById('saveConfirm'),
    saveConfirmText: document.getElementById('saveConfirmText'),
    saveConfirmYes: document.getElementById('saveConfirmYes'),
    saveConfirmNo: document.getElementById('saveConfirmNo'),
    poolWriteForm: document.getElementById('poolWriteForm'),
    poolWriteName: document.getElementById('poolWriteName'),
    writeNote: document.getElementById('writeNote'),
    writeConfirm: document.getElementById('writeConfirm'),
    writeConfirmText: document.getElementById('writeConfirmText'),
    writeConfirmYes: document.getElementById('writeConfirmYes'),
    writeConfirmNo: document.getElementById('writeConfirmNo'),
    combineForm: document.getElementById('combineForm'),
    combineSelection: document.getElementById('combineSelection'),
    combineOp: document.getElementById('combineOp'),
    combineOut: document.getElementById('combineOut'),
    combineSubmit: document.getElementById('combineSubmit'),
    combineConfirm: document.getElementById('combineConfirm'),
    combineConfirmText: document.getElementById('combineConfirmText'),
    combineConfirmYes: document.getElementById('combineConfirmYes'),
    combineConfirmNo: document.getElementById('combineConfirmNo'),
    quickIntersectForm: document.getElementById('quickIntersectForm'),
    quickIntersectDictionary: document.getElementById('quickIntersectDictionary'),
    quickIntersectOut: document.getElementById('quickIntersectOut'),
    quickIntersectSubmit: document.getElementById('quickIntersectSubmit'),
    quickIntersectConfirm: document.getElementById('quickIntersectConfirm'),
    quickIntersectConfirmText: document.getElementById('quickIntersectConfirmText'),
    quickIntersectConfirmYes: document.getElementById('quickIntersectConfirmYes'),
    quickIntersectConfirmNo: document.getElementById('quickIntersectConfirmNo'),
    cmdForm: document.getElementById('cmdForm'),
    cmdInput: document.getElementById('cmdInput'),
    cmdOutput: document.getElementById('cmdOutput'),
    cmdConfirm: document.getElementById('cmdConfirm'),
    cmdConfirmText: document.getElementById('cmdConfirmText'),
    cmdConfirmYes: document.getElementById('cmdConfirmYes'),
    cmdConfirmNo: document.getElementById('cmdConfirmNo'),
  };

  // ---------- small helpers ----------

  function fmtWords(n) {
    return n.toLocaleString('en-US') + (n === 1 ? ' word' : ' words');
  }

  function fmtTokens(n) {
    return n.toLocaleString('en-US') + (n === 1 ? ' token' : ' tokens');
  }

  function baseName(path) {
    var parts = path.split('/');
    return parts[parts.length - 1];
  }

  function stripTxt(name) {
    return name.replace(/\.txt$/i, '');
  }

  // ---------- toast / errors ----------

  var toastTimer = null;

  function showError(message) {
    el.toastMessage.textContent = message || 'Something went wrong.';
    el.toast.hidden = false;
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 7000);
  }

  function hideToast() {
    el.toast.hidden = true;
    if (toastTimer) { clearTimeout(toastTimer); toastTimer = null; }
  }

  el.toastClose.addEventListener('click', hideToast);

  // ---------- API ----------

  function apiGet(path) {
    return fetch(path, { headers: { 'Accept': 'application/json' } })
      .then(readJson)
      .then(handleResult)
      .catch(function () {
        showError('Could not reach the server.');
        return null;
      });
  }

  function apiPost(path, body) {
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    })
      .then(readJson)
      .then(handleResult)
      .catch(function () {
        showError('Could not reach the server.');
        return null;
      });
  }

  function apiDelete(path) {
    return fetch(path, { method: 'DELETE', headers: { 'Accept': 'application/json' } })
      .then(readJson)
      .then(handleResult)
      .catch(function () {
        showError('Could not reach the server.');
        return null;
      });
  }

  function readJson(res) {
    return res.json().catch(function () {
      throw new Error('bad json');
    });
  }

  // Every response, success or failure, comes back as JSON with an `ok`
  // flag. A 409 asking to confirm carries `ok: true` alongside `confirm`,
  // so it passes straight through here rather than being caught below —
  // the save form and the command line are what read `confirm` off the
  // result this returns.
  function handleResult(data) {
    if (!data || typeof data !== 'object') {
      showError('The server sent back something unexpected.');
      return null;
    }
    if (!data.ok) {
      showError(data.message || 'That did not work.');
      return null;
    }
    return data;
  }

  // ---------- library tree ----------

  function fetchFolder(path) {
    if (state.library.has(path)) {
      return Promise.resolve(state.library.get(path));
    }
    state.loading.add(path);
    return apiGet('/api/library?path=' + encodeURIComponent(path))
      .then(function (data) {
        state.loading.delete(path);
        if (!data) return null;
        state.library.set(path, data.entries);
        return data.entries;
      })
      .catch(function () {
        state.loading.delete(path);
        return null;
      });
  }

  function toggleFolder(path) {
    if (state.expanded.has(path)) {
      state.expanded.delete(path);
      renderTree();
      return;
    }
    state.expanded.add(path);
    renderTree();
    if (!state.library.has(path)) {
      fetchFolder(path).then(renderTree);
    }
  }

  function updateCachedSize(path, size) {
    state.library.forEach(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].path === path) {
          entries[i].size = size;
        }
      }
    });
  }

  function renderTree() {
    el.tree.innerHTML = '';
    var rootEntries = state.library.get('');
    if (!rootEntries) {
      var msg = document.createElement('p');
      msg.className = state.loading.has('') ? 'tree-loading' : 'tree-error';
      msg.textContent = state.loading.has('') ? 'Reading the library…' : 'The library could not be read.';
      el.tree.appendChild(msg);
      return;
    }
    if (rootEntries.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'tree-empty';
      empty.textContent = 'The library is empty.';
      el.tree.appendChild(empty);
      return;
    }
    el.tree.appendChild(renderFolderList(rootEntries, 0));
  }

  function renderFolderList(entries, depth) {
    var ul = document.createElement('ul');
    ul.className = 'tree-children';
    entries.forEach(function (entry) {
      ul.appendChild(renderEntry(entry, depth));
    });
    return ul;
  }

  function renderEntry(entry, depth) {
    var li = document.createElement('li');
    var row = document.createElement('button');
    row.type = 'button';
    row.className = 'tree-row ' + (entry.is_dir ? 'is-dir' : 'is-file');
    row.style.paddingLeft = (0.75 + depth * 1) + 'rem';
    row.setAttribute('role', 'treeitem');
    row.dataset.path = entry.path;

    if (entry.is_dir) {
      var expanded = state.expanded.has(entry.path);
      if (expanded) row.classList.add('is-expanded');
      row.setAttribute('aria-expanded', String(expanded));

      var toggle = document.createElement('span');
      toggle.className = 'tree-toggle';
      toggle.textContent = '▸';
      toggle.setAttribute('aria-hidden', 'true');
      row.appendChild(toggle);

      var name = document.createElement('span');
      name.className = 'tree-name';
      name.textContent = entry.name;
      row.appendChild(name);

      var count = document.createElement('span');
      count.className = 'tree-count';
      count.textContent = entry.texts + (entry.texts === 1 ? ' text' : ' texts');
      row.appendChild(count);

      row.addEventListener('click', function () { toggleFolder(entry.path); });

      li.appendChild(row);

      if (expanded) {
        if (state.library.has(entry.path)) {
          var children = state.library.get(entry.path);
          if (children.length === 0) {
            var noneMsg = document.createElement('p');
            noneMsg.className = 'tree-empty';
            noneMsg.style.paddingLeft = (0.75 + (depth + 1) * 1) + 'rem';
            noneMsg.textContent = 'Nothing here.';
            li.appendChild(noneMsg);
          } else {
            li.appendChild(renderFolderList(children, depth + 1));
          }
        } else {
          var loadingMsg = document.createElement('p');
          loadingMsg.className = 'tree-loading';
          loadingMsg.style.paddingLeft = (0.75 + (depth + 1) * 1) + 'rem';
          loadingMsg.textContent = 'Reading…';
          li.appendChild(loadingMsg);
        }
      }
    } else {
      var isLoaded = !!(state.currentSource && state.currentSource.path === entry.path);
      if (isLoaded) {
        row.classList.add('is-loaded');
        row.setAttribute('aria-current', 'true');
      }

      var toggleSpace = document.createElement('span');
      toggleSpace.className = 'tree-toggle';
      row.appendChild(toggleSpace);

      var fname = document.createElement('span');
      fname.className = 'tree-name';
      fname.textContent = stripTxt(entry.name);
      row.appendChild(fname);

      var fcount = document.createElement('span');
      fcount.className = 'tree-count';
      fcount.textContent = (entry.size == null) ? '' : entry.size.toLocaleString('en-US');
      row.appendChild(fcount);

      row.addEventListener('click', function () { loadText(entry.path); });

      li.appendChild(row);
    }

    return li;
  }

  // ---------- loading texts ----------

  function loadText(path) {
    if (state.busy) return;
    setBusy(true);
    apiPost('/api/pools/load', { source: path })
      .then(function (data) {
        if (!data) return;
        adoptServerPool(data.pools);
        state.currentSource = { path: path, size: data.data.size };
        state.poolSize = data.data.size;
        updateCachedSize(path, data.data.size);
        pushRecentText(path);
        renderTree();
        renderPools(data.pools);
        return performDraw(getCount());
      })
      .finally(function () { setBusy(false); });
  }

  function loadRandom(mode) {
    if (state.busy) return;
    setBusy(true);
    apiPost('/api/pools/random', { under: '', mode: mode })
      .then(function (data) {
        if (!data) return;
        adoptServerPool(data.pools);
        var source = data.data.source;
        var size = data.data.size;
        state.currentSource = { path: source, size: size };
        state.poolSize = size;
        updateCachedSize(source, size);
        pushRecentText(source);
        renderTree();
        renderPools(data.pools);
        return performDraw(getCount());
      })
      .finally(function () { setBusy(false); });
  }

  el.randFlatBtn.addEventListener('click', function () { loadRandom('flat'); });
  el.randWalkBtn.addEventListener('click', function () { loadRandom('walk'); });

  // ---------- drawing ----------

  function getCount() {
    var n = parseInt(el.countInput.value, 10);
    if (!Number.isFinite(n) || n < 1) n = 1;
    if (n > 1000) n = 1000;
    return n;
  }

  function setCount(n) {
    if (n < 1) n = 1;
    if (n > 1000) n = 1000;
    el.countInput.value = String(n);
  }

  el.stepUp.addEventListener('click', function () { setCount(getCount() + 1); });
  el.stepDown.addEventListener('click', function () { setCount(getCount() - 1); });
  el.countInput.addEventListener('change', function () { setCount(getCount()); });

  function setSamplingMode(mode, syncServer) {
    if (mode !== 'uniform' && mode !== 'weighted') mode = 'uniform';
    state.samplingMode = mode;
    try {
      localStorage.setItem(SAMPLING_MODE_KEY, mode);
    } catch (_) {}
    renderModeToggle();
    if (syncServer) {
      apiPost('/api/mode', { mode: mode });
    }
  }

  function renderModeToggle() {
    var isWeighted = state.samplingMode === 'weighted';
    if (el.modeFlatBtn && el.modeWeightedBtn) {
      el.modeFlatBtn.classList.toggle('is-active', !isWeighted);
      el.modeFlatBtn.setAttribute('aria-checked', !isWeighted ? 'true' : 'false');
      el.modeWeightedBtn.classList.toggle('is-active', isWeighted);
      el.modeWeightedBtn.setAttribute('aria-checked', isWeighted ? 'true' : 'false');
    }
  }

  if (el.modeFlatBtn) {
    el.modeFlatBtn.addEventListener('click', function () { setSamplingMode('uniform', true); });
  }
  if (el.modeWeightedBtn) {
    el.modeWeightedBtn.addEventListener('click', function () { setSamplingMode('weighted', true); });
  }

  // Does the actual draw and re-render, with no busy-guard of its own, so a
  // load's success handler can chain straight into it while the load still
  // holds the busy flag.
  function performDraw(count) {
    var seq = ++state.drawSeq;
    var isWeighted = state.samplingMode === 'weighted';
    return apiPost('/api/draw', { count: count, weighted: isWeighted })
      .then(function (data) {
        if (!data) return;
        // A slower earlier draw must not overwrite a newer one.
        if (seq !== state.drawSeq) return;
        var drawn = data.data.drawn || [];
        var counts = data.data.counts || {};
        for (var k in counts) {
          state.wordCounts[k] = counts[k];
        }
        if (state.current.length) {
          state.history = state.current.concat(state.history);
        }
        state.history = state.history.slice(0, HISTORY_LIMIT);
        state.current = drawn;
        state.lastMultiDrawSources = null;
        renderBench();
      });
  }

  // Draws are cheap and independent, so they are deliberately not behind the
  // busy flag: that flag exists to stop a second load, and using it here made
  // rapid presses of the space bar drop all but the first.
  function drawWords(count) {
    return performDraw(count);
  }

  // A one-each draw does not load any source.  It therefore keeps the active
  // pool untouched, while still using the normal current-word and history
  // rendering path.
  function drawOneEach() {
    if (state.selection.length < 1) return;
    var sources = state.selection.map(function (s) { return s.id; });
    var labels = state.selection.map(labelForSelection);
    var seq = ++state.drawSeq;
    return apiPost('/api/draw/multi', { sources: sources })
      .then(function (data) {
        if (!data || seq !== state.drawSeq) return;
        if (state.current.length) {
          state.history = state.current.concat(state.history);
        }
        state.history = state.history.slice(0, HISTORY_LIMIT);
        state.current = data.data.drawn || [];
        state.lastMultiDrawSources = labels;
        renderBench();
      });
  }

  el.drawBtn.addEventListener('click', function () { drawWords(getCount()); });
  el.multiDrawBtn.addEventListener('click', drawOneEach);

  document.addEventListener('keydown', function (e) {
    if (e.code !== 'Space' && e.key !== ' ') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var target = document.activeElement;
    var tag = target ? target.tagName : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || tag === 'BUTTON') return;
    if (target && target.isContentEditable) return;
    e.preventDefault();
    drawWords(getCount());
  });

  // ---------- rendering: bench ----------

  function makeWordChip(word, isKept, onClick) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'word-chip' + (isKept ? ' is-kept' : '');
    btn.textContent = word;
    if (state.wordCounts && state.wordCounts[word] != null) {
      var c = state.wordCounts[word];
      btn.title = word + ' (' + c.toLocaleString('en-US') + (c === 1 ? ' occurrence' : ' occurrences') + ')';
    }
    btn.addEventListener('click', onClick);
    return btn;
  }

  function renderCurrent() {
    el.currentWords.innerHTML = '';
    el.currentWords.dataset.count = state.current.length <= 1 ? '1' : 'multi';
    state.current.forEach(function (word) {
      el.currentWords.appendChild(
        makeWordChip(word, isKept(word), function () { keepWord(word); }));
    });
  }

  function renderSourceLine() {
    if (state.lastMultiDrawSources) {
      el.sourceLine.textContent = 'One each from selected sources: '
          + state.lastMultiDrawSources.join(' · ');
      return;
    }
    var name = state.currentSource ? baseName(state.currentSource.path) : 'Loaded pool';
    var size = state.poolSize;
    var tokens = state.poolTokens;
    var text = name;
    if (size != null) {
      text += ' · ' + fmtWords(size);
      if (tokens != null && tokens !== size) {
        text += ' (' + fmtTokens(tokens) + ')';
      }
    }
    el.sourceLine.textContent = text;
  }

  function renderHistory() {
    el.historyList.innerHTML = '';
    if (state.history.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = 'Words you draw will collect here, most recent first.';
      el.historyList.appendChild(empty);
      return;
    }
    state.history.forEach(function (word) {
      el.historyList.appendChild(
        makeWordChip(word, isKept(word), function () { keepWord(word); }));
    });
  }

  // After a reload the page knows nothing, but the server still does: the
  // active pool reports the text it came from.
  function adoptServerPool(pools) {
    if (!pools) return;
    var active = null;
    for (var i = 0; i < pools.length; i++) {
      if (pools[i].active) { active = pools[i]; break; }
    }
    if (!active) return;
    state.poolSize = active.size;
    state.poolTokens = active.tokens || null;
    if (active.source) {
      state.currentSource = { path: active.source, size: active.size };
    }
  }

  function renderBench() {
    renderCurrent();
    renderSourceLine();
    renderHistory();
    renderTree();
  }

  // ---------- kept words ----------

  function isKept(word) {
    return state.kept.indexOf(word) !== -1;
  }

  function keepWord(word) {
    if (isKept(word)) return;
    state.kept.push(word);
    saveKept();
    renderKept();
    renderCurrent();
    renderHistory();
  }

  function removeKept(word) {
    var idx = state.kept.indexOf(word);
    if (idx === -1) return;
    state.kept.splice(idx, 1);
    saveKept();
    renderKept();
    renderCurrent();
    renderHistory();
  }

  function renderKept() {
    el.keptCount.textContent = '(' + state.kept.length + ')';
    el.keptList.innerHTML = '';
    if (state.kept.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = 'Click a word, anywhere, to keep it.';
      el.keptList.appendChild(empty);
    } else {
      state.kept.forEach(function (word) {
        var chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'word-chip';
        chip.textContent = word;
        chip.setAttribute('aria-label', 'Remove ' + word + ' from kept words');
        chip.addEventListener('click', function () { removeKept(word); });
        el.keptList.appendChild(chip);
      });
    }
    var hasKept = state.kept.length > 0;
    el.copyBtn.disabled = !hasKept;
    el.exportBtn.disabled = !hasKept;
  }

  function loadKept() {
    try {
      var raw = window.localStorage.getItem(KEPT_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && parsed.v === 1 && Array.isArray(parsed.words)) {
        state.kept = parsed.words.filter(function (w) { return typeof w === 'string'; });
      }
    } catch (e) {
      // Storage unavailable or corrupt. The page still works, just without
      // remembering.
    }
  }

  function saveKept() {
    try {
      window.localStorage.setItem(KEPT_KEY, JSON.stringify({ v: 1, words: state.kept }));
    } catch (e) {
      // Ignored on purpose: a full or unavailable store must not block
      // keeping a word for the rest of this session.
    }
  }

  el.copyBtn.addEventListener('click', function () {
    var text = state.kept.join(' ');
    var done = function () {
      var original = el.copyBtn.textContent;
      el.copyBtn.textContent = 'Copied';
      setTimeout(function () { el.copyBtn.textContent = original; }, 1200);
    };
    var fail = function () { showError('Could not copy to the clipboard.'); };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {
        legacyCopy(text) ? done() : fail();
      });
    } else {
      legacyCopy(text) ? done() : fail();
    }
  });

  function legacyCopy(text) {
    try {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      var ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }

  el.exportBtn.addEventListener('click', function () {
    try {
      var text = state.kept.join('\n') + '\n';
      var blob = new Blob([text], { type: 'text/plain' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'kept-words.txt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    } catch (e) {
      showError('Could not export the kept words.');
    }
  });

  // ---------- recent texts (MRU, client-side only) ----------

  function loadRecentTexts() {
    try {
      var raw = window.localStorage.getItem(RECENT_TEXTS_KEY);
      if (!raw) return;
      var parsed = JSON.parse(raw);
      if (parsed && parsed.v === 1 && Array.isArray(parsed.texts)) {
        state.recentTexts = parsed.texts.filter(function (t) {
          return t && typeof t.path === 'string';
        });
      }
    } catch (e) {
      // Storage unavailable or corrupt. The page still works, just without
      // remembering.
    }
  }

  function saveRecentTexts() {
    try {
      window.localStorage.setItem(RECENT_TEXTS_KEY,
          JSON.stringify({ v: 1, texts: state.recentTexts }));
    } catch (e) {
      // Ignored on purpose, the same as saveKept: a full or unavailable
      // store must not block loading a text for the rest of this session.
    }
  }

  // Moves `path` to the front of the MRU list, or adds it, then trims to
  // the cap. Called once a text has actually finished loading.
  function pushRecentText(path) {
    if (!path) return;
    state.recentTexts = state.recentTexts.filter(function (t) { return t.path !== path; });
    state.recentTexts.unshift({ path: path, label: stripTxt(baseName(path)) });
    state.recentTexts = state.recentTexts.slice(0, RECENT_TEXTS_LIMIT);
    saveRecentTexts();
    renderRecentTexts();
  }

  // Drops a text from the MRU list only -- the text itself is untouched.
  function dropRecentText(path) {
    state.recentTexts = state.recentTexts.filter(function (t) { return t.path !== path; });
    state.selection = state.selection.filter(function (s) {
      return !(s.kind === 'text' && s.id === path);
    });
    saveRecentTexts();
    renderRecentTexts();
    renderSelection();
  }

  function renderRecentTexts() {
    el.recentTextsList.innerHTML = '';
    if (state.recentTexts.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = 'Texts you load will collect here.';
      el.recentTextsList.appendChild(empty);
      return;
    }
    state.recentTexts.forEach(function (entry) {
      el.recentTextsList.appendChild(renderRecentTextRow(entry));
    });
  }

  function renderRecentTextRow(entry) {
    var row = document.createElement('div');
    row.className = 'pool-row';

    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'select-checkbox';
    checkbox.checked = isSelected('text', entry.path);
    checkbox.setAttribute('aria-label',
        'Select ' + entry.label + ' for drawing, quick intersecting, or combining');
    checkbox.addEventListener('change', function () { toggleSelection('text', entry.path); });
    row.appendChild(checkbox);

    var load = document.createElement('button');
    load.type = 'button';
    load.className = 'pool-load';
    load.setAttribute('aria-label', 'Load ' + entry.label);
    var name = document.createElement('span');
    name.className = 'pool-name';
    name.textContent = entry.label;
    load.appendChild(name);
    load.addEventListener('click', function () { loadText(entry.path); });
    row.appendChild(load);

    var forget = document.createElement('button');
    forget.type = 'button';
    forget.className = 'pool-forget';
    forget.textContent = '×';
    forget.setAttribute('aria-label', 'Remove ' + entry.label + ' from recent texts');
    forget.addEventListener('click', function () { dropRecentText(entry.path); });
    row.appendChild(forget);

    return row;
  }

  // ---------- selection (checked pools + recent texts, for combining) ----------

  function isSelected(kind, id) {
    return state.selection.some(function (s) { return s.kind === kind && s.id === id; });
  }

  function toggleSelection(kind, id) {
    if (isSelected(kind, id)) {
      state.selection = state.selection.filter(function (s) {
        return !(s.kind === kind && s.id === id);
      });
    } else {
      state.selection.push({ kind: kind, id: id });
    }
    renderPoolsList();
    renderRecentTexts();
    renderSelection();
  }

  function labelForSelection(item) {
    if (item.kind === 'pool') return item.id;
    var text = state.recentTexts.filter(function (t) { return t.path === item.id; })[0];
    return text ? text.label : stripTxt(baseName(item.id));
  }

  function renderSelection() {
    el.combineSelection.innerHTML = '';
    if (state.selection.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = 'Nothing checked yet.';
      el.combineSelection.appendChild(empty);
    } else {
      state.selection.forEach(function (item) {
        var chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'word-chip';
        chip.textContent = labelForSelection(item);
        chip.setAttribute('aria-label', 'Remove ' + labelForSelection(item) + ' from the selection');
        chip.addEventListener('click', function () { toggleSelection(item.kind, item.id); });
        el.combineSelection.appendChild(chip);
      });
    }
    el.combineSubmit.disabled = state.selection.length < 2;
    el.multiDrawBtn.disabled = state.busy || state.selection.length < 1;
    renderQuickIntersectAvailability();
  }

  // ---------- pools pane ----------

  // Every command that can touch a pool hands back a fresh `pools` array, so
  // this is the one place that redraws the list and prunes stale
  // selections (a forgotten pool can't stay checked), rather than each
  // caller patching state by hand.
  function renderPools(pools) {
    if (!pools) return;
    state.pools = pools;
    state.selection = state.selection.filter(function (s) {
      return s.kind !== 'pool' || pools.some(function (p) { return p.name === s.id; });
    });
    renderPoolsList();
    renderSelection();
  }

  function renderPoolsList() {
    el.poolsList.innerHTML = '';
    if (state.pools.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'empty-note';
      empty.textContent = 'No pools yet.';
      el.poolsList.appendChild(empty);
      return;
    }
    state.pools.forEach(function (pool) {
      el.poolsList.appendChild(renderPoolRow(pool));
    });
  }

  function renderPoolRow(pool) {
    var row = document.createElement('div');
    row.className = 'pool-row' + (pool.active ? ' is-active' : '');

    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'select-checkbox';
    checkbox.checked = isSelected('pool', pool.name);
    checkbox.setAttribute('aria-label',
        'Select ' + pool.name + ' for drawing, quick intersecting, or combining');
    checkbox.addEventListener('change', function () { toggleSelection('pool', pool.name); });
    row.appendChild(checkbox);

    var load = document.createElement('button');
    load.type = 'button';
    load.className = 'pool-load';
    load.setAttribute('aria-label',
        (pool.active ? pool.name + ', active. Load it again' : 'Load ' + pool.name)
        + ', ' + fmtWords(pool.size) + '.');
    load.addEventListener('click', function () { loadPool(pool.name); });

    var nameRow = document.createElement('span');
    nameRow.className = 'pool-name-row';
    var name = document.createElement('span');
    name.className = 'pool-name';
    name.textContent = pool.name;
    nameRow.appendChild(name);
    if (pool.active) {
      var badge = document.createElement('span');
      badge.className = 'pool-badge';
      badge.textContent = 'active';
      nameRow.appendChild(badge);
    }
    load.appendChild(nameRow);

    var source = document.createElement('span');
    source.className = 'pool-source';
    source.textContent = pool.source ? stripTxt(baseName(pool.source)) : '—';
    if (pool.source) source.title = pool.source;
    load.appendChild(source);

    var size = document.createElement('span');
    size.className = 'pool-size';
    size.textContent = pool.size.toLocaleString('en-US');
    if (pool.tokens && pool.tokens !== pool.size) {
      size.title = pool.size.toLocaleString('en-US') + ' words, ' + pool.tokens.toLocaleString('en-US') + ' occurrences';
    }

    var forget = document.createElement('button');
    forget.type = 'button';
    forget.className = 'pool-forget';
    forget.textContent = '×';
    forget.setAttribute('aria-label', 'Forget ' + pool.name);
    forget.addEventListener('click', function () { forgetPool(pool.name); });

    row.appendChild(load);
    row.appendChild(size);
    row.appendChild(forget);
    return row;
  }

  function loadPool(name) {
    if (state.busy) return;
    setBusy(true);
    apiPost('/api/pools/load', { source: name })
      .then(function (data) {
        if (!data) return;
        adoptServerPool(data.pools);
        renderPools(data.pools);
        renderTree();
        return performDraw(getCount());
      })
      .finally(function () { setBusy(false); });
  }

  function forgetPool(name) {
    apiDelete('/api/pools/' + encodeURIComponent(name)).then(function (data) {
      if (!data) return;
      renderPools(data.pools);
    });
  }

  // ---------- pools pane: save form ----------

  el.poolSaveForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = el.poolSaveName.value.trim();
    if (!name) return;
    submitSave(name, false);
  });

  // A 409 here carries `ok: true` alongside `confirm`, so apiPost's usual
  // handling (a toast on failure) never fires for it — it comes straight
  // through, and this is the one place that reads `confirm` off the result.
  function submitSave(name, force) {
    var body = { name: name };
    if (force) body.force = true;
    apiPost('/api/pools/save', body).then(function (data) {
      if (!data) return;
      if (data.confirm) {
        state.pendingSave = name;
        showSaveConfirm(data.confirm);
        return;
      }
      hideSaveConfirm();
      el.poolSaveName.value = '';
      renderPools(data.pools);
    });
  }

  function showSaveConfirm(question) {
    el.saveConfirmText.textContent = question;
    el.saveConfirm.hidden = false;
  }

  function hideSaveConfirm() {
    el.saveConfirm.hidden = true;
    state.pendingSave = null;
  }

  el.saveConfirmYes.addEventListener('click', function () {
    var name = state.pendingSave;
    hideSaveConfirm();
    if (name) submitSave(name, true);
  });

  el.saveConfirmNo.addEventListener('click', function () {
    hideSaveConfirm();
  });

  // ---------- pools pane: write-to-disk form ----------

  // Restored after a write reports its result, so the note goes back to
  // explaining the form rather than describing whatever was last written.
  var writeNoteDefault = el.writeNote.textContent;

  el.poolWriteForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = el.poolWriteName.value.trim();
    if (!name) return;
    submitWrite(name, false);
  });

  // A 409 here carries `ok: true` alongside `confirm`, so apiPost's usual
  // handling (a toast on failure) never fires for it — it comes straight
  // through, and this is the one place that reads `confirm` off the result.
  function submitWrite(name, force) {
    var body = { name: name };
    if (force) body.force = true;
    apiPost('/api/pools/write', body).then(function (data) {
      if (!data) return;
      if (data.confirm) {
        state.pendingWrite = name;
        showWriteConfirm(data.confirm);
        return;
      }
      hideWriteConfirm();
      el.poolWriteName.value = '';
      el.writeNote.textContent = data.message || writeNoteDefault;
      renderPools(data.pools);
    });
  }

  function showWriteConfirm(question) {
    el.writeConfirmText.textContent = question;
    el.writeConfirm.hidden = false;
  }

  function hideWriteConfirm() {
    el.writeConfirm.hidden = true;
    state.pendingWrite = null;
  }

  el.writeConfirmYes.addEventListener('click', function () {
    var name = state.pendingWrite;
    hideWriteConfirm();
    if (name) submitWrite(name, true);
  });

  el.writeConfirmNo.addEventListener('click', function () {
    hideWriteConfirm();
  });

  // ---------- pools pane: combine form ----------

  el.combineForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (state.selection.length < 2) return;
    var body = {
      op: el.combineOp.value,
      sources: state.selection.map(function (s) { return s.id; }),
    };
    var out = el.combineOut.value.trim();
    if (out) body.out = out;
    submitCombine(body, false);
  });

  // A 409 here carries `ok: true` alongside `confirm`, so apiPost's usual
  // handling (a toast on failure) never fires for it — it comes straight
  // through, and this is the one place that reads `confirm` off the result.
  function submitCombine(body, force) {
    if (force) body.force = true;
    apiPost('/api/pools/op', body).then(function (data) {
      if (!data) return;
      if (data.confirm) {
        state.pendingCombine = body;
        showCombineConfirm(data.confirm);
        return;
      }
      hideCombineConfirm();
      el.combineOut.value = '';
      state.selection = [];
      renderPools(data.pools);
      renderRecentTexts();
    });
  }

  function showCombineConfirm(question) {
    el.combineConfirmText.textContent = question;
    el.combineConfirm.hidden = false;
  }

  function hideCombineConfirm() {
    el.combineConfirm.hidden = true;
    state.pendingCombine = null;
  }

  el.combineConfirmYes.addEventListener('click', function () {
    var body = state.pendingCombine;
    hideCombineConfirm();
    if (body) submitCombine(body, true);
  });

  el.combineConfirmNo.addEventListener('click', function () {
    hideCombineConfirm();
  });

  // ---------- pools pane: quick intersection ----------

  // Dictionaries are ordinary library files, so this reads the same endpoint
  // as the tree rather than maintaining a second, subtly different list.
  function loadDictionaries() {
    fetchFolder('dicts').then(function (entries) {
      el.quickIntersectDictionary.innerHTML = '';
      var placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = entries ? 'Choose a dictionary…' : 'No dictionaries available';
      el.quickIntersectDictionary.appendChild(placeholder);

      var dictionaries = entries ? entries.filter(function (entry) { return !entry.is_dir; }) : [];
      if (entries) {
        dictionaries
          .forEach(function (entry) {
            var option = document.createElement('option');
            option.value = entry.path;
            option.textContent = stripTxt(entry.name);
            el.quickIntersectDictionary.appendChild(option);
          });
      }
      el.quickIntersectDictionary.disabled = dictionaries.length === 0;
      renderQuickIntersectAvailability();
    });
  }

  function renderQuickIntersectAvailability() {
    if (!el.quickIntersectSubmit) return;
    var hasDictionary = !!el.quickIntersectDictionary.value;
    el.quickIntersectSubmit.disabled = state.selection.length !== 1 || !hasDictionary;
  }

  el.quickIntersectDictionary.addEventListener('change', renderQuickIntersectAvailability);

  el.quickIntersectForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (state.selection.length !== 1) return;
    var dictionary = el.quickIntersectDictionary.value;
    var out = el.quickIntersectOut.value.trim();
    if (!dictionary || !out) return;
    submitQuickIntersect({
      op: 'intersection',
      sources: [state.selection[0].id, dictionary],
      out: out,
    }, false);
  });

  function submitQuickIntersect(body, force) {
    if (force) body.force = true;
    apiPost('/api/pools/op', body).then(function (data) {
      if (!data) return;
      if (data.confirm) {
        state.pendingQuickIntersect = body;
        showQuickIntersectConfirm(data.confirm);
        return;
      }
      hideQuickIntersectConfirm();
      el.quickIntersectOut.value = '';
      state.selection = [];
      renderPools(data.pools);
      renderRecentTexts();
    });
  }

  function showQuickIntersectConfirm(question) {
    el.quickIntersectConfirmText.textContent = question;
    el.quickIntersectConfirm.hidden = false;
  }

  function hideQuickIntersectConfirm() {
    el.quickIntersectConfirm.hidden = true;
    state.pendingQuickIntersect = null;
  }

  el.quickIntersectConfirmYes.addEventListener('click', function () {
    var body = state.pendingQuickIntersect;
    hideQuickIntersectConfirm();
    if (body) submitQuickIntersect(body, true);
  });

  el.quickIntersectConfirmNo.addEventListener('click', hideQuickIntersectConfirm);

  // ---------- busy state ----------

  function setBusy(isBusy) {
    state.busy = isBusy;
    el.drawBtn.disabled = isBusy;
    el.multiDrawBtn.disabled = isBusy || state.selection.length < 1;
    el.randFlatBtn.disabled = isBusy;
    el.randWalkBtn.disabled = isBusy;
  }

  // ---------- command line ----------

  // Bypasses apiPost/handleResult on purpose: a failed command (ok: false)
  // is not a network problem, it is the terminal's own output, and
  // handleResult's toast-and-swallow behaviour would throw the message
  // away instead of putting it where a command line's answer belongs.
  function apiCommandRaw(line, force) {
    var body = { line: line };
    if (force) body.force = true;
    return fetch('/api/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(readJson)
      .catch(function () {
        showError('Could not reach the server.');
        return null;
      });
  }

  function logCmd(kind, text) {
    state.cmdLog.push({ kind: kind, text: text });
    if (state.cmdLog.length > 100) state.cmdLog.shift();
    renderCmdLog();
  }

  function renderCmdLog() {
    el.cmdOutput.innerHTML = '';
    state.cmdLog.forEach(function (entry) {
      var p = document.createElement('p');
      p.className = 'cmdline-line cmdline-line-' + entry.kind;
      p.textContent = entry.text;
      el.cmdOutput.appendChild(p);
    });
    el.cmdOutput.scrollTop = el.cmdOutput.scrollHeight;
  }

  function submitCommand(line, force) {
    return apiCommandRaw(line, force).then(function (data) {
      if (!data || typeof data !== 'object') return;
      if (data.confirm) {
        state.pendingCommand = line;
        showCmdConfirm(data.confirm);
        return;
      }
      hideCmdConfirm();
      logCmd(data.ok ? 'out' : 'err', data.message || 'Done.');
      // A command can load, save, forget, or combine pools just as easily
      // as any button here can, so the pane is refreshed on every answer
      if (data.pools) renderPools(data.pools);
      if (data.data && data.data.mode) {
        setSamplingMode(data.data.mode, false);
      }
      if (data.data && data.data.counts) {
        for (var k in data.data.counts) {
          state.wordCounts[k] = data.data.counts[k];
        }
      }
    });
  }

  function showCmdConfirm(question) {
    el.cmdConfirmText.textContent = question;
    el.cmdConfirm.hidden = false;
    el.cmdInput.disabled = true;
  }

  function hideCmdConfirm() {
    el.cmdConfirm.hidden = true;
    state.pendingCommand = null;
    el.cmdInput.disabled = false;
    el.cmdInput.focus();
  }

  el.cmdConfirmYes.addEventListener('click', function () {
    var line = state.pendingCommand;
    hideCmdConfirm();
    if (line != null) submitCommand(line, true);
  });

  el.cmdConfirmNo.addEventListener('click', function () {
    hideCmdConfirm();
  });

  el.cmdForm.addEventListener('submit', function (e) {
    e.preventDefault();
    if (state.pendingCommand !== null) return;
    var line = el.cmdInput.value;
    if (!line.trim()) return;
    state.cmdHistory.push(line);
    state.cmdHistIndex = -1;
    state.cmdDraft = '';
    logCmd('in', '> ' + line);
    el.cmdInput.value = '';
    submitCommand(line, false);
  });

  el.cmdInput.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      navigateCmdHistory(-1);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      navigateCmdHistory(1);
    } else if (e.key === 'Enter' || e.key === 'Return' || e.keyCode === 13) {
      // A single-text-field form submits implicitly on Enter in most
      // browsers, but forcing it here means that is not load-bearing.
      e.preventDefault();
      el.cmdForm.requestSubmit();
    }
  });

  // -1 is the live draft; 0..length-1 walks backward from the most recent
  // line. Up from the draft stashes it so Down can return to it later.
  function navigateCmdHistory(dir) {
    var hist = state.cmdHistory;
    if (hist.length === 0) return;
    if (state.cmdHistIndex === -1) {
      if (dir > 0) return;
      state.cmdDraft = el.cmdInput.value;
      state.cmdHistIndex = hist.length - 1;
    } else {
      var next = state.cmdHistIndex + dir;
      if (next < 0) next = 0;
      if (next >= hist.length) {
        state.cmdHistIndex = -1;
        el.cmdInput.value = state.cmdDraft;
        return;
      }
      state.cmdHistIndex = next;
    }
    el.cmdInput.value = hist[state.cmdHistIndex];
    var v = el.cmdInput.value;
    el.cmdInput.setSelectionRange(v.length, v.length);
  }

  // `/` focuses the command line from anywhere, the same way the space
  // handler above guards itself: skip it while any field is already taking
  // input. That guard is also what lets `/` reach the command line's own
  // input as an ordinary character once it is focused, rather than being
  // swallowed on every keystroke.
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var target = document.activeElement;
    var tag = target ? target.tagName : '';
    // Only somewhere text can be typed should swallow this. A button never
    // consumes '/', and focus lands on a button after almost every click,
    // which left the shortcut dead most of the time.
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (target && target.isContentEditable) return;
    e.preventDefault();
    el.cmdInput.focus();
  });

  // ---------- init ----------

  function init() {
    fetch('/api/world/tree').then(function (response) {
      if (response.ok) document.getElementById('worldLink').hidden = false;
    }).catch(function () {});
    loadKept();
    renderKept();

    loadRecentTexts();
    renderRecentTexts();

    try {
      var savedMode = localStorage.getItem(SAMPLING_MODE_KEY);
      if (savedMode === 'weighted' || savedMode === 'uniform') {
        setSamplingMode(savedMode, true);
      }
    } catch (_) {}
    renderModeToggle();

    fetchFolder('').then(renderTree);
    loadDictionaries();

    apiGet('/api/pools').then(function (data) {
      if (!data) return;
      adoptServerPool(data.pools);
      renderSourceLine();
      renderTree();
      renderPools(data.pools);
    });

    drawWords(getCount());
  }

  init();
})();
