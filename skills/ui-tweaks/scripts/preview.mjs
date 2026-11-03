#!/usr/bin/env node
// ui-tweaks: a preview address that shows the running app with the Tweaks panel on top.
//
//   node preview.mjs --target http://localhost:3000 [--app <app root>] [--port 3999] [--config <file>]
//   node preview.mjs --check [--app <app root>] [--config <file>]
//
// The config defaults to <app root>/.ui-tweaks/config.json; the app root defaults to the current
// directory, so either run it from the app root or pass --app.
//
// Forwards every request to the dev server (hot reload websockets included) and adds one
// <script> tag to HTML pages; the app's code is not touched. Serves the panel and the config
// under /__ui-tweaks/. Origin, Referer and redirects are rewritten so the dev server sees its own
// address. --check validates the config and exits (1 on errors). Stop with Ctrl-C.
//
// Standard library only.

import http from "node:http";
import https from "node:https";
import net from "node:net";
import tls from "node:tls";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : def; };
const here = path.dirname(fileURLToPath(import.meta.url));
const panelFile = path.join(here, "ui-tweaks.js");
const appRoot = path.resolve(opt("--app", "."));
const configFile = path.resolve(appRoot, opt("--config", ".ui-tweaks/config.json"));
const PREFIX = "/__ui-tweaks/";
const TAG = Buffer.from(`<script src="${PREFIX}ui-tweaks.js" async></script>`);

// The panel's own config validation, run in a sandbox so this works whatever package.json says about modules.
function loadHelpers() {
  const sandbox = { module: { exports: {} } };
  vm.runInNewContext(fs.readFileSync(panelFile, "utf8"), sandbox, { filename: panelFile });
  return sandbox.module.exports;
}

function check() {
  if (!fs.existsSync(configFile)) return { errors: [`no config at ${configFile}`], warnings: [], count: 0 };
  let raw;
  try { raw = JSON.parse(fs.readFileSync(configFile, "utf8")); } catch (e) { return { errors: [`${configFile} is not valid JSON: ${e.message}`], warnings: [], count: 0 }; }
  const m = loadHelpers().normalizeConfig(raw);
  return { errors: m.errors, warnings: m.warnings, count: m.groups.reduce((n, g) => n + g.controls.length, 0) };
}

function report(r) {
  r.errors.forEach((e) => console.log(`  error: ${e}`));
  r.warnings.forEach((w) => console.log(`  warning: ${w}`));
}

if (args.includes("--check")) {
  const r = check();
  report(r);
  console.log(r.errors.length ? `config has ${r.errors.length} error(s)` : `config ok: ${r.count} controls`);
  process.exit(r.errors.length ? 1 : 0);
}

const target = new URL(opt("--target", "http://localhost:3000"));
const secure = target.protocol === "https:";
const targetPort = Number(target.port) || (secure ? 443 : 80);
const client = secure ? https : http;
const agent = new client.Agent({ keepAlive: true });
const firstPort = Number(opt("--port", "3999"));

const first = check();
report(first);
if (first.errors.length && !first.count) {
  console.log("Write the config first (see references/config.md), then start the preview.");
  process.exit(1);
}

// Make the dev server believe the request came to its own address (Next.js blocks cross-origin dev requests).
const toTarget = (value) => {
  try { const u = new URL(value); return target.origin + u.pathname + u.search + u.hash; } catch { return value; }
};
const upstreamHeaders = (req) => {
  const h = { ...req.headers, host: target.host };
  delete h["accept-encoding"]; // plain bodies, so the tag can be added to HTML
  if (h.origin && h.origin !== "null") h.origin = target.origin;
  if (h.referer) h.referer = toTarget(h.referer);
  return h;
};

function serveOwn(req, res) {
  const name = req.url.slice(PREFIX.length).split("?")[0];
  const send = (status, type, data) => { res.writeHead(status, { "content-type": type, "cache-control": "no-store" }); res.end(data); };
  if (name === "ui-tweaks.js") return send(200, "text/javascript; charset=utf-8", fs.readFileSync(panelFile));
  if (name === "config.json") {
    try { return send(200, "application/json; charset=utf-8", fs.readFileSync(configFile)); }
    catch { return send(404, "application/json", JSON.stringify({ error: `no config at ${configFile}` })); }
  }
  send(404, "text/plain", "not found");
}

function unreachable(res, err) {
  if (res.headersSent) return res.destroy();
  res.writeHead(502, { "content-type": "text/html; charset=utf-8" });
  res.end(`<!doctype html><meta charset="utf-8"><title>Dev server not answering</title>
<body style="font:14px/1.5 -apple-system,system-ui,sans-serif;max-width:34em;margin:18vh auto;padding:0 24px;color:#333">
<h1 style="font-size:17px">Nothing is answering at ${target.origin}</h1>
<p>The ui-tweaks preview forwards to your dev server. Start it (or ask your agent to), then reload this page.</p>
<p style="color:#888">${String(err && err.code || err)}</p></body>`);
}

// Streams the page through, adding the tag before </head> (or at the end when there is no head).
function injectInto(upRes, res) {
  let pending = Buffer.alloc(0), done = false;
  upRes.on("data", (chunk) => {
    if (done) return res.write(chunk);
    pending = Buffer.concat([pending, chunk]);
    const at = pending.toString("latin1").search(/<\/head\s*>/i);
    if (at >= 0) {
      res.write(Buffer.concat([pending.subarray(0, at), TAG, pending.subarray(at)]));
      done = true;
      pending = null;
    } else if (pending.length > 512 * 1024) {
      res.write(pending.subarray(0, pending.length - 16));
      pending = pending.subarray(pending.length - 16);
    }
  });
  upRes.on("end", () => { res.end(done ? undefined : Buffer.concat([pending, TAG])); });
  upRes.on("error", () => res.destroy());
}

function proxy(req, res, ownOrigin) {
  const up = client.request(
    { host: target.hostname, port: targetPort, method: req.method, path: req.url, headers: upstreamHeaders(req), agent, rejectUnauthorized: false },
    (upRes) => {
      const h = { ...upRes.headers };
      if (h.location) h.location = h.location.replace(target.origin, ownOrigin);
      const html = /text\/html/i.test(h["content-type"] || "") && req.method !== "HEAD" && ![204, 304].includes(upRes.statusCode);
      const encoded = h["content-encoding"] && h["content-encoding"] !== "identity";
      if (!html || encoded) { res.writeHead(upRes.statusCode, h); return upRes.pipe(res); }
      delete h["content-length"];
      delete h["content-security-policy"];
      delete h["content-security-policy-report-only"];
      res.writeHead(upRes.statusCode, h);
      injectInto(upRes, res);
    }
  );
  up.on("error", (err) => unreachable(res, err));
  res.on("close", () => { if (!res.writableFinished) up.destroy(); });
  req.pipe(up);
}

const server = http.createServer((req, res) => {
  if (req.url.startsWith(PREFIX)) return serveOwn(req, res);
  proxy(req, res, `http://${req.headers.host}`);
});

// Hot reload: tunnel websocket upgrades byte for byte after rewriting the handshake headers.
server.on("upgrade", (req, socket, head) => {
  const connect = secure
    ? (cb) => tls.connect({ host: target.hostname, port: targetPort, servername: target.hostname, rejectUnauthorized: false }, cb)
    : (cb) => net.connect(targetPort, target.hostname, cb);
  const up = connect(() => {
    let raw = `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`;
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      const name = req.rawHeaders[i], lower = name.toLowerCase();
      let value = req.rawHeaders[i + 1];
      if (lower === "host") value = target.host;
      else if (lower === "origin" && value !== "null") value = target.origin;
      else if (lower === "referer") value = toTarget(value);
      raw += `${name}: ${value}\r\n`;
    }
    up.write(raw + "\r\n");
    if (head && head.length) up.write(head);
    up.pipe(socket);
    socket.pipe(up);
  });
  up.on("error", () => socket.destroy());
  socket.on("error", () => up.destroy());
});

// Report config changes as the agent edits it; the panel picks them up on its own.
fs.watchFile(configFile, { interval: 1000 }, (now, before) => {
  if (now.mtimeMs === before.mtimeMs) return;
  const r = check();
  console.log(r.errors.length ? "config updated, with errors:" : `config updated: ${r.count} controls`);
  report(r);
});

// Busy port: try the next one, up to 20 times. Report the address once, when it is really listening.
let port = firstPort, tries = 20;
server.on("error", (err) => {
  if (err.code === "EADDRINUSE" && tries-- > 0 && port !== 0) return server.listen(++port);
  console.error(`ui-tweaks preview: ${err.message}`);
  process.exit(1);
});
server.once("listening", () => {
  console.log(`ui-tweaks preview: http://localhost:${server.address().port}  (your app at ${target.origin}, plus the Tweaks panel)`);
  console.log(`config: ${configFile}`);
});
server.listen(port);
