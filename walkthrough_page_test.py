import unittest

import walkthrough_page


class WalkthroughPageTest(unittest.TestCase):

  def test_page_comes_from_the_markdown_walkthrough(self):
    page = walkthrough_page.page()

    for section in ('Open your vault', 'Find or create an entry',
                    'Write, preview, and save',
                    'Use the reports to guide the next edit', 'Map and Story'):
      self.assertIn(section, page)
    self.assertIn('python3 serve.py --vault ~/Documents/Worldbuilding', page)
    self.assertIn('A reed bird that predicts the fog', page)
    self.assertIn('<h2 id="open-your-vault">Open your vault</h2>', page)
    self.assertIn('href="#open-your-vault"', page)
    self.assertEqual(page.count('<h1'), 1)

  def test_desk_link_depends_on_vault_configuration(self):
    self.assertNotIn('href="/world">Open desk', walkthrough_page.page())
    self.assertIn('href="/world">Open desk',
                  walkthrough_page.page(vault_configured=True))

  def test_renderer_escapes_note_content(self):
    rendered = walkthrough_page.render_markdown('# A <script>bad()</script>\n\n- **safe**')

    self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', rendered)
    self.assertNotIn('<script>', rendered)
    self.assertIn('<strong>safe</strong>', rendered)
