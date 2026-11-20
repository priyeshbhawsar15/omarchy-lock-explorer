const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

// C on a stock design runs Service.qml's customizeScript. A design customized
// before opens that copy again instead of stranding it behind a new one;
// Shift+C ("fresh") still makes another.

const root = path.join(__dirname, "..");
const service = fs.readFileSync(path.join(root, "Service.qml"), "utf8");
const start = service.indexOf("readonly property string customizeScript: '") + "readonly property string customizeScript: '".length;
let end = start;
while (!(service[end] === "'" && service[end - 1] !== "\\")) end++;
const script = service.slice(start, end).replace(/\\'/g, "'").replace(/\r/g, "");

const linux = process.platform === "linux";

function run(dir, src, fresh) {
  return execFileSync("bash", ["-c", script, path.join(root, "extras", "safe-paths.sh"), src, dir, "Classic", "", "Classic", fresh], { encoding: "utf8" }).trim();
}

function setup() {
  const base = fs.mkdtempSync(path.join(os.homedir(), ".customize-test-"));
  const dir = path.join(base, "lock-designs");
  fs.mkdirSync(dir, { mode: 0o700 });
  const src = path.join(base, "Classic.qml");
  fs.writeFileSync(src, "import QtQuick\nItem {}\n");
  return { base, dir, src };
}

test("C opens the copy made before", { skip: !linux }, () => {
  const { base, dir, src } = setup();
  try {
    const first = run(dir, src, "");
    assert.equal(path.basename(first), "Classic.qml");
    assert.equal(run(dir, src, ""), first);
    assert.deepEqual(fs.readdirSync(dir), ["Classic.qml"]);
  } finally { fs.rmSync(base, { recursive: true, force: true }); }
});

test("C picks the newest of several copies", { skip: !linux }, () => {
  const { base, dir, src } = setup();
  try {
    const a = run(dir, src, "fresh");
    const b = run(dir, src, "fresh");
    assert.notEqual(a, b);
    fs.utimesSync(b, new Date(1000), new Date(1000));
    assert.equal(run(dir, src, ""), a);
  } finally { fs.rmSync(base, { recursive: true, force: true }); }
});

test("Shift+C makes a fresh copy, and a link is never taken for a copy", { skip: !linux }, () => {
  const { base, dir, src } = setup();
  try {
    fs.writeFileSync(path.join(base, "elsewhere.qml"), "// Customized copy of the Classic design. Edit it here or with:\n");
    fs.symlinkSync(path.join(base, "elsewhere.qml"), path.join(dir, "Linked.qml"));
    const made = run(dir, src, "");
    assert.equal(path.basename(made), "Classic.qml");
    assert.equal(path.basename(run(dir, src, "fresh")), "Classic2.qml");
  } finally { fs.rmSync(base, { recursive: true, force: true }); }
});
