'use strict';
// Entry point for `node --test js_tests/`. Newer Node versions treat a
// directory argument as a single module to run rather than as a folder of
// tests, so this loads every *.test.mjs file beside it. Running one file
// directly (`node --test js_tests/storage.test.mjs`) works as well.

const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const files = fs.readdirSync(__dirname).filter((name) => name.endsWith('.test.mjs')).sort();
for (const name of files) {
  import(pathToFileURL(path.join(__dirname, name)).href).catch((error) => {
    console.error('Could not load ' + name);
    console.error(error);
    process.exitCode = 1;
  });
}
