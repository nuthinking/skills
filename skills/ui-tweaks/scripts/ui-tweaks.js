/*! ui-tweaks panel · https://github.com/nuthinking/skills · MIT */
// ui-tweaks: the Tweaks panel. One file, no dependencies, its CSS inside a shadow root.
//
// preview.mjs adds it to every page of the app (or a dev-only <script> tag does, in fallback mode).
// It reads the list of controls from config.json next to this file (or the tag's data-config),
// shows them in a draggable panel, applies changed values as one stylesheet of !important
// overrides, and copies the changes as a message for the agent. The app's code is never touched.
//
// In Node (tests, preview.mjs --check) only the pure helpers run; they are exported on `module`.

(function () {
  "use strict";

  // ---------------------------------------------------------------------------------------------
  // Pure helpers: config, CSS, copy text
  // ---------------------------------------------------------------------------------------------

  const TYPES = ["number", "shade", "choice", "color", "scale"];

  const parseLength = (s) => {
    const m = /^\s*(-?\d*\.?\d+)\s*([a-z%]*)\s*$/i.exec(String(s));
    return m ? { n: parseFloat(m[1]), unit: m[2] } : null;
  };
  const decimalsOf = (step) => { const s = String(step); const i = s.indexOf("."); return i < 0 ? 0 : s.length - i - 1; };
  const roundTo = (n, d) => { const f = Math.pow(10, d); return Math.round(n * f) / f; };
  const num = (n, d) => { const r = roundTo(n, d); return String(Object.is(r, -0) ? 0 : r); };
  const slug = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const plural = (n) => n + (n === 1 ? " change" : " changes");
  const cssEscape = (s) =>
    typeof CSS !== "undefined" && CSS.escape
      ? CSS.escape(s)
      : String(s).replace(/^(\d)/, "\\3$1 ").replace(/[^a-zA-Z0-9_ -￿-]/g, "\\$&");

  // 0.5rem × 1.5 → 0.75rem. Lengths that are not plain numbers fall back to calc().
  const scaleLength = (base, k) => {
    const p = parseLength(base);
    if (!p) return "calc(" + base + " * " + num(k, 4) + ")";
    return num(p.n * k, p.unit === "px" ? 1 : p.unit === "" ? 3 : 4) + p.unit;
  };

  // OKLCH, so "a touch darker" keeps the hue. Hex in, hex out; out-of-gamut chroma is reduced.
  const normHex = (s) => {
    const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(s || "").trim());
    if (!m) return null;
    const x = m[1].toLowerCase();
    return "#" + (x.length === 3 ? x.replace(/./g, "$&$&") : x);
  };
  const toLin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  const fromLin = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
  function hexToOklch(hex) {
    const n = parseInt(hex.slice(1), 16);
    const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => toLin(v / 255));
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    const L = 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s;
    const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
    const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
    return [L, Math.hypot(A, B), Math.atan2(B, A)];
  }
  function oklchToRgb(L, C, h) {
    const A = C * Math.cos(h), B = C * Math.sin(h);
    const l = Math.pow(L + 0.3963377774 * A + 0.2158037573 * B, 3);
    const m = Math.pow(L - 0.1055613458 * A - 0.0638541728 * B, 3);
    const s = Math.pow(L - 0.0894841775 * A - 1.291485548 * B, 3);
    return [
      4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
    ].map(fromLin);
  }
  function shadeHex(baseHex, d) {
    const [L, C, h] = hexToOklch(baseHex);
    const L2 = Math.min(1, Math.max(0, L - d));
    let c = C, rgb = oklchToRgb(L2, c, h);
    while (c > 0 && rgb.some((v) => v < -1e-4 || v > 1 + 1e-4)) { c = Math.max(0, c - 0.002); rgb = oklchToRgb(L2, c, h); }
    return "#" + rgb.map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255).toString(16).padStart(2, "0")).join("");
  }

  // A shade control is a lightness offset from the code's colour (positive = darker). The app's
  // neighbouring shades become marks on the slider; landing on one gives exactly that colour.
  function shadeSetup(c, toHexFn) {
    const base = toHexFn(c.value);
    if (!base) return false;
    const L = hexToOklch(base)[0];
    c.baseHex = base;
    c.marks = [{ d: 0, hex: base, code: null }];
    c.steps.forEach((st) => {
      const hex = toHexFn(st.value);
      if (!hex) return;
      if (hex === base) { c.marks[0].code = st.code; return; }
      c.marks.push({ d: roundTo(L - hexToOklch(hex)[0], 4), hex, code: st.code });
    });
    c.marks.sort((a, b) => a.d - b.d);
    const reach = Math.max(0, ...c.marks.map((mk) => Math.abs(mk.d)));
    c.range = c.rangeSet || Math.min(0.4, Math.max(0.08, roundTo(reach + 0.02, 2)));
    c.min = -c.range;
    c.max = c.range;
    return true;
  }
  const markAt = (c, d) => (c.marks || []).find((mk) => Math.abs(mk.d - d) < 1e-6) || null;
  const shadeColor = (c, d) => { const mk = markAt(c, d); return mk ? mk.hex : shadeHex(c.baseHex, d); };
  const shadeShown = (c, d) => { const mk = markAt(c, d); return shadeColor(c, d) + (mk && mk.code ? " (" + mk.code + ")" : ""); };

  // Craft-sized defaults: about ±50% around the code's value, in steps a designer would take.
  const STEP_FOR_UNIT = { px: 1, em: 0.005, rem: 0.0625, "%": 1, ms: 10, s: 0.01, deg: 1, "": 0.01 };

  const selectorFor = (t) => t.selector || (t.class ? "." + cssEscape(t.class) : ":root");
  const targetName = (t) =>
    t.var ? (t.selector || t.class ? selectorFor(t) + " " : "") + t.var : (t.class ? "." + t.class : t.selector) + " " + t.property;

  function normTarget(t, type, where) {
    if (!t || typeof t !== "object") return { error: where + ": each target must be an object" };
    if (!t.var && !t.property) return { error: where + ': each target needs "var" (a CSS variable) or "property" (with "selector" or "class")' };
    if (t.var && !/^--/.test(t.var)) return { error: where + ': "var" must start with -- (got ' + t.var + ")" };
    if (t.property && !t.var && !t.selector && !t.class) return { error: where + ': a "property" target needs a "selector" or a "class"' };
    if (type === "scale" && t.base == null) return { error: where + ': scale targets need a "base" (the current value, e.g. "0.5rem")' };
    return {
      target: {
        var: t.var || null,
        property: t.var ? null : t.property,
        selector: t.selector ? String(t.selector) : null,
        class: t.class ? String(t.class) : null,
        media: t.media ? String(t.media) : null,
        base: t.base != null ? String(t.base) : null,
      },
    };
  }

  function normControl(c, where, ids, warnings) {
    if (!c || typeof c !== "object") return { error: where + ": not an object" };
    if (TYPES.indexOf(c.type) < 0) return { error: where + ': "type" must be one of ' + TYPES.join(", ") };
    const id = c.id ? String(c.id) : slug(c.label);
    if (!id) return { error: where + ': needs an "id" or a "label"' };
    if (ids[id]) return { error: where + ': duplicate id "' + id + '"' };
    const raw = Array.isArray(c.targets) ? c.targets : c.target ? [c.target] : [];
    if (!raw.length) return { error: where + ': needs "targets"' };
    const source = Array.isArray(c.source) ? c.source.map(String).join(", ") : c.source ? String(c.source) : "";
    const out = { id, label: String(c.label || id), type: c.type, source, targets: [] };
    for (const t of raw) {
      const r = normTarget(t, c.type, where);
      if (r.error) return r;
      out.targets.push(r.target);
    }
    if (c.type === "scale") {
      out.targets.forEach((t) => {
        if (!parseLength(t.base)) warnings.push(where + ': base "' + t.base + '" is not a plain length; it will be scaled with calc()');
      });
    }
    out.hint = c.hint != null ? String(c.hint) : targetName(out.targets[0]) + (out.targets.length > 1 ? " +" + (out.targets.length - 1) : "");
    const budget = c.type === "shade" || c.type === "color" ? 22 : 28;
    if (c.hint != null && out.hint.length > budget) warnings.push(where + ': hint is ' + out.hint.length + " characters; it is cut after about " + budget);

    if (c.type === "color") {
      if (typeof c.value !== "string" || !c.value.trim()) return { error: where + ': colour "value" must be a CSS colour string' };
      out.value = c.value.trim();
      out.swatches = Array.isArray(c.swatches) ? c.swatches.map(String) : null;
    } else if (c.type === "shade") {
      if (typeof c.value !== "string" || !c.value.trim()) return { error: where + ': shade "value" must be a CSS colour string' };
      out.value = c.value.trim();
      out.steps = (Array.isArray(c.steps) ? c.steps : []).map((st) => (st && typeof st === "object" ? { value: String(st.value), code: st.code ? String(st.code) : null } : { value: String(st), code: null }));
      out.rangeSet = Number(c.range) > 0 ? Math.min(0.5, Number(c.range)) : 0;
      out.step = Number(c.step) > 0 ? Number(c.step) : 0.005;
      out.decimals = 4;
      shadeSetup(out, normHex); // again in the browser for colours that aren't hex
    } else if (c.type === "number" || c.type === "scale") {
      let v = c.value, unit = c.unit;
      if (c.type === "scale" && v == null) v = 1;
      if (typeof v === "string") {
        const p = parseLength(v);
        if (!p) return { error: where + ': "value" must be a number' };
        v = p.n;
        if (unit == null) unit = p.unit;
      }
      if (typeof v !== "number" || !isFinite(v)) return { error: where + ': "value" must be a number' };
      const scale = c.type === "scale";
      out.value = v;
      out.unit = scale ? "" : String(unit || "");
      out.step = Number(c.step) > 0 ? Number(c.step) : scale ? 0.01 : STEP_FOR_UNIT[out.unit] || 0.01;
      const span = scale ? 0.5 : Math.max(Math.abs(v) * 0.5, out.step * 10);
      const floor = !scale && v >= 0 && ["px", "rem", "ms", "s", "%", ""].indexOf(out.unit) >= 0 ? 0 : -Infinity;
      out.min = typeof c.min === "number" ? c.min : roundTo(Math.max(floor, v - span), 4);
      out.max = typeof c.max === "number" ? c.max : roundTo(v + span, 4);
      if (out.min >= out.max) return { error: where + ': "min" must be below "max"' };
      if (v < out.min || v > out.max) {
        warnings.push(where + ": value " + v + " is outside min/max; the range was widened");
        out.min = Math.min(out.min, v);
        out.max = Math.max(out.max, v);
      }
      out.decimals = Math.max(decimalsOf(out.step), decimalsOf(v));
      out.snaps = Array.isArray(c.snaps) ? c.snaps.filter((s) => typeof s === "number") : [];
    } else if (c.type === "choice") {
      const opts = Array.isArray(c.options) ? c.options : [];
      if (opts.length < 2) return { error: where + ': a choice needs at least two "options"' };
      out.options = [];
      for (const o of opts) {
        if (!o || o.value == null) return { error: where + ': each option needs a "value" (and a "label")' };
        out.options.push({ label: String(o.label != null ? o.label : o.value), value: String(o.value), code: o.code != null ? String(o.code) : null });
      }
      const seen = {};
      out.options.forEach((o) => {
        if (seen[o.value]) warnings.push(where + ': options "' + seen[o.value] + '" and "' + o.label + '" have the same value; the first one wins');
        seen[o.value] = o.label;
      });
      const match = out.options.find((o) => o.value === String(c.value)) || out.options.find((o) => o.label === String(c.value));
      if (!match) return { error: where + ': "value" must be one of the options\' values' };
      out.value = match.value;
    }
    return { control: out };
  }

  // Validates and fills defaults. Bad controls are dropped with an error; the rest still work.
  function normalizeConfig(raw) {
    const errors = [], warnings = [], groups = [], ids = {};
    let count = 0;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      return { title: "", palette: [], groups, errors: ["config must be a JSON object"], warnings };
    }
    const rawGroups = Array.isArray(raw.groups) ? raw.groups : Array.isArray(raw.controls) ? [{ label: "", controls: raw.controls }] : null;
    if (!rawGroups) errors.push('config needs "groups": [{ "label": "Colour", "controls": [ ... ] }]');
    (rawGroups || []).forEach((g, gi) => {
      const controls = [];
      ((g && g.controls) || []).forEach((c, ci) => {
        const where = ((g && g.label) || "group " + (gi + 1)) + " › " + ((c && (c.label || c.id)) || "control " + (ci + 1));
        const r = normControl(c, where, ids, warnings);
        if (r.error) return errors.push(r.error);
        ids[r.control.id] = true;
        count++;
        controls.push(r.control);
      });
      if (controls.length) groups.push({ label: String((g && g.label) || ""), controls });
    });
    if (!count && !errors.length) errors.push("config has no controls");
    if (count > 12) warnings.push(count + " controls; keep it to 6–8 (12 at most) so the panel stays easy to scan");
    return { title: raw.title ? String(raw.title) : "", palette: Array.isArray(raw.palette) ? raw.palette.map(String) : [], groups, errors, warnings };
  }

  const optionFor = (c, v) => (c.options || []).find((o) => o.value === v) || null;

  function isChanged(c, v) {
    if (v === undefined || v === null) return false;
    if (c.type === "number" || c.type === "scale") return Math.abs(v - c.value) > 1e-9;
    if (c.type === "shade") return Math.abs(v) > 1e-9;
    if (c.type === "color") return String(v).toLowerCase() !== (c.baseHex || String(c.value).toLowerCase());
    return v !== c.value;
  }

  function cssValue(c, v, t) {
    if (c.type === "number") return num(v, c.decimals) + c.unit;
    if (c.type === "scale") return t && t.base != null ? scaleLength(t.base, v) : num(v, 4);
    if (c.type === "shade") return c.baseHex ? shadeColor(c, v) : c.value;
    return String(v);
  }

  // What a person reads: 14px, 150%, "Medium", #4f46e5.
  function shown(c, v) {
    if (c.type === "number") return num(v, c.decimals) + c.unit;
    if (c.type === "scale") return Math.round(v * 100) + "%";
    if (c.type === "choice") { const o = optionFor(c, v); return o ? o.label : String(v); }
    if (c.type === "shade") return c.baseHex ? shadeShown(c, v) : c.value;
    return String(v).toLowerCase();
  }

  // One rule per selector (and media query), only for controls that differ from the code.
  function buildCss(controls, values) {
    const blocks = [], index = {};
    controls.forEach((c) => {
      const v = values[c.id];
      if (!isChanged(c, v)) return;
      c.targets.forEach((t) => {
        const sel = selectorFor(t), key = (t.media || "") + "\u0000" + sel;
        let b = index[key];
        if (!b) { b = index[key] = { media: t.media, sel, decls: [] }; blocks.push(b); }
        b.decls.push((t.var || t.property) + ": " + cssValue(c, v, t) + " !important;");
      });
    });
    return blocks
      .map((b) => { const rule = b.sel + " { " + b.decls.join(" ") + " }"; return b.media ? "@media " + b.media + " { " + rule + " }" : rule; })
      .join("\n");
  }

  // The message the designer pastes back to the agent. Only changed values, old → new, and where they live.
  function formatCopy(controls, values) {
    const rows = [];
    controls.forEach((c) => {
      const v = values[c.id];
      if (!isChanged(c, v)) return;
      const origin = c.type === "shade" ? markAt(c, 0) : null;
      const was = c.type === "color" ? c.value : c.type === "shade" ? c.value + (origin && origin.code ? " (" + origin.code + ")" : "") : shown(c, c.value);
      let change = was + " → " + shown(c, v);
      if (c.type === "choice") {
        // code "" is an option with nothing in the source (no border): the change reads as add or remove
        const a = optionFor(c, c.value), b = optionFor(c, v);
        if (a && b && a.code !== null && b.code !== null) {
          if (a.code && b.code) change += " (" + a.code + " → " + b.code + ")";
          else if (b.code) change += " (add " + b.code + ")";
          else if (a.code) change += " (remove " + a.code + ")";
        }
      }
      const details = c.type === "scale" ? c.targets.map((t) => [targetName(t), t.base + " → " + cssValue(c, v, t)]) : [];
      const where = [c.type !== "scale" ? c.hint : "", c.source].filter(Boolean).join(" · ");
      rows.push({ label: c.label, change, where, details });
    });
    if (!rows.length) return "";
    const w1 = Math.max(...rows.map((r) => r.label.length));
    const w2 = Math.max(...rows.map((r) => r.change.length));
    const w3 = Math.max(0, ...rows.flatMap((r) => r.details.map((d) => d[0].length)));
    const lines = ["Apply these UI tweaks with the ui-tweaks skill (" + plural(rows.length) + "):", ""];
    rows.forEach((r) => {
      lines.push((r.label.padEnd(w1) + "  " + (r.where ? r.change.padEnd(w2) + "  " + r.where : r.change)).trimEnd());
      r.details.forEach((d) => lines.push("  " + d[0].padEnd(w3) + "  " + d[1]));
    });
    return lines.join("\n") + "\n";
  }

  if (typeof module === "object" && module && module.exports) {
    module.exports = { parseLength, scaleLength, normalizeConfig, isChanged, cssValue, shown, buildCss, formatCopy, selectorFor, shadeHex, hexToOklch };
  }
  if (typeof window === "undefined" || typeof document === "undefined" || window.__uiTweaks) return;
  window.__uiTweaks = true; // loaded once per page

  // ---------------------------------------------------------------------------------------------
  // Browser: state
  // ---------------------------------------------------------------------------------------------

  const script = document.currentScript;
  const configUrl =
    (script && script.getAttribute("data-config")) || (script && script.src ? new URL("config.json", script.src).href : "/__ui-tweaks/config.json");
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const SHORTCUT = isMac ? "⌥T" : "Alt+T";

  const store = {
    get(key, def) { try { const s = localStorage.getItem("ui-tweaks:" + key); return s ? JSON.parse(s) : def; } catch (e) { return def; } },
    set(key, v) { try { localStorage.setItem("ui-tweaks:" + key, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };

  // Overrides live in a constructed stylesheet: outside the DOM, so the app's framework cannot remove it.
  const overrides = (() => {
    try {
      const s = new CSSStyleSheet();
      const adopt = () => { if (document.adoptedStyleSheets.indexOf(s) < 0) document.adoptedStyleSheets = document.adoptedStyleSheets.concat([s]); };
      adopt();
      return { set(css) { s.replaceSync(css); adopt(); }, off(b) { s.disabled = b; } };
    } catch (e) {
      const el = document.createElement("style");
      el.setAttribute("data-ui-tweaks", "");
      const put = () => { if (!el.isConnected) (document.head || document.documentElement).appendChild(el); };
      return { set(css) { el.textContent = css; put(); }, off(b) { el.disabled = b; } };
    }
  })();
  overrides.set(store.get("css", "")); // last session's tweaks, before the config arrives: no flash of the original

  let model = null, controls = [], values = {}, rows = {}, lastText = null, failed = false;
  const ui = Object.assign({ side: "right", x: 16, y: 16, collapsed: false }, store.get("ui", {}));

  const sig = (c) => JSON.stringify([c.type, c.value, c.targets.map((t) => t.base), (c.steps || []).map((st) => st.value)]);
  const baseOf = (c) => (c.type === "color" ? c.baseHex : c.type === "shade" ? 0 : c.value);
  const changedCount = () => controls.filter((c) => isChanged(c, values[c.id])).length;

  let probe = null;
  // Any CSS colour → [r, g, b, alpha] through a 1px canvas; null when the browser can't parse it.
  function rgbaOf(str) {
    if (!str) return null;
    try {
      if (!probe) { const cv = document.createElement("canvas"); cv.width = cv.height = 1; probe = cv.getContext("2d", { willReadFrequently: true }); }
      probe.fillStyle = "#010203";
      probe.fillStyle = str;
      if (probe.fillStyle === "#010203" && !/^#010203$/i.test(str)) return null;
      probe.clearRect(0, 0, 1, 1);
      probe.fillRect(0, 0, 1, 1);
      const d = probe.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2], d[3] / 255];
    } catch (e) { return null; }
  }

  function toHex(str) {
    str = String(str || "").trim();
    const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(str);
    if (m) { const x = m[1].toLowerCase(); return "#" + (x.length === 3 ? x.replace(/./g, "$&$&") : x); }
    let resolved = str;
    if (/var\(/.test(str)) {
      const el = document.createElement("i");
      el.style.color = str;
      document.documentElement.appendChild(el);
      resolved = getComputedStyle(el).color;
      el.remove();
    }
    const d = rgbaOf(resolved);
    return d ? "#" + d.slice(0, 3).map((n) => (n < 16 ? "0" : "") + n.toString(16)).join("") : null;
  }

  // ---------------------------------------------------------------------------------------------
  // Browser: DOM
  // ---------------------------------------------------------------------------------------------

  function h(tag, props, kids) {
    const el = document.createElement(tag);
    for (const k in props || {}) {
      const v = props[k];
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "icon") el.innerHTML = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    (kids || []).forEach((kid) => { if (kid != null && kid !== false) el.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid); });
    return el;
  }

  const svg = (body, cls) => '<svg viewBox="0 0 16 16" aria-hidden="true"' + (cls ? ' class="' + cls + '"' : "") + ">" + body + "</svg>";
  const ICON = {
    sliders: svg('<path d="M2.75 4.75h5.5M11.75 4.75h1.5M2.75 11.25h1.5M7.75 11.25h5.5"/><circle cx="10" cy="4.75" r="1.75"/><circle cx="6" cy="11.25" r="1.75"/>'),
    reset: svg('<path d="M3.1 6.4A5 5 0 1 1 3 8.9"/><path d="M2.75 3.25v3.4h3.4"/>'),
    chevron: svg('<path d="M4.75 9.75 8 6.5l3.25 3.25"/>', "chev"),
    compare: svg('<rect x="2.25" y="3.25" width="11.5" height="9.5" rx="2.25"/><path d="M8 3.25h3.5a2.25 2.25 0 0 1 2.25 2.25v5a2.25 2.25 0 0 1-2.25 2.25H8z" class="fill"/><path d="M8 3.25v9.5"/>'),
    copy: svg('<rect x="5.25" y="5.25" width="8.5" height="8.5" rx="2"/><path d="M10.75 5.25V4.5a2 2 0 0 0-2-2h-4.25a2 2 0 0 0-2 2v4.25a2 2 0 0 0 2 2h.75"/>'),
    check: svg('<path d="M3.5 8.5 6.5 11.5 12.5 4.75"/>'),
    updown: svg('<path d="M5.5 6.25 8 3.75l2.5 2.5M5.5 9.75 8 12.25l2.5-2.5"/>'),
  };

  const host = document.createElement("ui-tweaks");
  host.setAttribute("style", "all:initial;position:fixed;top:0;left:0;width:0;height:0;z-index:2147483647;");
  const shadow = host.attachShadow({ mode: "open" });

  const count = h("span", { class: "count", hidden: true });
  const resetAll = h("button", { class: "icon reset-all", title: "Reset all", "aria-label": "Reset all", icon: ICON.reset, disabled: true, onclick: () => resetEverything() });
  const collapseBtn = h("button", { class: "icon collapse", title: "Collapse  (" + SHORTCUT + " hides)", "aria-label": "Collapse", "aria-expanded": "true", icon: ICON.chevron, onclick: () => setCollapsed(!ui.collapsed) });
  const header = h("div", { class: "header" }, [
    h("div", { class: "title" }, [h("span", { class: "glyph", icon: ICON.sliders }), h("span", { text: "Tweaks" }), count]),
    h("span", { class: "spacer" }),
    resetAll,
    collapseBtn,
  ]);
  const body = h("div", { class: "body" });
  const copyLabel = h("span", { class: "copy-label", text: "No changes yet" });
  const copyBtn = h("button", { class: "btn primary copy", disabled: true, onclick: () => copy() }, [h("span", { class: "copy-icon", icon: ICON.copy }), copyLabel]);
  const compareBtn = h("button", { class: "btn secondary compare", title: "Hold to see the original", disabled: true, icon: ICON.compare }, [h("span", { text: "Compare" })]);
  const footer = h("div", { class: "footer" }, [compareBtn, copyBtn]);
  const panel = h("div", { class: "panel enter", role: "region", "aria-label": "Tweaks" }, [
    header,
    h("div", { class: "main" }, [h("div", { class: "main-inner" }, [body, footer])]),
  ]);
  shadow.appendChild(h("style", { text: CSS_TEXT() }));
  shadow.appendChild(panel);
  panel.addEventListener("animationend", () => panel.classList.remove("enter"));

  // ---------------------------------------------------------------------------------------------
  // Rows
  // ---------------------------------------------------------------------------------------------

  function set(c, v) {
    values[c.id] = v;
    if (rows[c.id]) rows[c.id].update();
    schedule();
  }

  function baseRow(c, labelEl, right, below) {
    const dot = h("button", { class: "dot", title: "Reset to " + shown(c, baseOf(c)).replace(/^#[0-9a-f]{6}/i, (s) => s.toUpperCase()), "aria-label": "Reset " + c.label, onclick: () => set(c, baseOf(c)) });
    const warn = h("span", { class: "warn", hidden: true });
    const row = h("div", { class: "row row-" + c.type }, [
      dot,
      h("div", { class: "head" }, [h("div", { class: "labels" }, [labelEl, h("div", { class: "sub" }, [h("span", { class: "hint", text: c.hint, title: c.hint + (c.source ? "\n" + c.source : "") }), warn])]), right]),
      below,
    ]);
    return { row, warn };
  }

  // A slider with tick marks that settles on the app's own values (and on the code's value).
  function slider(c, marks, origin) {
    const frac = (v) => Math.min(1, Math.max(0, (v - c.min) / (c.max - c.min)));
    const at = Array.from(new Set(marks)).filter((s) => s >= c.min && s <= c.max).sort((a, b) => a - b);
    const snap = (v) => { const th = (c.max - c.min) * 0.015; for (const s of at) if (Math.abs(v - s) <= th) return s; return v; };
    const clampStep = (v) => roundTo(Math.min(c.max, Math.max(c.min, Math.round((v - c.min) / c.step) * c.step + c.min)), c.decimals + 1);
    const range = h("input", { type: "range", name: "ui-tweaks-" + c.id + "-slider", min: c.min, max: c.max, step: "any", "aria-label": c.label });
    const ticks = h("div", { class: "ticks", "aria-hidden": "true" }, at.map((s) => h("i", { class: s === origin ? "origin" : null, style: "left:" + frac(s) * 100 + "%" })));
    range.addEventListener("input", () => set(c, snap(clampStep(parseFloat(range.value)))));
    const show = (v) => { range.value = String(v); range.style.setProperty("--f", frac(v)); };
    return { range, ticks, show, clampStep };
  }

  // Drag a label sideways to change its value; Shift for bigger steps.
  function bindScrub(label, c, clampStep) {
    label.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      const start = values[c.id], sx = e.clientX;
      label.setPointerCapture(e.pointerId);
      panel.classList.add("scrubbing");
      const move = (ev) => set(c, clampStep(start + Math.round((ev.clientX - sx) / 3) * c.step * (ev.shiftKey ? 10 : 1)));
      const up = () => { panel.classList.remove("scrubbing"); label.removeEventListener("pointermove", move); label.removeEventListener("pointerup", up); label.removeEventListener("pointercancel", up); };
      label.addEventListener("pointermove", move);
      label.addEventListener("pointerup", up);
      label.addEventListener("pointercancel", up);
    });
  }

  function numberRow(c) {
    const scale = c.type === "scale";
    const unit = scale ? "%" : c.unit;
    const toField = (v) => (scale ? num(v * 100, 1) : num(v, c.decimals));
    const fromField = (s) => { const n = parseFloat(String(s).replace(",", ".")); return isNaN(n) ? null : scale ? roundTo(n / 100, 4) : roundTo(n, Math.max(c.decimals, 2)); };
    const input = h("input", { class: "num", name: "ui-tweaks-" + c.id, inputmode: "decimal", spellcheck: "false", autocomplete: "off", "aria-label": c.label + (unit ? " (" + unit + ")" : "") });
    const field = h("label", { class: "field" }, [input, unit ? h("span", { class: "unit", text: unit }) : null]);
    const sl = slider(c, c.snaps.concat([c.value]), c.value);
    const label = h("span", { class: "label scrub", text: c.label, title: "Drag to adjust · Shift for bigger steps" });
    const { row, warn } = baseRow(c, label, field, h("div", { class: "slider" }, [sl.range, sl.ticks]));
    bindScrub(label, c, sl.clampStep);

    const commitField = () => { const v = fromField(input.value); if (v === null) update(); else set(c, v); };
    input.addEventListener("change", commitField);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { commitField(); input.blur(); }
      else if (e.key === "Escape") { update(true); input.blur(); }
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault();
        set(c, roundTo(values[c.id] + (e.key === "ArrowUp" ? 1 : -1) * c.step * (e.shiftKey ? 10 : 1), c.decimals + 1));
      }
    });
    input.addEventListener("blur", () => update(true));

    function update(force) {
      const v = values[c.id];
      if (force || shadow.activeElement !== input) { input.value = toField(v); input.style.width = Math.max(2, input.value.length) + 0.4 + "ch"; }
      sl.show(v);
      row.classList.toggle("changed", isChanged(c, v));
    }
    return { row, warn, update };
  }

  // Lighter ↔ darker on a track that shows the actual colours; marks are the app's neighbouring shades.
  function shadeRow(c) {
    const well = h("span", { class: "well static", "aria-hidden": "true" });
    const name = h("span", { class: "shade-name" });
    const sl = slider(c, c.marks.map((mk) => mk.d), 0);
    sl.range.setAttribute("aria-label", c.label + ", lighter to darker");
    const stops = [0, 0.25, 0.5, 0.75, 1].map((f) => shadeColor(c, c.min + (c.max - c.min) * f) + " " + f * 100 + "%");
    sl.range.style.setProperty("--track", "linear-gradient(90deg, " + stops.join(", ") + ")");
    const label = h("span", { class: "label scrub", text: c.label, title: "Drag to adjust · Shift for bigger steps" });
    const { row, warn } = baseRow(c, label, h("div", { class: "color" }, [name, well]), h("div", { class: "slider shade" }, [sl.range, sl.ticks]));
    bindScrub(label, c, sl.clampStep);
    function update() {
      const v = values[c.id], hex = shadeColor(c, v), mk = markAt(c, v);
      well.style.setProperty("--c", hex);
      name.textContent = mk && mk.code ? mk.code : hex.toUpperCase();
      name.title = hex.toUpperCase() + (mk && mk.code ? "  " + mk.code : "");
      sl.show(v);
      row.classList.toggle("changed", isChanged(c, v));
    }
    return { row, warn, update };
  }

  function colorRow(c) {
    const picker = h("input", { type: "color", name: "ui-tweaks-" + c.id + "-picker", tabindex: "-1", "aria-hidden": "true" });
    const well = h("label", { class: "well", title: "Pick a colour" }, [picker]);
    const hex = h("input", { class: "hex", name: "ui-tweaks-" + c.id, spellcheck: "false", autocomplete: "off", "aria-label": c.label });
    const list = [];
    [c.baseHex].concat((c.swatches || model.palette).map(toHex)).forEach((x) => { if (x && list.indexOf(x) < 0 && list.length < 16) list.push(x); });
    const swatches = list.map((x) =>
      h("button", { class: "sw", style: "--c:" + x, title: x.toUpperCase() + (x === c.baseHex ? "  (original)" : ""), "aria-label": x.toUpperCase(), onclick: () => set(c, x) })
    );
    const { row, warn } = baseRow(c, h("span", { class: "label", text: c.label }), h("div", { class: "color" }, [well, hex]), list.length > 1 ? h("div", { class: "swatches" }, swatches) : null);

    const commitHex = () => { const x = toHex(hex.value.indexOf("#") < 0 && /^[0-9a-f]{3,6}$/i.test(hex.value) ? "#" + hex.value : hex.value); if (x) set(c, x); else update(true); };
    picker.addEventListener("input", () => set(c, picker.value.toLowerCase()));
    hex.addEventListener("change", commitHex);
    hex.addEventListener("keydown", (e) => { if (e.key === "Enter") { commitHex(); hex.blur(); } else if (e.key === "Escape") { update(true); hex.blur(); } });
    hex.addEventListener("blur", () => update(true));

    function update(force) {
      const v = values[c.id];
      well.style.setProperty("--c", v);
      picker.value = v;
      if (force || shadow.activeElement !== hex) hex.value = v.toUpperCase();
      swatches.forEach((s, i) => s.classList.toggle("on", list[i] === v));
      row.classList.toggle("changed", isChanged(c, v));
    }
    return { row, warn, update };
  }

  function choiceRow(c) {
    const label = h("span", { class: "label", text: c.label });
    const segmented = c.options.length <= 4 && c.options.reduce((n, o) => n + o.label.length, 0) <= 26;
    if (segmented) {
      const buttons = c.options.map((o) => h("button", { role: "radio", title: o.code || o.label, text: o.label, onclick: () => set(c, o.value) }));
      const seg = h("div", { class: "seg", role: "radiogroup", "aria-label": c.label, style: "--n:" + c.options.length }, [h("span", { class: "seg-thumb" })].concat(buttons));
      seg.addEventListener("keydown", (e) => {
        const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        const i = Math.min(c.options.length - 1, Math.max(0, c.options.findIndex((o) => o.value === values[c.id]) + d));
        set(c, c.options[i].value);
        buttons[i].focus();
      });
      const { row, warn } = baseRow(c, label, null, seg);
      const update = () => {
        const i = Math.max(0, c.options.findIndex((o) => o.value === values[c.id]));
        seg.style.setProperty("--i", i);
        buttons.forEach((b, j) => { b.setAttribute("aria-checked", String(j === i)); b.tabIndex = j === i ? 0 : -1; });
        row.classList.toggle("changed", isChanged(c, values[c.id]));
      };
      return { row, warn, update };
    }
    const select = h("select", { name: "ui-tweaks-" + c.id, "aria-label": c.label }, c.options.map((o) => h("option", { value: o.value, text: o.label })));
    select.addEventListener("change", () => set(c, select.value));
    const { row, warn } = baseRow(c, label, h("div", { class: "popup" }, [select, h("span", { class: "popup-chev", icon: ICON.updown })]), null);
    const update = () => { select.value = values[c.id]; row.classList.toggle("changed", isChanged(c, values[c.id])); };
    return { row, warn, update };
  }

  const buildRow = (c) =>
    c.type === "color" ? colorRow(c) : c.type === "shade" ? shadeRow(c) : c.type === "choice" ? choiceRow(c) : numberRow(c);

  // ---------------------------------------------------------------------------------------------
  // Config, overrides, chrome
  // ---------------------------------------------------------------------------------------------

  function adopt(text) {
    let raw;
    try { raw = JSON.parse(text); } catch (e) { return fail("config.json is not valid JSON", e.message); }
    const m = normalizeConfig(raw);
    m.errors.concat(m.warnings).forEach((w) => console.warn("[ui-tweaks] " + w));
    if (!m.groups.length) return fail("The tweaks list has no usable controls", m.errors.join("\n"));
    const stored = store.get("values", {});
    model = m;
    controls = [];
    values = {};
    m.groups.forEach((g) => (g.controls = g.controls.filter((c) => {
      if (c.type === "shade" && !shadeSetup(c, toHex)) return console.warn("[ui-tweaks] " + c.label + ": can't read the colour " + c.value), false;
      return true;
    })));
    m.groups = m.groups.filter((g) => g.controls.length);
    m.groups.forEach((g) => g.controls.forEach((c) => {
      if (c.type === "color") c.baseHex = toHex(c.value) || "#000000";
      controls.push(c);
      const s = stored[c.id];
      values[c.id] = s && s.sig === sig(c) ? s.value : baseOf(c); // a new baseline (after the agent applied) wins
    }));
    failed = false;
    const top = body.scrollTop;
    body.textContent = "";
    rows = {};
    m.groups.forEach((g) => {
      const built = g.controls.map((c) => (rows[c.id] = buildRow(c)));
      body.appendChild(h("section", { class: "group" }, [g.label ? h("h3", { class: "group-label", text: g.label }) : null].concat(built.map((r) => r.row))));
    });
    body.scrollTop = top;
    controls.forEach((c) => rows[c.id].update());
    if (m.title) panel.setAttribute("aria-label", "Tweaks for " + m.title);
    commit();
    checkPresence();
  }

  function fail(title, detail) {
    failed = true;
    controls = [];
    overrides.set("");
    body.textContent = "";
    body.appendChild(h("div", { class: "error" }, [
      h("h4", { text: title }),
      h("p", { text: "Ask your agent to check the ui-tweaks config." }),
      detail ? h("pre", { text: detail }) : null,
    ]));
    refreshChrome();
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; commit(); });
  }

  function commit() {
    const css = buildCss(controls, values);
    overrides.set(css);
    store.set("css", css);
    const keep = {};
    controls.forEach((c) => { if (isChanged(c, values[c.id])) keep[c.id] = { sig: sig(c), value: values[c.id] }; });
    store.set("values", keep);
    refreshChrome();
  }

  let copiedTimer = 0;
  function refreshChrome() {
    const n = failed ? 0 : changedCount();
    count.textContent = String(n);
    count.hidden = !n;
    resetAll.disabled = !n;
    compareBtn.disabled = !n;
    copyBtn.disabled = !n;
    if (!copiedTimer) copyLabel.textContent = n ? "Copy " + plural(n) : "No changes yet";
  }

  function resetEverything() {
    controls.forEach((c) => { values[c.id] = baseOf(c); rows[c.id].update(); });
    commit();
  }

  // How many elements each control reaches on this page, and whether its variables exist here.
  function reach(c) {
    let elements = 0, undefinedVars = [];
    const root = getComputedStyle(document.documentElement);
    c.targets.forEach((t) => {
      if (t.property) { try { elements += document.querySelectorAll(selectorFor(t)).length; } catch (e) { /* bad selector */ } }
      else if (!t.selector && !t.class && !root.getPropertyValue(t.var).trim()) undefinedVars.push(t.var);
    });
    return { elements, undefinedVars, usesElements: c.targets.some((t) => t.property) };
  }

  function checkPresence() {
    controls.forEach((c) => {
      const r = rows[c.id];
      if (!r) return;
      const x = reach(c);
      const missing = x.usesElements && !x.elements;
      r.warn.hidden = !missing && !x.undefinedVars.length;
      r.warn.textContent = missing ? "not on this page" : "not defined here";
      r.warn.title = missing ? "Nothing on this page matches; it may be on another screen" : x.undefinedVars.join(", ") + " has no value on this page, so changing it does nothing here";
    });
  }

  // Does an element's computed value equal what `css` computes to in the same place? Transparent shadow layers
  // (Tailwind's ring placeholders) are ignored.
  function sameComputed(t, css, computed) {
    try {
      const el = document.querySelector(selectorFor(t));
      if (!el || !el.parentElement) return null;
      const probe = document.createElement(el.tagName === "TR" || el.tagName === "TD" ? "div" : el.tagName);
      probe.setAttribute("style", "position:absolute;visibility:hidden;pointer-events:none;font-size:" + getComputedStyle(el).fontSize);
      probe.style.setProperty(t.property, css);
      el.parentElement.appendChild(probe);
      const want = getComputedStyle(probe).getPropertyValue(t.property).trim();
      probe.remove();
      const clean = (v) => v.split(/,(?![^(]*\))/).map((x) => x.trim()).filter((x) => !/^rgba\(0, 0, 0, 0\) 0px 0px 0px 0px$/.test(x)).join(", ");
      return clean(want) === clean(computed);
    } catch (e) { return null; }
  }

  // For agents verifying the setup from a browser tool: uiTweaks.check(), uiTweaks.set(id, value), uiTweaks.reset().
  window.uiTweaks = {
    // computed is read from the first element a property target matches (or the variable on :root).
    // matches compares it with the control's current CSS for colours and px values; null when it can't tell.
    check: () => controls.map((c) => {
      const x = reach(c), first = c.targets.find((t) => t.property);
      let computed = null;
      if (first) { try { const el = document.querySelector(selectorFor(first)); if (el) computed = getComputedStyle(el).getPropertyValue(first.property).trim(); } catch (e) { /* bad selector */ } }
      else computed = getComputedStyle(document.documentElement).getPropertyValue(c.targets[0].var).trim();
      const css = cssValue(c, values[c.id], c.targets[0]);
      let matches = null;
      if (computed) {
        if (c.type === "shade" || c.type === "color") matches = toHex(computed) === toHex(css);
        else if (first) matches = sameComputed(first, css, computed);
        else if (c.type === "number" && c.unit === "px") matches = Math.abs(parseFloat(computed) - values[c.id]) < 0.05;
        else matches = computed === css;
      }
      return { id: c.id, label: c.label, value: c.value, current: values[c.id], css, changed: isChanged(c, values[c.id]), elements: x.usesElements ? x.elements : null, undefinedVars: x.undefinedVars, computed, matches };
    }),
    // value is what the control holds: a number, an option's value, a hex colour; for a shade, a colour or a lightness offset.
    set: (id, v) => {
      const c = controls.find((k) => k.id === id);
      if (!c) throw new Error("no control " + id);
      if (c.type === "shade" && typeof v === "string") {
        const hex = toHex(v);
        if (!hex) throw new Error("not a colour: " + v);
        const mk = (c.marks || []).find((m) => m.hex === hex);
        v = mk ? mk.d : roundTo(hexToOklch(c.baseHex)[0] - hexToOklch(hex)[0], 4);
      }
      set(c, v);
      commit();
      return cssValue(c, v, c.targets[0]);
    },
    reset: () => resetEverything(),
    message: () => formatCopy(controls, values),
  };

  async function copy() {
    const text = formatCopy(controls, values);
    if (!text) return;
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("style", "position:fixed;top:0;left:0;opacity:0;");
      document.body.appendChild(ta);
      ta.select();
      try { ok = document.execCommand("copy"); } catch (e2) { ok = false; }
      ta.remove();
    }
    if (!ok) console.log("[ui-tweaks] Copy this to your agent:\n\n" + text);
    clearTimeout(copiedTimer);
    copyBtn.classList.add("copied");
    copyBtn.querySelector(".copy-icon").innerHTML = ok ? ICON.check : ICON.copy;
    copyLabel.textContent = ok ? "Copied. Paste it to your agent" : "Couldn't copy. It's in the console";
    copyLabel.classList.remove("swap");
    void copyLabel.offsetWidth;
    copyLabel.classList.add("swap");
    copiedTimer = setTimeout(() => {
      copiedTimer = 0;
      copyBtn.classList.remove("copied");
      copyBtn.querySelector(".copy-icon").innerHTML = ICON.copy;
      refreshChrome();
    }, 2600);
  }

  // Hold Compare (pointer or Space/Enter) to see the app without the tweaks.
  const comparing = (on) => { overrides.off(on); compareBtn.classList.toggle("on", on); panel.classList.toggle("comparing", on); };
  compareBtn.addEventListener("pointerdown", (e) => { if (!compareBtn.disabled && e.button === 0) { compareBtn.setPointerCapture(e.pointerId); comparing(true); } });
  ["pointerup", "pointercancel", "lostpointercapture", "blur"].forEach((t) => compareBtn.addEventListener(t, () => comparing(false)));
  compareBtn.addEventListener("keydown", (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); comparing(true); } });
  compareBtn.addEventListener("keyup", (e) => { if (e.key === " " || e.key === "Enter") comparing(false); });

  // ---------------------------------------------------------------------------------------------
  // Position, drag, collapse, hide
  // ---------------------------------------------------------------------------------------------

  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  function place() {
    const w = panel.offsetWidth;
    const x = clamp(ui.x, 8, Math.max(8, innerWidth - w - 8));
    const y = clamp(ui.y, 8, Math.max(8, innerHeight - 48));
    panel.style.top = y + "px";
    panel.style.setProperty("--top", y + "px");
    panel.style.left = ui.side === "left" ? x + "px" : "auto";
    panel.style.right = ui.side === "left" ? "auto" : x + "px";
    panel.style.setProperty("--origin", ui.side === "left" ? "top left" : "top right");
  }
  const saveUi = () => store.set("ui", { side: ui.side, x: ui.x, y: ui.y, collapsed: ui.collapsed });

  function setCollapsed(b) {
    ui.collapsed = b;
    panel.classList.toggle("collapsed", b);
    collapseBtn.setAttribute("aria-expanded", String(!b));
    collapseBtn.setAttribute("aria-label", b ? "Expand" : "Collapse");
    collapseBtn.title = b ? "Expand" : "Collapse  (" + SHORTCUT + " hides)";
    saveUi();
  }

  header.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || e.target.closest("button")) return;
    const r = panel.getBoundingClientRect(), sx = e.clientX, sy = e.clientY;
    let moved = false;
    header.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const dx = ev.clientX - sx, dy = ev.clientY - sy;
      if (!moved && Math.hypot(dx, dy) < 3) return;
      moved = true;
      panel.classList.add("dragging");
      panel.style.left = clamp(r.left + dx, 8, innerWidth - r.width - 8) + "px";
      panel.style.right = "auto";
      panel.style.top = clamp(r.top + dy, 8, innerHeight - 48) + "px";
    };
    const up = () => {
      header.removeEventListener("pointermove", move);
      header.removeEventListener("pointerup", up);
      header.removeEventListener("pointercancel", up);
      panel.classList.remove("dragging");
      if (!moved) { if (ui.collapsed) setCollapsed(false); return; }
      const n = panel.getBoundingClientRect();
      ui.side = n.left + n.width / 2 > innerWidth / 2 ? "right" : "left";
      ui.x = ui.side === "right" ? innerWidth - n.right : n.left;
      ui.y = n.top;
      saveUi();
      place();
      pickTheme();
    };
    header.addEventListener("pointermove", move);
    header.addEventListener("pointerup", up);
    header.addEventListener("pointercancel", up);
  });

  addEventListener("keydown", (e) => {
    if (!e.altKey || e.metaKey || e.ctrlKey || e.code !== "KeyT") return;
    const a = e.composedPath()[0];
    if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) return;
    e.preventDefault();
    const hide = host.style.display !== "none";
    host.style.display = hide ? "none" : "";
    if (!hide) { panel.classList.add("enter"); place(); }
  }, true);

  // ---------------------------------------------------------------------------------------------
  // Boot: mount after the app has hydrated, keep the config in sync with the agent's edits
  // ---------------------------------------------------------------------------------------------

  // The panel lives on <html>, after <body> (as browser extensions do): a transform, filter or
  // overflow on the app's body can't trap it, and re-rendering the body can't remove it.
  const attach = () => { if (!host.isConnected) document.documentElement.appendChild(host); };

  // Dark over light pages, light over dark ones: average the first solid background behind three points of the panel.
  function pickTheme() {
    const r = panel.getBoundingClientRect();
    if (!r.width) return;
    let sum = 0;
    const points = [[r.left + r.width / 2, r.top + r.height / 2], [r.left + 12, r.top + 12], [r.right - 12, r.bottom - 12]];
    points.forEach(([px, py]) => {
      let c = null;
      for (const el of document.elementsFromPoint(clamp(px, 0, innerWidth - 1), clamp(py, 0, innerHeight - 1))) {
        if (el === host) continue;
        const v = rgbaOf(getComputedStyle(el).backgroundColor);
        if (v && v[3] > 0.5) { c = v; break; }
      }
      if (!c) c = /dark/.test(getComputedStyle(document.documentElement).colorScheme) ? [0, 0, 0] : [255, 255, 255];
      sum += 0.2126 * toLin(c[0] / 255) + 0.7152 * toLin(c[1] / 255) + 0.0722 * toLin(c[2] / 255);
    });
    panel.classList.toggle("dark", sum / points.length > 0.3);
  }

  async function poll() {
    attach();
    if (document.hidden) return;
    try {
      const res = await fetch(configUrl, { cache: "no-store" });
      if (!res.ok) throw new Error(res.status + " " + res.statusText + " for " + configUrl);
      const text = await res.text();
      if (text !== lastText) { lastText = text; adopt(text); }
    } catch (e) {
      if (lastText === null) fail("The tweaks list didn't load", e.message);
    }
    if (!failed) checkPresence();
    pickTheme();
  }

  function boot() {
    attach();
    if (ui.collapsed) setCollapsed(true);
    place();
    pickTheme();
    new MutationObserver(attach).observe(document.documentElement, { childList: true });
    addEventListener("resize", () => { place(); pickTheme(); });
    poll();
    setInterval(poll, 1500);
  }
  const later = () => setTimeout(boot, 80);
  if (document.readyState === "complete") later();
  else addEventListener("load", later, { once: true });

  // ---------------------------------------------------------------------------------------------
  // Look: macOS inspector. Translucent material, system type, hairlines, spring motion.
  // ---------------------------------------------------------------------------------------------

  function CSS_TEXT() {
    return `
:host { all: initial; }
*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
button, input, select { font: inherit; color: inherit; margin: 0; }
button { -webkit-tap-highlight-color: transparent; }

.panel {
  --spring: cubic-bezier(.32, .72, 0, 1);
  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", system-ui, sans-serif;
  --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
  --bg: rgba(246, 246, 248, .9);
  --bg-solid: #f5f5f7;
  --fg: rgba(0, 0, 0, .86);
  --fg2: rgba(60, 60, 67, .62);
  --fg3: rgba(60, 60, 67, .34);
  --sep: rgba(60, 60, 67, .14);
  --fill: rgba(120, 120, 128, .12);
  --fill2: rgba(120, 120, 128, .2);
  --track: rgba(120, 120, 128, .2);
  --raised: #fff;
  --knob: #fff;
  --accent: #007aff;
  --ring: rgba(0, 122, 255, .3);
  --warn: #c45500;
  --rim: rgba(0, 0, 0, .18);
  --shadow: 0 0 0 .5px rgba(0, 0, 0, .12), 0 1px 1px rgba(0, 0, 0, .03), 0 4px 12px rgba(0, 0, 0, .06), 0 20px 48px rgba(0, 0, 0, .14);
  --shadow-lift: 0 0 0 .5px rgba(0, 0, 0, .12), 0 2px 2px rgba(0, 0, 0, .03), 0 8px 20px rgba(0, 0, 0, .08), 0 32px 72px rgba(0, 0, 0, .2);
  --edge: inset 0 .5px 0 rgba(255, 255, 255, .75);
  position: fixed;
  top: 16px;
  right: 16px;
  width: 296px;
  max-height: calc(100vh - var(--top, 16px) - 12px);
  display: flex;
  flex-direction: column;
  font: 400 12px/16px var(--font);
  letter-spacing: 0;
  color: var(--fg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg);
  -webkit-backdrop-filter: blur(32px) saturate(180%);
  backdrop-filter: blur(32px) saturate(180%);
  border-radius: 14px;
  box-shadow: var(--shadow), var(--edge);
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  transform-origin: var(--origin, top right);
  interpolate-size: allow-keywords;
  transition: width .46s var(--spring), border-radius .46s var(--spring), box-shadow .25s ease, background-color .35s ease, color .35s ease;
}
/* Over a light page the panel goes dark, over a dark page light, so it never blends into the app. */
.panel.dark {
  --bg: rgba(28, 28, 30, .86);
  --bg-solid: #1c1c1e;
  --fg: rgba(255, 255, 255, .92);
  --fg2: rgba(235, 235, 245, .6);
  --fg3: rgba(235, 235, 245, .3);
  --sep: rgba(255, 255, 255, .09);
  --fill: rgba(118, 118, 128, .24);
  --fill2: rgba(118, 118, 128, .36);
  --track: rgba(118, 118, 128, .36);
  --raised: #636366;
  --knob: #f2f2f7;
  --accent: #0a84ff;
  --ring: rgba(10, 132, 255, .45);
  --warn: #ff9f0a;
  --rim: rgba(255, 255, 255, .22);
  --shadow: 0 0 0 .5px rgba(0, 0, 0, .45), 0 4px 12px rgba(0, 0, 0, .1), 0 20px 48px rgba(0, 0, 0, .22);
  --shadow-lift: 0 0 0 .5px rgba(0, 0, 0, .45), 0 8px 20px rgba(0, 0, 0, .14), 0 32px 72px rgba(0, 0, 0, .3);
  --edge: inset 0 0 0 .5px rgba(255, 255, 255, .1);
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .panel { background: var(--bg-solid); }
}
@supports (corner-shape: squircle) {
  .panel { corner-shape: squircle; border-radius: 22px; }
  .panel.collapsed { corner-shape: round; border-radius: 20px; }
}
.panel.enter { animation: enter .5s var(--spring) both; }
@keyframes enter { from { opacity: 0; transform: translateY(-6px) scale(.965); } }
.panel.dragging { box-shadow: var(--shadow-lift), var(--edge); }

/* Header */
.header {
  flex: none;
  display: flex;
  align-items: center;
  gap: 4px;
  height: 40px;
  padding: 0 7px 0 13px;
  cursor: grab;
}
.panel.dragging .header { cursor: grabbing; }
.title { display: flex; align-items: center; gap: 7px; font-weight: 600; font-size: 13px; letter-spacing: -.008em; white-space: nowrap; }
.glyph { display: grid; color: var(--fg2); }
.count {
  min-width: 17px;
  height: 17px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--accent);
  color: #fff;
  font: 600 10.5px/17px var(--font);
  font-variant-numeric: tabular-nums;
  text-align: center;
  animation: pop .4s var(--spring);
}
@keyframes pop { from { transform: scale(.4); opacity: 0; } }
.spacer { flex: 1; min-width: 8px; }
svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
svg .fill { fill: currentColor; stroke: none; opacity: .32; }
.icon {
  flex: none;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--fg2);
  cursor: default;
  transition: background .15s, color .15s, opacity .25s, width .46s var(--spring), margin .46s var(--spring);
}
.icon:hover:not(:disabled) { background: var(--fill); color: var(--fg); }
.icon:active:not(:disabled) { background: var(--fill2); }
.icon:disabled { opacity: .3; }
.chev { transition: transform .46s var(--spring); }
.panel.collapsed .chev { transform: rotate(180deg); }
.panel.collapsed { width: max-content; border-radius: 20px; }
.panel.collapsed .header { cursor: pointer; }
.panel.collapsed .reset-all { width: 0; margin-left: -4px; opacity: 0; pointer-events: none; }
.panel.collapsed .spacer { min-width: 0; }

/* Body */
.main {
  flex: 0 1 auto;
  min-height: 0;
  display: grid;
  grid-template-rows: 1fr;
  contain: inline-size;
  transition: grid-template-rows .46s var(--spring), opacity .3s ease;
}
.panel.collapsed .main { grid-template-rows: 0fr; opacity: 0; }
.main-inner { min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
.body {
  flex: 0 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 0 14px 4px;
  border-top: .5px solid var(--sep);
  scrollbar-width: thin;
  scrollbar-color: var(--fill2) transparent;
  transition: opacity .2s ease;
}
.panel.comparing .body { opacity: .45; }
.group { padding: 2px 0 6px; }
.group + .group { border-top: .5px solid var(--sep); }
.group-label { margin: 0; padding: 11px 0 1px; font: 600 11px/14px var(--font); color: var(--fg2); letter-spacing: .01em; }

.row { position: relative; padding: 7px 0; }
.head { display: flex; align-items: center; gap: 10px; min-height: 24px; }
.labels { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.label { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.scrub { cursor: ew-resize; align-self: flex-start; max-width: 100%; }
.panel.scrubbing, .panel.scrubbing * { cursor: ew-resize !important; }
.sub { display: flex; gap: 6px; min-width: 0; }
.hint { font: 10.5px/13px var(--mono); color: var(--fg3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.warn { font-size: 10.5px; line-height: 13px; color: var(--warn); white-space: nowrap; }

/* Changed: a dot in the margin. Click it to go back to the code's value. */
.dot {
  position: absolute;
  left: -11px;
  top: 9px;
  width: 12px;
  height: 12px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  display: grid;
  place-items: center;
  cursor: default;
  opacity: 0;
  transform: scale(.3);
  pointer-events: none;
  transition: opacity .2s ease, transform .4s var(--spring);
}
.dot::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); transition: transform .25s var(--spring); }
.dot:hover::before { transform: scale(1.4); }
.row.changed .dot { opacity: 1; transform: scale(1); pointer-events: auto; }

/* Number field */
.field {
  flex: none;
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 7px;
  border-radius: 6px;
  background: var(--fill);
  cursor: text;
  transition: background .15s, box-shadow .15s;
}
.field:hover { background: var(--fill2); }
.field:focus-within, .hex:focus { background: var(--raised); box-shadow: 0 0 0 .5px var(--accent), 0 0 0 3.5px var(--ring); }
.num {
  width: 3ch;
  border: 0;
  padding: 0;
  background: transparent;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  text-align: right;
  outline: none;
  user-select: text;
}
.unit { margin-left: 1px; color: var(--fg2); font-weight: 500; }

/* Slider */
.slider { position: relative; height: 22px; margin-top: 6px; }
.slider input {
  position: absolute;
  inset: 0 0 auto;
  width: 100%;
  height: 18px;
  margin: 0;
  background: transparent;
  -webkit-appearance: none;
  appearance: none;
  outline: none;
  cursor: default;
}
.slider input::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--accent) 0 calc(9px + (100% - 18px) * var(--f, 0)), var(--track) 0);
}
.slider input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  margin-top: -7px;
  border-radius: 50%;
  background: var(--knob);
  box-shadow: 0 0 0 .5px rgba(0, 0, 0, .1), 0 1px 2px rgba(0, 0, 0, .2), 0 3px 8px rgba(0, 0, 0, .1);
  transition: transform .3s var(--spring), box-shadow .15s;
}
.slider input:active::-webkit-slider-thumb { transform: scale(1.12); }
.slider input:focus-visible::-webkit-slider-thumb { box-shadow: 0 0 0 .5px rgba(0, 0, 0, .1), 0 1px 2px rgba(0, 0, 0, .2), 0 0 0 3.5px var(--ring); }
.slider input::-moz-range-track { height: 4px; border-radius: 2px; background: var(--track); }
.slider input::-moz-range-progress { height: 4px; border-radius: 2px; background: var(--accent); }
.slider input::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 50%;
  background: var(--knob);
  box-shadow: 0 0 0 .5px rgba(0, 0, 0, .1), 0 1px 2px rgba(0, 0, 0, .2), 0 3px 8px rgba(0, 0, 0, .1);
}
/* Shade: the track shows the colours themselves */
.slider.shade input::-webkit-slider-runnable-track { height: 6px; border-radius: 3px; background: var(--track); box-shadow: inset 0 0 0 .5px var(--rim); }
.slider.shade input::-webkit-slider-thumb { margin-top: -6px; }
.slider.shade input::-moz-range-track { height: 6px; border-radius: 3px; background: var(--track); box-shadow: inset 0 0 0 .5px var(--rim); }
.slider.shade input::-moz-range-progress { background: transparent; }
.shade-name { font: 500 11px/22px var(--mono); letter-spacing: .02em; color: var(--fg2); white-space: nowrap; user-select: text; }
.well.static { cursor: default; }
.well.static:hover, .well.static:active { transform: none; }
.ticks { position: absolute; left: 9px; right: 9px; top: 16px; height: 4px; pointer-events: none; }
.ticks i { position: absolute; top: 0; width: 1px; height: 4px; margin-left: -.5px; border-radius: 1px; background: var(--fg3); }
.ticks i.origin { background: var(--fg2); }

/* Colour */
.color { flex: none; display: flex; align-items: center; gap: 7px; }
.well {
  position: relative;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--c);
  box-shadow: inset 0 0 0 .5px var(--rim), inset 0 1px 0 rgba(255, 255, 255, .18);
  cursor: pointer;
  transition: transform .3s var(--spring);
}
.well:hover { transform: scale(1.08); }
.well:active { transform: scale(.96); }
.well input { position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; border: 0; opacity: 0; cursor: pointer; }
.hex {
  width: 70px;
  height: 22px;
  padding: 0 7px;
  border: 0;
  border-radius: 6px;
  background: var(--fill);
  font: 500 11px/22px var(--mono);
  letter-spacing: .02em;
  text-transform: uppercase;
  outline: none;
  user-select: text;
  transition: background .15s, box-shadow .15s;
}
.hex:hover:not(:focus) { background: var(--fill2); }
.swatches { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 8px; }
.sw {
  width: 17px;
  height: 17px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: var(--c);
  box-shadow: inset 0 0 0 .5px var(--rim);
  cursor: pointer;
  transition: transform .3s var(--spring), box-shadow .2s ease;
}
.sw:hover { transform: scale(1.14); }
.sw:active { transform: scale(.94); }
.sw.on { outline: 2px solid var(--accent); outline-offset: 2px; }

/* Segmented control */
.seg {
  position: relative;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  margin-top: 7px;
  padding: 2px;
  border-radius: 8px;
  background: var(--fill);
}
.seg-thumb {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: 2px;
  width: calc((100% - 4px) / var(--n));
  border-radius: 6px;
  background: var(--raised);
  box-shadow: 0 0 0 .5px rgba(0, 0, 0, .04), 0 1px 2px rgba(0, 0, 0, .12), 0 2px 6px rgba(0, 0, 0, .04);
  transform: translateX(calc(var(--i, 0) * 100%));
  transition: transform .38s var(--spring);
}
.seg button {
  position: relative;
  height: 22px;
  padding: 0 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  font-size: 11.5px;
  font-weight: 500;
  color: var(--fg2);
  white-space: nowrap;
  cursor: default;
  transition: color .2s ease;
}
.seg button[aria-checked="true"] { color: var(--fg); }
.seg button:hover:not([aria-checked="true"]) { color: var(--fg); }

/* Pop-up button */
.popup { flex: none; position: relative; max-width: 150px; }
.popup select {
  width: 100%;
  height: 22px;
  padding: 0 28px 0 8px;
  border: 0;
  border-radius: 6px;
  background: var(--raised);
  box-shadow: 0 0 0 .5px rgba(0, 0, 0, .14), 0 1px 1.5px rgba(0, 0, 0, .08);
  font-weight: 500;
  text-overflow: ellipsis;
  -webkit-appearance: none;
  appearance: none;
  outline: none;
  cursor: default;
}
.popup select:focus-visible { box-shadow: 0 0 0 .5px var(--accent), 0 0 0 3.5px var(--ring); }
.popup-chev {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 16px;
  height: 16px;
  display: grid;
  place-items: center;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  pointer-events: none;
}
.popup-chev svg { width: 12px; height: 12px; stroke-width: 1.75; }

/* Footer */
.footer { flex: none; display: flex; gap: 8px; padding: 10px 12px 12px; border-top: .5px solid var(--sep); }
.btn {
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 12px;
  border: 0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -.005em;
  white-space: nowrap;
  cursor: default;
  transition: background .18s ease, color .18s ease, box-shadow .18s ease, transform .25s var(--spring), filter .15s;
}
.btn:active:not(:disabled) { transform: scale(.97); }
.btn svg { flex: none; }
.secondary { background: var(--fill); color: var(--fg); }
.secondary:hover:not(:disabled) { background: var(--fill2); }
.secondary.on { background: var(--fg); color: var(--bg-solid); }
.secondary:disabled { color: var(--fg3); }
.primary {
  flex: 1;
  min-width: 0;
  background: var(--accent);
  color: #fff;
  box-shadow: inset 0 .5px 0 rgba(255, 255, 255, .22), 0 1px 2px rgba(0, 0, 0, .12);
}
.primary:hover:not(:disabled) { filter: brightness(1.07); }
.primary:disabled { background: var(--fill); color: var(--fg3); box-shadow: none; }
.copy-icon { display: grid; }
.copy-label { overflow: hidden; text-overflow: ellipsis; }
.copy-label.swap { animation: swap .4s var(--spring); }
@keyframes swap { from { opacity: 0; transform: translateY(4px); } }
.btn:focus-visible, .icon:focus-visible, .dot:focus-visible, .sw:focus-visible, .seg button:focus-visible { outline: none; box-shadow: 0 0 0 3.5px var(--ring); }

/* Error */
.error { padding: 14px 0 12px; }
.error h4 { margin: 0 0 3px; font-size: 12px; font-weight: 600; }
.error p { margin: 0 0 10px; color: var(--fg2); }
.error pre {
  margin: 0;
  padding: 8px 9px;
  border-radius: 6px;
  background: var(--fill);
  font: 10.5px/14px var(--mono);
  color: var(--fg2);
  white-space: pre-wrap;
  word-break: break-word;
  user-select: text;
}

@media (prefers-reduced-motion: reduce) {
  .panel, .panel *, .panel *::before { transition-duration: 0s !important; animation: none !important; }
}
`;
  }
})();
