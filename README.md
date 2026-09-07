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
> ls classics
20k_leagues.txt
HoD.txt
analects.txt
...
> load classics/moby_dick.txt
> word
harpooneer
> 3
leviathan gale mizzen
> al moby                            # save the pool as "moby"
> d moby dicts/10k_words.txt rare    # drop the 10k commonest words
> gaw rare
ambergris
> quit
```

`quit`, `exit`, `q`, Ctrl-D, and Ctrl-C all leave cleanly.

## The browser interface

The same commands are also reachable in a browser. Start the server:

```bash
python3 serve.py
```

It binds to `127.0.0.1:8100` and prints its address. `--port` moves it,
`--words` picks the startup pool, and `--no-warm` skips the startup read of
the dictionaries.

On startup it reads the four dictionaries, which takes about a third of a
second, then reads the 132 books on a background thread over the next six.
After that a draw from any text is instant: a warm read of the 450k
dictionary takes 49 microseconds rather than 256 milliseconds. The whole
parsed corpus is 1.8 million words, comfortably inside the cache's two
million word budget, so nothing is evicted in practice.

The page has a library on the left and a bench on the right. Click a text to
load it, then draw. The last twenty draws stay on screen, and clicking any
word keeps it; kept words survive a restart in browser storage and can be
copied or exported as a one-word-per-line file.

### What the server exposes

| Method | Path | Body or query | Does |
|---|---|---|---|
| `GET` | `/api/library` | `?path=myth` | Folders and texts, with a word count for texts already read |
| `GET` | `/api/pools` | | Every pool with its size |
| `GET` | `/api/status` | | Cache statistics and pools |
| `POST` | `/api/pools/load` | `{source}` | Loads a text or a saved pool |
| `POST` | `/api/pools/random` | `{under, mode}` | Loads a random text; `mode` is `flat` or `walk` |
| `POST` | `/api/pools/save` | `{name, from, force}` | Names the active pool, or a text |
| `POST` | `/api/pools/op` | `{op, a, b, out}` | Union, difference or intersection |
| `DELETE` | `/api/pools/{name}` | | Forgets a pool |
| `POST` | `/api/draw` | `{count}` | Draws from the active pool, capped at 1000 |
| `POST` | `/api/command` | `{line}` | Runs a line of the command language |

Pool contents never cross this boundary, only sizes and the words actually
drawn. The largest pool is six megabytes of JSON, to support a draw that
takes under a microsecond on the server.

Responses carry `{ok, message}` and sometimes `data`. The status is a
function of `ok` and `confirm`: 400 for anything the user got wrong, 409
when a command needs a yes before it acts, 500 for anything unhandled.

A 409 is how the overwrite question crosses the wire. Saving over an existing
name comes back unapplied, carrying the question the terminal would have
asked; the client repeats the request with `"force": true` to answer yes.
The command computes its answer either way and never learns which front end
asked.

### Why it is only for you

Binding to loopback keeps the network out. It does not keep out a web page:
any tab in the same browser can post to a loopback server, and DNS rebinding
lets a page the attacker controls read the replies too. Three checks close
that, and `web_server_test.py` drives each one:

1. The `Host` header must name localhost with the served port.
2. Every POST must be `application/json`, a type a cross-origin form cannot
   send without a preflight this server never answers.
3. An `Origin` header, when present, must match the served origin.

There is no authentication, which is only defensible while the bind address
is loopback. Those two decisions have to move together.

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

### Paths, and the absence of a current directory

There is no `cd`. Every path you type is relative to the `sources/` root and
means the same thing wherever you are in a session, so `classics/moby_dick.txt`
is that book from anywhere. A path that tries to leave the library, whether by
starting with `/` or by climbing with `..`, is refused rather than resolved.
`ls` is how you look around.

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
| `ls [folder]` | List sub-folders and `.txt` files in `folder`, or in the library root. Folders are shown with a trailing `/`, and hidden folders are skipped. The argument is a library path, so `ls myth` and `ls classics` both work. |

### Loading a pool

| Command | Description |
|---|---|
| `load <file>` | Read `file` and make its words the active pool. |
| `load <alias>` | Copy an alias into the active pool. |
| `<file>.txt` | Shorthand for `load <file>.txt`: typing a path that ends in `.txt` loads it. |
| `r [folder]`, `rand`, `random` | Load a random `.txt` from anywhere under `folder`, or under the whole library. Every file is equally likely, regardless of how deep it is or how many siblings it has. Prints which file was chosen. |
| `dr`, `drand`, `dir_random` | Load a random `.txt` by walking down from the library root, choosing uniformly among the entries at each level. A folder with two files is as likely to be chosen as a folder with twenty, which is useful when the collections are very uneven in size. Folders that contain no texts are skipped. |

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
| `forget <name>`, `rm` | Forget a saved pool. The active pool cannot be forgotten. |
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
`B`. So `d moby dicts/10k_words.txt rare` gives you the words of
*Moby Dick* minus the 10,000 most common English words, saved as `rare`.

## Path rules

Every file and folder argument is a **library path**: relative to `sources/`,
with `/` between segments. `dicts/10k_words.txt` is that dictionary,
`classics` is that folder, and an empty argument means the library root.

There is deliberately no way to name anything outside the library. Each of
these is refused with `Not a path in the library`:

| You type | Why it is refused |
|---|---|
| `/etc/passwd` | Absolute paths are not library paths. |
| `../../etc/passwd` | A `..` segment cannot appear in a library path. |
| `myth/../../etc` | Rejected before the path is normalised, not after. |
| a symlink pointing out of `sources/` | Checked after resolution, because a symlink is not a string. |

The check lives in one function, `FileManager.resolve`, which every path
passes through. It has no branch that returns a path outside its root, which
is what lets commands hand it whatever the user typed.

Filenames themselves are restricted to letters, digits, underscores and `/`,
plus the `.txt` extension: no spaces, no hyphens, no other dots. All files in
`sources/` follow this rule.

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
| `file_manager.py` | `FileManager`: all filesystem access, and stateless. Resolves library paths (`resolve`, `relative`), lists and walks folders (`ls`, `get_txts`, `rand_file`, `rand_dir`), and extracts words (`get_words`, `remove_gutenberg`). Raises `InvalidPath` for anything outside its root and `UnreadableSource` for a file it cannot read. `ROOT_DIR` is the absolute `sources/` path, derived from this file's own location. |
| `command_result.py` | `CommandResult`: what every command returns. Carries `ok`, `message`, `data`, `updates`, `confirm` and `quit`. Commands never print, so the same command can serve a terminal or an HTTP request. |
| `command.py` | `Command` base class: `cmd_name()`, `cmd_args()`, `matches(line)`, `parse_args(line)`, `execute(args, context)`, `overview()`. The default `matches` builds a regex from the name and argument list; most commands override it to add short aliases. |
| `file_command.py` | `FileCommand`: a `Command` that holds a `FileManager`. |
| `set_op_cmd.py` | `SetOpCommand`: shared argument handling for `combine`, `diff`, and `intersection`; subclasses supply `aliases()` and `set_operation(s1, s2)`. |
| `arg.py` | `Arg`: a typed, optionally optional/repeated argument description used for validation and help text. |
| `*_cmd.py` | One file per command (see the table below). |
| `command_list.py` | `CommandList`: constructs every command instance (`cmd_list`) and holds the name → command registry. Registration order is the order the parser tries matches in. |
| `command_manager.py` | `CommandManager`: owns the context. `execute` runs a command, pops a `result` key from what it returns, and merges the rest into the context. |
| `word_cache.py` | `CachingFileManager`: a `FileManager` that remembers what it has read, keyed by path and modification time and bounded by total words. The terminal does not need it; a browser does. |
| `session.py` | `Session`, one person's pools and the commands that change them, and `SessionStore`, the one place identity would go. |
| `web_routes.py` | Route handlers, as plain functions from a request to a status and a payload, so the transport can be swapped without touching them. |
| `web_server.py` | The standard-library HTTP server, the origin checks, and static file serving from a fixed table. |
| `serve.py` | Entry point for the browser interface. Warms the dictionaries, then the books. |
| `parser.py` | `Parser`: reads a line and finds the first command whose `matches` accepts it. A line nothing claims comes back as `(None, [])`, and the caller turns that into a result. Importing it enables `readline` line editing where available. |

Command classes:

| File | Class | Command |
|---|---|---|
| `ls_cmd.py` | `LS` | `ls` |
| `load_cmd.py` | `Load` | `load`, bare `*.txt` |
| `get_word_cmd.py` | `GetWord` | `word`, `next`, empty line, number |
| `load_rand_file_cmd.py` | `LoadRandFile` | `r` |
| `load_rand_dir_file_cmd.py` | `LoadRandDirFile` | `dr` |
| `alias_load_cmd.py` | `AliasLoad` | `al` |
| `get_alias_words_cmd.py` | `GetAliasWords` | `gaw` |
| `multi_folder_get_words_cmd.py` | `MultiFolderGetWords` | `mul` |
| `combine_cmd.py` / `diff_cmd.py` / `intersection_cmd.py` | `Combine` / `Diff` / `Intersection` | `c` / `d` / `i` |
| `rand_diff_cmd.py` | `RandDiff` | `rd` |
| `forget_cmd.py` | `Forget` | `forget`, `rm` |
| `dump_cmd.py` | `Dump` | `dump` |
| `help_cmd.py` | `Help` | `help` |
| `quit_cmd.py` | `Quit` | `quit` |

### Control flow of one command

1. `Parser.get_command` reads a line, strips it, and calls `matches` on each
   registered command in registration order; the first match wins and its
   `parse_args` splits the line into arguments.
2. `CommandManager.execute` calls `command.execute(args, context)`.
3. The command reads whatever it needs from the context and the
   `FileManager` and returns a `CommandResult`. It never prints. `message`
   is the line to show, `ok` is false for a user error, `updates` are the
   context entries to store, `data` is a structured payload for an API,
   `confirm` is a question that must be answered before the updates apply,
   `removes` are pools to forget, and `quit` ends the session.
4. The manager applies `removes` and merges `updates` into the context, but
   only when the command succeeded and set no `confirm`, so a failed command
   cannot change the session. It hands the result back.
5. The front end decides what to do with it. The terminal prints `message`,
   asks `confirm` and calls `CommandManager.apply` on a yes, and stops on
   `quit`. An HTTP handler would serialise `message` and `data` instead.

### Adding a command

1. Create `my_cmd.py` with a class extending `Command` (or `FileCommand` if
   it needs the filesystem). Implement `cmd_name`, `cmd_args`, and `execute`;
   override `matches` and `parse_args` if you want aliases or a non-standard
   syntax, and `overview` for a friendlier `help` line.
2. Return a `CommandResult` from `execute`, never a bare dict and never
   `None`. Use `CommandResult.fail(message)` for a user error.
3. Add an instance to the list in `CommandList.cmd_list`. Put it **before**
   any command whose pattern could also match your syntax.
4. Add `my_cmd_test.py` next to it, and add the new syntax to the
   precedence table in `parser_test.test_parse_every_documented_syntax`. If
   it takes a path, add it to the table in `path_safety_test.py` too.

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

There are 207 tests and they all pass. Files named `fake_*.py`
(`fake_command.py`, `fake_directories.py`, `fake_file_manager.py`) are test
doubles, not test cases. Tests that touch the filesystem build a temporary
directory tree through `FakeDirectories` / `FakeFileManager` rather than
mocking, so they need a writable temp dir. Tests that involve randomness
patch `random.choice` with a deterministic function.

Two files are worth keeping an eye on. `path_safety_test.py` drives every
command that takes a path, through the real parser and command manager, with
every spelling of a path that tries to leave the library, and asserts each is
refused and the session unchanged. `web_server_test.py` runs a real server on
an ephemeral port and drives the origin table above with the headers a
browser would really send. `web_parity_test.py` drives every documented
command syntax through the one endpoint that accepts the command language,
sharing its table with the parser test, so the browser cannot quietly lose a
command the terminal has.

## Known limitations

- Filenames are restricted to letters, digits, underscores, and `/`. A file
  with a space or a hyphen in its name cannot be typed as an argument.
- There is no way to read a text outside `sources/`. That was possible when
  the tool had a working directory, and is not now. If you want it back, the
  intended shape is a second root given at startup rather than a path that
  escapes the first one.
- The terminal tool re-reads a file on every command that touches it; the
  450k dictionary takes about a quarter of a second each time. The server
  caches, the terminal deliberately does not, because a person types slower
  than a parse.
- `Command.validate_args` can only ever check `str` arguments, because
  `parse_args` yields strings for every command except `get_word`.
- Sampling is uniform over distinct spellings, not over occurrences, so rare
  words are as likely as common ones. That is usually the point, but it is
  worth knowing.
