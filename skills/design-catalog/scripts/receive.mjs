#!/usr/bin/env node
// design-catalog: tiny local receiver for snapshots posted by collect-styles.js.
//
//   node receive.mjs [--out .design-catalog/snapshots] [--port 4848]
//
// Writes one JSON file per snapshot, named <label>.json or <path>__<width>[__dark].json
// (the root path becomes "home"). Prints each file as it arrives. GET /collect.js serves the
// collector so a browser tool can fetch and evaluate it. Stop with Ctrl-C.
//
// Standard library only.

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf(name); return i >= 0 && args[i + 1] ? args[i + 1] : def; };
const out = path.resolve(opt("--out", ".design-catalog/snapshots"));
const port = Number(opt("--port", "4848"));
const here = path.dirname(fileURLToPath(import.meta.url));

fs.mkdirSync(out, { recursive: true });

const fileNameFor = (snap) => {
  if (snap.label) return snap.label.replace(/[^\w.-]+/g, "-") + ".json";
  let p = (snap.path || "/").replace(/^\/+|\/+$/g, "").replace(/[^\w-]+/g, "-") || "home";
  p += "__" + (snap.viewport ? snap.viewport.width : "w");
  if (snap.colorScheme === "dark") p += "__dark";
  if (snap.filter) p += "__filtered";
  return p + ".json";
};

const server = http.createServer((req, res) => {
  const cors = { "access-control-allow-origin": "*", "access-control-allow-headers": "content-type", "access-control-allow-methods": "POST, GET, OPTIONS" };
  if (req.method === "OPTIONS") { res.writeHead(204, cors); return res.end(); }
  if (req.method === "GET" && req.url.startsWith("/collect.js")) {
    res.writeHead(200, { ...cors, "content-type": "application/javascript" });
    return res.end(fs.readFileSync(path.join(here, "collect-styles.js")));
  }
  if (req.method === "GET") {
    res.writeHead(200, { ...cors, "content-type": "text/plain" });
    return res.end(`design-catalog receiver. Writing to ${out}\nFiles: ${fs.readdirSync(out).join(", ") || "(none yet)"}\n`);
  }
  if (req.method === "POST" && req.url.startsWith("/snapshot")) {
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      try {
        const snap = JSON.parse(body);
        const file = path.join(out, fileNameFor(snap));
        fs.writeFileSync(file, body);
        const msg = `saved ${snap.elements ? snap.elements.length : 0} elements to ${path.relative(process.cwd(), file)}`;
        console.log(new Date().toISOString().slice(11, 19), msg);
        res.writeHead(200, { ...cors, "content-type": "text/plain" });
        res.end(msg);
      } catch (e) {
        res.writeHead(400, { ...cors, "content-type": "text/plain" });
        res.end("invalid snapshot: " + e.message);
      }
    });
    return;
  }
  res.writeHead(404, cors);
  res.end();
});

server.on("error", (e) => {
  if (e.code === "EADDRINUSE") { console.error(`port ${port} is busy; pass --port <n> and set window.__dc = { endpoint: "http://127.0.0.1:<n>" } before collecting`); process.exit(1); }
  throw e;
});
server.listen(port, "127.0.0.1", () => {
  console.log(`design-catalog receiver on http://127.0.0.1:${port}  ->  ${out}`);
  console.log(`In the page: evaluate scripts/collect-styles.js (or fetch http://127.0.0.1:${port}/collect.js). Ctrl-C to stop.`);
});
