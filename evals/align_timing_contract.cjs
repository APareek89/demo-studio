// Test the real timing formatter used by both Align review surfaces.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const source = fs.readFileSync("web/studio/align.js", "utf8");
const code = source.slice(source.indexOf("export function scriptTiming"), source.indexOf("// Keep the reviewed route editable"));
const timing = vm.runInNewContext(code.replace("export function", "function") + "; scriptTiming");
assert.equal(timing(24.2, 20.1, true, true), "24 s planned / 20 s measured");
assert.equal(timing(24.2, 20.1, false, true), "24 s planned / 20 s mixed measured/estimated");
assert.equal(timing(24.2, 20.1), "24 s planned / 20 s estimated");
assert.equal(timing(null, 0), "no planned time / 0 s estimated");
assert.equal(timing(undefined, undefined), "no planned time / not voiced yet");
console.log("5/5 Align timing contracts passed");
