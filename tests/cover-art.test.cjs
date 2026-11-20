const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");

// A player's cover art is foreign data: any program on the session bus can
// claim to be a player. It only reaches the screen through
// designs/CoverArt.qml, which re-encodes it in a capped child process, so the
// player's trackArtUrl may appear nowhere but as a CoverArt's url.

const root = path.join(__dirname, "..");
const SKIP = new Set([".git", "node_modules", ".claude"]);

function files(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) files(p, out);
    else if (/\.(qml|js)$/.test(entry.name)) out.push(p);
  }
  return out;
}

test("trackArtUrl only feeds a CoverArt", () => {
  const offenders = [];
  for (const file of files(root)) {
    const rel = path.relative(root, file).replace(/\\/g, "/");
    const lines = fs.readFileSync(file, "utf8").split("\n");
    lines.forEach((line, i) => {
      if (!/trackArtUrl/.test(line) || /^\s*\/\//.test(line)) return;
      if (/^\s*CoverArt\s*\{[^}]*\burl:/.test(line)) return;
      offenders.push(`${rel}:${i + 1}`);
    });
  }
  assert.deepEqual(offenders, [], "pass the player's art through CoverArt");
});

test("CoverArt hands the shell only its own PNG", () => {
  const src = fs.readFileSync(path.join(root, "designs", "CoverArt.qml"), "utf8");
  assert.match(src, /"data:image\/png;base64," \+ b64/);
  assert.match(src, /ulimit -v \d+; ulimit -t \d+/);
  assert.match(src, /--max-filesize "\$cap"/);
  assert.match(src, /-strip/);
});
