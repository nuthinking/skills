#!/usr/bin/env node
// design-catalog: snapshot pages of a running app with Playwright or Puppeteer, if either is installed.
//
//   node snapshot.mjs --base http://localhost:3000 --paths / /tasks /settings [options]
//
// Options
//   --paths-file <file>     one path per line (lines starting with # ignored); may be combined with --paths
//   --out <dir>             default .design-catalog/snapshots
//   --viewport WxH          repeatable; default 1280x800
//   --scheme light|dark     repeatable; emulates prefers-color-scheme; default: the app's own
//   --dark-class <name>     also set this class on <html> when --scheme dark (e.g. "dark")
//   --storage-state <file>  Playwright storage state (cookies/localStorage) for a logged-in session
//   --cookie name=value     repeatable; set on the base URL's domain
//   --screenshot            also save a full-page PNG next to each snapshot
//   --wait <ms>             extra settle time after load (default 600)
//   --headed                show the browser
//
// Resolution order: playwright, playwright-core, puppeteer, puppeteer-core, from the current project
// first, then globally. When none is available it exits 2 with instructions for the receiver flow.
// Standard library plus whichever browser driver the project already has; nothing is installed.

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const flags = {};
const lists = { "--paths": [], "--viewport": [], "--scheme": [], "--cookie": [] };
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a in lists) { while (args[i + 1] && !args[i + 1].startsWith("--")) lists[a].push(args[++i]); continue; }
  if (a.startsWith("--")) { const next = args[i + 1]; if (next && !next.startsWith("--")) { flags[a] = next; i++; } else flags[a] = true; }
}
const base = (flags["--base"] || "").replace(/\/$/, "");
if (!base) { console.error("--base <url> is required"); process.exit(1); }
let paths = lists["--paths"];
if (flags["--paths-file"]) paths = paths.concat(fs.readFileSync(flags["--paths-file"], "utf8").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#")));
if (!paths.length) paths = ["/"];
const viewports = (lists["--viewport"].length ? lists["--viewport"] : ["1280x800"]).map((v) => { const [w, h] = v.split("x").map(Number); return { width: w, height: h }; });
const schemes = lists["--scheme"].length ? lists["--scheme"] : [null];
const out = path.resolve(flags["--out"] || ".design-catalog/snapshots");
const wait = Number(flags["--wait"] || 600);
fs.mkdirSync(out, { recursive: true });
const collector = fs.readFileSync(path.join(here, "collect-styles.js"), "utf8");

const tryRequire = (name) => {
  for (const from of [path.join(process.cwd(), "package.json"), import.meta.url]) {
    try { return createRequire(from)(name); } catch (e) { /* next */ }
  }
  try { return createRequire(path.join(process.env.HOME || "/", "package.json"))(name); } catch (e) { return null; }
};

const fileNameFor = (p, vp, scheme) => {
  let name = p.replace(/^\/+|\/+$/g, "").replace(/[^\w-]+/g, "-") || "home";
  name += "__" + vp.width;
  if (scheme === "dark") name += "__dark";
  return name;
};

const pw = tryRequire("playwright") || tryRequire("playwright-core");
const pp = pw ? null : tryRequire("puppeteer") || tryRequire("puppeteer-core");

if (!pw && !pp) {
  console.error(`No browser driver found (playwright, playwright-core, puppeteer or puppeteer-core) in this project or globally.
Nothing was installed. Use the receiver flow instead:
  1. node ${path.relative(process.cwd(), path.join(here, "receive.mjs"))} --out ${path.relative(process.cwd(), out)}
  2. Open each page in your browser tool at the viewport you want, then evaluate the contents of
     ${path.relative(process.cwd(), path.join(here, "collect-styles.js"))} in the page. Each evaluation saves one file.
  3. Stop the receiver with Ctrl-C.`);
  process.exit(2);
}

const run = async () => {
  const results = [];
  if (pw) {
    const browser = await pw.chromium.launch({ headless: !flags["--headed"] });
    for (const scheme of schemes) {
      for (const vp of viewports) {
        const ctx = await browser.newContext({
          viewport: vp,
          colorScheme: scheme || undefined,
          storageState: flags["--storage-state"] || undefined,
          deviceScaleFactor: 1,
        });
        if (lists["--cookie"].length) {
          const u = new URL(base);
          await ctx.addCookies(lists["--cookie"].map((c) => { const [name, ...rest] = c.split("="); return { name, value: rest.join("="), domain: u.hostname, path: "/" }; }));
        }
        const page = await ctx.newPage();
        for (const p of paths) {
          const name = fileNameFor(p, vp, scheme);
          try {
            await page.goto(base + p, { waitUntil: "networkidle", timeout: 45000 });
            if (scheme === "dark" && flags["--dark-class"]) await page.evaluate((c) => document.documentElement.classList.add(c), flags["--dark-class"]);
            await page.waitForTimeout(wait);
            await page.evaluate(() => { window.__dc = { endpoint: null }; });
            const json = await page.evaluate(collector);
            const snap = JSON.parse(json);
            snap.label = name;
            fs.writeFileSync(path.join(out, name + ".json"), JSON.stringify(snap));
            if (flags["--screenshot"]) await page.screenshot({ path: path.join(out, name + ".png"), fullPage: true });
            results.push({ name, elements: snap.elements.length, ok: true });
            console.log(`${name}: ${snap.elements.length} elements`);
          } catch (e) {
            results.push({ name, ok: false, error: e.message });
            console.error(`${name}: FAILED ${e.message.split("\n")[0]}`);
          }
        }
        await ctx.close();
      }
    }
    await browser.close();
  } else {
    const browser = await pp.launch({ headless: !flags["--headed"] });
    const page = await browser.newPage();
    if (lists["--cookie"].length) {
      const u = new URL(base);
      await page.setCookie(...lists["--cookie"].map((c) => { const [name, ...rest] = c.split("="); return { name, value: rest.join("="), domain: u.hostname, path: "/" }; }));
    }
    for (const scheme of schemes) {
      if (scheme) await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
      for (const vp of viewports) {
        await page.setViewport({ ...vp, deviceScaleFactor: 1 });
        for (const p of paths) {
          const name = fileNameFor(p, vp, scheme);
          try {
            await page.goto(base + p, { waitUntil: "networkidle0", timeout: 45000 });
            if (scheme === "dark" && flags["--dark-class"]) await page.evaluate((c) => document.documentElement.classList.add(c), flags["--dark-class"]);
            await new Promise((r) => setTimeout(r, wait));
            await page.evaluate(() => { window.__dc = { endpoint: null }; });
            const json = await page.evaluate(collector);
            const snap = JSON.parse(json);
            snap.label = name;
            fs.writeFileSync(path.join(out, name + ".json"), JSON.stringify(snap));
            if (flags["--screenshot"]) await page.screenshot({ path: path.join(out, name + ".png"), fullPage: true });
            results.push({ name, elements: snap.elements.length, ok: true });
            console.log(`${name}: ${snap.elements.length} elements`);
          } catch (e) {
            results.push({ name, ok: false, error: e.message });
            console.error(`${name}: FAILED ${e.message.split("\n")[0]}`);
          }
        }
      }
    }
    await browser.close();
  }
  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} snapshots written to ${path.relative(process.cwd(), out)}${failed.length ? `; ${failed.length} failed` : ""}`);
  process.exit(failed.length ? 1 : 0);
};

run().catch((e) => { console.error(e); process.exit(1); });
