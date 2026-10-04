// /?embed=1 is the generator inside the world desk's drawer: no site header,
// no links that would navigate the frame away. Loaded as a blocking script in
// <head>, so the attribute is set before paint and nothing flashes. A separate
// file rather than an inline script, so a hosted Content-Security-Policy can
// forbid inline scripts.
if (/(^|[?&])embed=1(&|$)/.test(location.search)) document.documentElement.setAttribute('data-embed', '');
