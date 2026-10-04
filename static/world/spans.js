// Checks and edits for replacing a known span of editor text. Pure.
//
// Reports and suggestions describe a span as UTF-16 offsets (start, end), the
// text they expect there, and the revision they were computed against. A span
// is only safe to edit when all three still match.

export function spanIsCurrent(current, span) {
  return current.revision === span.revision
    && current.text.slice(span.start, span.end) === span.expected;
}

export function replaceSpan(text, start, end, replacement) {
  return text.slice(0, start) + replacement + text.slice(end);
}
