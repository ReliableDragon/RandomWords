"""Safe, deliberately small renderer for the bundled Worldbuilding guide."""

import html
import os
import re


GUIDE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'WORLD_WALKTHROUGH.md')


def inline(text):
  """Render the few inline forms used by the maintained walkthrough."""
  escaped = html.escape(text)
  escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
  escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
  return escaped


def heading_id(text):
  """Create a stable, safe fragment identifier from a Markdown heading."""
  slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
  return slug or 'section'


def render_markdown(markdown):
  """Render headings, paragraphs, bullets, and fenced examples without HTML."""
  output = []
  paragraph = []
  list_items = []
  code_lines = []
  code_language = ''
  in_code = False

  def flush_paragraph():
    if paragraph:
      output.append('<p>%s</p>' % inline(' '.join(paragraph)))
      paragraph.clear()

  def flush_list():
    if list_items:
      output.append('<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(item)
                                             for item in list_items))
      list_items.clear()

  for raw_line in markdown.splitlines():
    line = raw_line.rstrip()
    if line.startswith('```'):
      flush_paragraph()
      flush_list()
      if in_code:
        output.append('<pre><code%s>%s</code></pre>' % (
            (' class="language-%s"' % html.escape(code_language))
            if code_language else '', html.escape('\n'.join(code_lines))))
        code_lines.clear()
      else:
        code_language = line[3:].strip()
      in_code = not in_code
      continue
    if in_code:
      code_lines.append(raw_line)
      continue
    if not line:
      flush_paragraph()
      flush_list()
      continue
    match = re.match(r'^(#{1,6})\s+(.+)$', line)
    if match:
      flush_paragraph()
      flush_list()
      level = len(match.group(1))
      title = match.group(2)
      output.append('<h%d id="%s">%s</h%d>' % (
          level, heading_id(title), inline(title), level))
      continue
    if line.startswith('- '):
      flush_paragraph()
      list_items.append(line[2:])
      continue
    flush_list()
    paragraph.append(line)

  flush_paragraph()
  flush_list()
  if in_code:
    output.append('<pre><code>%s</code></pre>' % html.escape('\n'.join(code_lines)))
  return '\n'.join(output)


def page(vault_configured=False):
  with open(GUIDE_PATH, encoding='utf-8') as guide:
    content = render_markdown(guide.read())
  return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Worldbuilding walkthrough · RandomWords</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/app.css"></head>
<body class="guide-page"><header class="guide-top"><a href="/" class="world-brand">RandomWords</a><span class="world-sep">/</span><span>Worldbuilding walkthrough</span>%s</header>
<main class="guide-layout"><aside class="guide-aside"><p class="eyebrow">WORLD BUILDING</p><h2>Build a world one connected note at a time.</h2><p>The desk works with your Markdown vault in place.</p><a class="btn btn-primary" href="#open-your-vault">Set up your vault</a></aside><article class="guide-content">%s</article></main>
</body></html>''' % (
      '<a class="btn btn-small btn-quiet" href="/world">Open desk</a>'
      if vault_configured else '', content)
