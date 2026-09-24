(function () {
  'use strict';
  var DRAFT_PREFIX = 'randomwords.world.draft.v1:';
  var RECOVERY_PREFIX = 'randomwords.world.recovery.v1:';
  var KEPT_KEY = 'randomwords.kept.v1';
  var state = { current:null, savedText:'', revision:null, lineEnding:'\n', dirty:false, preview:false, treeLoaded:new Set(), expanded:new Set(), nearbySeq:0, nearby:null, searchSeq:0, kept:[], drawn:[], conflict:null, replaceRevision:null, autocomplete:null, acItems:[], acIndex:0, polling:null };
  var $ = function (id) { return document.getElementById(id); };
  var el = { status:$('worldStatus'), tree:$('worldTree'), search:$('worldSearch'), searchResults:$('searchResults'), welcome:$('welcome'), pane:$('entryPane'), create:$('createPane'), title:$('entryTitle'), folder:$('entryFolder'), words:$('entryWords'), text:$('entryText'), draftState:$('draftState'), saveNotice:$('saveNotice'), conflict:$('conflictPanel'), conflictDraft:$('conflictDraft'), conflictDisk:$('conflictDisk'), preview:$('entryPreview'), compose:$('composeArea'), backlinks:$('backlinkList'), backlinkCount:$('backlinkCount'), groups:$('nearbyGroups'), nearbyState:$('nearbyState'), reference:$('referenceCard'), ac:$('autocomplete'), benchWords:$('benchWords'), startKept:$('startFromKept'), createForm:$('createForm'), createError:$('createError') };
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
      showPane('entry'); renderBacklinks(d.backlinks||[]); renderPreview(d.html); showRecovery(state.current); setDirty(); scheduleNearby(); pollRevision(); loadRoot();
    } catch(e) { status(e.message,'error'); }
  }
  function renderPreview(html) { if(typeof html==='string') { el.preview.innerHTML=html; bindPreviewLinks(); } }
  function bindPreviewLinks() { el.preview.querySelectorAll('a').forEach(function(a){ var href=a.getAttribute('href')||''; var isEntry=href.indexOf('world:')===0||/\/world\/entry(?:\?|$)/.test(href)||/\/api\/world\/entry(?:\?|$)/.test(href); if(isEntry) { a.addEventListener('click',function(ev){ev.preventDefault(); var p=href.indexOf('world:')===0?decodeURIComponent(href.slice(6)):new URL(href,location.href).searchParams.get('path'); if(!p)return; if(ev.ctrlKey||ev.metaKey)findAndOpenReference(p);else openEntry(p); }); } }); }
  function showNotice(text,error) { el.saveNotice.textContent=text; el.saveNotice.className='save-notice'+(error?' error':''); el.saveNotice.hidden=false; }
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
  async function loadNearby(){if(!state.current)return;var seq=++state.nearbySeq, rev=String(Date.now())+'-'+seq, text=el.text.value;el.nearbyState.textContent='Reading draft…';try{var d=await post('/api/world/nearby',{text:text,path:state.current,client_revision:rev});if(seq!==state.nearbySeq)return;state.nearby=d;renderPreview(d.html);renderNearby(d.groups||{},rev,text);el.nearbyState.textContent='Live suggestions';}catch(e){el.nearbyState.textContent=e.message;}}
  var groupsSpec=[['named_not_linked','Named, not linked'],['same_biome','Same biome'],['same_tags','Same tags']];
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
  function beginCreate(seedTitle, fromName){showPane('create');$('newTitle').value=seedTitle||'';$('newOrigin').value=state.kept.join(', ');$('newFrom').value=fromName||'';$('createError').hidden=true;loadFolders();}
  async function loadFolders(){try{var d=await get('/api/world/tree'),folders=[],queue=(d.entries||[]).filter(function(x){return x.is_dir;}).map(function(x){return x.path||x.name;});while(queue.length){var path=queue.shift();folders.push(path);var child=await get('/api/world/tree?path='+encodeURIComponent(path));(child.entries||[]).forEach(function(x){if(x.is_dir)queue.push(x.path||path+'/'+x.name);});}var list=$('worldFolders');list.innerHTML='';Array.from(new Set(folders)).sort().forEach(function(p){var o=document.createElement('option');o.value=p;list.appendChild(o);});}catch(e){$('newFolder').placeholder='Enter the exact folder path';}}
  $('newEntryBtn').addEventListener('click',function(){beginCreate();});$('welcomeNew').addEventListener('click',function(){beginCreate();});$('cancelCreate').addEventListener('click',function(){showPane(state.current?'entry':'welcome');});
  el.createForm.addEventListener('submit',async function(e){e.preventDefault();var payload={folder:$('newFolder').value,title:$('newTitle').value.trim(),from_targets:$('newFrom').value.split(/\n/).map(function(s){return s.trim();}).filter(Boolean),tags:$('newTags').value.split(',').map(function(s){return s.trim().replace(/^#/,'');}).filter(Boolean),origin:$('newOrigin').value.split(/[\s,]+/).map(function(s){return s.trim();}).filter(Boolean),template:$('newTemplate').value.trim()||null};el.createError.hidden=true;try{var d=await post('/api/world/new',payload);await loadRoot();if(d.path)openEntry(d.path);}catch(err){el.createError.textContent=err.message;el.createError.hidden=false;}});

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
