#!/bin/sh
# The tests are named *_test.py, which the default unittest discovery
# pattern (test*.py) does not match, so the pattern must be given.
python3 -m unittest discover -p '*_test.py' "$@"
status=$?

# The world desk's JavaScript modules are tested with Node's built-in runner
# (no npm packages). Skipped, with a note, when node is not installed.
if command -v node >/dev/null 2>&1; then
  # Pass each test file to Node so its native per-file process isolation
  # protects fake DOM, timer and storage globals from neighboring suites.
  node --test js_tests/*.test.mjs
  js_status=$?
  if [ "$js_status" -ne 0 ]; then
    status=$js_status
  fi
else
  echo "node not found; skipping js_tests/" >&2
fi

exit $status
