const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

// The lock claims the password field's focus back whenever its window becomes
// active (issue #85: after a resume the keyboard was ignored until a click).
// The same LockHost draws every preview in the explorer, the side panel and the
// editor, so a preview that takes input would pull the keyboard away from them
// each time their window is activated.

const root = path.join(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(root, f), "utf8");

test("the lock reclaims the field when its window becomes active", () => {
  const host = read("LockHost.qml");
  assert.match(host, /readonly property bool windowActive: Window\.active/);
  assert.match(host, /onWindowActiveChanged: if \(windowActive && inputEnabled\) Qt\.callLater\(forcePasswordFocus\)/);
});

test("every preview LockHost leaves the keyboard alone", () => {
  const offenders = [];
  for (const file of ["Explorer.qml", "SidePanel.qml", "Editor.qml"]) {
    const src = read(file);
    let at = 0;
    while ((at = src.indexOf("LockHost {", at)) >= 0) {
      // The LockHost's own lines, up to its closing brace at the same depth.
      let depth = 0, end = at;
      for (; end < src.length; end++) {
        if (src[end] === "{") depth++;
        else if (src[end] === "}" && --depth === 0) break;
      }
      const body = src.slice(at, end);
      const line = src.slice(0, at).split("\n").length;
      if (!/^\s*inputEnabled:\s*false\s*$/m.test(body)) offenders.push(`${file}:${line}`);
      at = end;
    }
  }
  assert.deepEqual(offenders, [], "a preview LockHost needs inputEnabled: false");
});
