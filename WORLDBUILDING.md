# Proposal: a worldbuilding desk on top of RandomWords

The vault at `~/Documents/Worldbuilding` is an Obsidian vault of 287 notes
and about 72,000 words, most of them written by drawing two or three words
from the 450k list and following where they led. This proposes a second page
in the RandomWords browser interface that opens that vault: to write entries
beside the word bench, to see what an entry is connected to, and to be told,
while writing, which existing entries the new one probably touches.

It is a proposal, not a plan of record. Each phase is usable on its own,
starting with the complete writing loop. The vault measurements below are
from 2026-09-09; the design and delivery sequence were revised on 2026-09-23.

---

## Contents

- [What the vault is](#what-the-vault-is)
- [Where it hurts](#where-it-hurts)
- [Principles](#principles)
- [The pieces](#the-pieces)
  - [The vault behind the library](#the-vault-behind-the-library)
  - [An entry, parsed](#an-entry-parsed)
  - [The vault index](#the-vault-index)
  - [The desk](#the-desk)
  - [Nearby](#nearby)
  - [The map](#the-map)
  - [From words to entries](#from-words-to-entries)
  - [Housekeeping](#housekeeping)
  - [The lexicon](#the-lexicon)
  - [Story mode](#story-mode)
- [The page](#the-page)
- [What the server would expose](#what-the-server-would-expose)
- [Files](#files)
- [Phases](#phases)
- [Open questions and risks](#open-questions-and-risks)

---

## What the vault is

An Obsidian vault, in git, with Obsidian Sync turned on. Folders are the
taxonomy: the top level is the *kind* of thing, and under `Flora and Fauna`
and `Cultures` the next levels are biome class and region.

| Folder | Notes | Holds |
|---|---|---|
| `Flora and Fauna/<class>/<region>/` | 104 | Creatures and plants, one per note |
| `Othernatural/Arts/{Kinds,Examples}/…`, `Occurrences/`, `Structures/` | 73 | The magic systems and their examples |
| `Locations/Biomes/<class>/`, `Places/`, `Settlements/` | 50 | The regions themselves |
| `Cultures/<region>/` | 22 | Customs, institutions, technologies |
| `People/` | 13 | The Order of Uncovery, the expedition whose members narrate the entries |
| `Cosmology/`, `Geonomy/`, `Phenomena/` | 15 | Gods, minerals, weather |
| `Ideas/`, `Templates/`, root | 10 | Backlog, templates, the overview and cheat sheet |

Notes are short. The median entry is 199 words, nine in ten are under 540,
and the longest (Escarchaic) is 1,484. Twenty-three are under twenty
words: placeholders, or headers with nothing under them yet.

### The conventions already in use

Nothing in the vault is enforced by a schema, but the notes are far more
regular than that suggests. These are the shapes an app has to read, and,
when it writes, has to write back unchanged:

| Convention | Seen in | Example |
|---|---|---|
| Title is the filename | every note | `Józef Kościuszko, Journeyman.md` |
| `From: [[Region]]` as the first line | 152 notes | `From: [[Loaming Country]]` |
| `Origin:` or `Source:` line listing the seed words, with glosses in escaped brackets | 151 notes | `Source: calothrix \[genus of freshwater cyanobacteria\] …` |
| `Themes:` line on biome notes | 22 notes | `Themes: Heat, Sun` |
| Inline `#tags`, drawn from `Tags.md` plus one tag per region | most creature notes | `#loaming #animal` |
| `aliases` in YAML frontmatter | 23 notes, 34 aliases | `Unilux` is also `Sightstone` |
| `[[wikilinks]]`, with `\|text` and `#heading` forms | 373 links | `[[Dr. Otto Battar, Zoologist]]` |
| `${…}` for a note to yourself inside the text | 16 notes | `${Should the Wagtail be able to lay eggs more than once?}` |
| `#rework` on an entry you are not happy with | 8 notes | |
| A quotation ending in `- [[Person]]` | 29 quotes, 8 speakers | the Battar passage in Aurochult |
| ` ```base ` blocks that list linked notes by folder | biome notes, via the template | `file.links.contains(this.file.name)` |

`How-To.md` is the method: two or three words from the 450k list, a list of
facets to write about (Behaviors, Legends, Misconceptions, Uses, …), and one
sentence of advice that this whole proposal is really about:

> If it's possible to work in at least one interaction with or reference to
> a previous entry, that adds a lot of depth.

## Where it hurts

The difficulty of managing connections is measurable, and the numbers say
what the tool needs to do.

| | Count | Meaning |
|---|---|---|
| Entries nothing links to | 191 of 287 | Two thirds of the world is reachable only through the folder tree |
| Entries linking to nothing | 65 | |
| Fully isolated notes | 16 | |
| Names of entries used in other notes without a link | about 90 | `Aitrip` is discussed in Helay and in Examainour, unlinked; `Teutriallus` in Judicial Appointment |
| Links to notes that do not exist | 6 | Port Bofala, Eonian Cypresses, Jibber-Jabber, Hush Blossom, fiefdoms, Sunless Sycamore |
| Hub notes that are empty | at least 1 | `Episteme`, which fifteen entries link to, is a zero-byte file |
| Capitalised names with no entry | several | Shimmering Folk, Fate Foulers, Gelatinate Janitors, Impetals |
| Coined words with a second spelling | dozens | `alzarati`/`alzerati`, `daindowne`/`dainedowne`, `dzarantic`/`dzurantic`, `batar's`/`battar's` |
| Counts maintained by hand | one file | `Overview.md` carries `(8)`, `(3)`, `(1)` after each biome |

Obsidian's backlinks pane does list unlinked mentions, but only exact title
matches, and the workspace has that section collapsed. The graph view shows
what is linked, not what should be. Neither of them knows what you are
writing right now, and neither of them is in the same window as the word
bench. That gap is the product.

## Principles

1. **The files are the truth.** The vault stays an Obsidian vault, in git,
   under Sync. The app is a second front end onto the same markdown files,
   the way the browser is a second front end onto the same commands. There is
   no import, no database, and nothing that has to be kept in step.
2. **Read every convention in use, and write the same ones back.** The raw
   source is kept beside the parsed views. An untouched note is not rewritten;
   an edited one keeps its existing frontmatter location, newline convention,
   BOM and final-newline convention. No frontmatter is added to a note that
   has none; no `From:` line is moved. Migration to properties can happen
   later, note by note, if Bases ever needs it.
3. **Derived data never goes in the vault.** The vault index is small enough
   to live only in memory and be rebuilt. Recovery copies made before an
   explicitly confirmed replacement are user data, not derived data; they go
   in a RandomWords-owned recovery directory outside the vault. Obsidian Sync
   and the vault's git repository see neither.
4. **Same stack, same shapes.** Standard library Python, one static page in
   vanilla JavaScript, the tokens in `app.css`, `CommandResult`-shaped
   responses with `{ok, message, data}`, and a 409 question for anything that
   would overwrite. A stale save is a reviewable conflict, not a surprise.
5. **Do not rebuild Obsidian.** Obsidian already renames with link updates,
   syncs, searches, and draws a graph. The app builds what Obsidian does not:
   suggestion while writing, health reports, the lexicon, the coverage
   matrix, and the join with the word bench. Where the app repeats something
   (rendering a note, a local graph) it is because the feature next to it
   needs it, and it is kept small.

---

## The pieces

### The vault behind the library

`serve.py --vault ~/Documents/Worldbuilding` opens a second root. Without
the flag the world routes answer 404 and the page hides its tab, so the tool
is unchanged for anyone who has no vault.

`FileManager` cannot be reused for this root, because its rules are the
library's rules: filenames of letters, digits and underscores, ending in
`.txt`. Vault names have spaces, commas, ampersands, diacritics and one
called `???`. A `VaultManager` in `vault.py` follows `FileManager`'s design
rather than its code:

- A *vault path* is relative to the vault root, `/`-separated. A segment may
  be anything except empty, `.`, `..`, or something starting with `.`. That
  last rule is what keeps `.obsidian`, `.git` and Obsidian's `.trash` out of
  every listing, read and write.
- `resolve` checks the resolved real path is under the root, exactly as
  `FileManager.resolve` does, so a symlink cannot walk out either.
- A note's canonical identity is its vault path, not its title. Title and
  alias keys are compared after NFC normalisation and case-folding, but their
  indexes are multimaps: the vault already contains two notes called
  `Wickrill`, two called `Overview`, and two called `Biomes`. A collision in
  path spelling after normalisation or case-folding is diagnosed instead of
  silently merging two files.
- Reads and writes are `.md` only. A read returns the decoded text and an
  opaque revision string: a content hash of the exact bytes read. JavaScript
  never has to preserve a nanosecond integer or infer identity from a time.
- Writes are serialized per path inside the process. Under that path's lock,
  `write` reads the file again, compares its revision with the caller's, and
  only then writes a temporary file and uses `os.replace`. A mismatch becomes
  a 409 containing the current revision and source for comparison.
- Replacing a changed file is a second, version-bound operation, not an
  unqualified `force: true`. The user reviews the conflicting source, and the
  retry names that exact `replace_revision`. Under the same path lock the
  server rechecks it, saves those replaced bytes to the recovery directory,
  and then writes; another intervening change produces another 409. The
  response names the recovery copy.
- No delete, no rename. Obsidian renames with `alwaysUpdateLinks` on, which
  rewrites every link to the note; the app should not have a worse version.

The one file outside `.md` that the app reads is `.obsidian/graph.json`, for
its colour groups, so the map can use the same colours as Obsidian's graph.
It is read-only and specific.

The lock makes two RandomWords requests behave correctly, and the revision
checks make ordinary Obsidian edits visible. They cannot lock Obsidian or
Sync: an external writer can still land between the final check and the
replace. Atomic replacement prevents a torn file; it is not by itself a
cross-process lost-update guarantee. Keeping the draft recoverable in the
browser and keeping the replaced bytes outside the vault are the backstops.

### An entry, parsed

`entry.py` turns a note's text into an `Entry`, and an `Entry` back into
text for rendering and export. Nothing is lost in the round trip; the raw
text is kept and the fields are views onto it.

```
Entry
  path        'Cultures/Loaming Country/The Fernlicht.md'
  title       'The Fernlicht'
  kind        'Cultures'                 # top folder
  folder      'Cultures/Loaming Country'
  from_targets [Link('Loaming Country')] # ordered, exactly as written
  biomes      [Membership(path='Locations/Biomes/Grassland-Savannah/Loaming Country.md',
                          via='from_target')]
  origin      ['hamperedness', 'kallitype', 'corespondency']
  glosses     {'kallitype': 'An early photograph …'}
  themes      []
  aliases     []
  tags        []
  links       [Link('Unilux', resolved_path='Geonomy/Unilux.md'),
               Link('Fotografluorite', resolved_path='Geonomy/Fotografluorite.md')]
  notes       []                         # the ${…} asides
  quotes      []                         # (text, speaker) pairs
  body        # text after the header lines
  words       1484
  stub        False
  revision    'sha256:…'                 # opaque outside VaultManager
```

`from_targets` is plural. Eighteen notes already name more than one place:
`Mayoral Accessibility` comes from both `Ever-Dismal Okeree` and `Fenaya`,
and `Geomecko` names both `Cloudlands` and `Moonpierce Mountains`. The parser
keeps target order, display text and source span. API spans are measured in
UTF-16 code units, the same units JavaScript uses for textarea selection;
the Python parser converts to that coordinate system at the boundary instead
of exposing Python code-point offsets. Geography is a separate,
resolved view. A target that is itself a biome gives a direct membership; a
settlement or place can lead through its own `From:` links to one or more
biomes. Folder fallback is allowed only for declared taxonomy shapes such as
`Flora and Fauna/<class>/<region>/` and `Cultures/<region>/`, using an explicit
folder-to-biome mapping first (`Bitters` to `Bitter Return Mountains`, for
example) and otherwise a unique biome title or alias. `People/`,
`Locations/Settlements/` and arbitrary Othernatural folders are never
mistaken for regions. Every inferred membership retains whether it came from
a direct target, an ancestor target or a schema-specific folder fallback.
Following place ancestry has cycle detection and deduplicates canonical biome
paths without losing the original ordered `From:` targets.

Links resolve with the source note as context. An explicit vault-relative
path wins, then an exact title in the source folder, then a unique global
title or alias. More than one remaining candidate is *ambiguous*, not an
arbitrary edge; the candidates are returned to the UI. Autocomplete inserts
the short title when it is unique and a qualified target such as
`[[Othernatural/Arts/Instances/Paranatural Arts/Techne/Wickrill|Wickrill]]`
when it is not. Unresolved and ambiguous links remain distinct graph node
states.

Rendering covers the subset of markdown the vault actually uses: headings,
bullets with tab indentation, bold, italic, strikethrough, blockquotes,
wikilinks in all three forms, plain links and bare URLs, escaped brackets,
and `${…}` asides, which render as margin notes in the muted colour. Raw HTML
is always escaped. External links are emitted only for an allowlist of
schemes (`http`, `https`, `mailto`) after rejecting control-character and
scheme-obfuscation tricks; internal targets are encoded as vault paths rather
than copied into an `href`. HTML-escaping label text does not make an unsafe
URL safe, so both halves are tested separately.

The first release shows every ` ```base ` block as code. Evaluating the
small `file.links.contains` and `file.path.contains` subset is useful beside
the map, but it comes later, after fixtures cover the indentation and view
forms actually in the vault. An unrecognised Base expression always remains
visible code rather than being partly or silently evaluated.

Rendering is server-side, in Python, for two reasons: one implementation for
the preview and the export, and one that a test can drive.

### The vault index

`vault_index.py` is to the vault what `word_index.py` is to the library:
the one structure that knows the whole thing. It holds:

- every `Entry`, by canonical path, with title and alias multimaps and a list
  of normalisation collisions;
- the link graph, both directions, with unresolved targets kept as their own
  node type and ambiguous targets kept with all candidates;
- a term index over entry bodies, keeping actual term frequencies and
  document lengths for BM25. It uses the library's Unicode word regular
  expression but only a small grammatical stop list; world-bearing words
  such as `water`, `forest`, `medicine`, `glass` and `river` stay in the
  index and BM25's IDF handles ordinary corpus frequency;
- the lexicon (see below);
- tag, direct-place and canonical-biome tables, with membership provenance.

Unlike the word index it needs no on-disk cache. The library is 131 books
and 1.8 million words and takes seven seconds to read; the vault is 287
files and 72,000 words and parses in a fraction of a second. So: build on
the first request that needs it, stat the tree on later requests (throttled
to once a second), and rebuild the whole thing when any modification time
has changed. Incremental updates are a complexity the size does not justify.
The index is shared by every session, like `WordIndex`, and swapped in under
a lock the same way.

### The desk

The middle column is an editor. A textarea, not a rich editor: the vault's
markdown is simple enough that a textarea in `--font-display` at a readable
measure is the right tool, and it keeps the page dependency-free.

- **Open** from the tree, from search, from a link in a rendered note, from a
  node on the map, or from a Nearby card.
- **Save** with Ctrl-S or the button. The request carries the opaque revision
  returned when the exact source bytes were read. A 409 preserves the draft,
  shows the on-disk version beside it, and offers *Keep draft*, *Reload* and
  *Replace reviewed version*. Reloading first stashes the draft in browser
  recovery storage; replacing sends the revision of the on-disk version just
  reviewed, and the server keeps its own recovery copy. While the draft is
  untouched, the page polls the note's revision and reloads silently if
  Obsidian changed it. A dirty draft is never silently reloaded or discarded.
- **`[[` autocomplete.** Typing `[[` opens a list over titles and aliases,
  filtered as you type, ordered by Nearby's current ranking so the entry you
  probably mean is at the top. Choosing an alias inserts `[[Title|alias]]`
  when unique; duplicate titles show their folders and insert a qualified
  target. Typing `#` offers the tags from `Tags.md` and every tag in use.
- **Preview** toggles between the textarea and the rendered note, or shows
  both side by side when the window is wide. The rendered view is what the
  same debounced request that powers Nearby sends back, so there is one
  round trip per pause in typing, not two.
- **Backlinks** under the note, as Obsidian shows them, with the sentence
  each link sits in. This is the cheap half of "what is this connected to";
  the map is the other half.
- **Reference cards.** Ctrl-click a wikilink or click a Nearby title to open
  the entry's header lines, first paragraph, `## Facts` section if present,
  and attributed quotes in a split beside the draft. Looking something up
  never navigates away from the sentence being written.

### Nearby

The right column, and the reason to build any of this. Every half second of
quiet while you type, the page posts the draft with a client revision, and
the server answers with the entries it probably concerns, grouped by *why*,
not merged into one opaque score. The first release includes named mentions,
shared biome or tags, and reference cards. The later groups build on the same
response shape:

| Group | Signal | Action offered |
|---|---|---|
| **Named, not linked** | An unambiguous entry title or alias appears in prose and that occurrence is not linked | *Link it* at that exact source span |
| **Same biome** | The draft and entry share at least one canonical biome membership; direct shared settlements or places are called out separately | open, insert link |
| **Same tags** | Tag overlap, ranked by Jaccard | open, insert link |
| **Talks about the same things** | BM25 over body term frequencies and document lengths: two entries that both say `Fotografluorite` are nearly linked already | open, insert link, and the shared words are shown |
| **Linked from what you link** | Two hops through the graph | open, insert link |
| **Names without an entry** | Capitalised phrases in the draft that match no title and no alias | *Start an entry*, prefilled |

Each card is the entry's title, kind and biome memberships, its first sentence
or two, and the reason it is here. Clicking the title opens it in a split so the
draft stays in place; this is the "pull up reference" part of the request,
and it should never navigate away from what you are writing.

A *Link it* result carries the canonical target path, exact `[start, end)`
source span in UTF-16 code units, expected text and client revision. Detection
excludes existing wikilinks, frontmatter and fenced code. The browser discards
out-of-order Nearby responses and, before changing the textarea, checks the revision
and expected span. If either changed, it asks for a fresh result. This keeps
a delayed suggestion from editing newer prose and makes overlapping title or
alias matches explicit.

The whole scoring pass is over fewer than three hundred documents, so there
is nothing to optimise: it is a few milliseconds of Python per keystroke
pause.

BM25 and two-hop graph suggestions come after the basic panel. Their ranking
is accepted against a small fixture of known related and unrelated note pairs,
not merely because it produces a list. The book index already
knows which words keep company with which (`like`), so an entry whose seed
words are neighbours of the draft's seed words could be surfaced as *seeded
from the same corner of the dictionary*. And the draft's own seed words can
be looked up with `which` to show what the library thinks they mean, which is
half of what the glosses in `Origin:` lines are for today.

### The map

Obsidian has a graph, and the app should not have a worse one. So the map
does three things Obsidian's does not.

**It shows what might connect, not only what does.** The local map around
the open note (depth one or two) draws Nearby's results as ghost nodes with
dashed edges: link one and it becomes solid. This is the picture of the
suggestion panel.

**It marks the state of things.** Node size follows inbound links. Stubs are
hollow. Unresolved targets are dashed outlines. `#rework` entries carry a
ring. Colours are read from `.obsidian/graph.json`, so the kinds are the
same colours in both tools.

**It has a shape.** The force layout is one view; the other is the *biome
view*: pick a canonical biome path, and its note sits in the centre with its
wildlife, culture, geonomy, othernatural, settlements and the people who have
been there in sectors around it. That is the Biome Template's five base
blocks drawn as a picture, and the first time the vault's own taxonomy is
visible rather than implied.

Alongside the map, the **coverage matrix**: canonical biomes as rows, kinds as
columns, counts in the cells, and a click on a cell lists the entries and how
each membership was derived. A note with two biome memberships is counted
once in each, while a biome plus one of its settlements remains one biome
membership. Empty cells are where the world is thin: a biome with six
creatures and no culture note, a magic system with kinds but no examples. It
replaces the counts kept by hand in `Overview.md`, and unlike them it is
never out of date.

The layout is a small Verlet simulation in `world.js`, about a hundred
lines, drawing to SVG. Three hundred nodes is well inside what that handles.
Vendoring `d3-force` as a single file into `static/` would also be
defensible, but the house style is no dependencies and the simulation is not
hard.

### From words to entries

The join with the bench, and the part that exists nowhere else.

- **The bench in a drawer.** The page keeps the existing draw controls and
  kept words in a strip along the bottom, over the same `/api/draw` and pool
  routes. Draw three from `450k_words`, keep the ones that spark. `Sandbox.md`
  is where those words go today; kept words are that scratch, structured.
- **Start an entry.** From kept words: choose the exact destination folder,
  zero or more canonical `From:` targets, a title, tags, and optionally a
  template from `Templates/`. The folder choice and geography are separate;
  neither silently derives the other. The file is written with the selected
  ordered targets (and no `From:` header when there are none), an `Origin:`
  line built from the kept words, and only the tags the form displays and
  confirms, then opens in the desk. Creation is
  exclusive at that destination path. Another note with the same basename in
  a different folder is allowed; an existing or NFC/casefold-equivalent
  destination is a 409 and is never a force-overwrite flow. Glosses are typed
  by hand, with a Wiktionary
  link per word, because the server has no reason to go on the network. An
  entry started from a Nearby *name without an entry* is the same flow with
  the title filled in.
- **The roller.** One button, and the advice in `How-To.md` becomes
  mechanical: it picks a facet from the cheat sheet (parsed from the file, so
  editing the list changes the roller), an existing entry weighted toward the
  191 that nothing links to, and two words from the active pool:

  > *Misconceptions* · **Helay** · `showful` `arthrosporic`

  or, with two entries from the same biome, an *interaction*:

  > *Interaction* · **Wickrill** × **Charing Oxen**

  Every roll is an invitation to link something old from something new,
  which is the one habit that fixes the numbers in the table above.
- **The backlog.** `Ideas/` rendered as a list; *Start an entry* from an idea
  strikes it through in the file, which is the convention already in use
  there.

### Housekeeping

One page, computed from the index, that answers "what needs doing" without
anybody keeping a list:

| Section | Today | One click does |
|---|---|---|
| Stubs (under twenty words) | 23, including `Episteme` with 15 inbound links | open |
| Links to nothing | 6 targets | open the create form with the source note's ordered `From:` targets prefilled for review |
| Isolated notes | 16 | open, with Nearby already populated |
| Nothing links here | 191 | roll an interaction for it |
| `#rework` | 8 | open |
| Notes to yourself | 16 notes' `${…}` asides, gathered into one list with their context | jump to the line |
| Names without an entry | Shimmering Folk, Fate Foulers, Gelatinate Janitors, … | start an entry |
| Spelling drift | see below | open both |

The asides are worth singling out. Questions like *Should the Wagtail be
able to lay eggs more than once?* are scattered through sixteen files where
only rereading finds them. Gathered, they are the design to-do list the vault
already contains.

### The lexicon

The vault's vocabulary minus the 450k list is the invented language of the
world: 651 words, 361 of them capitalised somewhere, and 263 of those used
in a single note. This is exactly the set operation the tool exists to do, computed with
the same tokeniser, so "not in the dictionary" here means what `diff` means.

The lexicon page lists them with every spelling seen and every note that
uses them, filtered by canonical biome or by "used once". Its two useful checks:

- **Drift.** Coined words within edit distance two of a more frequent coined
  word. Plurals and possessives are filtered out; what remains today is
  `alzerati` beside `alzarati`, `dainedowne` beside `daindowne`, `dzarantic`
  beside `dzurantic`, `batar's` beside `battar's`, `escharchaics` beside
  `escarchaic`. The desk underlines the rarer spelling as you type it, with
  the common one offered.
- **Already a word?** `which` against the book index answers whether a
  coinage is real somewhere in 131 books, instantly. `unilux` is in none of
  them; a name that turns out to be a common word in three botany texts is
  worth knowing about before it is used in a hundred places.

### Story mode

Writing a story set in the world is the same activity with the text in a
different folder, so most of the desk carries over unchanged. Nearby works on
a scene exactly as it works on an entry: the scene mentions Fenaya and a
Coot, and there are Fenaya and the Coot. What story writing adds first is an
ordered report of what appears where. It does not pretend that scene order is
the same thing as the reader's introduction or a character's knowledge.

- **Scenes** are notes under a configured story folder with a small,
  deliberately supported frontmatter contract that Obsidian's properties
  pane can also edit:

  ```yaml
  ---
  when: 7
  where: "[[Fenaya]]"
  who: ["[[Artellus Poiné, Naturalist]]", "[[Dr. Otto Battar, Zoologist]]"]
  ---
  ```

  `when` is an integer; ties break by canonical scene path and missing or
  invalid values sort last with a diagnostic. `where` accepts one wikilink or
  a list, and `who` accepts a list. The parser supports only frontmatter
  scalars plus block or quoted flow lists; unsupported YAML remains raw and
  gets a diagnostic rather than a guess. This covers the vault's existing
  scalar `aliases: Juran`, block-list aliases, and the scene form without
  taking on all of YAML. Parsed fields remain views over the source, so saving
  an unrelated edit does not reformat frontmatter.
- **Appearance report.** Scenes sorted by `when` report the first and later
  body mention of every resolved entry. Metadata references from `where` and
  `who` are shown separately: they pin reference cards but do not count as a
  prose appearance. The first version makes no "introduced too late" warning;
  a mention is not proof that the narrative introduced a subject there.
- **Later continuity metadata.** Richer checks need explicit semantics such
  as `introduces`, point of view, and character `discovers` or `knows`
  events. Co-presence in a scene does not establish knowledge, and narration,
  flashbacks and secrets make that shortcut actively misleading. If those
  fields prove pleasant to maintain, later checks remain advisory and cite
  the metadata that produced them.
- **Voices.** The 29 attributed quotations, eight speakers, gathered onto
  each person's page automatically. Juran Calota has eight lines on record
  and Kath Ingerson one; when drafting a new one, the existing ones are
  beside it. The People notes already carry aliases (`de Relba`,
  `Arin de Relba`), so mention detection for people works today.
- **Export.** A folder or the story compiled to one HTML page in the app's
  typography, wikilinks turned into anchors, with a glossary of every entry
  referenced, in first-mention order for a story and alphabetical for a
  biome. Reading a biome straight through is the best consistency check
  there is, and today it takes opening fifty files.

---

## The page

A second page at `/world`, not a fourth column on the existing one. It
shares `app.css` and its tokens, and keeps the bench as a strip along the
bottom so a draw is never more than a glance away.

```
+----------------------+---------------------------------------+--------------------+
| World      [search]  | The Fernlicht         Cultures/Loaming| Nearby             |
|                      | From: [[Loaming Country]]             |                    |
| ▸ Cosmology          | Origin: hamperedness […] kallitype […]| Named, not linked  |
| ▾ Cultures           |                                       |  Unilux     [link] |
|   ▾ Loaming Country  | The value, and difficulty, of using   |                    |
|     The Fernlicht ●  | [[Unilux]] for communication spawned  | Same biome         |
|     Charing Oxen     | an entire field of study after its    |  Charing Oxen      |
| ▸ Flora and Fauna    | discovery. Numerous attempts were     |  Aurochult         |
| ▸ Geonomy            | made to find a way to …               |                    |
| ▸ Locations          |                                       | Talks about        |
| …                    |                                       |  Fotografluorite   |
|                      |                                       |   filter · lead    |
| Map  Matrix  Health  |                                       |                    |
| Lexicon  Roll        | [Save]  [Preview]      1,484 words    | Linked from those  |
|                      |                                       |  Dustlands         |
+----------------------+---------------------------------------+--------------------+
| 450k_words · 3 ▾ [Draw]  hamperedness  kallitype  corespondency   [Start an entry]|
| > _                                                                               |
+-----------------------------------------------------------------------------------+
```

The command line stays, and gains nothing at first. If some of this turns
out to be wanted in the terminal too (`orphans`, `lexicon`, `roll`), they are
ordinary commands and go through `command_list.py` like any other; the web
parity test would then cover them for free.

## What the server would expose

All under `/api/world/`, all behind the same loopback, Host, Origin and
content-type checks as everything else. The body cap becomes per-route: the
world routes accept a megabyte, because a story chapter is longer than a
pool name, and every existing route keeps its 64 KB.

| Method | Path | Body or query | Does |
|---|---|---|---|
| `GET` | `/api/world/tree` | `?path=Cultures` | Folders and notes under a vault path, with word count and stub flag |
| `GET` | `/api/world/entry` | `?path=…` | Raw text, opaque byte revision, parsed views, safe rendered HTML, links and backlinks with context |
| `POST` | `/api/world/entry` | `{path, text, revision}` or `{path, text, revision, replace_revision}` | Writes only against the named revision and returns the new revision; a 409 carries the current revision and source, and a replacement is bound to the reviewed `replace_revision` |
| `POST` | `/api/world/new` | `{folder, title, from_targets, tags, origin, template}` | Exclusively creates the destination path, returning its canonical path and initial revision; 409 only if that path or an NFC/casefold-equivalent spelling exists |
| `POST` | `/api/world/nearby` | `{text, path, client_revision}` | Safe rendered preview plus grouped suggestions and versioned source spans |
| `GET` | `/api/world/search` | `?q=` | Titles and aliases first, then full text |
| `GET` | `/api/world/graph` | `?around=…&depth=2` | Nodes and edges; the whole vault without `around` |
| `GET` | `/api/world/matrix` | | Canonical biome × kind counts, entries and membership provenance |
| `GET` | `/api/world/health` | | Every section of the housekeeping page |
| `GET` | `/api/world/lexicon` | `?q=&biome=` | Coined words, spellings, uses, drift pairs, and `which` counts |
| `POST` | `/api/world/roll` | `{facet, entry, words}` | A prompt; any field given is kept, the rest rolled |
| `GET` | `/api/world/quotes` | `?by=…` | Attributed quotations |
| `GET` | `/api/world/story` | | Scenes in deterministic order, body appearances, separate metadata references and diagnostics |
| `GET` | `/api/world/export` | `?path=…` | One HTML page of a folder or of the story |

Fields that identify existing notes, including `from_targets`, `around`,
`biome` and quotation `by`, carry canonical vault paths rather than titles.

No `DELETE`. Responses keep the `{ok, message, data}` shape. Revision
conflicts use 409, but do not reuse the pool routes' unbound boolean `force`:
the response and retry carry the exact reviewed revision. `app.js` currently
keeps its request helpers and confirmation rows inside an eager IIFE, so they
cannot be reused as-is on another page. The small transport and confirmation
pieces can be extracted into a shared script, or `world.js` can implement the
same response contract without sharing DOM-bound code.

## Files

Following the repository's flat layout and its habit of one module per
concern, with a test beside each.

| File | Role |
|---|---|
| `vault.py` | `VaultManager`: the second root. `resolve`, `ls`, byte-revisioned `read`, per-path serialized and revision-checked `write`, exclusive `create`, recovery copies, and `stat_all`. Raises `InvalidPath` and `UnreadableSource`, the same two exceptions `web_routes.dispatch` already turns into 400s. |
| `entry.py` | `parse(text, path) -> Entry`; `render(entry, index) -> str`. Lossless parsed views, the supported frontmatter subset, source spans, safe links and Markdown fallback. |
| `vault_index.py` | `VaultIndex`: path identity, title/alias multimaps, graph, BM25 term statistics, lexicon, tags and geographical membership with provenance; `ensure_ready`, staleness by filesystem stamps, memory-only rebuild under the same lock discipline as `WordIndex`. |
| `nearby.py` | The scorer: takes a draft `Entry` and the index, returns the groups. Pure, so it is easy to test with a fake index. |
| `world_routes.py` | The route functions, in a second table that `web_routes.dispatch` consults by prefix. Nothing in `web_routes.py` changes except the lookup. |
| `serve.py` | `--vault PATH`. Builds the `VaultManager` and index and hangs them on the server beside `fm` and `index`. |
| `web_server.py` | `/world`, `/world.js`, `/world.css` in the static table; the per-route body cap. |
| `static/world.html`, `world.js`, `world.css` | The page. `world.css` holds only what `app.css` does not. |
| `fake_vault.py` | A temp-directory vault built from a dict of path → text, for tests. |
| `vault_test.py`, `entry_test.py`, `vault_index_test.py`, `nearby_test.py`, `world_routes_test.py` | One suite per module. Fixtures include one real note per convention, duplicate `Wickrill` titles, multi-`From:` notes, stale and twice-stale replacements, unsafe URLs, frontmatter scalar/list forms, and known related/unrelated Nearby pairs. |
| `path_safety_test.py` | Gains a table of vault spellings that must be refused: `../`, `/`, `.obsidian/app.json`, `.git/config`, a symlink out. |

## Phases

Each phase is usable when it lands and none needs the next.
Implementation status on this branch as of 2026-09-24: phases 1–3 are
implemented; phase 4 remains future work. The descriptions and acceptance
criteria below retain the original proposal.

1. **The writing loop.** Add `--vault`, path-safe and revision-safe vault
   access, lossless entry parsing, the tree and search, the bench strip,
   *Start an entry*, the textarea and safe preview, save, backlinks, reference
   cards, autocomplete, and basic Nearby: named-but-unlinked, shared biome and
   shared tags. This is the complete useful loop: draw words, create at an
   explicit path with selected geography and tags, write with references
   beside the draft, and save without quietly replacing another editor's
   work.

   **Acceptance:** a note with multiple `From:` targets survives open/edit/save;
   both `Wickrill` notes remain separately addressable and autocomplete
   qualifies the ambiguous target; create refuses only an occupied destination
   path; every successful save returns the revision of the saved bytes;
   stale and twice-stale writes return 409, a confirmed replacement is
   recoverable, and no dirty
   browser draft is discarded; delayed link suggestions cannot edit a newer
   draft; unsafe external URL schemes render inert while encoded internal
   links still open.

   **Status on this branch (2026-09-24): Implemented.**
2. **Richer connections and upkeep.** Add BM25 and two-hop Nearby groups, the
   coverage matrix, roller, backlog, health page, lexicon, spelling drift and
   `which`. Geography reports canonical biome membership separately from
   direct settlements and retains provenance.

   **Acceptance:** all eighteen current multi-`From:` notes can contribute to
   every actual biome without double-counting a biome-plus-settlement pair;
   `People/` and arbitrary folders do not become regions; related/unrelated
   retrieval fixtures pass with ordinary world words still indexed; every
   health result opens the canonical path it describes.

   **Status on this branch (2026-09-24): Implemented.**
3. **The map and richer Bases.** Add the local and whole-vault graph, ghost
   Nearby edges, the biome view, Obsidian graph colours, and evaluation of the
   explicitly supported Base-filter subset. Until this phase, Base blocks
   remain visible code.

   **Acceptance:** duplicate titles, unresolved links and ambiguous links are
   visibly different node states; a qualified link selects the intended node;
   supported real Base fixtures match their expected entries, and unsupported
   expressions still render as code with a diagnostic.

   **Status on this branch (2026-09-24): Implemented.** The supported Base
   filters are nested `and`/`or` expressions over
   `file.links.contains(this.file.name)` and `file.path.contains("…")`.
4. **Story.** Add configured scene folders, deterministic ordering, the body
   appearance report, metadata reference cards, voices and export. Explicit
   introduction or discovery metadata and advisory continuity checks are a
   later extension, only if the metadata is worth maintaining.

   **Acceptance:** missing, duplicate and invalid `when` values have stable
   documented outcomes; `where` and `who` references do not count as body
   appearances; duplicate note titles produce distinct anchors and glossary
   entries; story notes outside the supported frontmatter subset stay editable
   and receive a visible diagnostic.

   **Status on this branch (2026-09-24): Future work.**

The first phase is intentionally the feature that earns the rest. The force
layout, Base interpreter and inferred character knowledge are not prerequisites
for writing one useful entry safely.

## Open questions and risks

- **Two editors, one file.** Exact-byte revisions, per-path in-process locks
  and version-bound replacement close the races the app controls. They cannot
  interlock an external Obsidian or Sync process, and atomic replacement only
  prevents torn writes. The final recheck narrows that window; browser drafts
  and pre-replacement copies aid recovery but cannot guarantee preservation
  of an external update in that final window. Rule: never
  discard typed text without a question. The recovery directory and retention
  policy should be visible in the UI rather than becoming a hidden archive.
- **The markdown subset.** Anything the vault starts using that the renderer
  does not know will show as its raw text, which is safe but ugly. The
  renderer should say what it skipped, in the muted colour, so the gap is
  visible and gets closed. Raw HTML stays escaped, and adding a new link form
  includes an explicit URL-policy test.
- **Filenames.** `???.md` is a legal name and a real note. Vault paths go in
  query strings, so the client encodes and the server already `unquote`s.
  Worth one test with `?`, `&`, a comma and a diacritic in the same name.
- **The People bios live in a Google Doc.** The story pieces want them in
  `People/`. That is a copy-paste, and it can wait until story mode is real,
  but voices and cards are only as good as the notes they read.
- **Frontmatter or header lines?** The vault uses `From:` lines, and Bases
  would rather have properties. The parser reads both from the first day, so
  this never has to be decided globally; if a note gains `from:` in the
  supported frontmatter subset, the app prefers it and writes it back where
  it found it. Unsupported YAML is preserved and diagnosed, not normalised by
  a partial parser.
- **Where the biome view gets its sectors.** It starts from the documented
  kinds in the folder tree. Reading sectors from the Biome Template's Base
  blocks can follow once the Base subset is implemented in phase 3.
- **Scope.** Nothing here needs a dependency, a build step, or a change to
  the terminal tool. If any piece starts to need one, that is the signal to
  stop and ask whether it belongs here at all.
