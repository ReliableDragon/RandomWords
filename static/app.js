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
    pools: [],               // every pool, as last reported by the server
    pendingSave: null,       // name awaiting a yes/no on the save form, or null
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
    poolSaveForm: document.getElementById('poolSaveForm'),
    poolSaveName: document.getElementById('poolSaveName'),
    saveConfirm: document.getElementById('saveConfirm'),
    saveConfirmText: document.getElementById('saveConfirmText'),
    saveConfirmYes: document.getElementById('saveConfirmYes'),
    saveConfirmNo: document.getElementById('saveConfirmNo'),
    combineForm: document.getElementById('combineForm'),
    combineA: document.getElementById('combineA'),
    combineB: document.getElementById('combineB'),
    combineOp: document.getElementById('combineOp'),
    combineOut: document.getElementById('combineOut'),
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
        state.currentSource = { path: path, size: data.data.size };
        state.poolSize = data.data.size;
        updateCachedSize(path, data.data.size);
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
        var source = data.data.source;
        var size = data.data.size;
        state.currentSource = { path: source, size: size };
        state.poolSize = size;
        updateCachedSize(source, size);
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

  // ---------- pools pane ----------

  // Every command that can touch a pool hands back a fresh `pools` array, so
  // this is the one place that redraws both the list and the two pickers in
  // the combine form, rather than each caller patching state by hand.
  function renderPools(pools) {
    if (!pools) return;
    state.pools = pools;
    renderPoolsList();
    populateSelect(el.combineA);
    populateSelect(el.combineB);
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

  // Fills a <select> with every known pool name, keeping the current
  // selection if it still names a pool that exists.
  function populateSelect(select) {
    var prevValue = select.value;
    select.innerHTML = '';
    state.pools.forEach(function (pool) {
      var opt = document.createElement('option');
      opt.value = pool.name;
      opt.textContent = pool.name;
      select.appendChild(opt);
    });
    if (state.pools.some(function (p) { return p.name === prevValue; })) {
      select.value = prevValue;
    }
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

  // ---------- pools pane: combine form ----------

  el.combineForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var a = el.combineA.value;
    var b = el.combineB.value;
    if (!a || !b) return;
    var body = { op: el.combineOp.value, a: a, b: b };
    var out = el.combineOut.value.trim();
    if (out) body.out = out;
    apiPost('/api/pools/op', body).then(function (data) {
      if (!data) return;
      el.combineOut.value = '';
      renderPools(data.pools);
    });
  });

  // ---------- busy state ----------

  function setBusy(isBusy) {
    state.busy = isBusy;
    el.drawBtn.disabled = isBusy;
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
      // rather than only on the requests this file itself made.
      if (data.pools) renderPools(data.pools);
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
    loadKept();
    renderKept();

    fetchFolder('').then(renderTree);

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
