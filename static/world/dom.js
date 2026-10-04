// Small DOM helpers. Importing this module does not touch the document.

export const $ = (id) => document.getElementById(id);

function applyProp(node, key, value) {
  if (value == null || value === false) return;
  if (key === 'class') node.className = value;
  else if (key === 'text') node.textContent = String(value);
  else if (key === 'dataset') Object.assign(node.dataset, value);
  else if (key.indexOf('on') === 0) node.addEventListener(key.slice(2), value);
  else if (value === true) node[key] = true;
  else node.setAttribute(key, String(value));
}

function appendChild(node, child) {
  if (child == null || child === false) return;
  if (Array.isArray(child)) child.forEach((item) => appendChild(node, item));
  else node.appendChild(typeof child === 'object' ? child : document.createTextNode(String(child)));
}

// h('button', {class: 'btn', type: 'button', onclick: fn}, 'Label', child...)
export function h(tag, props, ...children) {
  const node = document.createElement(tag);
  Object.keys(props || {}).forEach((key) => applyProp(node, key, props[key]));
  children.forEach((child) => appendChild(node, child));
  return node;
}

// An element holding only text; the most common shape in the reports.
export function textNode(tag, text, className) {
  return h(tag, { class: className, text: text == null ? '' : text });
}

export function button(label, className, onclick) {
  return h('button', { type: 'button', class: className, onclick }, label);
}

export function setStatus(text, kind) {
  const node = $('worldStatus');
  node.textContent = text;
  node.className = 'world-status' + (kind ? ' is-' + kind : '');
}
