// Pure selection checks. No server, SDK network, device or paid provider calls.
import assert from "node:assert/strict";
import fs from "node:fs";
const source = fs.readFileSync(new URL("../web/player/voice-transport.js", import.meta.url), "utf8");
const { resolveLiveClientFactory: resolve } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
let passed = 0;
function check(name, condition) { assert.ok(condition, name); passed++; console.log("PASS", name); }
const bundle = { version: 3, knowledge_snapshot_id: "snapshot", runtime: { version: 1 } };
function fixture(capability = { transport: "livekit", livekit_enabled: true, livekit_available: true, mode: "hosted" }) {
  const calls = { capability: 0, module: 0, clients: [] };
  class Client { constructor(options) { this.options = options; calls.clients.push(this); } }
  return { calls, Client, options: { search: "", loadCapability: async () => { calls.capability++; return capability; }, loadLiveKit: async () => { calls.module++; return { LiveKitVoiceClient: Client }; } } };
}
{
  const f = fixture(), factory = await resolve(bundle, f.options), client = factory({ sessionId: "first" });
  check("normal URLs select server-advertised hosted LiveKit", client instanceof f.Client && f.calls.capability === 1 && f.calls.module === 1);
  check("selection pins the loaded publication before any token request", client.options.demoVersion === 3 && client.options.knowledgeSnapshotId === "snapshot");
  factory({ sessionId: "restarted" });
  check("restart gets a new client in the same selected transport", f.calls.clients.length === 2 && f.calls.clients[1].options.sessionId === "restarted");
}
{
  const f = fixture({ transport: "livekit", livekit_enabled: true, livekit_available: false, mode: "hosted" });
  check("misconfigured enabled LiveKit remains selected for visible player recovery", typeof await resolve(bundle, f.options) === "function" && f.calls.module === 1);
}
{
  const f = fixture({ transport: "livekit", livekit_enabled: true, livekit_available: true, mode: "trial" });
  check("a configured local trial also works without a URL flag", typeof await resolve(bundle, f.options) === "function");
}
{
  const f = fixture();
  check("explicit websocket diagnostic avoids discovery and LiveKit import", await resolve(bundle, { ...f.options, search: "?voice_transport=websocket" }) === undefined && !f.calls.module && !f.calls.capability);
}
{
  const f = fixture();
  check("explicit legacy LiveKit flag works without a capability endpoint", typeof await resolve(bundle, { ...f.options, search: "?voice_transport=livekit", loadCapability: () => { throw Error("old endpoint absent"); } }) === "function" && !f.calls.capability);
}
{
  const f = fixture({ transport: "websocket", livekit_enabled: false, livekit_available: false, mode: "disabled" });
  check("disabled server retains the established websocket rollback", await resolve(bundle, f.options) === undefined && !f.calls.module);
}
{
  const f = fixture();
  check("legacy publications retain their recorded player without discovery", await resolve({}, f.options) === undefined && !f.calls.module && !f.calls.capability);
  await assert.rejects(resolve({}, { ...f.options, search: "?voice_transport=livekit" }), /does not support live conversation/); passed++; console.log("PASS explicit LiveKit cannot pretend a legacy publication is compatible");
}
{
  const f = fixture({ transport: "unexpected" });
  await assert.rejects(resolve(bundle, f.options), /settings are unavailable/);
  check("invalid capability cannot silently load an alternative client", !f.calls.module && !f.calls.clients.length);
}
{
  const f = fixture();
  await assert.rejects(resolve(bundle, { ...f.options, loadCapability: () => Promise.reject(new Error("offline")) }), /offline/);
  check("discovery failure cannot create a microphone or fallback client", !f.calls.module && !f.calls.clients.length);
}
{
  const f = fixture();
  await assert.rejects(resolve(bundle, { ...f.options, loadCapability: () => new Promise(() => {}), timeoutMs: 5 }), /timed out/);
  check("capability discovery has a finite deadline", !f.calls.module);
}
{
  const f = fixture();
  await assert.rejects(resolve(bundle, { ...f.options, loadLiveKit: () => Promise.reject(new Error("missing SDK")) }), /missing SDK/);
  check("SDK load failure cannot open or replay through another transport", !f.calls.clients.length);
}
{
  const f = fixture(); let release;
  await assert.rejects(resolve(bundle, { ...f.options, loadLiveKit: () => new Promise(done => { release = done; }), timeoutMs: 5 }), /took too long to load/);
  release({ LiveKitVoiceClient: f.Client }); await Promise.resolve();
  check("stalled SDK import has a finite deadline and late completion cannot acquire a client", !f.calls.clients.length);
}
console.log(`voice_transport: ${passed}/${passed}`);
