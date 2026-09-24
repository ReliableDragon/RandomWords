(function () {
  'use strict';
  var DRAFT_PREFIX = 'randomwords.world.draft.v1:';
  var RECOVERY_PREFIX = 'randomwords.world.recovery.v1:';
  var KEPT_KEY = 'randomwords.kept.v1';
  var state = { current:null, savedText:'', revision:null, lineEnding:'\n', dirty:false, preview:false, treeLoaded:new Set(), expanded:new Set(), nearbySeq:0, nearby:null, searchSeq:0, lexiconSeq:0, kept:[], drawn:[], conflict:null, replaceRevision:null, autocomplete:null, acItems:[], acIndex:0, polling:null, pendingIdea:null, retryIdea:null };
  var $ = function (id) { return document.getElementById(id); };
  var el = { status:$('worldStatus'), tree:$('worldTree'), search:$('worldSearch'), searchResults:$('searchResults'), welcome:$('welcome'), pane:$('entryPane'), create:$('createPane'), title:$('entryTitle'), folder:$('entryFolder'), words:$('entryWords'), text:$('entryText'), draftState:$('draftState'), saveNotice:$('saveNotice'), conflict:$('conflictPanel'), conflictDraft:$('conflictDraft'), conflictDisk:$('conflictDisk'), preview:$('entryPreview'), compose:$('composeArea'), backlinks:$('backlinkList'), backlinkCount:$('backlinkCount'), groups:$('nearbyGroups'), nearbyState:$('nearbyState'), reference:$('referenceCard'), ac:$('autocomplete'), benchWords:$('benchWords'), startKept:$('startFromKept'), createForm:$('createForm'), createError:$('createError') };
  var activeView='desk';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function textareaText(s) { return String(s == null ? '' : s).replace(/\r\n?/g,'\n'); }
  function detectLineEnding(s) { return String(s||'').indexOf('\r\n')>=0?'\r\n':(String(s||'').indexOf('\r')>=0?'\r':'\n'); }
  function diskText(s) { return state.lineEnding==='\n'?textareaText(s):textareaText(s).replace(/\n/g,state.lineEnding); }
  function status(s, kind) { el.status.textContent=s; el.status.className='world-status'+(kind?' is-'+kind:''); }
  async function request(url, options) {
    var r=await fetch(url,Object.assign({headers:{'Accept':'application/json'}},options||{}));
    var body; try { body=await r.json(); } catch (_) { throw new Error('The server returned an unreadable response.'); }
    if (!r.ok || body.ok===false) { var e=new Error(body.message||('Request failed ('+r.status+').')); e.status=r.status; e.data=body.data||{}; throw e; }
    return body.data==null?body:body.data;
  }
  function get(path) { return request(path); }
  function post(path, body) { return request(path,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(body)}); }
  function pathUrl(p) { return encodeURIComponent(p); }
  function entryTitle(entry) { return entry.title||entry.name||(entry.path||'').split('/').pop().replace(/\.md$/i,''); }
  function textNode(tag, text, className) { var node=document.createElement(tag); node.textContent=String(text==null?'':text); if(className)node.className=className; return node; }
  function loadCoverage(force) {
    if(!force&&$('coverageContent').dataset.loaded==='yes')return;
    var host=$('coverageContent'); host.dataset.loaded='loading'; host.replaceChildren(textNode('p','Loading coverage…','muted'));
    get('/api/world/matrix').then(function(data){renderCoverage(data);host.dataset.loaded='yes';}).catch(function(error){host.dataset.loaded='no';host.replaceChildren(textNode('p',error.message,'tree-error'));});
  }
  function renderCoverage(data) {
    var host=$('coverageContent'), kinds=Array.isArray(data.kinds)?data.kinds:[], rows=Array.isArray(data.rows)?data.rows:[];
    if(!rows.length){host.replaceChildren(textNode('p','No canonical biome rows were found.','muted'));return;}
    var wrap=document.createElement('div');wrap.className='coverage-table-wrap';var table=document.createElement('table');table.className='coverage-table';var head=document.createElement('thead'),hr=document.createElement('tr');
    hr.appendChild(textNode('th','Biome'));kinds.forEach(function(kind){hr.appendChild(textNode('th',kind));});head.appendChild(hr);table.appendChild(head);
    var body=document.createElement('tbody');
    rows.forEach(function(row){var tr=document.createElement('tr'),nameCell=document.createElement('th');nameCell.scope='row';var openBiome=document.createElement('button');openBiome.type='button';openBiome.className='report-entry-link';openBiome.textContent=row.title||entryTitle(row);openBiome.addEventListener('click',function(){openEntry(row.path);});nameCell.appendChild(openBiome);nameCell.appendChild(textNode('small',row.path,'report-path'));tr.appendChild(nameCell);
      kinds.forEach(function(kind){var td=document.createElement('td'),cell=(row.cells&&row.cells[kind])||{count:0,entries:[]},button=document.createElement('button');button.type='button';button.className='coverage-count';button.textContent=String(cell.count==null?(cell.entries||[]).length:cell.count);button.setAttribute('aria-label',(cell.count||0)+' '+kind+' entries in '+(row.title||row.path));
        var listing=document.createElement('div');listing.className='coverage-cell-entries';listing.hidden=true;
        (cell.entries||[]).forEach(function(entry){var item=document.createElement('div');item.className='coverage-entry';var link=document.createElement('button');link.type='button';link.className='report-entry-link';link.textContent=entry.title||entryTitle(entry);link.addEventListener('click',function(){openEntry(entry.path);});item.appendChild(link);
          (entry.memberships||[]).forEach(function(member){var via=typeof member==='string'?member:(member.via||'membership');var source=typeof member==='string'?'':(member.source_path||'');item.appendChild(textNode('small',via+(source?' · '+source:''),'report-provenance'));});
          (entry.direct_places||[]).forEach(function(place){var direct=document.createElement('button');direct.type='button';direct.className='report-entry-link';direct.textContent='Direct place: '+(place.title||entryTitle(place));direct.addEventListener('click',function(){openEntry(place.path);});item.appendChild(direct);});listing.appendChild(item);});
        button.addEventListener('click',function(){listing.hidden=!listing.hidden;button.setAttribute('aria-expanded',listing.hidden?'false':'true');});td.appendChild(button);td.appendChild(listing);tr.appendChild(td);});body.appendChild(tr);});
    table.appendChild(body);wrap.appendChild(table);host.replaceChildren(wrap);
  }
  function loadUpkeep(force) {
    if(!force&&$('upkeepContent').dataset.loaded==='yes')return;
    var host=$('upkeepContent');host.dataset.loaded='loading';host.replaceChildren(textNode('p','Loading upkeep…','muted'));
    get('/api/world/health').then(function(data){renderUpkeep(data);host.dataset.loaded='yes';}).catch(function(error){host.dataset.loaded='no';host.replaceChildren(textNode('p',error.message,'tree-error'));});
  }
  function renderUpkeep(data) {
    var host=$('upkeepContent'), sections=data.sections||{}, counts=data.counts||{}, fragment=document.createDocumentFragment();
    if(Array.isArray(sections)) { sections=sections.reduce(function(map,section){map[section.key||section.id||section.title||'Findings']=section.items||section.entries||[];return map;},{}); }
    var names=Object.keys(sections);if(!names.length){host.replaceChildren(textNode('p','No upkeep findings.','muted'));return;}
    names.forEach(function(name){var values=sections[name];if(!Array.isArray(values))values=values&&Array.isArray(values.items)?values.items:[];var section=document.createElement('details');section.className='report-section';section.open=values.length<=24;var heading=document.createElement('summary');heading.className='report-section-heading';heading.appendChild(textNode('h3',name.replace(/_/g,' ')));var count=counts[name];if(count==null)count=values.length;heading.appendChild(textNode('span',count,'report-count'));section.appendChild(heading);
      if(!values.length){section.appendChild(textNode('p','Nothing to review.','muted'));}
      values.forEach(function(item){var card=document.createElement('article');card.className='report-card';var path=item.path||item.source_path||item.canonical_path||'';var headingText=item.title||item.name||item.phrase||item.target||item.from||item.text||path||'Finding';card.appendChild(textNode('h4',headingText));
        if(item.count!=null&&item.phrase)card.appendChild(textNode('small','Named '+item.count+' times','report-path'));
        var detail=item.context||item.reason||item.text||item.target||item.message||'';if(detail&&detail!==headingText)card.appendChild(textNode('p',detail));
        if(item.to)card.appendChild(textNode('p','Possible spelling: '+item.from+' → '+item.to));
        if(item.other_path){var other=document.createElement('button');other.type='button';other.className='report-entry-link';other.textContent='Open '+item.to;other.addEventListener('click',function(){openEntry(item.other_path);});card.appendChild(other);}
        if(item.line!=null)card.appendChild(textNode('small','Line '+item.line,'report-path'));
        if(path){var action=document.createElement('button');action.type='button';action.className='btn btn-small btn-quiet';action.textContent='Open note';action.addEventListener('click',function(){openEntry(path);});card.appendChild(action);}
        section.appendChild(card);});fragment.appendChild(section);});host.replaceChildren(fragment);
  }
  function loadLexicon(force) {
    if(!force&&$('lexiconContent').dataset.loaded==='yes')return;
    var params=new URLSearchParams(),q=$('lexiconQuery').value.trim(),biome=$('lexiconBiome').value;
    if(q)params.set('q',q);if(biome)params.set('biome',biome);if($('lexiconOnce').checked)params.set('once','1');
    var host=$('lexiconContent'),sequence=++state.lexiconSeq;host.dataset.loaded='loading';host.replaceChildren(textNode('p','Loading lexicon…','muted'));
    get('/api/world/lexicon?'+params.toString()).then(function(data){if(sequence!==state.lexiconSeq)return;renderLexicon(data);host.dataset.loaded='yes';}).catch(function(error){if(sequence!==state.lexiconSeq)return;host.dataset.loaded='no';host.replaceChildren(textNode('p',error.message,'tree-error'));});
  }
  function renderLexicon(data) {
    var host=$('lexiconContent'),select=$('lexiconBiome'),selected=select.value,biomes=data.biomes||[];
    while(select.options.length>1)select.remove(1);
    biomes.forEach(function(biome){var option=document.createElement('option');option.value=biome.path;option.textContent=biome.title||biome.path;select.appendChild(option);});
    if(biomes.some(function(b){return b.path===selected;}))select.value=selected;
    var fragment=document.createDocumentFragment(),drift=data.drift||[],entries=data.entries||[];
    if(drift.length){var driftSection=document.createElement('section');driftSection.className='report-section';driftSection.appendChild(textNode('h3','Possible spelling drift'));drift.forEach(function(pair){var card=document.createElement('article');card.className='report-card';card.appendChild(textNode('strong',pair.from+' → '+pair.to));card.appendChild(textNode('small','Distance '+pair.distance+' · '+pair.from_count+' uses vs '+pair.to_count,'report-path'));(pair.paths||[]).forEach(function(path){var b=document.createElement('button');b.type='button';b.className='report-entry-link';b.textContent='Open '+path;b.addEventListener('click',function(){openEntry(path);});card.appendChild(b);});driftSection.appendChild(card);});fragment.appendChild(driftSection);}
    if(!entries.length)fragment.appendChild(textNode('p','No coined words match these filters.','muted'));
    entries.forEach(function(entry){var card=document.createElement('article');card.className='lexicon-entry report-card';var head=document.createElement('div');head.className='report-section-heading';head.appendChild(textNode('h3',entry.word));head.appendChild(textNode('span',entry.count+' uses','report-count'));card.appendChild(head);
      card.appendChild(textNode('p',(entry.spellings||[]).map(function(s){return s.spelling+' ('+s.count+')';}).join(' · '),'lexicon-spellings'));
      var uses=document.createElement('div');uses.className='lexicon-uses';(entry.uses||[]).forEach(function(use){var row=document.createElement('div');row.className='lexicon-use';var open=document.createElement('button');open.type='button';open.className='report-entry-link';open.textContent=use.path;open.addEventListener('click',function(){openEntry(use.path);});row.appendChild(open);row.appendChild(textNode('small',use.count+' occurrences'+((use.biomes||[]).length?' · '+use.biomes.join(', '):''),'report-path'));uses.appendChild(row);});card.appendChild(uses);
      if(entry.which){card.appendChild(textNode('small','In '+entry.which.count+' library texts','report-path'));(entry.which.texts||[]).slice(0,5).forEach(function(path){card.appendChild(textNode('small',path,'lexicon-library-use'));});}
      fragment.appendChild(card);});host.replaceChildren(fragment);
  }
  var lexiconTimer=null;
  $('lexiconQuery').addEventListener('input',function(){clearTimeout(lexiconTimer);lexiconTimer=setTimeout(function(){loadLexicon(true);},220);});
  $('lexiconBiome').addEventListener('change',function(){loadLexicon(true);});
  $('lexiconOnce').addEventListener('change',function(){loadLexicon(true);});
  function loadBacklog(force) {
    var host=$('backlogContent');if(!force&&host.dataset.loaded==='yes')return;
    host.dataset.loaded='loading';host.replaceChildren(textNode('p','Loading ideas…','muted'));
    get('/api/world/backlog').then(function(data){renderBacklog(data);host.dataset.loaded='yes';}).catch(function(error){host.dataset.loaded='no';host.replaceChildren(textNode('p',error.message,'tree-error'));});
  }
  function renderBacklog(data) {
    var host=$('backlogContent'),ideas=data.ideas||[],fragment=document.createDocumentFragment();
    if(!ideas.length){host.replaceChildren(textNode('p','No backlog ideas were found.','muted'));return;}
    ideas.forEach(function(idea){var card=document.createElement('article');card.className='report-card backlog-idea'+(idea.done?' is-done':'');
      card.appendChild(textNode('p',idea.expected||idea.text||idea.title||idea.path,'backlog-idea-text'));
      card.appendChild(textNode('small',idea.path,'report-path'));
      var actions=document.createElement('div');actions.className='world-actions';
      if(idea.done){var open=document.createElement('button');open.type='button';open.className='btn btn-small btn-quiet';open.textContent='Open idea';open.addEventListener('click',function(){openEntry(idea.path);});actions.appendChild(open);}
      else {var start=document.createElement('button');start.type='button';start.className='btn btn-small btn-primary';start.textContent='Start an entry';start.addEventListener('click',function(){var seed=(idea.expected||'').trim().split(/\s+/).slice(0,4).join(' ').replace(/[.,;:!?]+$/,'');beginCreate(seed,'',idea);});actions.appendChild(start);}
      card.appendChild(actions);fragment.appendChild(card);});host.replaceChildren(fragment);
  }
  function renderRoll(result) {
    var card=$('rollCard'),entry=result.entry,entries=Array.isArray(entry)?entry:(entry?[entry]:[]);card.replaceChildren();card.hidden=false;card.className='roll-card';
    card.appendChild(textNode('p',result.facet||'Writing prompt','eyebrow'));
    var entriesBox=document.createElement('div');entriesBox.className='roll-entries';entries.forEach(function(item,index){if(index)entriesBox.appendChild(textNode('span','×','roll-times'));var open=document.createElement('button');open.type='button';open.className='report-entry-link roll-entry';open.textContent=item.title||entryTitle(item);open.addEventListener('click',function(){openEntry(item.path);});entriesBox.appendChild(open);});card.appendChild(entriesBox);
    var words=result.words||[];if(words.length)card.appendChild(textNode('p',words.join(' · '),'roll-words'));
  }
  $('rollPrompt').addEventListener('click',async function(){var card=$('rollCard');card.hidden=false;card.replaceChildren(textNode('p','Rolling…','muted'));try{renderRoll(await post('/api/world/roll',{}));}catch(error){card.replaceChildren(textNode('p',error.message,'tree-error'));}});
  function draftKey(path) { return DRAFT_PREFIX+path; }
  function recoveryKey(path) { return RECOVERY_PREFIX+path; }
  function storeDraft() { if (!state.current) return; try { if (state.dirty) localStorage.setItem(draftKey(state.current),JSON.stringify({text:el.text.value,revision:state.revision,updated:new Date().toISOString()})); else localStorage.removeItem(draftKey(state.current)); } catch (_) {} }
  function readDraft(path) { try { return JSON.parse(localStorage.getItem(draftKey(path))||'null'); } catch (_) { return null; } }
  function stashRecovery(path, draft) { if(!path||!draft)return; try { localStorage.setItem(recoveryKey(path),JSON.stringify(Object.assign({},draft,{recoveredAt:new Date().toISOString()}))); } catch (_) {} }
  function readRecovery(path) { try { return JSON.parse(localStorage.getItem(recoveryKey(path))||'null'); } catch (_) { return null; } }
  function showRecovery(path) { var recovery=readRecovery(path); var notice=$('recoveryNotice'); if(!recovery||!notice)return; notice.dataset.path=path; $('recoveryText').textContent='A previous draft for this entry is kept in browser recovery.'; notice.hidden=false; }
  function showPane(which) { el.welcome.hidden=which!=='welcome'; el.pane.hidden=which!=='entry'; el.create.hidden=which!=='create'; }
  function displayPath(path) { return path.replace(/\.md$/i,''); }
  function setDirty() { state.dirty=el.text.value!==state.savedText; el.draftState.textContent=state.dirty?'Unsaved draft':'Saved'; el.draftState.className='draft-state'+(state.dirty?' is-dirty':''); storeDraft(); }
  function setWorldView(name) {
    activeView=name;
    document.querySelectorAll('[data-view-panel]').forEach(function(panel){panel.hidden=panel.getAttribute('data-view-panel')!==name;});
    document.querySelectorAll('[data-world-view]').forEach(function(button){if(button.getAttribute('data-world-view')===name)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
    if(name==='coverage')loadCoverage();
    if(name==='upkeep')loadUpkeep();
    if(name==='lexicon')loadLexicon();
    if(name==='backlog')loadBacklog();
    if(name==='map')window.dispatchEvent(new CustomEvent('world:map-visible'));
  }
  document.querySelectorAll('[data-world-view]').forEach(function(button){button.addEventListener('click',function(){setWorldView(button.getAttribute('data-world-view'));});});
  document.querySelectorAll('[data-refresh-view]').forEach(function(button){button.addEventListener('click',function(){if(button.dataset.refreshView==='coverage')loadCoverage(true);if(button.dataset.refreshView==='upkeep')loadUpkeep(true);if(button.dataset.refreshView==='lexicon')loadLexicon(true);if(button.dataset.refreshView==='backlog')loadBacklog(true);});});

  // Folder tree is loaded on demand. Paths, rather than titles, remain the
  // identity so duplicate titles in different folders stay distinct.
  function renderTree(path, entries, host) {
    host.innerHTML='';
    (entries||[]).forEach(function (item) {
      var p=item.path||((path?path+'/':'')+item.name), isDir=!!item.is_dir;
      var row=document.createElement('button'); row.type='button'; row.className='tree-row'+(state.current===p?' is-selected':'');
      row.style.paddingLeft=(.8+(path?path.split('/').length*.58:0))+'rem';
      row.innerHTML='<span class="tree-toggle">'+(isDir?(state.expanded.has(p)?'▾':'▸'):'·')+'</span><span class="tree-name">'+esc(isDir?item.name:entryTitle(item))+'</span>'+(isDir?'':'<span class="tree-count">'+(item.stub?'stub':(item.words==null?'':item.words))+'</span>');
      row.addEventListener('click',function () { if(isDir) toggleFolder(p,row); else openEntry(p); }); host.appendChild(row);
      if (isDir&&state.expanded.has(p)) { var children=document.createElement('div'); children.className='tree-children'; children.innerHTML='<p class="tree-loading">Loading…</p>'; host.appendChild(children); if(item.entries) renderTree(p,item.entries,children); else loadFolder(p,children); }
    });
  }
  async function loadFolder(path, host) { try { var d=await get('/api/world/tree?path='+encodeURIComponent(path)); state.treeLoaded.add(path); renderTree(path,d.entries||[],host); } catch(e) { host.innerHTML='<p class="tree-error">'+esc(e.message)+'</p>'; } }
  async function toggleFolder(path,row) {
    var child=row.nextElementSibling;
    if(state.expanded.has(path)) { state.expanded.delete(path); if(child&&child.classList.contains('tree-children')) child.remove(); row.querySelector('.tree-toggle').textContent='▸'; return; }
    state.expanded.add(path); row.querySelector('.tree-toggle').textContent='▾';
    child=document.createElement('div'); child.className='tree-children'; child.innerHTML='<p class="tree-loading">Loading…</p>'; row.after(child);
    if(!state.treeLoaded.has(path)) await loadFolder(path,child); else { var d=await get('/api/world/tree?path='+encodeURIComponent(path)); renderTree(path,d.entries||[],child); }
  }
  async function loadRoot() { try { var d=await get('/api/world/tree'); renderTree('',d.entries||[],el.tree); status('Vault connected','ready'); } catch(e) { el.tree.innerHTML='<p class="tree-error">'+esc(e.message)+'<br><small>Start the server with a configured vault.</small></p>'; status('Vault unavailable','error'); } }

  function pathFromResult(x) { return x.path||x.entry_path||''; }
  function renderBacklinks(items) {
    items=items||[]; el.backlinkCount.textContent=items.length?'('+items.length+')':'';
    if(!items.length) { el.backlinks.innerHTML='<p class="muted">Nothing links here yet.</p>'; return; }
    el.backlinks.innerHTML=''; items.forEach(function (x) { var p=document.createElement('button'); p.type='button'; p.className='backlink-item'; p.innerHTML='<strong>'+esc(x.title||entryTitle(x))+'</strong><p>'+esc(x.context||x.sentence||x.text||x.path||'')+'</p>'; p.addEventListener('click',function(){openEntry(pathFromResult(x));}); el.backlinks.appendChild(p); });
  }
  async function openEntry(path) {
    if(state.current&&state.dirty&&state.current!==path) { var leave=window.confirm('Keep this unsaved draft in browser recovery and open another entry?'); if(!leave) return; storeDraft(); }
    clearInterval(state.polling); hideAutocomplete(); state.conflict=null; el.conflict.hidden=true; el.saveNotice.hidden=true; el.reference.hidden=true;
    try {
      var d=await get('/api/world/entry?path='+encodeURIComponent(path)); state.current=d.path||path; state.revision=d.revision; state.lineEnding=detectLineEnding(d.text); state.savedText=textareaText(d.text); state.dirty=false;
      var recovered=readDraft(state.current); if(recovered&&recovered.text!==state.savedText) { el.text.value=textareaText(recovered.text); state.dirty=true; el.saveNotice.textContent='Recovered an unsaved browser draft for this entry.'; el.saveNotice.className='save-notice'; el.saveNotice.hidden=false; } else el.text.value=state.savedText;
      el.title.textContent=(d.entry&&d.entry.title)||entryTitle({path:state.current}); el.folder.textContent=state.current.includes('/')?state.current.slice(0,state.current.lastIndexOf('/')):'Vault root'; el.words.textContent=(d.entry&&d.entry.words!=null)?d.entry.words+' words':'';
      setWorldView('desk'); showPane('entry'); renderBacklinks(d.backlinks||[]); renderPreview(d.html); showRecovery(state.current); setDirty(); scheduleNearby(); pollRevision(); loadRoot();
      window.dispatchEvent(new CustomEvent('world:entry-opened',{detail:{path:state.current,title:el.title.textContent}}));
    } catch(e) { status(e.message,'error'); }
  }
  function renderPreview(html) { if(typeof html==='string') { el.preview.innerHTML=html; bindPreviewLinks(); } }
  function bindPreviewLinks() { el.preview.querySelectorAll('a').forEach(function(a){ var href=a.getAttribute('href')||''; var isEntry=href.indexOf('world:')===0||/\/world\/entry(?:\?|$)/.test(href)||/\/api\/world\/entry(?:\?|$)/.test(href); if(isEntry) { a.addEventListener('click',function(ev){ev.preventDefault(); var p=href.indexOf('world:')===0?decodeURIComponent(href.slice(6)):new URL(href,location.href).searchParams.get('path'); if(!p)return; if(ev.ctrlKey||ev.metaKey)findAndOpenReference(p);else openEntry(p); }); } }); }
  function showNotice(text,error) { el.saveNotice.textContent=text; el.saveNotice.className='save-notice'+(error?' error':''); el.saveNotice.hidden=false; }
  function offerIdeaRetry() { if(!state.retryIdea)return;var button=document.createElement('button');button.type='button';button.className='btn btn-small btn-quiet';button.textContent='Review and retry idea';button.addEventListener('click',async function(){button.disabled=true;var prior=state.retryIdea;try{var data=await get('/api/world/backlog'),matches=(data.ideas||[]).filter(function(row){return row.path===prior.path&&row.expected===prior.expected&&!row.done;});if(matches.length!==1){showNotice(matches.length?'Several matching ideas remain. Review the Ideas source manually.':'The original idea changed or was completed. Review the Ideas source manually.',true);await openEntry(prior.path);return;}var current=matches[0],approved=window.confirm('Current idea source:\n'+current.path+'\n\n- '+current.expected+'\n\nMark this current idea as started?');if(!approved)return;await post('/api/world/backlog/strike',current);state.retryIdea=null;showNotice('Idea marked as started.');$('backlogContent').dataset.loaded='no';if(activeView==='backlog')loadBacklog(true);}catch(error){showNotice(error.message+' Review the Ideas source manually.',true);await openEntry(prior.path);}});el.saveNotice.appendChild(button); }
  async function saveEntry(replaceRevision) {
    if(!state.current) return;
    var payload={path:state.current,text:diskText(el.text.value),revision:state.revision}; if(replaceRevision) payload.replace_revision=replaceRevision;
    try { var d=await post('/api/world/entry',payload); state.revision=d.revision; state.savedText=textareaText(payload.text); state.dirty=false; state.conflict=null; el.conflict.hidden=true; setDirty(); var recovery=d.recovery_path||d.recovery; showNotice(recovery?'Saved. Replaced bytes were preserved at '+recovery:'Saved.'); scheduleNearby(); pollRevision(); }
    catch(e) { if(e.status===409) { state.conflict={text:el.text.value,currentText:textareaText(e.data.text||''),currentRevision:e.data.revision,lineEnding:detectLineEnding(e.data.text)}; state.replaceRevision=null; el.conflictDraft.textContent=el.text.value; el.conflictDisk.textContent=state.conflict.currentText; el.conflict.hidden=false; setDirty(); storeDraft(); }
      else showNotice(e.message,true); }
  }
  $('saveBtn').addEventListener('click',function(){saveEntry();}); $('keepDraftBtn').addEventListener('click',function(){storeDraft();el.conflict.hidden=true;showNotice('Draft kept in browser recovery.');});
  $('reloadBtn').addEventListener('click',function(){if(!state.conflict)return;stashRecovery(state.current,{text:state.conflict.text,revision:state.revision,updated:new Date().toISOString()});state.revision=state.conflict.currentRevision;state.lineEnding=state.conflict.lineEnding||'\n';state.savedText=state.conflict.currentText;el.text.value=state.savedText;state.dirty=false;state.conflict=null;el.conflict.hidden=true;setDirty();showRecovery(state.current);showNotice('Reloaded disk version. The previous draft is available from the recovery notice.');});
  $('reopenRecovery').addEventListener('click',function(){var path=$('recoveryNotice').dataset.path,draft=readRecovery(path);if(!draft)return;if(path!==state.current){openEntry(path).then(function(){restoreRecovery(path,draft);});}else restoreRecovery(path,draft);});
  function restoreRecovery(path,draft){if(!draft||path!==state.current)return;el.text.value=draft.text||'';state.dirty=el.text.value!==state.savedText;setDirty();$('recoveryNotice').hidden=true;showNotice('Recovered the earlier draft. Review and save when ready.');scheduleNearby();}
  $('dismissRecovery').addEventListener('click',function(){var path=$('recoveryNotice').dataset.path;if(path){try{localStorage.removeItem(recoveryKey(path));}catch(_){}}$('recoveryNotice').hidden=true;});
  $('replaceBtn').addEventListener('click',function(){if(!state.conflict)return;var reviewed=state.conflict.currentRevision;state.lineEnding=state.conflict.lineEnding||state.lineEnding;saveEntry(reviewed);});
  $('previewBtn').addEventListener('click',function(){state.preview=!state.preview;el.compose.hidden=state.preview;el.preview.hidden=!state.preview;this.textContent=state.preview?'Edit':'Preview';if(state.preview)scheduleNearby();});
  el.text.addEventListener('input',function(){setDirty();scheduleNearby();detectAutocomplete();});
  document.addEventListener('keydown',function(e){if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='s'&&!el.pane.hidden){e.preventDefault();saveEntry();} });
  async function pollRevision() { clearInterval(state.polling); if(!state.current)return; var watched=state.current; state.polling=setInterval(async function(){if(state.current!==watched)return;try{var d=await get('/api/world/entry?path='+encodeURIComponent(watched));if(d.revision!==state.revision){if(state.dirty){state.conflict={text:el.text.value,currentText:textareaText(d.text),currentRevision:d.revision,lineEnding:detectLineEnding(d.text)};el.conflictDraft.textContent=el.text.value;el.conflictDisk.textContent=state.conflict.currentText;el.conflict.hidden=false;showNotice('Disk version changed while you were editing.',true);}else {state.lineEnding=detectLineEnding(d.text);state.revision=d.revision;state.savedText=textareaText(d.text);el.text.value=state.savedText;renderPreview(d.html);renderBacklinks(d.backlinks||[]);setDirty();}}}catch(_){ }},12000); }

  // Nearby suggestions carry the source revision and exact text span. Recheck
  // both before a one-click link edit so late responses cannot touch new text.
  var nearbyTimer=null;
  function scheduleNearby(){clearTimeout(nearbyTimer);if(!state.current)return;nearbyTimer=setTimeout(loadNearby,500);}
  async function loadNearby(){if(!state.current)return;var seq=++state.nearbySeq, rev=String(Date.now())+'-'+seq, text=el.text.value;el.nearbyState.textContent='Reading draft…';try{var d=await post('/api/world/nearby',{text:text,path:state.current,client_revision:rev});if(seq!==state.nearbySeq)return;state.nearby=d;renderPreview(d.html);renderNearby(d.groups||{},rev,text);el.nearbyState.textContent='Live suggestions';window.dispatchEvent(new CustomEvent('world:nearby-updated',{detail:{path:state.current,groups:d.groups||{}}}));}catch(e){el.nearbyState.textContent=e.message;}}
  var groupsSpec=[['named_not_linked','Named, not linked'],['same_biome','Same biome'],['same_tags','Same tags'],['talks_about_same_things','Talks about the same things'],['linked_from_what_you_link','Linked from what you link']];
  function renderNearby(groups,rev,text){el.groups.innerHTML='';var any=false;groupsSpec.forEach(function(spec){var list=groups[spec[0]]||[];if(!list.length)return;any=true;var sec=document.createElement('section');sec.className='nearby-group';sec.innerHTML='<h3>'+esc(spec[1])+' <span>'+list.length+'</span></h3>';var cards=document.createElement('div');cards.className='nearby-cards';list.forEach(function(x){var card=document.createElement('article');card.className='nearby-card';var title=document.createElement('button');title.type='button';title.className='nearby-title';title.textContent=x.title||entryTitle(x);title.addEventListener('click',function(){findAndOpenReference(pathFromResult(x));});var top=document.createElement('div');top.className='nearby-card-top';top.appendChild(title);if(spec[0]==='named_not_linked'){var link=document.createElement('button');link.type='button';link.className='btn btn-small btn-quiet link-suggestion';link.textContent='Link';link.addEventListener('click',function(){applySuggestion(x,rev,text);});top.appendChild(link);}card.appendChild(top);var folder=document.createElement('span');folder.className='nearby-folder';folder.textContent=x.folder||x.path||'';card.appendChild(folder);if(x.reason){var reason=document.createElement('span');reason.className='nearby-reason';reason.textContent=x.reason;card.appendChild(reason);}cards.appendChild(card);});sec.appendChild(cards);el.groups.appendChild(sec);});if(!any)el.groups.innerHTML='<p class="muted nearby-empty">No nearby entries yet. Add references, places, or tags as you write.</p>';}
  function applySuggestion(x,rev,original){var start=x.start,end=x.end,expected=x.expected,now=el.text.value;if(String(x.client_revision||rev)!==rev||now!==original||now.slice(start,end)!==expected){scheduleNearby();el.nearbyState.textContent='Draft changed; refreshing suggestion';return;}var title=x.title||entryTitle(x),target=String(x.link_target||title).replace(/\.md$/i,'');var insert='[['+target+((expected!==title||target!==title)?'|'+expected:'')+']]';el.text.value=now.slice(0,start)+insert+now.slice(end);el.text.focus();el.text.setSelectionRange(start+insert.length,start+insert.length);setDirty();scheduleNearby();}
  async function findAndOpenReference(path){if(!path)return;try{var d=await get('/api/world/entry?path='+encodeURIComponent(path));$('referenceTitle').textContent=(d.entry&&d.entry.title)||entryTitle({path:path});$('referencePath').textContent=path;var box=$('referenceBody');box.textContent='';var raw=textareaText(d.text||''),lines=raw.split('\n'),header=[],at=0;
      if(lines[0]&&lines[0].trim()==='---'){header.push(lines[0]);at=1;while(at<lines.length){header.push(lines[at]);if(lines[at].trim()==='---'){at++;break;}at++;}}
      while(at<lines.length&&/^(From|Origin|Source|Themes):/i.test(lines[at])){header.push(lines[at]);at++;}
      while(at<lines.length&&!lines[at].trim())at++;
      var first=[];while(at<lines.length&&lines[at].trim()){first.push(lines[at]);at++;}
      var facts=[],inFacts=false;for(var i=at;i<lines.length;i++){if(/^##\s+Facts\s*$/i.test(lines[i])){inFacts=true;facts.push(lines[i]);continue;}if(inFacts&&/^##\s+/.test(lines[i]))break;if(inFacts)facts.push(lines[i]);}
      var quotes=[];for(var q=0;q<lines.length;q++){if(/(?:^|\s)-\s*\[\[[^\]]+\]\]\s*$/.test(lines[q])){var begin=q;while(begin>0&&/^\s*>/.test(lines[begin-1]))begin--;quotes.push(lines.slice(begin,q+1).join('\n'));}}
      function addReferenceSection(label,value){value=(value||'').trim();if(!value)return;var section=document.createElement('section'),heading=document.createElement('strong'),body=document.createElement('p');section.className='reference-section';heading.textContent=label;body.textContent=value.slice(0,1800);section.appendChild(heading);section.appendChild(body);box.appendChild(section);}
      addReferenceSection('Header',header.join('\n'));addReferenceSection('First paragraph',first.join('\n'));addReferenceSection('Facts',facts.join('\n'));addReferenceSection('Attributed quotes',quotes.join('\n\n'));el.reference.hidden=false;}catch(e){el.nearbyState.textContent=e.message;}}
  $('closeReference').addEventListener('click',function(){el.reference.hidden=true;});
  window.addEventListener('world:map-open-entry',function(event){if(event.detail&&event.detail.path)openEntry(event.detail.path);});
  window.addEventListener('world:map-open-reference',function(event){if(event.detail&&event.detail.path)findAndOpenReference(event.detail.path);});

  // Search, also used to supply wikilink and tag completion.
  var searchTimer=null;
  el.search.addEventListener('input',function(){clearTimeout(searchTimer);var q=this.value.trim();if(!q){el.searchResults.hidden=true;return;}searchTimer=setTimeout(async function(){var seq=++state.searchSeq;try{var d=await get('/api/world/search?q='+encodeURIComponent(q));if(seq!==state.searchSeq)return;renderSearch(d.results||[]);}catch(e){el.searchResults.innerHTML='<p class="tree-error">'+esc(e.message)+'</p>';el.searchResults.hidden=false;}},180);});
  function renderSearch(results){el.searchResults.innerHTML='';el.searchResults.hidden=false;if(!results.length){el.searchResults.innerHTML='<p class="muted">No matches.</p>';return;}results.slice(0,30).forEach(function(x){var b=document.createElement('button');b.type='button';b.className='tree-row';b.innerHTML='<span class="tree-toggle">·</span><span class="tree-name">'+esc(x.title||entryTitle(x))+'</span><span class="tree-count">'+esc(x.folder||'')+'</span>';b.addEventListener('click',function(){el.searchResults.hidden=true;el.search.value='';openEntry(x.path);});el.searchResults.appendChild(b);});}
  function detectAutocomplete(){var pos=el.text.selectionStart, before=el.text.value.slice(0,pos), match=before.match(/(?:\[\[|#)([^\]\n#]*)$/);if(!match){hideAutocomplete();return;}var marker=before.lastIndexOf(match[0].charAt(0)==='#'?'#':'[[');state.autocomplete={marker:marker,start:pos-match[1].length,query:match[1],token:match[0].startsWith('[[')?'link':'tag'};if(state.autocomplete.token==='tag'){get('/api/world/tags').then(function(d){var tags=Array.isArray(d)?d:(d.tags||[]);var items=tags.map(function(t){return typeof t==='string'?t:(t.tag||t.name||'');}).filter(Boolean).map(function(t){return t.charAt(0)==='#'?t:'#'+t;}).filter(function(t){return t.toLocaleLowerCase().indexOf(('#'+match[1]).toLocaleLowerCase())===0;}).slice(0,10).map(function(tag){return {title:tag,path:''};});showCompletions(items);}).catch(function(){hideAutocomplete();});return;}if(match[1].length<1){hideAutocomplete();return;}get('/api/world/search?q='+encodeURIComponent(match[1])).then(function(d){var near=[];groupsSpec.forEach(function(g){(state.nearby&&state.nearby.groups&&state.nearby.groups[g[0]]||[]).forEach(function(x){near.push(x.path);});});var results=d.results||[];results.sort(function(a,b){return (near.indexOf(a.path)<0?1:0)-(near.indexOf(b.path)<0?1:0);});showCompletions(results.slice(0,8));}).catch(function(){hideAutocomplete();});}
  function showCompletions(items){state.acItems=items;state.acIndex=0;el.ac.innerHTML='';items.forEach(function(x,i){var b=document.createElement('button');b.type='button';b.role='option';b.setAttribute('aria-selected',i===0?'true':'false');b.innerHTML='<strong>'+esc(x.title||entryTitle(x))+'</strong><small>'+esc(x.folder||x.path||'')+'</small>';b.addEventListener('mousedown',function(e){e.preventDefault();chooseCompletion(i);});el.ac.appendChild(b);});el.ac.hidden=!items.length;}
  function hideAutocomplete(){el.ac.hidden=true;state.autocomplete=null;}
  function chooseCompletion(index){var c=state.autocomplete,x=state.acItems[index];if(!c||!x)return;var value=el.text.value,insert;if(c.token==='tag')insert=x.title;else {var title=x.title||entryTitle(x),query=(c.query||'').toLocaleLowerCase(),aliases=(x.aliases||[]),alias=aliases.find(function(a){return typeof a==='string'&&a.toLocaleLowerCase().indexOf(query)===0&&a.toLocaleLowerCase()!==title.toLocaleLowerCase();}),ambiguous=state.acItems.filter(function(i){return(i.title||entryTitle(i)).toLocaleLowerCase()===title.toLocaleLowerCase();}).length>1;var target=ambiguous?(x.path||((x.folder||'')+'/'+title)).replace(/\.md$/i,''):title;var label=alias||title;insert='[['+target+(label!==title?'|'+label:'')+']]';}var start=c.marker,end=el.text.selectionStart;el.text.value=value.slice(0,start)+insert+value.slice(end);var at=start+insert.length;el.text.focus();el.text.setSelectionRange(at,at);hideAutocomplete();setDirty();scheduleNearby();}
  el.text.addEventListener('keydown',function(e){if(el.ac.hidden)return;if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();state.acIndex=(state.acIndex+(e.key==='ArrowDown'?1:-1)+state.acItems.length)%state.acItems.length;Array.from(el.ac.children).forEach(function(b,i){b.setAttribute('aria-selected',i===state.acIndex?'true':'false');});}else if(e.key==='Enter'||e.key==='Tab'){e.preventDefault();chooseCompletion(state.acIndex);}else if(e.key==='Escape')hideAutocomplete();});

  // Explicit destination form: geography targets and taxonomy folder are
  // independent, and creation is only retried after an occupied-path error.
  function beginCreate(seedTitle, fromName, idea){state.pendingIdea=idea||null;setWorldView('desk');showPane('create');$('newTitle').value=seedTitle||'';$('newOrigin').value=state.kept.join(', ');$('newFrom').value=fromName||'';$('createError').hidden=true;loadFolders();}
  async function loadFolders(){try{var d=await get('/api/world/tree'),folders=[],queue=(d.entries||[]).filter(function(x){return x.is_dir;}).map(function(x){return x.path||x.name;});while(queue.length){var path=queue.shift();folders.push(path);var child=await get('/api/world/tree?path='+encodeURIComponent(path));(child.entries||[]).forEach(function(x){if(x.is_dir)queue.push(x.path||path+'/'+x.name);});}var list=$('worldFolders');list.innerHTML='';Array.from(new Set(folders)).sort().forEach(function(p){var o=document.createElement('option');o.value=p;list.appendChild(o);});}catch(e){$('newFolder').placeholder='Enter the exact folder path';}}
  $('newEntryBtn').addEventListener('click',function(){beginCreate();});$('welcomeNew').addEventListener('click',function(){beginCreate();});$('cancelCreate').addEventListener('click',function(){state.pendingIdea=null;showPane(state.current?'entry':'welcome');});
  el.createForm.addEventListener('submit',async function(e){e.preventDefault();var payload={folder:$('newFolder').value,title:$('newTitle').value.trim(),from_targets:$('newFrom').value.split(/\n/).map(function(s){return s.trim();}).filter(Boolean),tags:$('newTags').value.split(',').map(function(s){return s.trim().replace(/^#/,'');}).filter(Boolean),origin:$('newOrigin').value.split(/[\s,]+/).map(function(s){return s.trim();}).filter(Boolean),template:$('newTemplate').value.trim()||null};if(state.pendingIdea)payload.idea=state.pendingIdea;el.createError.hidden=true;try{var d=await post('/api/world/new',payload);await loadRoot();state.pendingIdea=null;if(payload.idea)$('backlogContent').dataset.loaded='no';if(d.path)await openEntry(d.path);if(d.idea_updated===false){state.retryIdea=payload.idea||null;showNotice(d.idea_error||'Entry created, but the idea was not struck through.',true);offerIdeaRetry();}}catch(err){el.createError.textContent=err.message;el.createError.hidden=false;}});

  // A small bench strip uses the same draw and pool routes as the main page.
  function saveKept(){try{localStorage.setItem(KEPT_KEY,JSON.stringify({v:1,words:state.kept}));}catch(_){}}
  function renderBench(){saveKept();el.benchWords.innerHTML='';if(!state.drawn.length&&!state.kept.length){el.benchWords.innerHTML='<span class="muted">Draw some words, then keep the ones you want to use.</span>';}
    state.drawn.forEach(function(w){var b=document.createElement('button');b.type='button';b.className='bench-word'+(state.kept.indexOf(w)>=0?' is-kept':'');b.textContent=w;b.title=state.kept.indexOf(w)>=0?'Remove from kept':'Keep word';b.addEventListener('click',function(){var i=state.kept.indexOf(w);if(i>=0)state.kept.splice(i,1);else state.kept.push(w);renderBench();});el.benchWords.appendChild(b);});state.kept.forEach(function(w){if(state.drawn.indexOf(w)<0){var b=document.createElement('button');b.type='button';b.className='bench-word is-kept';b.textContent=w;b.title='Remove from kept';b.addEventListener('click',function(){state.kept=state.kept.filter(function(k){return k!==w;});renderBench();});el.benchWords.appendChild(b);}});el.startKept.disabled=!state.kept.length;}
  $('drawWords').addEventListener('click',async function(){var count=Math.max(1,Math.min(20,parseInt($('drawCount').value,10)||3));try{var d=await post('/api/draw',{count:count});state.drawn=d.drawn||[];renderBench();}catch(e){status(e.message,'error');}});
  $('startFromKept').addEventListener('click',function(){beginCreate('', '');});$('clearKept').addEventListener('click',function(){state.kept=[];renderBench();});
  async function loadPools(){try{var d=await get('/api/pools');var pools=d.pools||[];var s=$('benchPool');pools.forEach(function(p){var o=document.createElement('option');o.value=p.path||p.name;o.textContent=p.name||p.path;s.appendChild(o);});}catch(_){}}
  $('benchPool').addEventListener('change',async function(){if(!this.value)return;try{var d=await post('/api/pools/load',{source:this.value});status('Loaded '+this.value,'ready');}catch(e){status(e.message,'error');}});
  try{var saved=JSON.parse(localStorage.getItem(KEPT_KEY)||'null');if(saved&&saved.v===1&&Array.isArray(saved.words))state.kept=saved.words.filter(function(w){return typeof w==='string';});}catch(_){}
  renderBench();loadRoot();loadPools();
})();
