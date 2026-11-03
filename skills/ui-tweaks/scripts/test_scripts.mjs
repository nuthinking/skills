#!/usr/bin/env node
// Tests for ui-tweaks: the panel's pure helpers, the config check, and the preview proxy
// against a fake dev server (HTML injection, streaming, redirects, origin rewrite, websockets).
//
//   node skills/ui-tweaks/scripts/test_scripts.mjs
//
// Node built-ins only.

import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const sandbox = { module: { exports: {} } };
vm.runInNewContext(fs.readFileSync(path.join(here, "ui-tweaks.js"), "utf8"), sandbox);
const T = sandbox.module.exports;

const CONFIG = {
  title: "Taskflow",
  palette: ["#4f46e5", "#e11d48", "#0f766e"],
  groups: [
    {
      label: "Colour",
      controls: [
        { id: "brand", label: "Brand colour", type: "color", value: "#4f46e5", targets: [{ var: "--color-brand" }], source: "src/app/globals.css" },
      ],
    },
    {
      label: "Shape",
      controls: [
        {
          id: "roundness", label: "Roundness", type: "scale", value: 1, min: 0, max: 2,
          targets: [{ var: "--radius-card", base: "0.75rem" }, { var: "--radius-control", base: "0.375rem" }],
          source: "src/app/globals.css",
        },
        {
          id: "shadow", label: "Card shadow", type: "choice", value: "sm",
          options: [
            { label: "None", value: "none", code: "shadow-none" },
            { label: "Small", value: "sm", code: "shadow-sm" },
            { label: "Medium", value: "0 4px 6px rgb(0 0 0 / .1)", code: "shadow-md" },
          ],
          targets: [{ class: "shadow-sm", property: "box-shadow" }],
          source: "src/components/Card.tsx",
        },
      ],
    },
    {
      label: "Type",
      controls: [
        { id: "body", label: "Body text", type: "number", value: "14px", min: 12, max: 20, targets: [{ selector: "body", property: "font-size" }], source: "src/app/globals.css" },
      ],
    },
  ],
};

const norm = () => T.normalizeConfig(JSON.parse(JSON.stringify(CONFIG)));
const flat = (m) => m.groups.flatMap((g) => g.controls);

test("normalizeConfig fills defaults and keeps valid controls", () => {
  const m = norm();
  assert.equal(m.errors.length, 0, m.errors.join("\n"));
  const [brand, round, shadow, body] = flat(m);
  assert.equal(brand.hint, "--color-brand");
  assert.equal(round.hint, "--radius-card +1");
  assert.equal(round.step, 0.01);
  assert.equal(shadow.hint, ".shadow-sm box-shadow");
  assert.equal(body.value, 14);
  assert.equal(body.unit, "px");
  assert.equal(body.step, 1);
});

test("normalizeConfig reports bad controls and keeps the rest", () => {
  const m = T.normalizeConfig({
    groups: [{
      label: "G",
      controls: [
        { id: "a", label: "A", type: "slider", value: 1, targets: [{ var: "--a" }] },
        { id: "b", label: "B", type: "scale", targets: [{ var: "--b" }] },
        { id: "c", label: "C", type: "number", value: 4, targets: [{ property: "gap" }] },
        { id: "d", label: "D", type: "choice", value: "x", options: [{ value: "y" }, { value: "z" }], targets: [{ var: "--d" }] },
        { id: "e", label: "E", type: "number", value: 4, targets: [{ var: "e" }] },
        { id: "f", label: "F", type: "number", value: 50, min: 0, max: 10, targets: [{ var: "--f" }] },
        { id: "f", label: "F again", type: "number", value: 1, targets: [{ var: "--f2" }] },
      ],
    }],
  });
  assert.equal(m.errors.length, 6, m.errors.join("\n"));
  assert.match(m.errors[0], /type/);
  assert.match(m.errors[1], /base/);
  assert.match(m.errors[2], /selector/);
  assert.match(m.errors[3], /options/);
  assert.match(m.errors[4], /--/);
  assert.match(m.errors[5], /duplicate/);
  assert.equal(flat(m).length, 1);
  assert.equal(flat(m)[0].max, 50, "range widened to include the value");
  assert.ok(m.warnings.some((w) => /outside/.test(w)));
});

test("source can list several files; identical options are flagged", () => {
  const m = T.normalizeConfig({ controls: [
    { id: "r", label: "Card corners", type: "number", value: 12, unit: "px", targets: [{ var: "--r" }], source: ["src/components/Card.tsx", "src/app/page.tsx"] },
    { id: "s", label: "Shadow", type: "choice", value: "a", options: [{ label: "Soft", value: "a" }, { label: "Card", value: "a" }, { label: "None", value: "none" }], targets: [{ var: "--s" }] },
  ] });
  assert.equal(m.errors.length, 0, m.errors.join("\n"));
  assert.equal(flat(m)[0].source, "src/components/Card.tsx, src/app/page.tsx");
  assert.ok(m.warnings.some((w) => /same value/.test(w)), m.warnings.join("\n"));
});

test("long hints are flagged", () => {
  const m = T.normalizeConfig({ controls: [
    { id: "a", label: "A", type: "number", value: 1, hint: "this hint is much too long for the panel row", targets: [{ var: "--a" }] },
    { id: "b", label: "B", type: "shade", value: "#e5e7eb", hint: "border · app-wide", targets: [{ var: "--b" }] },
  ] });
  assert.equal(m.warnings.filter((w) => /hint is/.test(w)).length, 1, m.warnings.join("\n"));
});

test("normalizeConfig rejects a config without groups", () => {
  assert.ok(T.normalizeConfig({}).errors.length);
  assert.ok(T.normalizeConfig(null).errors.length);
  assert.equal(T.normalizeConfig({ controls: CONFIG.groups[0].controls }).errors.length, 0, "bare controls list is accepted");
});

test("number defaults are craft-sized: about ±50%, steps by unit", () => {
  const m = T.normalizeConfig({ controls: [
    { id: "pad", label: "Card padding", type: "number", value: 24, unit: "px", targets: [{ var: "--p" }] },
    { id: "lh", label: "Line height", type: "number", value: 1.5, targets: [{ var: "--lh" }] },
    { id: "tr", label: "Tracking", type: "number", value: -0.025, unit: "em", targets: [{ var: "--tr" }] },
    { id: "ms", label: "Hover speed", type: "number", value: "150ms", targets: [{ var: "--d" }] },
    { id: "zero", label: "Offset", type: "number", value: 0, unit: "px", targets: [{ var: "--o" }] },
  ] });
  const [pad, lh, tr, ms, zero] = flat(m);
  assert.deepEqual([pad.min, pad.max, pad.step], [12, 36, 1]);
  assert.deepEqual([lh.min, lh.max, lh.step], [0.75, 2.25, 0.01]);
  assert.deepEqual([tr.min, tr.max, tr.step, tr.decimals], [-0.075, 0.025, 0.005, 3]);
  assert.deepEqual([ms.min, ms.max, ms.step, ms.unit], [50, 250, 10, "ms"]);
  assert.deepEqual([zero.min, zero.max], [0, 10]);
  assert.equal(T.cssValue(tr, -0.015), "-0.015em");
});

const SHADE = {
  id: "border", label: "Borders", type: "shade", value: "#e5e7eb",
  steps: [{ value: "#f3f4f6", code: "gray-100" }, { value: "#e5e7eb", code: "gray-200" }, { value: "#d1d5db", code: "gray-300" }, "#9ca3af"],
  targets: [{ var: "--color-border" }], source: "src/app/globals.css",
};

test("OKLCH round trip keeps colours", () => {
  for (const hex of ["#e5e7eb", "#71717b", "#4f46e5", "#000000", "#ffffff", "#0d9488"]) assert.equal(T.shadeHex(hex, 0), hex);
  const [L1] = T.hexToOklch("#e5e7eb"), [L2] = T.hexToOklch(T.shadeHex("#e5e7eb", 0.05));
  assert.ok(Math.abs(L1 - L2 - 0.05) < 0.003, "darker by the asked lightness");
  assert.equal(T.shadeHex("#ffffff", -0.2), "#ffffff", "clamped at white");
});

test("shade marks the app's neighbouring shades and lands on them exactly", () => {
  const m = T.normalizeConfig({ controls: [SHADE] });
  assert.equal(m.errors.length, 0, m.errors.join("\n"));
  const c = flat(m)[0];
  assert.equal(c.marks.length, 4);
  assert.equal(c.marks.find((mk) => mk.d === 0).code, "gray-200", "the code's own shade carries its name");
  const darker = c.marks.find((mk) => mk.code === "gray-300");
  assert.ok(darker.d > 0.04 && darker.d < 0.07, String(darker.d));
  assert.ok(c.max >= c.marks[c.marks.length - 1].d, "range reaches the darkest mark");
  assert.equal(T.cssValue(c, darker.d), "#d1d5db");
  assert.equal(T.shown(c, darker.d), "#d1d5db (gray-300)");
  assert.equal(T.isChanged(c, 0), false);
  assert.equal(T.buildCss([c], { border: darker.d }), ":root { --color-border: #d1d5db !important; }");
  assert.match(T.cssValue(c, 0.02), /^#[0-9a-f]{6}$/);
  assert.equal(
    T.formatCopy([c], { border: darker.d }),
    "Apply these UI tweaks with the ui-tweaks skill (1 change):\n\nBorders  #e5e7eb (gray-200) → #d1d5db (gray-300)  --color-border · src/app/globals.css\n"
  );
});

test("shade needs a colour value", () => {
  const m = T.normalizeConfig({ controls: [{ id: "x", label: "X", type: "shade", targets: [{ var: "--x" }] }] });
  assert.match(m.errors[0], /colour/);
});

test("scaleLength keeps units and rounds sensibly", () => {
  assert.equal(T.scaleLength("0.75rem", 1.5), "1.125rem");
  assert.equal(T.scaleLength("0.375rem", 1.5), "0.5625rem");
  assert.equal(T.scaleLength("12px", 1.25), "15px");
  assert.equal(T.scaleLength("10px", 0.33), "3.3px");
  assert.equal(T.scaleLength("1.5", 1.1), "1.65");
  assert.equal(T.scaleLength("var(--x)", 2), "calc(var(--x) * 2)");
});

test("buildCss only overrides changed controls, grouped by selector", () => {
  const m = norm();
  const cs = flat(m);
  const values = { brand: "#4f46e5", roundness: 1.5, shadow: "none", body: 14 };
  const css = T.buildCss(cs, values);
  assert.equal(
    css,
    [
      ":root { --radius-card: 1.125rem !important; --radius-control: 0.5625rem !important; }",
      ".shadow-sm { box-shadow: none !important; }",
    ].join("\n")
  );
  assert.equal(T.buildCss(cs, { brand: "#4F46E5", roundness: 1, shadow: "sm", body: 14 }), "", "case-insensitive colour, no changes");
});

test("buildCss handles media queries and scoped variables", () => {
  const m = T.normalizeConfig({ controls: [
    { id: "p", label: "Padding", type: "number", value: 32, unit: "px", targets: [{ class: "md:p-8", property: "padding", media: "(min-width: 768px)" }] },
    { id: "d", label: "Dark brand", type: "color", value: "#000000", targets: [{ var: "--primary", selector: ".dark" }] },
  ] });
  const css = T.buildCss(flat(m), { p: 40, d: "#111111" });
  assert.equal(css, "@media (min-width: 768px) { .md\\:p-8 { padding: 40px !important; } }\n.dark { --primary: #111111 !important; }");
});

test("formatCopy lists only changes, old → new, with where they live", () => {
  const cs = flat(norm());
  const text = T.formatCopy(cs, { brand: "#e11d48", roundness: 1.5, shadow: "0 4px 6px rgb(0 0 0 / .1)", body: 14 });
  assert.equal(
    text,
    [
      "Apply these UI tweaks with the ui-tweaks skill (3 changes):",
      "",
      "Brand colour  #4f46e5 → #e11d48                       --color-brand · src/app/globals.css",
      "Roundness     100% → 150%                             src/app/globals.css",
      "  --radius-card     0.75rem → 1.125rem",
      "  --radius-control  0.375rem → 0.5625rem",
      "Card shadow   Small → Medium (shadow-sm → shadow-md)  .shadow-sm box-shadow · src/components/Card.tsx",
      "",
    ].join("\n")
  );
  assert.equal(T.formatCopy(cs, { brand: "#4f46e5", roundness: 1, shadow: "sm", body: 14 }), "");
});

test("choices with an empty code read as add or remove", () => {
  const m = T.normalizeConfig({ controls: [
    { id: "o", label: "List outline", type: "choice", value: "0px solid", options: [{ label: "None", value: "0px solid", code: "" }, { label: "Hairline", value: "1px solid #e5e7eb", code: "border border-border" }], targets: [{ selector: ".list", property: "border" }] },
  ] });
  const c = flat(m)[0];
  assert.match(T.formatCopy([c], { o: "1px solid #e5e7eb" }), /None → Hairline \(add border border-border\)/);
  c.value = "1px solid #e5e7eb";
  assert.match(T.formatCopy([c], { o: "0px solid" }), /Hairline → None \(remove border border-border\)/);
});

test("formatCopy says 1 change", () => {
  const cs = flat(norm());
  assert.match(T.formatCopy(cs, { brand: "#4f46e5", roundness: 1, shadow: "sm", body: 16 }), /\(1 change\):\n\nBody text  14px → 16px  body font-size · src\/app\/globals.css\n$/);
});

// ------------------------------------------------------------------------------------------------
// preview.mjs
// ------------------------------------------------------------------------------------------------

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "ui-tweaks-test-"));
const configPath = path.join(tmp, "config.json");
fs.writeFileSync(configPath, JSON.stringify(CONFIG));
const previewScript = path.join(here, "preview.mjs");

test("--check passes a good config and fails a bad one", () => {
  const ok = spawnSync(process.execPath, [previewScript, "--check", "--config", configPath], { encoding: "utf8" });
  assert.equal(ok.status, 0, ok.stdout + ok.stderr);
  assert.match(ok.stdout, /config ok: 4 controls/);
  const bad = path.join(tmp, "bad.json");
  fs.writeFileSync(bad, JSON.stringify({ groups: [{ label: "x", controls: [{ id: "a", type: "nope", targets: [] }] }] }));
  const r = spawnSync(process.execPath, [previewScript, "--check", "--config", bad], { encoding: "utf8" });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /error:/);
  const missing = spawnSync(process.execPath, [previewScript, "--check", "--config", path.join(tmp, "nope.json")], { encoding: "utf8" });
  assert.equal(missing.status, 1);
});

test("--app finds the config from any working directory", () => {
  const app = fs.mkdtempSync(path.join(os.tmpdir(), "ui-tweaks-app-"));
  fs.mkdirSync(path.join(app, ".ui-tweaks"));
  fs.writeFileSync(path.join(app, ".ui-tweaks", "config.json"), JSON.stringify(CONFIG));
  const r = spawnSync(process.execPath, [previewScript, "--check", "--app", app], { encoding: "utf8", cwd: os.tmpdir() });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  assert.match(r.stdout, /config ok/);
});

function fakeDevServer() {
  const seen = [];
  const server = http.createServer((req, res) => {
    seen.push({ url: req.url, host: req.headers.host, origin: req.headers.origin, referer: req.headers.referer, enc: req.headers["accept-encoding"] });
    if (req.url === "/") {
      res.writeHead(200, { "content-type": "text/html; charset=utf-8", "content-security-policy": "script-src 'none'" });
      res.write("<!doctype html><html><head><title>Ünïcode</title></he");
      setTimeout(() => res.end("ad><body><p>hi</p></body></html>"), 20);
    } else if (req.url === "/fragment") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<p>no head here</p>");
    } else if (req.url === "/app.js") {
      res.writeHead(200, { "content-type": "text/javascript", "content-length": "9" });
      res.end("var a=1;\n");
    } else if (req.url === "/go") {
      res.writeHead(307, { location: `http://127.0.0.1:${server.address().port}/login?next=1` });
      res.end();
    } else if (req.url === "/echo" && req.method === "POST") {
      let b = "";
      req.on("data", (c) => (b += c));
      req.on("end", () => { res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify({ body: b })); });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  server.on("upgrade", (req, socket) => {
    seen.push({ upgrade: req.url, host: req.headers.host, origin: req.headers.origin });
    socket.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n");
    socket.on("data", (d) => socket.write(d)); // echo
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, seen, port: server.address().port })));
}

function startPreview(targetPort) {
  const child = spawn(process.execPath, [previewScript, "--target", `http://127.0.0.1:${targetPort}`, "--port", "0", "--config", configPath]);
  return new Promise((resolve, reject) => {
    let out = "";
    child.stdout.on("data", (d) => {
      out += d;
      const m = /http:\/\/localhost:(\d+)/.exec(out);
      if (m) resolve({ child, port: Number(m[1]) });
    });
    child.on("exit", (code) => reject(new Error("preview exited " + code + ": " + out)));
  });
}

function get(port, p, opts = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, path: p, method: opts.method || "GET", headers: opts.headers || {} }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", reject);
    req.end(opts.body);
  });
}

test("preview proxies the app and adds the panel", async (t) => {
  const dev = await fakeDevServer();
  const { child, port } = await startPreview(dev.port);
  t.after(() => { child.kill(); dev.server.close(); dev.server.closeAllConnections?.(); });

  const page = await get(port, "/", { headers: { "accept-encoding": "gzip", origin: `http://localhost:${port}`, referer: `http://localhost:${port}/tasks?x=1` } });
  assert.equal(page.status, 200);
  assert.equal(page.body, '<!doctype html><html><head><title>Ünïcode</title><script src="/__ui-tweaks/ui-tweaks.js" async></script></head><body><p>hi</p></body></html>');
  assert.equal(page.headers["content-security-policy"], undefined, "CSP removed so the panel can load");
  const first = dev.seen[0];
  assert.equal(first.host, `127.0.0.1:${dev.port}`);
  assert.equal(first.origin, `http://127.0.0.1:${dev.port}`);
  assert.equal(first.referer, `http://127.0.0.1:${dev.port}/tasks?x=1`);
  assert.equal(first.enc, undefined, "asks for plain bodies");

  const frag = await get(port, "/fragment");
  assert.equal(frag.body, '<p>no head here</p><script src="/__ui-tweaks/ui-tweaks.js" async></script>');

  const js = await get(port, "/app.js");
  assert.equal(js.body, "var a=1;\n");
  assert.equal(js.headers["content-length"], "9");

  const redirect = await get(port, "/go");
  assert.equal(redirect.status, 307);
  assert.equal(redirect.headers.location, `http://127.0.0.1:${port}/login?next=1`);

  const echo = await get(port, "/echo", { method: "POST", body: "hello", headers: { "content-type": "text/plain" } });
  assert.deepEqual(JSON.parse(echo.body), { body: "hello" });

  const panel = await get(port, "/__ui-tweaks/ui-tweaks.js");
  assert.equal(panel.status, 200);
  assert.match(panel.headers["content-type"], /javascript/);
  assert.match(panel.body, /ui-tweaks panel/);
  const cfg = await get(port, "/__ui-tweaks/config.json");
  assert.equal(JSON.parse(cfg.body).title, "Taskflow");
  assert.equal(cfg.headers["cache-control"], "no-store");

  // Websocket upgrade (hot reload) is tunnelled both ways.
  const echoed = await new Promise((resolve, reject) => {
    const s = net.connect(port, "127.0.0.1", () => {
      s.write(`GET /_next/webpack-hmr HTTP/1.1\r\nHost: localhost:${port}\r\nOrigin: http://localhost:${port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: x\r\nSec-WebSocket-Version: 13\r\n\r\n`);
    });
    let buf = "";
    s.on("data", (d) => {
      buf += d;
      if (/101 Switching/.test(buf) && !buf.includes("ping")) s.write("ping");
      if (buf.endsWith("ping")) { s.end(); resolve(buf); }
    });
    s.on("error", reject);
  });
  assert.match(echoed, /101 Switching Protocols/);
  const up = dev.seen.find((s) => s.upgrade);
  assert.equal(up.upgrade, "/_next/webpack-hmr");
  assert.equal(up.host, `127.0.0.1:${dev.port}`);
  assert.equal(up.origin, `http://127.0.0.1:${dev.port}`);
});

test("preview moves to the next port when busy and prints the address once", async (t) => {
  const busy = await new Promise((resolve) => { const s = net.createServer(); s.listen(0, () => resolve(s)); });
  t.after(() => busy.close());
  const taken = busy.address().port;
  const child = spawn(process.execPath, [previewScript, "--target", "http://127.0.0.1:9", "--port", String(taken), "--config", configPath]);
  t.after(() => child.kill());
  const out = await new Promise((resolve) => {
    let buf = "";
    child.stdout.on("data", (d) => { buf += d; if (/config:/.test(buf)) setTimeout(() => resolve(buf), 150); });
  });
  assert.equal((out.match(/ui-tweaks preview:/g) || []).length, 1, out);
  assert.match(out, new RegExp("localhost:" + (taken + 1)));
});

test("preview explains when the dev server is not running", async (t) => {
  const dead = await new Promise((resolve) => { const s = net.createServer(); s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => resolve(p)); }); });
  const { child, port } = await startPreview(dead);
  t.after(() => child.kill());
  const r = await get(port, "/");
  assert.equal(r.status, 502);
  assert.match(r.body, /Nothing is answering/);
});

test("preview refuses to start without a config", () => {
  const r = spawnSync(process.execPath, [previewScript, "--target", "http://127.0.0.1:9", "--port", "0", "--config", path.join(tmp, "missing.json")], { encoding: "utf8", timeout: 5000 });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /no config/);
});
