// A very small DOM, just enough to run the world desk modules under Node.
// It does not parse HTML: elements looked up by id are created on demand.

class Node {
  constructor() { this.parentNode = null; this.childNodes = []; }
  get children() { return this.childNodes.filter((n) => n instanceof Element); }
  get firstChild() { return this.childNodes[0] || null; }
  get nextElementSibling() {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.children;
    return siblings[siblings.indexOf(this) + 1] || null;
  }
  appendChild(child) {
    if (child instanceof DocumentFragment) {
      child.childNodes.slice().forEach((c) => this.appendChild(c));
      return child;
    }
    if (child.parentNode) child.parentNode.childNodes.splice(child.parentNode.childNodes.indexOf(child), 1);
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }
  append(...nodes) { nodes.forEach((n) => this.appendChild(typeof n === 'string' ? new Text(n) : n)); }
  replaceChildren(...nodes) {
    this.childNodes.forEach((c) => { c.parentNode = null; });
    this.childNodes = [];
    this.append(...nodes);
  }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.childNodes.splice(this.parentNode.childNodes.indexOf(this), 1);
    this.parentNode = null;
  }
  after(node) {
    const siblings = this.parentNode.childNodes;
    if (node.parentNode) node.remove();
    node.parentNode = this.parentNode;
    siblings.splice(siblings.indexOf(this) + 1, 0, node);
  }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(''); }
  set textContent(value) {
    this.replaceChildren();
    if (value !== '') this.appendChild(new Text(String(value)));
  }
}

class Text extends Node {
  constructor(data) { super(); this.data = data; }
  get textContent() { return this.data; }
  set textContent(value) { this.data = String(value); }
}

class DocumentFragment extends Node {}

class ClassList {
  constructor(el) { this.el = el; }
  list() { return this.el.className.split(/\s+/).filter(Boolean); }
  contains(name) { return this.list().includes(name); }
  add(name) { if (!this.contains(name)) this.el.className = this.list().concat(name).join(' '); }
  remove(name) { this.el.className = this.list().filter((n) => n !== name).join(' '); }
  toggle(name, force) {
    const on = force === undefined ? !this.contains(name) : force;
    if (on) this.add(name); else this.remove(name);
  }
}

export class Element extends Node {
  constructor(tagName) {
    super();
    this.tagName = tagName.toLowerCase();
    this.attributes = new Map();
    this.className = '';
    this.dataset = {};
    this.style = { setProperty() {} };
    this.classList = new ClassList(this);
    this.listeners = new Map();
    this.hidden = false;
    this.disabled = false;
    this.value = '';
    this.checked = false;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.innerHTML = '';
  }
  get id() { return this.attributes.get('id') || ''; }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === 'class') this.className = String(value);
    if (name === 'value') this.value = String(value);
    if (name === 'hidden') this.hidden = true;
  }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  removeAttribute(name) { this.attributes.delete(name); }
  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(fn);
  }
  dispatch(type, extra) {
    const event = Object.assign({
      type, target: this, currentTarget: this, preventDefault() {}, key: '', button: 0,
    }, extra);
    (this.listeners.get(type) || []).forEach((fn) => fn(event));
  }
  click() { this.dispatch('click'); }
  focus() {}
  setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; }
  closest() { return null; }
  matches(selector) {
    return selector.split(',').some((part) => matchesSimple(this, part.trim()));
  }
  querySelectorAll(selector) {
    const found = [];
    const walk = (node) => node.children.forEach((child) => {
      if (child.matches(selector)) found.push(child);
      walk(child);
    });
    walk(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  get options() { return this.children.filter((c) => c.tagName === 'option'); }
  remove(index) {
    if (this.tagName === 'select' && index !== undefined) this.options[index].remove();
    else super.remove();
  }
  select() {}
  reset() {}
  showModal() {}
  close() {}
}

// Supports tag, .class, [attr], [attr="v"], and combinations like input:checked.
function matchesSimple(el, selector) {
  const pattern = /^([a-z][a-z0-9]*)?((?:\.[\w-]+)*)((?:\[[^\]]+\])*)(:checked)?$/i;
  const m = selector.match(pattern);
  if (!m) return false;
  if (m[1] && el.tagName !== m[1].toLowerCase()) return false;
  if (!(m[2] || '').split('.').filter(Boolean).every((c) => el.classList.contains(c))) return false;
  const attrs = (m[3] || '').match(/\[[^\]]+\]/g) || [];
  for (const attr of attrs) {
    const [name, raw] = attr.slice(1, -1).split('=');
    const value = raw === undefined ? null : raw.replace(/^"|"$/g, '');
    const has = el.attributes.has(name);
    if (!has || (value !== null && el.attributes.get(name) !== value)) return false;
  }
  return !(m[4] && !el.checked);
}

class Option extends Element {
  constructor(text, value) {
    super('option');
    this.textContent = text;
    this.value = value === undefined ? text : value;
  }
}

export function installFakeDom() {
  const byId = new Map();
  const listeners = new Map();
  const body = new Element('body');
  const document = {
    body,
    getElementById(id) {
      if (!byId.has(id)) {
        const el = new Element(id === 'entryText' ? 'textarea' : 'div');
        el.setAttribute('id', id);
        byId.set(id, el);
      }
      return byId.get(id);
    },
    createElement: (tag) => (tag === 'option' ? new Option('', '') : new Element(tag)),
    createElementNS: (_ns, tag) => new Element(tag),
    createTextNode: (data) => new Text(String(data)),
    createDocumentFragment: () => new DocumentFragment(),
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    },
  };
  Object.assign(globalThis, {
    document,
    Option,
    window: { confirm: () => true, addEventListener() {}, location: { origin: 'http://127.0.0.1:8000' } },
    location: { href: 'http://127.0.0.1:8000/world', origin: 'http://127.0.0.1:8000' },
  });
  return { document, byId, listeners };
}

export function uninstallFakeDom() {
  ['document', 'Option', 'window', 'location'].forEach((name) => { delete globalThis[name]; });
}

// Routes fake HTTP: routes maps 'METHOD /path' to a body or a function.
export function installFakeFetch(routes) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    const method = (init && init.method) || 'GET';
    const path = url.split('?')[0];
    calls.push({ method, url, path, body: init && init.body ? JSON.parse(init.body) : undefined });
    const route = routes[method + ' ' + path];
    if (route === undefined) return { status: 404, json: async () => ({ ok: false, message: 'No route ' + method + ' ' + path }) };
    const reply = typeof route === 'function' ? route(calls[calls.length - 1]) : route;
    const status = reply.status || 200;
    return { status, json: async () => reply.body };
  };
  return calls;
}

export function texts(el) {
  return el.textContent;
}

export function findAll(el, predicate) {
  const out = [];
  const walk = (node) => node.children.forEach((c) => { if (predicate(c)) out.push(c); walk(c); });
  walk(el);
  return out;
}
