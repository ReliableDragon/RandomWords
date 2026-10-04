'use strict';
// Node treats this directory argument as one test module, which cannot safely
// isolate the fake DOM, timer and storage globals used by neighboring suites.
console.error(
  'Do not run `node --test js_tests/`. Use `./run_tests.sh` or '
  + '`node --test js_tests/*.test.mjs` for per-file process isolation.',
);
process.exitCode = 1;
