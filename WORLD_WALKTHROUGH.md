# Worldbuilding walkthrough

The Worldbuilding desk puts an Obsidian vault beside the RandomWords word bench. It reads and writes the Markdown files in place, so the vault remains the source of truth.

## Open your vault

From the repository directory, start the browser server with the path to your vault:

```bash
python3 serve.py --vault ~/Documents/Worldbuilding
```

Open the address printed by the server, then choose **Worldbuilding desk** on the main page. Without `--vault`, the World page is unavailable. To enable Story, pass each existing scene folder with `--story-folder`:

```bash
python3 serve.py --vault ~/Documents/Worldbuilding \
  --story-folder Story --story-folder Drafts
```

Folder arguments are relative to the vault. Story scans Markdown notes directly in those folders and their subfolders.

## Find or create an entry

Use the folder tree to browse, or search by title, alias, or text. Each search result shows its kind, word count, a stub marker where it applies, whether it matched through an alias, and a snippet of the matching text; the arrow keys move between results and Enter opens one. The tree follows the open entry, expanding to it and scrolling it into view. Open an entry to edit it in the center pane. **Preview** shows the rendered note. You can edit the Markdown directly; the desk does not require a special editor format.

The desk trims its own furniture to the task. Only the **Desk** view shows Nearby; the other views give that space to the report. **Map** and **Coverage** also fold the folder tree into a narrow rail, and **Show files** brings it back. The word bench along the bottom collapses to a single line, and the desk remembers whether you left it open.

The desk's front page helps you pick up where you left off. It shows when no entry is open, and **World** at the top of the sidebar brings it back at any time; **Back to …** then returns to the entry or draft you were on, untouched. It lists your last eight **Recent entries**, any **Unsaved drafts** (new entries and unsaved changes to existing ones), and three things **Worth a look** from Upkeep, which load a moment after the rest. Drafts live in this browser only; **Clear drafts on this device** removes them (and any recovery copies) after one confirmation, and the confirmation says if the draft open in the editor is among them. Under the title of an opened entry, a **To do** strip shows only what applies: `#rework`, how many `${…}` notes to self (click to jump to the next one in the text), a stub marker, and unresolved or ambiguous links. It describes the saved note and updates after you save.

Switching views never loses your place: each view comes back at the scroll position you left it, and the editor keeps its caret and scroll. If a button in a view sends you to the desk (a Coverage ＋, an entry in Upkeep or the Atlas), **← Back to Coverage** (or whichever view it was) sits above the entry and returns you to that view exactly where you were. A small dot on the **Desk** tab means the draft there has unsaved changes.

**Open word generator**, on the bench, slides the full RandomWords generator in over the desk (full screen on a phone). Your draft stays exactly as it was behind it. Words you keep there appear on the bench straight away. Choose **Close** or press Esc to return; the generator keeps its own draw history while the page is open.

Choose **Start an entry** and the editor opens on a new draft. Write first and decide where it lives later. The title is the large field at the top and can stay empty until you save. If you have kept words on the bench, they are already on an `Origin:` line; delete any you do not want. Everything the entry will say, including its `From:` and `Origin:` lines, `#tags` and template headings, is ordinary text in the draft. Nearby, `[[` and `#` suggestions, spelling marks and the preview all work from the first keystroke. The draft is kept in this browser only, so a reload or a closed tab does not lose it; **Discard draft** throws it away after one confirmation.

The bar under the title reads like `Lives in: Flora and Fauna/Marsh/Loaming Country · From Loaming Country · Creature Template`. **Change** opens the placement panel. Pick a kind and a place, and the panel adds the place to the `From:` line and proposes a folder and a template together; the folder and template stay visible and editable, and **Choose another folder** opens the folder browser (open child folders, jump to a recent folder, search by name). A template's headings go in under the header lines only while you have written nothing below them; once you have, **Insert template headings at the end** adds them after your text instead. Choosing a template a second time before writing anything swaps the headings. On a phone the bar shrinks to one line, such as `Loaming Country · Change`, and the panel fills the screen.

**Save** (or ⌘S) needs a title and a folder. If one is missing, the page says which and takes you to it; if the title is already used in that folder, it says so and suggests another. The saved draft becomes the entry where it stands, with your text and caret untouched. Tick **Create another like this** in the panel to start a fresh draft with the same place, folder and template after saving. If you open another entry in the middle of a draft, the draft stays on this device and the notice offers **Back to the draft**. Tag autocomplete offers the tags already in use in the vault and those listed in `Tags.md`, and nothing else. The same editor opens prefilled from several other places, described below: a Coverage cell, an unresolved link, a name with no entry, a backlog roll, a territory on the Atlas, and Nearby's **Use as From** (on a draft that button adds the place to that draft instead).

The vault includes starter templates for biomes, cosmology, cultures, creatures, geonomy, places, settlements, people, phenomena, paranatural arts and art instances, othernatural occurrences, and othernatural structures. Templates are read from the vault's `Templates/` folder, so new Markdown templates appear in the chooser automatically.

The note path determines its kind and folder: for example, `Flora and Fauna/Marsh/Glowfin.md` has kind `Flora and Fauna`. Useful conventions recognized by the desk are:

```markdown
From: [[Loaming Country]]
Origin: kallitype ambergris
#loaming #animal

The glowfin gathers near the old ferry beside [[Aurochult]].
#rework
${Check whether it migrates in winter.}
```

`From:` links describe a note's source or location and contribute to biome coverage. `Origin:` and `Source:` identify seed words. These headers can also live in supported YAML frontmatter; a `Themes:` header is supported there too. Body links use Obsidian `[[wikilinks]]`; `[[Target|shown text]]` displays alternate text. YAML `aliases` let a note resolve under another name. Inline `#tags` power tag suggestions, and `${…}` marks a note to yourself for Upkeep.

Here is the full loop for that example. Start an entry from your kept words, write the body, pick `Loaming Country` as its place and `Flora and Fauna` as its kind in the placement panel, give it the title `Glowfin`, and save, which creates `Flora and Fauna/Marsh/Glowfin.md`. While drafting, type `Aurochult` without brackets; Nearby can list it as a named entry, and **Link** wraps that mention in a wikilink. After saving, open **Coverage**: Glowfin contributes once to Loaming Country under the `Flora and Fauna` kind, through its `From` link. In **Upkeep**, its `#rework` tag and migration aside appear as reminders; decide whether to revise the note and remove those markers. In **Lexicon**, `glowfin` appears if it is absent from the 450k dictionary, with this note listed as a use. Open the result to review the word in context. Refresh a report if it still shows the snapshot from before the save.

For the backlog side of the loop, put an idea such as `A reed bird that predicts the fog` in a bullet in a direct child note of `Ideas/`. In **Backlog**, choose **Start an entry** on that idea. Its first four words prefill the new entry title. Pick its folder when you save; after creation, the source bullet is crossed out only if its revision still matches. If the idea changed meanwhile, the entry can exist while the bullet remains open; review the source and retry marking it complete if appropriate. If creation fails, the idea stays open so you can correct the details and try again.

The parser supports a small YAML subset. Keep existing frontmatter intact; when a header is unsupported, the desk shows a diagnostic rather than interpreting it as valid metadata. Story has its own supported YAML fields described below.

## Write, preview, and save

As you type, **Nearby** updates with one card per entry. Each card combines every reason that entry was suggested, so a note that is named in the draft, shares its biome, and shares a tag appears once, not three times. The reasons are: named but not linked; the same biome or place; shared tags; shared terms, ranked by how much each term contributes to the BM25 score; and linked from something your draft links to (two hops). Select a card to inspect it. For a named, not linked reason, choose **Link** to replace the matched name with a wikilink; suggestions refresh as the draft changes, so review the resulting link in the editor.

Two smaller rules keep the cards honest. **Use as From** appears only on places, which are entries under `Locations/`, since only a place makes a sensible `From:` target. A card whose title matches the draft's title but is a different note carries a **Same name, different entry** badge. A name match written in lower case counts for less than an exact-case one, and the card labels it "(lowercase)", as in *Named as time (lowercase)*, because a common word that happens to be a title is a weak signal.

The editor marks problems as you type. A rarer spelling in a known drift pair is underlined, and so is any wikilink that is unresolved or ambiguous. With the caret inside a drift spelling, a small hint reads like `Foxfyre → Foxfire? Replace`; click it or press Alt+Enter to stage the replacement, then review and save as usual. The **Links** panel lists the open entry's unresolved links, each with **Create entry**, and its ambiguous links, each with the candidate notes to choose from. Typing `[[` on its own opens suggestions for the link target; `#` does the same for tags.

Where the window is wide, **Split** shows the editor and the preview side by side, and the preview scrolls in proportion to the editor. The preview renders links, inline code, numbered lists, horizontal rules and the rest of the supported Markdown; `${…}` asides appear as private note blocks. Constructs the renderer does not draw, namely tables, images, embeds and task-list boxes, appear in place as marked "not rendered" rather than vanishing or showing as raw text. Raw HTML stays escaped. The Map can show Nearby suggestions as ghost nodes while the current draft is open.

Choose **Save** to write the note. Unsaved drafts are kept in browser storage. If the file changed on disk while you were editing, the desk shows the disk and draft versions for review before allowing a replacement. That includes a recovered draft that was written before the note last changed on disk: saving it goes through the same review instead of overwriting the newer file. Replaced bytes are copied to `~/.randomwords/recovery`.

## Use the reports to guide the next edit

The World page rebuilds its in-memory view when vault files change, and the reports follow it. Each report remembers the index generation it loaded with; when a save here, another tab, or Obsidian moves the generation on, the visible report reloads in place and hidden ones reload when you next open them. The report views turn links, locations, tags, and body text into places to explore:

- **Coverage** counts entries by canonical biome and kind, shaded as a heatmap so thin cells stand out; the headers stay in view as you scroll. Select a count to list its entries and inspect how each note reaches that biome. Coverage uses explicit `From:` links and their `From:` ancestry, with a folder mapping fallback where one resolves uniquely. The **＋** in every cell, empty or not, opens a new draft already set to that cell's folder, with the biome on its `From:` line and the kind's template headings in. Add or correct a location link and the cell updates on its own.
- **Upkeep** gathers unresolved links, ambiguous links, duplicate names, notes with no incoming links, isolated notes, short stubs (under 20 body words), `#rework` notes, `${…}` asides, likely names without entries, and possible spelling drift. Drift rows show each occurrence with its note, line, and context. **Open** takes you to the note; **Stage …** stages that one replacement, highlights it, and leaves it for you to review and save. If the occurrence has changed since the report loaded, refresh the report and review the current text. The sections below are new or changed.
  - **Named but not linked** searches the whole vault for notes that mention another entry by name without linking it, with one row per note. **Stage link** puts the wikilink in that note for you to review; nothing is saved until you save. **Open** takes you to the note. **Not in this note** dismisses that one pairing, and **Never suggest** stops the target being offered anywhere, including in Nearby. By default only exact-case mentions that are not already linked are listed; **Show all** also reveals lower-case matches and mentions that are already linked.
  - **Review queue** sits at the top of Upkeep: "N suggestions, about M minutes" and **Start reviewing**. It walks the most useful fixes one at a time without leaving Upkeep: exact-case mentions grouped by the entry they name, then unresolved links, spelling drift, the stubs named most often, and notes to self. Each card shows the note and the sentence with the proposed change marked. **Link and save** (or **Fix and save** for drift) edits that note and saves it straight away, with no editor involved; **Skip** moves on; **Not in this note**, **Never suggest** and **Not drift** dismiss with an **Undo**; **Open in editor** is there when you want to look first. For an entry named in several notes the card says where you are, such as "Hozon · note 2 of 6". If the note changed on disk since Upkeep loaded, or was saved elsewhere meanwhile, nothing is written and the card offers **Open in editor**. If that note has unsaved changes in the editor, the queue stages the change there instead of saving behind it. Enter does the main action, **S** skips and Esc leaves; a running tally ("8 linked · 3 skipped · 2 dismissed") shows what this visit did.
  - **Names without entry** hides ordinary dictionary words (Despite, Water) behind **Show N common words**.
  - **Ambiguous links** lists links whose text matches several notes, with the candidates to pick from, and **Duplicate names** lists titles or aliases that more than one entry claims.
  - **Create entry** appears on each unresolved link and on each name with no entry. From an unresolved link it opens a new draft with the source note's `From` targets already on its `From:` line, on the reasonable guess that the missing note belongs to the same place.
- **Lexicon** lists body words absent from `dicts/450k_words.txt`, with spellings, occurrence counts, and the notes where they appear. Search or filter by biome; **Used once** narrows to words appearing in one note. Possible spelling pairs include each occurrence's note, line, and context. **Open** navigates to the note, and **Stage …** stages one highlighted replacement for you to review and save. Where available, the panel also shows matches in the source book index.
- **Backlog** reads bullet items from `Ideas/*.md`. Choose **Start an entry** to seed a new note from an idea. The idea is marked complete only after the new entry is created; if the idea changed meanwhile, review it before retrying.
- **Roll a prompt** combines a facet from `How-To.md`, existing entries, and two words from the active word pool. Open the suggested entries and follow a connection that interests you, or choose **Start entry from this roll** to open a new draft with the rolled words on its `Origin:` line, the first rolled entry's places on its `From:` line, and a first line that links what was rolled under a heading for the facet. The roller draws only world entries, never templates, ideas, or story scenes, and it favours biomes with fewer entries slightly, so thin corners come up a little more often.

### Dismissing false alarms

Upkeep and Lexicon will flag things that are not problems: a phrase that is not a name, a spelling pair that is deliberate, a coined word that is really a word. Each row offers the matching dismissal: **Not a name**, **Not drift**, **Real word**, **Not in this note**, or **Never suggest**. The row disappears and an **Undo** appears at once. A section with dismissals shows **N dismissed · Review**, which lists them with a **Restore** for each.

Dismissals are yours, not the vault's. They are saved in `~/.randomwords/worlds/<hash of the vault path>/triage.json`, one file per vault, so they are not synced by Obsidian and will not follow the vault to another machine. Deleting that file restores everything.

After a save or new entry the open reports catch up by themselves, and each view still has a Refresh button if you want to force it. From any result, open the linked entry to continue the writing loop.

## Map and Story

**Map** has two modes. **Around this entry** shows one or two links from the open note; drag nodes to arrange them, click a node to open it, or modifier-click to preview it. **Atlas** draws the whole world as a map: entries live in the territory of their biome, or of their folder when they have none, and biome types and top-level folders are separate continents. Templates, ideas, and loose root notes are left out. Hover a dot to trace its links, click it to see them in a side panel, and double-click it or press Enter to open it. The entry you have open is ringed; **Find open entry** pans to it. **Colour by** switches the dots between **Kind**, **Orphans** (entries nothing links to), **Stubs**, and **Rework**, with a legend and count beside the map. Click land, or pick from **Territory**, to open a territory: the panel lists its entries by kind, the kinds it has no entries for yet, and the territories it links to. **Roll here** in that panel rolls a prompt around a random entry from the territory, and **Start entry here** opens a new draft set to the territory's biome or folder. Names appear as you zoom in. In both modes, scroll to zoom at the pointer, drag the canvas to pan, or use **+**, **−**, and **Fit map**. Nodes distinguish resolved, unresolved, and ambiguous links, plus stubs and `#rework` notes. In **Around this entry**, Nearby suggestions appear as dashed ghost links, at most eight at a time; hover a ghost to see why it was suggested.

**Story** scans the configured scene folders. Until one is configured, the view says so and shows the `--story-folder` option to start the server with. Notes in those folders are scenes, not world entries: they do not count towards any kind in Coverage or the Atlas, and the roller never picks them. Give a scene integer `when` metadata to order it; ties use the canonical note path. `where` and `who` are lists of wikilinks shown as separate reference cards. Body mentions and links to existing entries appear under **Entries mentioned**, with a vault-wide first and later appearance report. Missing, invalid, or unsupported story metadata gets a diagnostic, and scenes without a valid `when` sort last. Open a scene to edit it, or use **Export story** for a compiled reading copy. **Voice** on a People entry opens attributed quotations.

For a scene with YAML frontmatter, the Story view recognizes `when`, `where`, and `who`. For example:

```yaml
---
when: 2
where:
  - "[[Loaming Country]]"
who:
  - "[[Dr. Otto Battar, Zoologist]]"
---
```

The body follows the closing `---`. `when` must be an integer; `where` and `who` values must be wikilinks. Story metadata is separate from prose appearances, so add a body link or mention when you want an entry to count as appearing in the scene.
