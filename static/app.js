(function () {
  'use strict';

  var KEPT_KEY = 'randomwords.kept.v1';
  var HISTORY_LIMIT = 20;

  var state = {
    library: new Map(),      // library path -> entries[]
    expanded: new Set(),     // library paths currently expanded
    loading: new Set(),      // library paths currently being fetched
    currentSource: null,     // { path, size } | null
    poolSize: null,
    current: [],             // words from the most recent draw
    history: [],             // words drawn before that, most recent first
    kept: [],                // kept words, in the order they were kept
    busy: false,
    drawSeq: 0,              // guards against an out-of-order draw response
  };

  // ---------- elements ----------

  var el = {
    tree: document.getElementById('tree'),
    randFlatBtn: document.getElementById('randFlatBtn'),
    randWalkBtn: document.getElementById('randWalkBtn'),
    currentWords: document.getElementById('currentWords'),
    sourceLine: document.getElementById('sourceLine'),
    drawBtn: document.getElementById('drawBtn'),
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
  };

  // ---------- small helpers ----------

  function fmtWords(n) {
    return n.toLocaleString('en-US') + (n === 1 ? ' word' : ' words');
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

  function readJson(res) {
    return res.json().catch(function () {
      throw new Error('bad json');
    });
  }

  // Every response, success or failure, comes back as JSON with an `ok`
  // flag. A 409's `confirm` field is not used by anything this front end
  // does yet, so it is treated like any other non-ok response rather than
  // crashing on it.
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
        state.currentSource = { path: path, size: data.data.size };
        state.poolSize = data.data.size;
        updateCachedSize(path, data.data.size);
        renderTree();
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
        var source = data.data.source;
        var size = data.data.size;
        state.currentSource = { path: source, size: size };
        state.poolSize = size;
        updateCachedSize(source, size);
        renderTree();
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

  // Does the actual draw and re-render, with no busy-guard of its own, so a
  // load's success handler can chain straight into it while the load still
  // holds the busy flag.
  function performDraw(count) {
    var seq = ++state.drawSeq;
    return apiPost('/api/draw', { count: count })
      .then(function (data) {
        if (!data) return;
        // A slower earlier draw must not overwrite a newer one.
        if (seq !== state.drawSeq) return;
        var drawn = data.data.drawn || [];
        if (state.current.length) {
          state.history = state.current.concat(state.history);
        }
        state.history = state.history.slice(0, HISTORY_LIMIT);
        state.current = drawn;
        renderBench();
      });
  }

  // Draws are cheap and independent, so they are deliberately not behind the
  // busy flag: that flag exists to stop a second load, and using it here made
  // rapid presses of the space bar drop all but the first.
  function drawWords(count) {
    return performDraw(count);
  }

  el.drawBtn.addEventListener('click', function () { drawWords(getCount()); });

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
    var name = state.currentSource ? baseName(state.currentSource.path) : 'Loaded pool';
    var size = state.poolSize;
    el.sourceLine.textContent = (size == null) ? name : (name + ' · ' + fmtWords(size));
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

  // ---------- busy state ----------

  function setBusy(isBusy) {
    state.busy = isBusy;
    el.drawBtn.disabled = isBusy;
    el.randFlatBtn.disabled = isBusy;
    el.randWalkBtn.disabled = isBusy;
  }

  // ---------- init ----------

  function init() {
    loadKept();
    renderKept();

    fetchFolder('').then(renderTree);

    apiGet('/api/pools').then(function (data) {
      if (!data) return;
      adoptServerPool(data.pools);
      renderSourceLine();
      renderTree();
    });

    drawWords(getCount());
  }

  init();
})();
