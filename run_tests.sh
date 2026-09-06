#!/bin/sh
# The tests are named *_test.py, which the default unittest discovery
# pattern (test*.py) does not match, so the pattern must be given.
exec python3 -m unittest discover -p '*_test.py' "$@"
