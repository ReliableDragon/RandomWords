# Code review: RandomWords

Reviewed at commit `0d2d0f2` on Python 3.13.7 (macOS), then fixed on the
`review-fixes` branch. Every bug was reproduced by driving the real program
or the real test suite before the fix, and re-checked the same way after.

**Status: all 13 findings addressed.** The suite went from 107 tests with 4
errors to 142 tests, all passing.

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | High | 4 tests fail on Python 3.13; `cd nowhere` + `ls` crashes | Fixed |
| 2 | High | `rand_diff` is a no-op | Fixed |
| 3 | High | Ten distinct typo paths crash the whole program | Fixed |
| 4 | Medium | No quit command; Ctrl-D prints a traceback | Fixed |
| 5 | Medium | Only works when run from the repo root | Fixed |
| 6 | Medium | `cd` accepts non-existent folders, does not normalise `..` | Fixed |
| 7 | Medium | Word splitting keeps `about—however`; case duplicates bias sampling | Fixed |
| 8 | Low | Hidden folders are not filtered | Fixed |
| 9 | Low | `CommandManager` shares one context dict across instances | Fixed |
| 10 | Low | Upper-case command word matches but then fails to parse | Fixed |
| 11 | Low | CLI `filename` argument is parsed at import time and ignored | Fixed |
| 12 | Low | `dump false` dumps everything | Fixed |
| 13 | Low | Test-suite gaps and duplicates | Fixed |

---

## 1. Tests failed on Python 3.13 (and `ls` after a bad `cd` crashed)

**Was.** `python3 -m unittest discover -p '*_test.py'` gave 4
`FileNotFoundError` errors from `file_manager.py`, and `cd nowhere` followed
by `ls` killed the program.

`FileManager.ls` called `pathlib.Path(dir_).iterdir()` *before* the `try`.
Up to Python 3.12 `iterdir()` was lazy and the error surfaced inside the loop,
where it was caught; in 3.13 it calls `os.scandir` eagerly.

**Now.** The call is inside the `try`, which catches `FileNotFoundError`,
`NotADirectoryError`, and `PermissionError` and returns `None`.
`LS.execute` names the directory it could not read instead of printing
`File 'None' not found.`

## 2. `rand_diff` was a no-op

**Was.** `rd 10` printed `Loaded .../20k_leagues.txt.` and left the word pool
byte-for-byte unchanged. Three separate problems: the result of the inner
`load_rand_file` was never merged into the context, so the diff ran against
the *old* pool; the diff's own result was then discarded; and the dictionary
path was relative to the current directory, so it only resolved at the
sources root.

**Now.** The freshly loaded words are merged into a scratch context that the
diff consumes, the diff's result is returned, and the dictionary path is
built from `ROOT_DIR`. Verified on real data: `rd 10` against
`aristotle_animals.txt` leaves 5,706 words out of the book's vocabulary.

`rand_diff_cmd_test.py` was a stub containing only `pass`. It now has four
tests. The main one seeds the context with a stale pool, so it fails if the
old "diff the wrong pool" behaviour ever returns.

## 3. Typos crashed the whole program

Ten inputs each ended the session with a traceback. All ten now print a
message and continue; re-verified by driving the real REPL.

| Input | Was | Now |
|---|---|---|
| `r nonexistent_folder` | `IndexError` | `No .txt files found under ...` |
| `load nonexistent.txt` then `word` | `IndexError` | Reports the bad file, keeps the current pool |
| `load nosuchalias` then `word` | `TypeError` | Lists the valid names, keeps the pool |
| `d nosuchalias foo` (also `c`, `i`) | `AssertionError` | Explains that the two-argument form needs an alias first |
| `mul nonexistent_folder` | `IndexError` | `No .txt files found under ...` |
| `gaw r` with no aliases | `IndexError` | `No aliases are defined yet.` |
| `al foo bad.txt` then `gaw foo` | `IndexError` | Refuses to create an empty alias |
| `LOAD dicts/test.txt` then `word` | `IndexError` | Loads correctly (finding 10) |
| `dr` where no texts exist below | `IndexError` | `No .txt files found under ...` |
| `word` with an empty pool | `IndexError` | `No words are loaded. Use load, r or dr first.` |

The root cause was that failure was signalled by an empty list or `None` that
nobody checked. Fixed in three layers:

- **`FileManager` reports failure.** `get_words` returns `None` (not `[]`)
  when a file cannot be read; `rand_file` and `rand_dir` return `None` when
  there is nothing to choose from. `rand_dir` also skips folders that turn
  out to hold no texts rather than returning an empty string.
- **Commands check before storing.** Every loading command refuses to put an
  empty or missing pool into the context, so a typo can no longer destroy the
  pool you were working with. The `assert` that validated user input in
  `set_op_cmd.py` is now a printed message. Two dead
  `except FileNotFoundError` blocks (unreachable, because `get_words` caught
  the error itself) are gone.
- **The loop has a backstop.** `RandomWords.run` catches any exception from a
  command, prints `Error: ...`, and carries on.

## 4. No quit command; Ctrl-D printed a traceback

**Was.** `quit`, `exit`, and `q` all printed "I'm sorry, I don't understand",
and end-of-input raised `EOFError` with a traceback. The loop waited for a
`'quit'` result that nothing produced.

**Now.** `quit_cmd.py` provides `quit` / `exit` / `q`, registered in
`CommandList`. The loop treats `EOFError` and `KeyboardInterrupt` as quit, so
Ctrl-D and Ctrl-C leave quietly. The startup banner mentions it.

## 5. Only worked when run from the repository root

**Was.** From any other directory the program crashed at startup, because
`ROOT_DIR` and `get_rooted` both used `os.path.abspath('.')` at import time.

**Now.** `ROOT_DIR` is derived from `__file__`, and the `sources/` prefix is a
constant. Verified by running the tool from an unrelated directory.

## 6. `cd` did not validate or normalise

**Was.** `cd nowhere` silently succeeded and poisoned the next `ls`.
`cd classics` then `cd ../..` produced `.../sources/classics/../../`, escaping
the sources root because the clamp only ran for a literal `..`.

**Now.** `FileManager.cd` joins and normalises the path, and clamps any
relative navigation that would leave `sources/`. Absolute paths are still
honoured as-is, which is the documented escape hatch. `CD.execute` checks
that the destination exists and restores the previous directory if not.

## 7. Word splitting quality

Measured on `sources/classics/moby_dick.txt`:

| Metric | Before | After |
|---|---|---|
| Tokens | 21,049 | 18,639 |
| Tokens containing an em/en dash (`about—however`) | 1,291 (6.1%) | 0 |
| Duplicates differing only by case (`The`/`the`) | 1,648 | 0 |
| Contractions kept whole (`ain't`) | no (`ain`, `t`) | yes |

Three causes: `—` and `–` were treated as word characters, and Gutenberg
texts use unspaced em dashes constantly; de-duplication happened *before*
lower-casing, so a word appearing both capitalised and not was twice as
likely to be picked; and apostrophes split words into stray single letters.

**Now.** A single `WORD_RE` matches runs of letters/digits optionally joined
by internal apostrophes or hyphens. `[^\W_]` is Unicode-aware, so accented
letters work without the hand-written `À-ÿ` range (which also wrongly
admitted `×` and `÷`). Lower-casing happens before de-duplication, and the
result is sorted for determinism.

The one test fixture that asserted `se—ven` stayed whole now expects `se` and
`ven`; new tests cover case-folding and possessives.

## 8. Hidden folders were not filtered

**Was.** `ls` tested `str(f)[0] != '.'`, but `str(f)` is an absolute path,
which always starts with `/`. The unit-test mock set `__str__` to the bare
name, which is why the test passed while the real behaviour was wrong.

**Now.** The check uses `f.name`, with a test that creates a real `.hidden`
directory.

## 9. `CommandManager` shared a mutable default

**Was.** `def __init__(self, command_list, context={})`, so two managers built
without an explicit context shared one dict.

**Now.** `context=None`, replaced with a fresh dict per instance.

## 10. Upper-case command words half-worked

**Was.** `LOAD dicts/test.txt` was accepted but loaded nothing, because
`check_match` lower-cases the line while `Load.parse_args` did
`removeprefix('load ')` on the original. Trailing whitespace broke matching
the other way.

**Now.** `Parser.parse` strips the line, and `Load.parse_args` removes the
command word case-insensitively. `GetWord` and `LoadRandDirFile`, which
compare strings by hand, lower-case first. Arguments keep their original case,
which matters for `HoD.txt`.

## 11. The CLI `filename` argument

**Was.** `book_word.py` built an `ArgumentParser` at module level and never
used the result, so importing the module parsed `sys.argv`.

**Now.** Parsing happens in `main()`, and the argument selects the startup
file, defaulting to `sources/dicts/70k_words.txt`.

## 12. `dump false` dumped everything

**Was.** `bool(args_[0])` on a string, so any argument at all meant "dump
everything".

**Now.** `dump` lists each pool with its word count, and only `dump all` (or
`dump full`) prints contents. `dump_cmd_test.py` is new.

## 13. Test-suite gaps

- `rand_diff_cmd_test.py` had no assertions. It now has four tests.
- `file_manager_test.py` defined `test_ls` twice; the duplicate is gone.
- Nothing tested `Parser.parse` against the real command list, so an alias
  collision between two commands would have gone unnoticed.
  `test_parse_every_documented_syntax` now checks all 32 documented forms
  resolve to the right command.
- `RandomWords.run` was untested. `book_word_test.py` covers quitting, EOF,
  Ctrl-C, a command that raises, and a missing startup file.
- The four helper modules were named `test_*.py`, so `python3 -m unittest`
  picked them up as tests while missing the real `*_test.py` files. They are
  renamed `fake_command.py`, `fake_directories.py`, `fake_file_manager.py`
  (classes `FakeCommand`, `FakeDirectories`, `FakeFileManager`), which also
  ends the collision between the helper `TestCommand(Command)` and the test
  case `TestCommand(unittest.TestCase)`. `test_util.py` was dead code and is
  deleted. `run_tests.sh` runs the suite with the right pattern.

New error-path tests cover the guards added for finding 3: bad loads, empty
folders, missing directories, empty aliases, and `cd` to nowhere.

---

## Code-quality items also applied

- Replaced `assert` on user input with a printed message; removed the two
  asserts guarding internal invariants that `__init__` already enforces.
- `== None` / `!= None` → `is None` throughout.
- Removed unused imports across 15 files and unused names `DEFAULT_COMMAND`,
  `RandomWords.cmd`, and `FileManager.get_relative_name`. `pyflakes` is clean
  apart from the deliberate `readline` side-effect import.
- `import readline` is wrapped in `try`/`except ImportError`, so the tool now
  runs on Windows.
- Dropped the redundant `get_rooted` call in commands that then call
  `get_words`, which roots the path itself.
- `remove_gutenberg` no longer raises when a file has a header but no footer;
  it keeps the rest of the file.
- `help` prints usage (`cd <folder>`, `dump [all]`) instead of a repr of the
  argument list, and documents the bare forms of `load` and `get_word`.
- `ls` output is sorted.

## Repository housekeeping

- Deleted `combine_cmd.py.bak` (editor backup of the pre-`SetOpCommand`
  version) and `book_word_orig.py` (the superseded first version, still in
  git history).
- Deleted the root `__init__.py`; there is no package layout.
- `.gitignore` now covers `__pycache__/`, `*.pyc`, and `.DS_Store`, and ends
  with a newline. The two tracked `.DS_Store` files are untracked with
  `git rm --cached` and left on disk.
- Committed `sources/custom/words.txt`, which was untracked.
- Added `run_tests.sh`.

## Deliberately not done

- **No word cache.** Re-reading the 450k dictionary costs about 0.35s and
  every other file under 0.07s, which is not worth the invalidation
  complexity for an interactive tool.
- **`Arg` type machinery left alone.** `validate_args` can only ever check
  `str`, because `parse_args` yields strings everywhere except `get_word`.
  Making it meaningful means converting arguments to their declared types in
  a generic `parse_args`; removing it means dropping validation. Both are
  design calls rather than fixes.
- **No `Session` object.** Passing the context, the file manager, and the
  registry to every command would remove the need for `FileCommand` and the
  special-casing of `Help` and `RandDiff`, but it is a rewrite of every
  command signature.
- **No formatter or linter config.** `ruff` would have caught several of the
  items above, but adding it is a workflow choice.
