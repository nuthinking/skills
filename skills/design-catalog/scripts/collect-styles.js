// design-catalog: collect computed styles and layout of every visible element on the current page.
//
// Evaluate this whole file in the page (browser devtools tool, Playwright page.evaluate, or the
// snapshot.mjs runner). It is an async expression that resolves to:
//   - a short string "saved <n> elements to <file>" when a design-catalog receiver is listening on
//     http://127.0.0.1:4848 (start one with: node receive.mjs), or
//   - the full snapshot JSON string when no receiver answers.
//
// Options can be set before evaluating, e.g. window.__dc = { filter: "main", endpoint: "http://127.0.0.1:4848", label: "tasks-hover" }.
//   filter   CSS selector; only matching elements and their descendants are collected (use after hovering/focusing one).
//   label    overrides the file name the receiver writes (default: derived from the path and viewport).
//   endpoint receiver base URL (default http://127.0.0.1:4848). Set to null to always return JSON.
//
// Snapshot schema (version 1):
// { version, url, path, title, viewport:{width,height}, dpr, colorScheme, label, collectedAt,
//   rootVars:{ "--name": "value" }, fonts:[family...], styles:[{prop:value...}], elements:[{...}] }
// element: { i, p (parent index or -1), t (tag), sel (selector path), r:[x,y,w,h], txt (own text, trimmed, max 60),
//            role, dc (data-component), rc:[react component chain, nearest first], cls (class attribute, max 300), s (index into styles) }

(async () => {
  const opts = Object.assign({ filter: null, label: null, endpoint: "http://127.0.0.1:4848" }, window.__dc || {});
  const PROPS = [
    "color", "background-color", "background-image",
    "border-top-width", "border-right-width", "border-bottom-width", "border-left-width",
    "border-top-color", "border-right-color", "border-bottom-color", "border-left-color",
    "border-top-style", "border-bottom-style",
    "border-top-left-radius", "border-top-right-radius", "border-bottom-right-radius", "border-bottom-left-radius",
    "box-shadow", "outline-width", "outline-color", "outline-style", "outline-offset",
    "font-family", "font-size", "font-weight", "line-height", "letter-spacing", "text-transform", "text-decoration-line", "text-align",
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "row-gap", "column-gap", "display", "flex-direction", "align-items", "justify-content",
    "opacity", "cursor", "transition-property", "transition-duration", "transition-timing-function",
    "min-height", "max-width",
  ];
  const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "LINK", "META", "HEAD", "TITLE", "NOSCRIPT", "TEMPLATE", "BR", "WBR", "PATH", "G", "DEFS", "CLIPPATH", "LINEARGRADIENT", "STOP", "USE", "SYMBOL", "RECT", "CIRCLE", "LINE", "POLYLINE", "POLYGON", "ELLIPSE"]);
  const FRAMEWORK_NAMES = /Boundary|Router|Template|HotReload|Root$|Segment|Handler|Context|Provider|Suspense|Fragment|Layout$|^Head$|^Body$|^Html$|Wrapper$|Insertion|^Dev|Portal|Presence|Slot$|Primitive|^Styled|^Anonymous$|^LinkComponent$|^Link$|^NextLink$|^Image$|^ReactDevOverlay|^AppDevOverlay|^Hydrat|^Lazy|^Memo|^ForwardRef/;

  const round = (n) => Math.round(n * 10) / 10;

  // --- CSS custom properties declared on :root / html across accessible stylesheets, plus computed values
  const rootVars = {};
  const rootStyle = getComputedStyle(document.documentElement);
  for (const sheet of Array.from(document.styleSheets)) {
    let rules;
    try { rules = sheet.cssRules; } catch (e) { continue; } // cross-origin
    const walk = (list) => {
      for (const rule of Array.from(list)) {
        if (rule.cssRules && rule.cssRules.length && !(rule.selectorText)) { walk(rule.cssRules); continue; }
        if (!rule.selectorText || !rule.style) continue;
        if (!/^(:root|html)(\s*,\s*(:root|html))?(\.[\w-]+)?$/.test(rule.selectorText.trim()) && !/^(:root|html)/.test(rule.selectorText.trim())) continue;
        for (let i = 0; i < rule.style.length; i++) {
          const name = rule.style[i];
          if (name.startsWith("--")) {
            const computed = rootStyle.getPropertyValue(name).trim();
            rootVars[name] = computed || rule.style.getPropertyValue(name).trim();
          }
        }
      }
    };
    walk(rules);
  }

  // --- fonts actually loaded
  const fonts = [];
  try {
    document.fonts.forEach((f) => { if (f.status === "loaded" && !fonts.includes(f.family)) fonts.push(f.family.replace(/^"|"$/g, "")); });
  } catch (e) {}

  // --- react component chain (dev builds only; production names are minified)
  const reactChain = (el) => {
    const key = Object.keys(el).find((k) => k.startsWith("__reactFiber$"));
    if (!key) return null;
    const out = [];
    let fiber = el[key];
    let hops = 0;
    while (fiber && out.length < 4 && hops < 60) {
      const t = fiber.type;
      let name = null;
      if (typeof t === "function") name = t.displayName || t.name;
      else if (t && typeof t === "object") name = t.displayName || (t.render && (t.render.displayName || t.render.name)) || (t.type && (t.type.displayName || t.type.name));
      if (name && /^[A-Z]/.test(name) && !FRAMEWORK_NAMES.test(name) && !out.includes(name)) out.push(name);
      fiber = fiber.return;
      hops++;
    }
    return out.length ? out : null;
  };

  const selectorPath = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id && /^[A-Za-z][\w-]*$/.test(node.id)) { parts.unshift(part + "#" + node.id); break; }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = parent;
      if (node === document.body) { parts.unshift("body"); break; }
    }
    return parts.join(" > ");
  };

  const ownText = (el) => {
    let t = "";
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.textContent;
    t = t.replace(/\s+/g, " ").trim();
    if (!t && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) t = el.placeholder || el.value || "";
    if (!t && el.tagName === "IMG") t = el.alt || "";
    return t.slice(0, 60);
  };

  // --- settle animations so measurements are stable
  try { document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} }); } catch (e) {}

  const root = opts.filter ? document.querySelector(opts.filter) : document.body;
  if (!root) return JSON.stringify({ error: `filter "${opts.filter}" matched nothing` });

  const styleIndex = new Map();
  const styles = [];
  const elements = [];
  const indexOf = new Map();
  const all = [root, ...root.querySelectorAll("*")];
  for (const el of all) {
    if (SKIP_TAGS.has(el.tagName.toUpperCase()) || el.closest("[data-site-edit]")) continue;
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") continue;
    if (rect.width === 0 && rect.height === 0) continue;
    const s = {};
    for (const p of PROPS) {
      const v = cs.getPropertyValue(p);
      if (v && v !== "none" && v !== "normal" && v !== "auto" && v !== "0px" && v !== "rgba(0, 0, 0, 0)" && v !== "0s" && !(p === "opacity" && v === "1") && !(p === "text-align" && v === "start")) s[p] = v;
      else if (p === "color" || p === "font-size" || p === "font-family" || p === "font-weight" || p === "display") s[p] = v;
    }
    if (!s["transition-duration"]) { delete s["transition-property"]; delete s["transition-timing-function"]; }
    if (cs.getPropertyValue("outline-style") === "none" || cs.getPropertyValue("outline-width") === "0px") { delete s["outline-width"]; delete s["outline-color"]; delete s["outline-offset"]; }
    // uniform borders collapse to a single key so analysis is simpler
    if (s["border-top-width"] && s["border-top-width"] === s["border-right-width"] && s["border-top-width"] === s["border-bottom-width"] && s["border-top-width"] === s["border-left-width"]) {
      s["border-width"] = s["border-top-width"];
      delete s["border-top-width"]; delete s["border-right-width"]; delete s["border-bottom-width"]; delete s["border-left-width"];
    }
    if (s["border-top-color"] && s["border-top-color"] === s["border-right-color"] && s["border-top-color"] === s["border-bottom-color"] && s["border-top-color"] === s["border-left-color"]) {
      s["border-color"] = s["border-top-color"];
      delete s["border-top-color"]; delete s["border-right-color"]; delete s["border-bottom-color"]; delete s["border-left-color"];
    }
    if (!s["border-width"] && !s["border-top-width"] && !s["border-bottom-width"] && !s["border-left-width"] && !s["border-right-width"]) {
      delete s["border-color"]; delete s["border-top-color"]; delete s["border-right-color"]; delete s["border-bottom-color"]; delete s["border-left-color"]; delete s["border-top-style"]; delete s["border-bottom-style"];
    }
    const corners = ["border-top-left-radius", "border-top-right-radius", "border-bottom-right-radius", "border-bottom-left-radius"].map((k) => s[k] || "0px");
    if (corners.every((c) => c === corners[0])) { if (corners[0] !== "0px") s["border-radius"] = corners[0]; }
    else s["border-radius"] = corners.join(" ");
    for (const k of ["border-top-left-radius", "border-top-right-radius", "border-bottom-right-radius", "border-bottom-left-radius"]) delete s[k];

    const key = JSON.stringify(s);
    let si = styleIndex.get(key);
    if (si === undefined) { si = styles.length; styles.push(s); styleIndex.set(key, si); }

    const parent = el.parentElement;
    const entry = {
      i: elements.length,
      p: parent && indexOf.has(parent) ? indexOf.get(parent) : -1,
      t: el.tagName.toLowerCase(),
      sel: selectorPath(el),
      r: [round(rect.x + window.scrollX), round(rect.y + window.scrollY), round(rect.width), round(rect.height)],
      txt: ownText(el),
      s: si,
    };
    const role = el.getAttribute("role"); if (role) entry.role = role;
    const dc = el.getAttribute("data-component"); if (dc) entry.dc = dc;
    const rc = reactChain(el); if (rc) entry.rc = rc;
    const cls = typeof el.className === "string" ? el.className : (el.getAttribute("class") || "");
    if (cls) entry.cls = cls.replace(/\s+/g, " ").trim().slice(0, 300);
    if (el.tagName === "INPUT") entry.type = el.type;
    if (el.disabled) entry.disabled = true;
    if (el === document.activeElement && el !== document.body) entry.focused = true;
    indexOf.set(el, entry.i);
    elements.push(entry);
  }

  const path = location.pathname;
  const snapshot = {
    version: 1,
    url: location.href,
    path,
    title: document.title,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    dpr: window.devicePixelRatio,
    colorScheme: (() => {
      // judged from what is rendered: a dark page background means dark
      const bg = (el) => { const v = getComputedStyle(el).backgroundColor; const m = v && v.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); return m && (m[4] === undefined || Number(m[4]) > 0.5) ? (0.2126 * m[1] + 0.7152 * m[2] + 0.0722 * m[3]) / 255 : null; };
      const lum = bg(document.body) ?? bg(document.documentElement);
      if (lum !== null) return lum < 0.5 ? "dark" : "light";
      return document.documentElement.classList.contains("dark") || document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    })(),
    prefersDark: matchMedia("(prefers-color-scheme: dark)").matches,
    label: opts.label || null,
    filter: opts.filter || null,
    collectedAt: new Date().toISOString(),
    rootVars,
    fonts,
    styles,
    elements,
  };
  const json = JSON.stringify(snapshot);

  if (opts.endpoint) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 2500);
      const res = await fetch(opts.endpoint.replace(/\/$/, "") + "/snapshot", { method: "POST", body: json, headers: { "content-type": "application/json" }, signal: ctrl.signal, mode: "cors" });
      clearTimeout(timer);
      if (res.ok) return await res.text();
    } catch (e) { /* no receiver: fall through and return the JSON */ }
  }
  return json;
})()
