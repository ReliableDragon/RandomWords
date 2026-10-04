// The Atlas map mode: the vault drawn as a political map.
// An entry lives in the territory of its biome, or of its folder when it has
// none. Biome types and top-level folders are realms, laid out as continents.
// Land is a Voronoi cell around each entry clipped to a disc, so neighbouring
// entries share land and lone entries become islands.
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg', BIOME = 'Locations/Biomes/';
  var SP = 24;       // spacing between entries, in layout units
  var COAST = 40;    // how far land reaches around an entry
  var HUE = { 'Forest & Jungle':128, 'Grassland & Savannah':68, 'Mountains & Hills':28, 'Water & Wetlands':188, 'Heath & Wasteland':318, 'Tundra & Desert':44,
    'Aerial & Celestial':208, 'Subterranean':12, 'Worldwide':160, 'Othernatural':262, 'People':342, 'Cultures':22, 'Cosmology':232 };

  function hash(s) { var x=2166136261; for(var i=0;i<s.length;i++){x^=s.charCodeAt(i);x=Math.imul(x,16777619);} return x>>>0; }
  function rng(seed) { var s=hash(seed)||1; return function(){s^=s<<13;s^=s>>>17;s^=s<<5;return (s>>>0)/4294967296;}; }
  function mean(list, key) { return list.reduce(function(sum,n){return sum+n[key];},0)/list.length; }
  function pairKey(a, b) { return a<b?a+'\u0000'+b:b+'\u0000'+a; }

  // ---------- model: territories, realms, positions and land
  function buildModel(graph) {
    var byId=new Map(), hidden=0;
    (graph.nodes||[]).forEach(function(n){byId.set(n.id,Object.assign({},n,{t:null}));});
    var entries=[]; byId.forEach(function(n){if(n.state!=='entry')return;if(n.world===false){hidden++;return;}entries.push(n);});
    var territories=new Map();
    function territory(id,name,realm){if(!territories.has(id))territories.set(id,{id:id,name:name,realm:realm,members:[],capital:null});return territories.get(id);}
    // Folder territories use the deepest folder holding at least four entries.
    var folderCount=new Map();
    entries.forEach(function(n){if(n.path.indexOf(BIOME)===0||(n.biomes||[]).length)return;var parts=(n.folder||'').split('/').filter(Boolean);for(var i=1;i<=parts.length;i++){var k=parts.slice(0,i).join('/');folderCount.set(k,(folderCount.get(k)||0)+1);}});
    entries.forEach(function(n){
      var t;
      if(n.path.indexOf(BIOME)===0||(n.biomes||[]).length){
        var bp=n.path.indexOf(BIOME)===0?n.path:(typeof n.biomes[0]==='string'?n.biomes[0]:n.biomes[0].path),rest=bp.slice(BIOME.length).split('/'),bn=byId.get(bp);
        var name=bn?bn.title:rest[rest.length-1].replace(/\.md$/i,'');
        t=territory(bp,name,rest.length>1?rest[0].replace(/-/g,' & '):name);
        if(n.path===bp)t.capital=n;
      }else{
        var parts=(n.folder||'').split('/').filter(Boolean),home=parts[0]||'';
        for(var i=parts.length;i>0;i--){var k=parts.slice(0,i).join('/');if(folderCount.get(k)>=4){home=k;break;}}
        var homeParts=home.split('/');t=territory('folder:'+home,homeParts[homeParts.length-1]||'Vault',parts[0]||'Vault');
      }
      n.t=t;t.members.push(n);
    });
    var links=[];
    (graph.edges||[]).forEach(function(e){var a=byId.get(e.source),b=byId.get(e.target);if(!a||!b||!a.t)return;
      // An unresolved target sits beside the first world entry that names it.
      if(!b.t&&b.state!=='entry'){b.t=a.t;a.t.members.push(b);}
      if(b.t)links.push({a:a,b:b,loose:e.status!=='resolved'});});
    // A folder territory with one or two entries folds into the sibling it links to most.
    Array.from(territories.values()).forEach(function(t){
      if(t.id.indexOf('folder:')!==0||t.members.length>=3)return;
      var peers=Array.from(territories.values()).filter(function(u){return u!==t&&u.realm===t.realm&&u.members.length>=3;});if(!peers.length)return;
      var score=new Map();links.forEach(function(l){var other=l.a.t===t?l.b.t:l.b.t===t?l.a.t:null;if(other&&peers.indexOf(other)>=0)score.set(other,(score.get(other)||0)+1);});
      peers.sort(function(a,b){return (score.get(b)||0)-(score.get(a)||0)||b.members.length-a.members.length;});
      t.members.forEach(function(n){n.t=peers[0];peers[0].members.push(n);});territories.delete(t.id);
    });
    var T=Array.from(territories.values()),realms=new Map();
    T.forEach(function(t){if(!realms.has(t.realm))realms.set(t.realm,{name:t.realm,territories:[]});realms.get(t.realm).territories.push(t);});
    var realmList=Array.from(realms.values()).sort(function(a,b){return a.name.localeCompare(b.name);});
    var cross=new Map();
    links.forEach(function(l){if(l.loose||l.a.t===l.b.t)return;var k=pairKey(l.a.t.id,l.b.t.id);if(!cross.has(k))cross.set(k,{a:l.a.t,b:l.b.t,w:0});cross.get(k).w++;});
    var routes=Array.from(cross.values()),N=[];byId.forEach(function(n){if(n.t)N.push(n);});
    var kinds=Array.from(new Set(entries.map(function(n){return n.kind;}).filter(Boolean))).sort(function(a,b){return a.localeCompare(b);});
    var model={T:T,N:N,realms:realmList,routes:routes,links:links,kinds:kinds,hidden:hidden,entryCount:entries.length,territories:territories};
    if(!N.length)return model;
    layoutTerritories(T,routes,realmList);layoutEntries(N,links);drawLand(model);colour(T);
    T.forEach(function(t){t.cx=mean(t.members,'x');t.cy=mean(t.members,'y');});
    var xs=N.map(function(n){return n.x;}),ys=N.map(function(n){return n.y;});
    model.box={x0:Math.min.apply(null,xs)-COAST,x1:Math.max.apply(null,xs)+COAST,y0:Math.min.apply(null,ys)-COAST,y1:Math.max.apply(null,ys)+COAST};
    return model;
  }

  // Territories are discs sized by entry count. Same-realm territories touch;
  // other realms keep a sea between them; links pull territories together.
  function layoutTerritories(T, routes, realms) {
    T.forEach(function(t){t.r=Math.sqrt(t.members.length)*SP*.62+16;});
    realms.forEach(function(r,i){var a=i/realms.length*Math.PI*2;r.territories.forEach(function(t){var rnd=rng(t.id);t.x=Math.cos(a)*520+(rnd()-.5)*160;t.y=Math.sin(a)*364+(rnd()-.5)*160;});});
    function gap(a,b){return a.r+b.r+(a.realm===b.realm?-4:70);}
    for(var it=0;it<900;it++){
      var alpha=1-it/900;
      for(var i=0;i<T.length;i++)for(var j=i+1;j<T.length;j++){
        var a=T[i],b=T[j],dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,min=gap(a,b),f;
        if(d<min)f=-(min-d)*.5;else if(a.realm===b.realm)f=(d-min)*.02*alpha;else f=-1800/(d*d)*alpha;
        dx/=d;dy/=d;var wa=b.r/(a.r+b.r),wb=a.r/(a.r+b.r);a.x+=dx*f*wa;a.y+=dy*f*wa;b.x-=dx*f*wb;b.y-=dy*f*wb;
      }
      routes.forEach(function(r){var a=r.a,b=r.b,dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,min=gap(a,b);if(d<=min)return;var f=(d-min)*.012*Math.log2(1+r.w)*alpha;dx/=d;dy/=d;a.x+=dx*f;a.y+=dy*f;b.x-=dx*f;b.y-=dy*f;});
      T.forEach(function(t){t.x*=1-.004*alpha;t.y*=1-.006*alpha;});
    }
  }

  // Entries repel, links inside a territory act as springs, and each entry is
  // held inside its territory's disc. The biome note stays at the centre.
  function layoutEntries(N, links) {
    N.forEach(function(n){var rnd=rng(n.id),a=rnd()*Math.PI*2,r=Math.sqrt(rnd())*n.t.r*.8;n.x=n.t.x+Math.cos(a)*r;n.y=n.t.y+Math.sin(a)*r;if(n.t.capital===n){n.x=n.t.x;n.y=n.t.y;}});
    for(var it=0;it<420;it++){
      var alpha=1-it/420;
      for(var i=0;i<N.length;i++)for(var j=i+1;j<N.length;j++){
        var a=N[i],b=N[j],dx=b.x-a.x,dy=b.y-a.y,d2=dx*dx+dy*dy;if(d2>8100)continue;
        var d=Math.sqrt(d2)||.01,f=320/(d2+30)*alpha;if(d<SP*.85)f+=(SP*.85-d)*.5;dx/=d;dy/=d;a.x-=dx*f;a.y-=dy*f;b.x+=dx*f;b.y+=dy*f;
      }
      links.forEach(function(l){var a=l.a,b=l.b,same=a.t===b.t,dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||1,f=(d-(same?SP*1.25:0))*(same?.04:.0025)*alpha;dx/=d;dy/=d;a.x+=dx*f;a.y+=dy*f;b.x-=dx*f;b.y-=dy*f;});
      N.forEach(function(n){var t=n.t,dx=n.x-t.x,dy=n.y-t.y,d=Math.sqrt(dx*dx+dy*dy)||1,k=t.capital===n?.3:.005;n.x-=dx*k;n.y-=dy*k;if(d>t.r){var f=(d-t.r)*.35;n.x-=dx/d*f;n.y-=dy/d*f;}});
    }
    N.forEach(function(n){var j=rng(n.id+'j');n.x+=(j()-.5)*1e-3;n.y+=(j()-.5)*1e-3;});
  }

  // Bowyer-Watson Delaunay triangulation inside a very large super-triangle.
  function delaunay(P) {
    var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    P.forEach(function(p){minX=Math.min(minX,p[0]);minY=Math.min(minY,p[1]);maxX=Math.max(maxX,p[0]);maxY=Math.max(maxY,p[1]);});
    var n=P.length,D=Math.max(maxX-minX,maxY-minY,COAST*4)*40,mx=(minX+maxX)/2,my=(minY+maxY)/2,pts=P.concat([[mx-D,my-D],[mx+D,my-D],[mx,my+D]]);
    function tri(a,b,c){var A=pts[a],B=pts[b],C=pts[c],d=2*(A[0]*(B[1]-C[1])+B[0]*(C[1]-A[1])+C[0]*(A[1]-B[1]));
      var a2=A[0]*A[0]+A[1]*A[1],b2=B[0]*B[0]+B[1]*B[1],c2=C[0]*C[0]+C[1]*C[1],ux=(a2*(B[1]-C[1])+b2*(C[1]-A[1])+c2*(A[1]-B[1]))/d,uy=(a2*(C[0]-B[0])+b2*(A[0]-C[0])+c2*(B[0]-A[0]))/d;
      return {v:[a,b,c],x:ux,y:uy,r2:(A[0]-ux)*(A[0]-ux)+(A[1]-uy)*(A[1]-uy)};}
    var tris=[tri(n,n+1,n+2)];
    for(var i=0;i<n;i++){
      var px=pts[i][0],py=pts[i][1],keep=[],edges=new Map();
      tris.forEach(function(t){if((px-t.x)*(px-t.x)+(py-t.y)*(py-t.y)<t.r2){for(var k=0;k<3;k++){var a=t.v[k],b=t.v[(k+1)%3],key=a<b?a+','+b:b+','+a;edges.set(key,edges.has(key)?null:[a,b]);}}else keep.push(t);});
      edges.forEach(function(e){if(e)keep.push(tri(e[0],e[1],i));});tris=keep;
    }
    return {tris:tris,n:n};
  }
  // Sutherland-Hodgman: clip a polygon against a convex, counter-clockwise one.
  function clip(poly, by) {
    var out=poly;
    for(var i=0;i<by.length&&out.length;i++){
      var A=by[i],B=by[(i+1)%by.length],inp=out;out=[];
      var side=function(p){return (B[0]-A[0])*(p[1]-A[1])-(B[1]-A[1])*(p[0]-A[0]);};
      for(var j=0;j<inp.length;j++){var P=inp[j],Q=inp[(j+1)%inp.length],sp=side(P),sq=side(Q);if(sp>=0)out.push(P);if((sp>=0)!==(sq>=0)){var t=sp/(sp-sq);out.push([P[0]+(Q[0]-P[0])*t,P[1]+(Q[1]-P[1])*t]);}}
    }
    return out;
  }
  function clipSegment(P, Q, cx, cy, r) {
    var dx=Q[0]-P[0],dy=Q[1]-P[1],fx=P[0]-cx,fy=P[1]-cy,A=dx*dx+dy*dy,B=2*(fx*dx+fy*dy),C=fx*fx+fy*fy-r*r,disc=B*B-4*A*C;
    if(disc<=0||!A)return null;var s=Math.sqrt(disc),t0=Math.max(0,(-B-s)/(2*A)),t1=Math.min(1,(-B+s)/(2*A));
    return t0<t1?[[P[0]+dx*t0,P[1]+dy*t0],[P[0]+dx*t1,P[1]+dy*t1]]:null;
  }
  function drawLand(model) {
    var N=model.N,dl=delaunay(N.map(function(n){return [n.x,n.y];})),fan=N.map(function(){return [];}),edgeTris=new Map();
    dl.tris.forEach(function(t){t.v.forEach(function(v){if(v<dl.n)fan[v].push(t);});for(var k=0;k<3;k++){var a=t.v[k],b=t.v[(k+1)%3];if(a>=dl.n||b>=dl.n)continue;var key=a<b?a+','+b:b+','+a;if(!edgeTris.has(key))edgeTris.set(key,[]);edgeTris.get(key).push(t);}});
    N.forEach(function(n,i){
      var cell=fan[i].map(function(t){return [t.x,t.y];}).sort(function(p,q){return Math.atan2(p[1]-n.y,p[0]-n.x)-Math.atan2(q[1]-n.y,q[0]-n.x);});
      // A slightly irregular disc, so the coast is not a chain of perfect arcs.
      var rnd=rng(n.id),disc=[];for(var k=0;k<28;k++){var a=k/28*Math.PI*2,r=COAST*(.86+rnd()*.22);disc.push([n.x+Math.cos(a)*r,n.y+Math.sin(a)*r]);}
      n.cell=clip(cell,disc);
    });
    model.borders=[];
    edgeTris.forEach(function(ts,key){if(ts.length!==2)return;var ij=key.split(','),a=N[+ij[0]],b=N[+ij[1]];if(a.t===b.t)return;
      var seg=clipSegment([ts[0].x,ts[0].y],[ts[1].x,ts[1].y],a.x,a.y,COAST*.9);if(seg)model.borders.push({seg:seg,realm:a.t.realm!==b.t.realm});});
  }
  function colour(T) {
    T.forEach(function(t){var h=HUE[t.realm],rnd=rng(t.id),grey=t.realm==='Vault';if(h==null)h=hash(t.realm)%360;
      t.fill='hsl('+(h+(rnd()-.5)*14).toFixed(1)+' '+(grey?4:26)+'% '+(17+rnd()*6).toFixed(1)+'%)';t.ink='hsl('+h+' '+(grey?6:30)+'% 70%)';});
  }

  // ---------- view
  function create(opts) {
    var svg=opts.svg,panel=opts.panel,model=null,signature='',view=null,W=0,H=0,dragged=false,drag=null,focused=null,selected=null,selectedT=null,anim=0,lastLabels=0,neighbours=new Map(),layers={},openPath=null,overlay='kind';
    function el(tag,attrs,parent){var n=document.createElementNS(NS,tag);Object.keys(attrs||{}).forEach(function(k){n.setAttribute(k,attrs[k]);});if(parent)parent.appendChild(n);return n;}
    function html(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;}
    function sx(x){return x*view.s+view.x;} function sy(y){return y*view.s+view.y;}
    function measure(){var r=svg.getBoundingClientRect();W=r.width;H=r.height;svg.setAttribute('viewBox','0 0 '+Math.max(1,W)+' '+Math.max(1,H));return W>0&&H>0;}
    // Space the side panel covers when it floats over the map.
    function inset(){return panel.hidden||getComputedStyle(panel).position!=='absolute'?0:panel.offsetWidth+16;}
    function fitBox(b,pad){var w=Math.max(80,W-inset()),s=Math.min((w-pad*2)/(b.x1-b.x0),(H-pad*2)/(b.y1-b.y0));return {s:s,x:w/2-(b.x0+b.x1)/2*s,y:H/2-(b.y0+b.y1)/2*s};}
    function centreOn(x,y,s){var w=Math.max(80,W-inset());return {s:s,x:w/2-x*s,y:H/2-y*s};}
    function flyTo(target,ms){
      cancelAnimationFrame(anim);if(!view||matchMedia('(prefers-reduced-motion: reduce)').matches){view=target;draw(true);return;}
      var from=view,t0=performance.now(),dur=ms||600,c0=[(W/2-from.x)/from.s,(H/2-from.y)/from.s],c1=[(W/2-target.x)/target.s,(H/2-target.y)/target.s];
      function step(now){var k=Math.min(1,(now-t0)/dur),e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2,s=from.s*Math.pow(target.s/from.s,e),cx=c0[0]+(c1[0]-c0[0])*e,cy=c0[1]+(c1[1]-c0[1])*e;
        view={s:s,x:W/2-cx*s,y:H/2-cy*s};draw(k===1);if(k<1)anim=requestAnimationFrame(step);}
      anim=requestAnimationFrame(step);
    }
    function polyPath(p){return p.length?'M'+p.map(function(q){return q[0].toFixed(1)+','+q[1].toFixed(1);}).join('L')+'Z':'';}

    function isOrphan(n){return n.state==='entry'&&!n.inbound;}
    function openNode(){if(!openPath||!model)return null;for(var i=0;i<model.N.length;i++)if(model.N[i].path===openPath)return model.N[i];return null;}
    // The entry open in the editor gets a ring (placed in draw) and a label.
    function markOpen(){
      if(!model||!layers.world)return;var o=openNode();
      model.N.forEach(function(n){var on=n===o;n.g.classList.toggle('is-open',on);n.g.setAttribute('aria-label',n.baseLabel+(on?' — open in the editor':''));});
      placeRing();
    }
    function placeRing(){
      if(!layers.ring)return;var o=openNode();
      if(!o||o.sxp==null){layers.ring.style.display='none';return;}
      layers.ring.style.display='';layers.ring.setAttribute('cx',o.sxp);layers.ring.setAttribute('cy',o.syp);layers.ring.setAttribute('r',(o.sr||4)+5);
    }
    function applyOverlay(){if(overlay==='kind')delete svg.dataset.overlay;else svg.dataset.overlay=overlay;}
    // What the current colouring means, with counts, for the legend.
    function legend(){
      if(!model)return null;
      var E=model.N.filter(function(n){return n.state==='entry';}),total=E.length;
      function pair(hit,hitLabel,restLabel){var c=E.filter(hit).length;return {mode:overlay,total:total,items:[{label:hitLabel,count:c,swatch:'hit'},{label:restLabel,count:total-c,swatch:'rest'}]};}
      if(overlay==='orphans')return pair(isOrphan,'No inbound links','Linked to');
      if(overlay==='stubs')return pair(function(n){return n.stub;},'Stubs','Written out');
      if(overlay==='rework')return pair(function(n){return n.rework;},'Marked for rework','Not marked');
      var kinds=new Map();
      E.forEach(function(n){var k=n.kind||'Other',row=kinds.get(k);if(!row){row={label:k,count:0,swatch:'kind',color:n.color||null};kinds.set(k,row);}row.count++;if(!row.color&&n.color)row.color=n.color;});
      return {mode:'kind',total:total,items:Array.from(kinds.values()).sort(function(a,b){return b.count-a.count||a.label.localeCompare(b.label);})};
    }

    function render() {
      // A hovered dot removed by a re-render never fires pointerleave.
      focused=null;svg.classList.remove('has-focus');
      svg.replaceChildren();svg.classList.add('is-atlas');
      var world=el('g',{class:'atlas-world'},svg);layers.world=world;
      var coast=el('g',{},world),land=el('g',{},world),borders=el('g',{},world),edges=el('g',{},world),routes=el('g',{},world);layers.focus=el('g',{},world);
      var overlay=el('g',{},svg),regionLabels=el('g',{},overlay),nodes=el('g',{},overlay);layers.ring=el('circle',{class:'atlas-open-ring'},nodes);layers.ring.style.display='none';layers.labels=el('g',{},overlay);
      model.T.forEach(function(t){
        var d=t.members.map(function(n){return polyPath(n.cell);}).join('');
        el('path',{d:d,class:'atlas-coast'},coast);
        t.el=el('path',{d:d,fill:t.fill,stroke:t.fill,class:'atlas-territory'+(t===selectedT?' is-selected':'')},land);
        el('title',{},t.el).textContent=t.name+' · '+t.realm;
        t.el.addEventListener('click',function(){if(!dragged&&layers.world)selectTerritory(t);});
        t.labelEl=el('text',{class:'atlas-territory-label'},regionLabels);t.labelEl.textContent=t.name.toUpperCase();t.labelEl.style.fill=t.ink;
      });
      model.borders.forEach(function(b){el('line',{x1:b.seg[0][0],y1:b.seg[0][1],x2:b.seg[1][0],y2:b.seg[1][1],class:'atlas-border'+(b.realm?' is-realm':'')},borders);});
      model.links.forEach(function(l){if(l.a.t===l.b.t)el('line',{x1:l.a.x,y1:l.a.y,x2:l.b.x,y2:l.b.y,class:'atlas-edge'+(l.loose?' is-loose':'')},edges);});
      model.routes.forEach(function(r){
        var mx=(r.a.cx+r.b.cx)/2,my=(r.a.cy+r.b.cy)/2,dx=r.b.cx-r.a.cx,dy=r.b.cy-r.a.cy,d=Math.sqrt(dx*dx+dy*dy)||1,bend=d*.12;
        r.el=el('path',{d:'M'+r.a.cx+','+r.a.cy+'Q'+(mx-dy/d*bend)+','+(my+dx/d*bend)+' '+r.b.cx+','+r.b.cy,class:'atlas-route'+(r.w===1?' is-minor':'')+(selectedT&&(r.a===selectedT||r.b===selectedT)?' is-lit':''),'stroke-width':(.8+Math.sqrt(r.w)*.9).toFixed(2)},routes);
        el('title',{},r.el).textContent=r.a.name+' ↔ '+r.b.name+': '+r.w+' link'+(r.w===1?'':'s');
      });
      neighbours=new Map(model.N.map(function(n){return [n,new Set()];}));
      model.links.forEach(function(l){neighbours.get(l.a).add(l.b);neighbours.get(l.b).add(l.a);});
      model.N.forEach(function(n){
        var capital=n.t.capital===n,g=el('g',{class:'atlas-node'+(n.state!=='entry'?' is-unresolved':'')+(n.stub?' is-stub':'')+(capital?' is-capital':'')+(n.rework?' is-rework':'')+(isOrphan(n)?' is-orphan':'')+(n===selected?' is-selected':''),tabindex:'0',role:'button'},nodes);
        n.baseLabel=(n.state==='entry'?'':n.state==='ambiguous'?'Ambiguous link: ':'Unresolved link: ')+n.title+' — '+n.t.name+(n.stub?' — stub':'')+(n.rework?' — marked for rework':'');g.setAttribute('aria-label',n.baseLabel);
        n.baseR=capital?7:Math.min(8,3.2+Math.sqrt(n.inbound||0)*1.1);
        n.core=el(n.state==='entry'&&!capital?'circle':'rect',{class:'atlas-node-core'},g);n.core.style.setProperty('--node-color',n.color||'var(--muted)');
        el('title',{},g).textContent=n.title+(n.path?'\n'+n.path:'');n.g=g;
        g.addEventListener('pointerenter',function(){focusNode(n);});g.addEventListener('pointerleave',function(){focusNode(null);});
        g.addEventListener('focus',function(){focusNode(n);if(n.sxp<0||n.sxp>W-inset()||n.syp<0||n.syp>H)flyTo(centreOn(n.x,n.y,view.s),300);});
        g.addEventListener('blur',function(){focusNode(null);});
        g.addEventListener('click',function(ev){ev.stopPropagation();if(dragged||!layers.world)return;if(n.path&&(ev.shiftKey||ev.metaKey||ev.ctrlKey))opts.preview(n.path);selectNode(n,false);});
        g.addEventListener('dblclick',function(ev){ev.stopPropagation();if(n.path&&layers.world)opts.open(n.path);});
        g.addEventListener('keydown',function(ev){if(ev.key==='Enter'){ev.preventDefault();if(n.path)opts.open(n.path);else selectNode(n,false);}else if(ev.key===' '){ev.preventDefault();selectNode(n,false);}});
        n.label=el('text',{class:'atlas-label'+(capital?' is-capital':'')},layers.labels);n.label.textContent=n.title.length>30?n.title.slice(0,28)+'…':n.title;
      });
      svg.classList.toggle('has-territory',!!selectedT);
      applyOverlay();markOpen();
      attach();
    }

    function draw(final) {
      if(!model||!model.N.length||!layers.world||!view)return;
      layers.world.setAttribute('transform','translate('+view.x+' '+view.y+') scale('+view.s+')');
      svg.dataset.zoom=view.s<.55?'far':view.s<1.3?'mid':'near';
      var k=Math.max(.7,Math.min(1.5,Math.sqrt(view.s)*1.1));
      model.N.forEach(function(n){var r=n.baseR*k,x=sx(n.x),y=sy(n.y);n.sr=r;n.sxp=x;n.syp=y;
        if(n.core.tagName==='circle'){n.core.setAttribute('cx',x);n.core.setAttribute('cy',y);n.core.setAttribute('r',r);}
        else{n.core.setAttribute('x',x-r);n.core.setAttribute('y',y-r);n.core.setAttribute('width',r*2);n.core.setAttribute('height',r*2);n.core.setAttribute('transform',n.t.capital===n?'rotate(45 '+x+' '+y+')':'');}});
      placeRing();
      var now=performance.now();if(final||now-lastLabels>60){lastLabels=now;placeLabels();}
    }
    // Territory names at middle zoom and entry names up close, placed greedily
    // by importance so no two labels overlap.
    function placeLabels() {
      var boxes=[],dots=[],zoom=svg.dataset.zoom;
      function over(list,b){return list.some(function(o){return b.x0<o.x1&&b.x1>o.x0&&b.y0<o.y1&&b.y1>o.y0;});}
      function inView(x,y){return x>-50&&x<W+50&&y>-30&&y<H+30;}
      model.N.forEach(function(n){dots.push({x0:n.sxp-n.sr,x1:n.sxp+n.sr,y0:n.syp-n.sr,y1:n.syp+n.sr});});
      model.T.slice().sort(function(a,b){return b.members.length-a.members.length;}).forEach(function(t){
        var x=sx(t.cx),y=sy(t.cy)-2,w=t.name.length*7.4+8,b={x0:x-w/2,x1:x+w/2,y0:y-11,y1:y+4},ok=!t.capital&&zoom!=='far'&&inView(x,y)&&(!over(boxes,b)||t===selectedT);
        t.labelEl.style.display=ok?'':'none';if(!ok)return;
        t.labelEl.setAttribute('x',x);t.labelEl.setAttribute('y',y);t.labelEl.classList.toggle('is-faint',zoom==='near');if(zoom==='mid')boxes.push(b);
      });
      // The hovered and selected entries always get a label; their neighbours go first but must still fit.
      var must=new Set([focused,selected,openNode()].filter(Boolean)),forced=new Set(must);if(focused)(neighbours.get(focused)||[]).forEach(function(n){forced.add(n);});
      model.N.slice().sort(function(a,b){return (forced.has(b)-forced.has(a))||((b.t.capital===b)-(a.t.capital===a))||(b.inbound||0)-(a.inbound||0);}).forEach(function(n){
        var capital=n.t.capital===n,want=forced.has(n)||(capital&&zoom!=='far')||zoom==='near'||(zoom==='mid'&&(n.inbound||0)>=8),placed=false;
        if(capital){n.label.classList.toggle('is-territory',zoom==='mid');n.label.textContent=zoom==='mid'?n.title.toUpperCase():n.title;}
        if(want&&inView(n.sxp,n.syp)){
          var w=n.title.length*(capital?7.4:5.6)+4,r=n.sr,spots=[[n.sxp,n.syp+r+11,'middle',-w/2],[n.sxp+r+3,n.syp+3.5,'start',0],[n.sxp-r-3,n.syp+3.5,'end',-w],[n.sxp,n.syp-r-4,'middle',-w/2]];
          for(var i=0;i<spots.length;i++){var s=spots[i],b={x0:s[0]+s[3],x1:s[0]+s[3]+w,y0:s[1]-9,y1:s[1]+2};
            if(must.has(n)||!(over(boxes,b)||(!capital&&over(dots,b)))){n.label.setAttribute('x',s[0]);n.label.setAttribute('y',s[1]);n.label.setAttribute('text-anchor',s[2]);boxes.push(b);placed=true;break;}}
        }
        n.label.style.display=placed?'':'none';n.label.classList.toggle('is-forced',forced.has(n));
      });
    }

    function focusNode(n) {
      if(!layers.focus)return;
      focused=n;layers.focus.replaceChildren();svg.classList.toggle('has-focus',!!n);
      var near=n&&neighbours.get(n);model.N.forEach(function(m){m.g.classList.toggle('is-lit',!!n&&(m===n||!!near&&near.has(m)));});
      if(n)model.links.forEach(function(l){if(l.a===n||l.b===n)el('line',{x1:l.a.x,y1:l.a.y,x2:l.b.x,y2:l.b.y,class:'atlas-focus-edge'+(l.a.t!==l.b.t?' is-abroad':'')+(l.loose?' is-loose':'')},layers.focus);});
      placeLabels();
    }
    function chip(n){var b=html('button','atlas-chip',n.title);b.type='button';b.style.setProperty('--node-color',n.color||'var(--muted)');if(n.t!==selectedT&&selected&&n.t!==selected.t)b.title=n.t.name;b.addEventListener('click',function(){selectNode(n,true);});return b;}
    function chips(list){var w=html('div','atlas-chips');list.forEach(function(n){w.appendChild(chip(n));});return w;}
    function openPanel(eyebrow,title){
      panel.replaceChildren();panel.hidden=false;
      var close=html('button','atlas-panel-close','×');close.type='button';close.setAttribute('aria-label','Close');close.addEventListener('click',clearSelection);
      var heading=html('h3','',title);heading.tabIndex=-1;
      panel.appendChild(close);panel.appendChild(html('p','eyebrow',eyebrow));panel.appendChild(heading);
      // Rebuilding the panel removes the button that had focus; keep keyboard users in the panel.
      if(panel.contains(document.activeElement)||document.activeElement===document.body)setTimeout(function(){heading.focus({preventScroll:true});},0);
    }
    function selectNode(n,fly) {
      selected=n;selectedT=null;svg.classList.remove('has-territory');
      model.T.forEach(function(t){t.el.classList.remove('is-selected');});model.routes.forEach(function(r){r.el.classList.remove('is-lit');});
      model.N.forEach(function(m){m.g.classList.toggle('is-selected',m===n);});
      openPanel(n.t.realm+' · '+n.t.name,n.title);
      if(n.path){
        panel.appendChild(html('small','map-selected-path',n.path));
        var actions=html('div','atlas-actions'),open=html('button','btn btn-small btn-primary','Open entry'),preview=html('button','btn btn-small btn-quiet','Preview');
        open.type=preview.type='button';open.addEventListener('click',function(){opts.open(n.path);});preview.addEventListener('click',function(){opts.preview(n.path);});
        actions.appendChild(open);actions.appendChild(preview);panel.appendChild(actions);
      }else{
        panel.appendChild(html('p','muted',n.state==='ambiguous'?'Ambiguous link. Candidate notes:':'Unresolved link. No note has this name yet.'));
        (n.candidates||[]).forEach(function(path){var b=html('button','report-entry-link',path);b.type='button';b.addEventListener('click',function(){opts.open(path);});panel.appendChild(b);});
      }
      var near=Array.from(neighbours.get(n)),home=near.filter(function(m){return m.t===n.t;}),abroad=near.filter(function(m){return m.t!==n.t;});
      if(home.length){panel.appendChild(html('h4','','Linked in '+n.t.name));panel.appendChild(chips(home));}
      if(abroad.length){panel.appendChild(html('h4','','Linked elsewhere'));panel.appendChild(chips(abroad));}
      if(!near.length)panel.appendChild(html('p','muted','No links yet.'));
      var all=html('button','atlas-panel-link','All of '+n.t.name+' →');all.type='button';all.addEventListener('click',function(){selectTerritory(n.t);});panel.appendChild(all);
      if(fly){var s=Math.max(view.s,1.6);flyTo(centreOn(n.x,n.y,s));}else placeLabels();
    }
    // A folder territory starts entries in its folder; a biome territory, "From" that biome.
    function startOptions(t){var o={};if(t.id.indexOf('folder:')===0){var folder=t.id.slice(7);if(folder)o.folder=folder;}else o.fromTargets=[t.id];return o;}
    function selectTerritory(t) {
      selectedT=t;selected=null;svg.classList.add('has-territory');
      model.N.forEach(function(m){m.g.classList.remove('is-selected');});model.T.forEach(function(u){u.el.classList.toggle('is-selected',u===t);});
      model.routes.forEach(function(r){r.el.classList.toggle('is-lit',r.a===t||r.b===t);});
      openPanel(t.realm,t.name);
      var entries=t.members.filter(function(n){return n.state==='entry';}),loose=t.members.filter(function(n){return n.state!=='entry';});
      panel.appendChild(html('p','muted',entries.length+' entr'+(entries.length===1?'y':'ies')+(loose.length?' · '+loose.length+' unwritten link'+(loose.length===1?'':'s'):'')));
      var actions=html('div','atlas-actions');
      if(t.capital){var open=html('button','btn btn-small btn-primary','Open biome note');open.type='button';open.addEventListener('click',function(){opts.open(t.capital.path);});actions.appendChild(open);}
      if(opts.roll){var roll=html('button','btn btn-small btn-quiet','Roll here');roll.type='button';roll.disabled=!entries.length;roll.title='Roll a writing prompt around a random entry from '+t.name;roll.addEventListener('click',function(){opts.roll(entries[Math.floor(Math.random()*entries.length)].path);});actions.appendChild(roll);}
      if(opts.create){var start=html('button','btn btn-small btn-quiet','Start entry here');start.type='button';start.addEventListener('click',function(){opts.create(startOptions(t));});actions.appendChild(start);}
      if(actions.children.length)panel.appendChild(actions);
      var groups=new Map();
      t.members.forEach(function(n){if(n===t.capital)return;var k=n.state!=='entry'?'Unwritten':n.kind||'Other';if(!groups.has(k))groups.set(k,[]);groups.get(k).push(n);});
      Array.from(groups.keys()).sort(function(a,b){return (a==='Unwritten')-(b==='Unwritten')||a.localeCompare(b);}).forEach(function(k){
        var list=groups.get(k).sort(function(a,b){return a.title.localeCompare(b.title);});panel.appendChild(html('h4','',k+' · '+list.length));panel.appendChild(chips(list));
      });
      // For a biome, the kinds it has no entries for are where the world is thin.
      var missing=t.capital?model.kinds.filter(function(k){return !groups.has(k)&&k!==t.capital.kind;}):[];
      if(missing.length){panel.appendChild(html('h4','','No entries yet'));panel.appendChild(html('p','muted',missing.join(', ')));}
      var rs=model.routes.filter(function(r){return r.a===t||r.b===t;}).sort(function(a,b){return b.w-a.w;});
      if(rs.length){panel.appendChild(html('h4','','Linked territories'));var w=html('div','atlas-chips');
        rs.forEach(function(r){var other=r.a===t?r.b:r.a,b=html('button','atlas-chip is-route',other.name+' · '+r.w);b.type='button';b.addEventListener('click',function(){selectTerritory(other);});w.appendChild(b);});panel.appendChild(w);}
      var xs=t.members.map(function(n){return n.x;}),ys=t.members.map(function(n){return n.y;}),fit=fitBox({x0:Math.min.apply(null,xs)-COAST*2,x1:Math.max.apply(null,xs)+COAST*2,y0:Math.min.apply(null,ys)-COAST*2,y1:Math.max.apply(null,ys)+COAST*2},40);
      flyTo(fit.s>2.4?centreOn(t.cx,t.cy,2.4):fit);
      if(opts.onTerritory)opts.onTerritory(t.id);
    }
    function clearSelection() {
      var back=panel.contains(document.activeElement)&&(selected||selectedT&&selectedT.capital);
      selected=null;selectedT=null;panel.hidden=true;panel.replaceChildren();svg.classList.remove('has-territory');
      if(model&&model.N.length){model.T.forEach(function(u){u.el.classList.remove('is-selected');});model.routes.forEach(function(r){r.el.classList.remove('is-lit');});model.N.forEach(function(m){m.g.classList.remove('is-selected');});placeLabels();}
      if(opts.onTerritory)opts.onTerritory('');
      if(back&&back.g&&back.g.isConnected)back.g.focus({preventScroll:true});
    }

    function attach() {
      svg.onwheel=function(ev){ev.preventDefault();cancelAnimationFrame(anim);var r=svg.getBoundingClientRect(),px=ev.clientX-r.left,py=ev.clientY-r.top,s=Math.max(.15,Math.min(6,view.s*Math.exp(-ev.deltaY*.0015)));
        view={s:s,x:px-(px-view.x)*s/view.s,y:py-(py-view.y)*s/view.s};draw(false);clearTimeout(svg._atlasWheel);svg._atlasWheel=setTimeout(function(){draw(true);},120);};
      // Capture only once a drag begins, so clicks still reach land and dots.
      svg.onpointerdown=function(ev){if(ev.button!==0)return;drag={id:ev.pointerId,x:ev.clientX,y:ev.clientY,vx:view.x,vy:view.y};dragged=false;};
      svg.onpointermove=function(ev){if(!drag||drag.id!==ev.pointerId)return;if(!ev.buttons&&ev.pointerType==='mouse'){drag=null;return;}var dx=ev.clientX-drag.x,dy=ev.clientY-drag.y;
        if(!dragged&&Math.abs(dx)+Math.abs(dy)>3){dragged=true;cancelAnimationFrame(anim);try{svg.setPointerCapture(ev.pointerId);}catch(e){}svg.classList.add('is-panning');}
        if(dragged){view={s:view.s,x:drag.vx+dx,y:drag.vy+dy};draw(false);}};
      svg.onpointerup=svg.onpointercancel=function(ev){if(!drag||drag.id!==ev.pointerId)return;if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);svg.classList.remove('is-panning');if(dragged)draw(true);drag=null;setTimeout(function(){dragged=false;},0);};
      svg.onclick=function(ev){if(!dragged&&ev.target===svg)clearSelection();};
      panel.onkeydown=svg.onkeydown=function(ev){if(ev.key==='Escape'&&!panel.hidden){ev.preventDefault();clearSelection();}};
    }

    return {
      show: function(graph) {
        var sig=JSON.stringify(graph),fresh=sig!==signature;
        if(fresh){cancelAnimationFrame(anim);model=buildModel(graph);signature=sig;view=null;selected=selectedT=null;panel.hidden=true;}
        else if(selected)selected=model.N.indexOf(selected)>=0?selected:null;
        if(!measure())return model;
        if(!model.N.length){svg.replaceChildren();svg.classList.add('is-atlas');layers={};return model;}
        render();if(!view)view=fitBox(model.box,24);draw(true);
        return model;
      },
      resize: function(){if(!model||!model.N.length||!layers.world||!svg.classList.contains('is-atlas'))return;var prior={w:W,h:H};if(!measure())return;view={s:view.s,x:view.x+(W-prior.w)/2,y:view.y+(H-prior.h)/2};draw(true);},
      fit: function(){if(model&&model.box)flyTo(fitBox(model.box,24));},
      zoomBy: function(f){if(!view)return;var s=Math.max(.15,Math.min(6,view.s*f)),cx=(W-inset())/2,cy=H/2;flyTo({s:s,x:cx-(cx-view.x)*s/view.s,y:cy-(cy-view.y)*s/view.s},200);},
      goTo: function(id){var t=model&&model.territories.get(id);if(t)selectTerritory(t);else clearSelection();},
      detach: function(){if(!svg.classList.contains('is-atlas'))return;cancelAnimationFrame(anim);svg.onwheel=svg.onpointerdown=svg.onpointermove=svg.onpointerup=svg.onpointercancel=svg.onclick=svg.onkeydown=panel.onkeydown=null;
        svg.replaceChildren();svg.classList.remove('is-atlas','has-focus','has-territory');delete svg.dataset.zoom;delete svg.dataset.overlay;panel.hidden=true;panel.replaceChildren();layers={};focused=selected=selectedT=null;drag=null;},
      selectedTerritory: function(){return selectedT?selectedT.id:'';},
      setOpen: function(path){openPath=path||null;markOpen();if(model&&layers.world)placeLabels();},
      // Selects and flies to the entry open in the editor; false when it is not on the map.
      flyToOpen: function(){var o=openNode();if(!o)return false;selectNode(o,true);return true;},
      setOverlay: function(mode){overlay=mode||'kind';applyOverlay();},
      legend: legend,
      summary: function(){return model?{entries:model.entryCount,territories:model.T.length,realms:model.realms.length,hidden:model.hidden,realmList:model.realms.map(function(r){return {name:r.name,territories:r.territories.slice().sort(function(a,b){return a.name.localeCompare(b.name);}).map(function(t){return {id:t.id,name:t.name,count:t.members.filter(function(n){return n.state==='entry';}).length};})};})}:null;}
    };
  }

  window.WorldAtlas = { create: create, buildModel: buildModel };
})();
