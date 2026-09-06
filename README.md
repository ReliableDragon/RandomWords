# RandomWords

An interactive command-line tool for pulling random words out of books.

Point it at a folder of plain-text books (Project Gutenberg texts work out of
the box), and it will hand you random words from whichever text or set of
texts you have loaded. Word pools can be named, combined, intersected, and
subtracted from one another, so you can do things like "give me a random word
from *Moby Dick* that is **not** one of the 10,000 most common English words".

It is a personal tool for name-generation, prompts, and general wordplay.

---

## Contents

- [Requirements](#requirements)
- [Running](#running)
- [Concepts](#concepts)
- [Command reference](#command-reference)
- [Path rules](#path-rules)
- [How words are extracted](#how-words-are-extracted)
- [The `sources/` directory](#the-sources-directory)
- [Architecture](#architecture)
- [Running the tests](#running-the-tests)
- [Known limitations](#known-limitations)

---

## Requirements

- Python 3.9 or newer to run the tool. The test suite uses parenthesised
  multi-line `with` statements, so running the tests needs 3.10 or newer.
- Standard library only. There are no third-party dependencies.
- Arrow-key editing at the prompt comes from the `readline` module. It is
  optional: where it is missing (notably Windows) the tool still runs, just
  without line editing.

## Running

```bash
python3 book_word.py
```

It can be started from any directory; `sources/` is located relative to the
program file, not to the working directory.

On startup it loads `sources/dicts/70k_words.txt` as the active word pool and
drops you at a `> ` prompt. Type `help` to list commands, `quit` to leave.
Pass a different startup file as an argument:

```bash
python3 book_word.py sources/dicts/10k_words.txt
```

A typical session:

```
> cd classics
> ls
20k_leagues.txt
HoD.txt
analects.txt
...
> load moby_dick.txt
> word
harpooneer
> 3
leviathan gale mizzen
> al moby                                    # save the pool as "moby"
> d moby sources/dicts/10k_words.txt rare    # drop the 10k commonest words
> gaw rare
ambergris
> quit
```

`quit`, `exit`, `q`, Ctrl-D, and Ctrl-C all leave cleanly.

## Concepts

### The context and the active pool

All state lives in a single dictionary called the **context**. Each entry maps
a name to a list of words.

- The entry named **`words`** is the *active pool*. It is what `word`, `next`,
  a bare number, or an empty line draw from. `load`, `r`, `dr`, and `rd`
  replace it.
- Every other entry is an **alias**: a named, saved word pool. You create
  aliases with `alias_load` (or as the output of a set operation), read from
  them with `gaw` and `mul`, and feed them into `combine` / `diff` /
  `intersection`.

`dump` shows what is currently in the context and how big each pool is.

A command that fails leaves the context untouched, so a typo never destroys
the pool you are working with.

### How commands work

Each command is a class with a `matches(line)` method that decides whether a
typed line is that command, and an `execute(args, context)` method that does
the work and returns a dictionary of context entries to add or replace. The
parser tries every registered command in order and uses the first one that
matches, so most commands have short aliases and a few have special
"bare" forms (`foo.txt` loads a file; `5` prints five words).

Command words are case-insensitive; arguments keep the case you typed, which
matters for filenames like `HoD.txt`.

## Command reference

Arguments in `<angle brackets>` are required, `[square brackets]` optional.
"Alias" means a name in the context; "file" means a `.txt` path (see
[Path rules](#path-rules)).

### Navigation

| Command | Description |
|---|---|
| `help` | List every command with a one-line summary. |
| `quit`, `exit`, `q` | Leave the program. |
| `pwd` | Print the current directory (an absolute path under `sources/`). |
| `ls [folder]` | List sub-folders and `.txt` files in the current directory, or in `folder`. Folders are shown with a trailing `/`. Hidden folders are skipped. The argument must be a single folder name, taken relative to the current directory. |
| `cd <folder>` | Change directory. `..` moves up one level, `/` jumps back to `sources/`, and an absolute path is used as-is. Relative paths are normalised and cannot climb above `sources/`. A folder that does not exist is reported and the current directory is left alone. |

### Loading a pool

| Command | Description |
|---|---|
| `load <file>` | Read `file` and make its words the active pool. |
| `load <alias>` | Copy an alias into the active pool. |
| `<file>.txt` | Shorthand for `load <file>.txt`: typing a path that ends in `.txt` loads it. |
| `r [folder]`, `rand`, `random` | Load a random `.txt` from anywhere under the current directory (or under `folder`). Every file is equally likely, regardless of how deep it is or how many siblings it has. Prints which file was chosen. |
| `dr`, `drand`, `dir_random` | Load a random `.txt` by walking down from the current directory, choosing uniformly among the entries at each level. A folder with two files is as likely to be chosen as a folder with twenty, which is useful when the collections are very uneven in size. Folders that contain no texts are skipped. |

### Getting words

| Command | Description |
|---|---|
| `word`, `next`, *(empty line)* | Print one random word from the active pool. |
| `<N>` (a number) | Print `N` random words from the active pool on one line. |
| `gaw <alias\|r>...`, `get_alias_words` | Print one random word from each named alias, space-separated. Any argument that is `r`, `rand`, or `random` is replaced with a randomly chosen alias (never `words`), and when that happens the chosen alias names are appended in `[brackets]`. Arguments cannot contain `/` or `.`, so files cannot be used here; use `mul` for that. |
| `mul <folder\|file\|alias>...`, `mfgw`, `multi_folder_get_words` | Print one random word per argument. A **folder** picks a random `.txt` under it and then a random word from that; a **file** (ending in `.txt`) picks a random word from that file; an **alias** picks a random word from the alias. Handy for "one word from myth, one from geology". |

### Saving and combining pools

| Command | Description |
|---|---|
| `al <name> [file]`, `alias`, `alias_load` | Save a pool under `name`. With a file argument, the file's words are saved; without one, the current active pool is saved. If `name` already exists you are asked `Alias exists. Overwrite? y/N`. |
| `c <A> [B] [C]`, `combine` | Set **union**. See below for how one, two, and three arguments are interpreted. |
| `d <A> [B] [C]`, `diff` | Set **difference** (words in the first pool that are not in the second). |
| `i <A> [B] [C]`, `intersection` | Set **intersection**. |
| `rd [10\|70\|450]`, `rand_diff` | Load a random file and subtract the 10k, 70k (default), or 450k most-common-words dictionary, leaving only that book's unusual words as the active pool. |
| `dump [all]` | Print each pool in the context with its size. `dump all` prints the full contents of every pool, which is enormous for real books. |

#### Set-operation argument forms

`combine`, `diff`, and `intersection` all take one to three arguments, each
of which may be an alias or a file. Where the result goes depends on how many
you give:

| Form | Meaning | Result stored in |
|---|---|---|
| `d X` | `words ∘ X` | `words` (the active pool) |
| `d A B` | `A ∘ B`; `A` **must** be an alias | `A` (overwritten) |
| `d A B C` | `A ∘ B` | `C` (new or overwritten alias) |

For `diff` the order matters: `d A B` keeps the words of `A` that are not in
`B`. So `d moby sources/dicts/10k_words.txt rare` gives you the words of
*Moby Dick* minus the 10,000 most common English words, saved as `rare`.

## Path rules

Every file and folder argument goes through the same resolution
(`FileManager.get_rooted`):

| You type | Resolves to |
|---|---|
| `/` | The `sources/` root. |
| `/abs/path/...` | Used unchanged as an absolute filesystem path. Note that `/dicts/x.txt` is **not** "dicts under sources"; it is a path at the filesystem root. |
| `sources/dicts/x.txt` | The `sources/` prefix is recognised and the rest is taken relative to the sources root, wherever you currently are. This is the way to reach a file in another folder without `cd`. |
| `dicts/x.txt` (anything else) | Relative to the current directory. |

Filenames must match `[A-Za-z0-9_/]` plus the `.txt` extension: no spaces, no
hyphens, no other dots. All files in `sources/` follow this rule.

## How words are extracted

`FileManager.get_words` turns a text file into a word list:

1. If the file contains a Project Gutenberg marker line
   (`*** START OF THE PROJECT GUTENBERG EBOOK ...`), everything outside the
   `START`/`END` marker pair is discarded, so licence boilerplate never shows
   up as words. Files with several such sections (anthologies) are handled,
   and a file whose footer is missing keeps everything after the header.
2. Words are matched as runs of letters and digits, optionally joined by
   internal apostrophes or hyphens. So `well-known` and `ain't` stay whole,
   while em dashes, en dashes, and every other punctuation mark separate
   words. Accented letters are matched as letters.
3. Tokens with no letter at all (bare numbers, stray punctuation) are dropped.
4. Everything is lower-cased, then de-duplicated and sorted.

The result is an unordered pool as far as sampling goes: every distinct
spelling is equally likely to be picked, regardless of how often it appears
in the book. Because lower-casing happens before de-duplication, a word that
appears both capitalised and not is counted once.

## The `sources/` directory

`sources/` holds the texts, one folder per theme. Any folder layout works;
the tool discovers `.txt` files recursively.

| Folder | Contents |
|---|---|
| `botany/`, `classics/`, `craft/`, `geology/`, `law_econ/`, `myth/`, `natural_history/`, `religion/`, `science/`, `war/`, `zoology/` | Project Gutenberg texts, grouped by theme (roughly 130 books). |
| `dicts/` | Frequency word lists: `10k_words.txt`, `70k_words.txt` (the startup pool), `450k_words.txt`, one word per line, plus a three-word `test.txt`. |
| `custom/` | Hand-written word lists, one word per line. |

To add a book, drop a `.txt` file into any folder. Gutenberg headers and
footers are stripped automatically. Use only letters, digits, and underscores
in the filename.

## Architecture

Everything is in the repository root; there is no package structure.

| File | Role |
|---|---|
| `book_word.py` | Entry point. Builds the objects below, loads the startup dictionary, and runs the read-eval-print loop in `RandomWords.run`. The loop catches errors so a bad command cannot end the session. |
| `file_manager.py` | `FileManager`: all filesystem access. Tracks the current directory, resolves paths (`get_rooted`), lists and walks folders (`ls`, `get_txts`, `rand_file`, `rand_dir`), and extracts words (`get_words`, `remove_gutenberg`). `ROOT_DIR` is the absolute `sources/` path, derived from this file's own location. |
| `command.py` | `Command` base class: `cmd_name()`, `cmd_args()`, `matches(line)`, `parse_args(line)`, `execute(args, context)`, `overview()`. The default `matches` builds a regex from the name and argument list; most commands override it to add short aliases. |
| `file_command.py` | `FileCommand`: a `Command` that holds a `FileManager`. |
| `set_op_cmd.py` | `SetOpCommand`: shared argument handling for `combine`, `diff`, and `intersection`; subclasses supply `aliases()` and `set_operation(s1, s2)`. |
| `arg.py` | `Arg`: a typed, optionally optional/repeated argument description used for validation and help text. |
| `*_cmd.py` | One file per command (see the table below). |
| `command_list.py` | `CommandList`: constructs every command instance (`cmd_list`) and holds the name → command registry. Registration order is the order the parser tries matches in. |
| `command_manager.py` | `CommandManager`: owns the context. `execute` runs a command, pops a `result` key from what it returns, and merges the rest into the context. |
| `parser.py` | `Parser`: reads a line from the user and finds the first command whose `matches` accepts it. Importing it enables `readline` line editing where available. |

Command classes:

| File | Class | Command |
|---|---|---|
| `ls_cmd.py` | `LS` | `ls` |
| `cd_cmd.py` | `CD` | `cd` |
| `pwd_cmd.py` | `PWD` | `pwd` |
| `load_cmd.py` | `Load` | `load`, bare `*.txt` |
| `get_word_cmd.py` | `GetWord` | `word`, `next`, empty line, number |
| `load_rand_file_cmd.py` | `LoadRandFile` | `r` |
| `load_rand_dir_file_cmd.py` | `LoadRandDirFile` | `dr` |
| `alias_load_cmd.py` | `AliasLoad` | `al` |
| `get_alias_words_cmd.py` | `GetAliasWords` | `gaw` |
| `multi_folder_get_words_cmd.py` | `MultiFolderGetWords` | `mul` |
| `combine_cmd.py` / `diff_cmd.py` / `intersection_cmd.py` | `Combine` / `Diff` / `Intersection` | `c` / `d` / `i` |
| `rand_diff_cmd.py` | `RandDiff` | `rd` |
| `dump_cmd.py` | `Dump` | `dump` |
| `help_cmd.py` | `Help` | `help` |
| `quit_cmd.py` | `Quit` | `quit` |

### Control flow of one command

1. `Parser.get_command` reads a line, strips it, and calls `matches` on each
   registered command in registration order; the first match wins and its
   `parse_args` splits the line into arguments.
2. `CommandManager.execute` calls `command.execute(args, context)`.
3. The command reads whatever it needs from the context and the
   `FileManager`, prints its output, and returns either `None` (nothing to
   store, which is also how a command reports a user error) or a dict of
   `{name: word_list}`.
4. The manager merges that dict into the context. If it contains a `result`
   key, that value is returned to the main loop instead of being stored; the
   loop exits when the result is the string `'quit'`.

### Adding a command

1. Create `my_cmd.py` with a class extending `Command` (or `FileCommand` if
   it needs the filesystem). Implement `cmd_name`, `cmd_args`, and `execute`;
   override `matches` and `parse_args` if you want aliases or a non-standard
   syntax, and `overview` for a friendlier `help` line.
2. Add an instance to the list in `CommandList.cmd_list`. Put it **before**
   any command whose pattern could also match your syntax.
3. Add `my_cmd_test.py` next to it, and add the new syntax to the
   precedence table in `parser_test.test_parse_every_documented_syntax`.

## Running the tests

```bash
./run_tests.sh
```

That is a one-line wrapper for:

```bash
python3 -m unittest discover -p '*_test.py'
```

The pattern is required because the tests are named `*_test.py`, which the
default discovery pattern (`test*.py`) does not match.

There are 142 tests and they all pass. Files named `fake_*.py`
(`fake_command.py`, `fake_directories.py`, `fake_file_manager.py`) are test
doubles, not test cases. Tests that touch the filesystem build a temporary
directory tree through `FakeDirectories` / `FakeFileManager` rather than
mocking, so they need a writable temp dir. Tests that involve randomness
patch `random.choice` with a deterministic function.

## Known limitations

- Filenames are restricted to letters, digits, underscores, and `/`. A file
  with a space or a hyphen in its name cannot be typed as an argument.
- `ls` takes a single folder name, not a path.
- An absolute path escapes the `sources/` root by design, so `cd /tmp` works
  and `pwd` will report it.
- Words are re-extracted from disk on every command that reads a file; the
  450k dictionary takes about a third of a second each time. There is no
  cache.
- `Command.validate_args` can only ever check `str` arguments, because
  `parse_args` yields strings for every command except `get_word`.
- Sampling is uniform over distinct spellings, not over occurrences, so rare
  words are as likely as common ones. That is usually the point, but it is
  worth knowing.
