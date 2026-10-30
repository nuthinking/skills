#!/usr/bin/env python3
"""design-catalog: turn page snapshots (and the source scan) into consolidation proposals.

Usage:
    python3 analyze.py --snapshots .design-catalog/snapshots [--scan .design-catalog/scan.json]
                       [--out .design-catalog] [--threshold 0.03] [--title "App name"]
                       [--allowed src/app/globals.css ...]

Writes into --out (default: the parent of the snapshots folder):
    proposals.json   every decision with members, counts, locations, suggested names; approved: null
    report.html      the one page a person reviews: swatches, type samples, rendered button/input/card variants
    summary.md       the same decisions as a short list, for the conversation
    drift.md/json    only with --allowed: values on screen that match none of the tokens declared in those CSS files

Decision IDs: C colours, T type sizes, H headings, F font families, S spacing, R radii, D shadows,
B buttons, I inputs, K cards, P badges. Each is approved or rejected one by one; compare.py reads the
approved ones as the allowed before/after mapping.

Standard library only.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import html
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_colors as C  # noqa: E402

try:
    from tailwind_palette import V3, V4, V4_THEME_VARS
except ImportError:  # pragma: no cover
    V3, V4, V4_THEME_VARS = {}, {}, []

TW_SIZES = [12, 14, 16, 18, 20, 24, 30, 36, 48, 60, 72, 96, 128]
INPUT_TYPES_SKIP = {"checkbox", "radio", "submit", "button", "range", "file", "hidden", "color", "image", "reset"}
SAMPLE_LIMIT = 6


# ------------------------------------------------------------------ helpers

def px(v) -> float | None:
    if v is None:
        return None
    m = re.match(r"^(-?\d*\.?\d+(?:e[-+]?\d+)?)px$", str(v).strip())
    return float(m.group(1)) if m else None


def fmt_px(n: float | None) -> str:
    if n is None:
        return "?"
    return f"{n:g}px"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def short_family(f: str | None) -> str:
    if not f:
        return "?"
    return f.split(",")[0].strip().strip("\"'")


TW_SPACING = [0, 1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240, 256]


def on_grid(n: float) -> bool:
    """On Tailwind's spacing scale (2px steps to 16px, 4px steps to 48px, then coarser)."""
    return any(abs(n - t) < 0.01 for t in TW_SPACING)


def snap_grid(n: float) -> float:
    return min(TW_SPACING[1:], key=lambda t: (abs(t - n), t))


def color_key(value: str) -> str:
    c = C.parse(value)
    return C.to_hex(c) if c else value


def hue_group_name(h: float) -> str:
    if h >= 345 or h < 36:
        return "danger"
    if h < 100:
        return "warning"
    if h < 185:
        return "success"
    if h < 262:
        return "info"
    if h < 300:
        return "indigo"
    if h < 330:
        return "purple"
    return "pink"


# ------------------------------------------------------------------ loading

class Screen:
    def __init__(self, path: str, data: dict):
        self.file = path
        self.data = data
        self.name = data.get("label") or (data.get("path", "/").strip("/").replace("/", "-") or "home")
        self.path = data.get("path", "/")
        self.viewport = data.get("viewport", {})
        self.scheme = data.get("colorScheme", "light")
        self.styles = data.get("styles", [])
        self.elements = data.get("elements", [])
        self.children = defaultdict(list)
        for e in self.elements:
            self.children[e.get("p", -1)].append(e["i"])
        self.png = next((p for p in (os.path.splitext(path)[0] + ".png",) if os.path.exists(p)), None)

    def style(self, e: dict) -> dict:
        return self.styles[e["s"]] if 0 <= e.get("s", -1) < len(self.styles) else {}

    def text_of(self, e: dict, depth: int = 3) -> str:
        """Own text, or the first text found in descendants (buttons often wrap their label in a span)."""
        if e.get("txt"):
            return e["txt"]
        queue = [(i, 1) for i in self.children.get(e["i"], [])]
        while queue:
            i, d = queue.pop(0)
            el = self.elements[i]
            if el.get("txt"):
                return el["txt"]
            if d < depth:
                queue.extend((j, d + 1) for j in self.children.get(i, []))
        return ""


def load_screens(folder: str) -> list[Screen]:
    screens = []
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("version") == 1 and "elements" in data:
            screens.append(Screen(f, data))
    return screens


def load_scan(path: str | None) -> dict | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sample_of(screen: Screen, e: dict) -> dict:
    s = {"screen": screen.name, "sel": e.get("sel", ""), "tag": e.get("t")}
    if e.get("txt"):
        s["text"] = e["txt"][:40]
    if e.get("rc"):
        s["component"] = " < ".join(e["rc"][:3])
    if e.get("dc"):
        s["component"] = e["dc"]
    if e.get("cls"):
        s["classes"] = e["cls"][:140]
    return s


def is_buttonish(screen: Screen, e: dict, st: dict) -> bool:
    if e.get("t") == "button" or e.get("role") == "button":
        return True
    if e.get("t") == "input" and e.get("type") in ("submit", "button"):
        return True
    if e.get("t") == "a":
        if re.search(r"\b(nav|header)\b", e.get("sel", "")):
            return False  # navigation items are not buttons
        bg = C.parse(st.get("background-color", ""))
        if bg and bg[3] > 0.05 and (px(st.get("padding-left")) or 0) >= 8:
            return True
    return False


# ------------------------------------------------------------------ source matching

def source_color_index(scan: dict | None) -> list[tuple[C.Color, str]]:
    """Colours the source declares, with a label naming the class/value and where it is."""
    out: list[tuple[C.Color, str]] = []
    if not scan:
        return out
    version = str(scan.get("project", {}).get("tailwind_version") or "4")
    table = V4 if version.startswith("4") else V3
    colors = scan.get("tailwind", {}).get("by_category", {}).get("color", {})
    for tok, e in colors.items():
        val = e["value"].split("/")[0]
        files = ", ".join(sorted(e["files"])[:3]) + (f" +{len(e['files']) - 3}" if len(e["files"]) > 3 else "")
        label = f"`{tok}` ×{e['count']} ({files})"
        m = re.match(r"^([a-z]+)-(\d{2,3})$", val)
        css = None
        if m and m.group(1) in table and m.group(2) in table[m.group(1)]:
            css = table[m.group(1)][m.group(2)]
        elif val in ("white", "black"):
            css = val
        elif val.startswith("[") and val.endswith("]"):
            css = val[1:-1].replace("_", " ")
        if css:
            c = C.parse(css)
            if c:
                out.append((c, label))
    for cat in ("colors",):
        for val, e in scan.get("css", {}).get(cat, {}).items():
            c = C.parse(val)
            if c:
                out.append((c, f"`{val}` ×{e['count']} ({', '.join(e['locations'][:2])})"))
    for name, decls in scan.get("custom_props", {}).items():
        for d in decls[:1]:
            c = C.parse(d["value"])
            if c:
                out.append((c, f"`{name}` ({d['file']}:{d['line']})"))
    for item in scan.get("inline_styles", []):
        for v in item.get("values", []):
            c = C.parse(v)
            if c:
                out.append((c, f"inline `{v}` ({item['file']}:{item['line']})"))
    return out


def sources_for(color: C.Color, index: list[tuple[C.Color, str]], max_delta: float = 0.008) -> list[str]:
    hits = [(C.delta(color, c), label) for c, label in index if abs(c[3] - color[3]) < 0.05]
    hits = sorted((d, l) for d, l in hits if d <= max_delta)
    seen, out = set(), []
    for _, l in hits:
        if l not in seen:
            seen.add(l)
            out.append(l)
    return out[:8]


# ------------------------------------------------------------------ existing tokens

def existing_tokens(screens: list[Screen], scan: dict | None) -> dict[str, dict]:
    """Semantic custom properties declared by the app (not Tailwind defaults), with computed values."""
    defaults = set(V4_THEME_VARS)
    tokens: dict[str, dict] = {}
    for sc in screens:
        for name, value in (sc.data.get("rootVars") or {}).items():
            if name in defaults or name.startswith("--tw-"):
                continue
            if re.match(r"^--color-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone|mauve|mist|olive|taupe)-\d+$", name):
                continue
            t = tokens.setdefault(name, {"name": name, "values": {}, "source": None})
            t["values"][sc.scheme] = value
    if scan:
        for name, decls in scan.get("custom_props", {}).items():
            if name in tokens:
                tokens[name]["source"] = f"{decls[0]['file']}:{decls[0]['line']}"
                tokens[name]["declared"] = decls[0]["value"]
            elif not re.match(r"^--color-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d+$", name) and name not in defaults:
                tokens[name] = {"name": name, "values": {}, "source": f"{decls[0]['file']}:{decls[0]['line']}", "declared": decls[0]["value"]}
    for t in tokens.values():
        val = t["values"].get("light") or next(iter(t["values"].values()), None) or t.get("declared")
        t["value"] = val
        c = C.parse(val) if val else None
        t["color"] = C.to_hex(c) if c else None
        t["parsed"] = c
        t["px"] = px(val) if val else None
        if t["px"] is None and val and re.match(r"^-?\d*\.?\d+rem$", val.strip()):
            t["px"] = float(val.strip()[:-3]) * 16
    return tokens


# ------------------------------------------------------------------ colours

def analyze_colors(screens: list[Screen], scan, tokens: dict, threshold: float, src_index) -> tuple[list[dict], dict]:
    table: dict[str, dict] = {}

    def add(value, role, screen, e, area=0):
        if not value:
            return
        c = C.parse(value)
        if c is None or c[3] <= 0.02:
            return
        key = C.to_hex(c)
        t = table.setdefault(key, {"value": value, "hex": key, "parsed": c, "count": 0, "roles": Counter(), "screens": set(), "samples": [], "button_bg": 0, "page_area": 0})
        t["count"] += 1
        t["roles"][role] += 1
        t["screens"].add(screen.name)
        if role == "background" and area > t["page_area"]:
            t["page_area"] = area
        if len(t["samples"]) < SAMPLE_LIMIT:
            t["samples"].append(sample_of(screen, e))
        return t

    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            w, h = (e.get("r") or [0, 0, 0, 0])[2:4]
            if e.get("txt") or (e.get("t") in ("input", "textarea", "select") and e.get("type") not in INPUT_TYPES_SKIP):
                add(st.get("color"), "text", sc, e)
            bg = st.get("background-color")
            if bg:
                t = add(bg, "background", sc, e, w * h)
                if t and is_buttonish(sc, e, st):
                    t["button_bg"] += 1
            if st.get("border-width") or any(st.get(f"border-{s}-width") for s in ("top", "right", "bottom", "left")):
                for key in ("border-color", "border-top-color", "border-bottom-color", "border-left-color", "border-right-color"):
                    if st.get(key):
                        add(st[key], "border", sc, e)
                        break
            if st.get("outline-color") and st.get("outline-width"):
                add(st["outline-color"], "outline", sc, e)
            if st.get("box-shadow"):
                for m in re.findall(r"(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^)]*\)|#[0-9a-fA-F]{3,8}", st["box-shadow"]):
                    add(m, "shadow", sc, e)

    clusters = C.cluster([(t["value"], t["count"]) for t in table.values()], threshold)
    # attach table data to members
    for cl in clusters:
        for m in cl["members"]:
            t = table[C.to_hex(C.parse(m["value"]))]
            m.update({"count": t["count"], "roles": dict(t["roles"]), "screens": sorted(t["screens"]), "samples": t["samples"], "button_bg": t["button_bg"], "page_area": t["page_area"], "tailwind": [f"{h['name']} ({h['version']})" for h in C.nearest_tailwind(t["parsed"])[:3]], "sources": sources_for(t["parsed"], src_index)})
            m.pop("parsed", None)
        cl["roles"] = Counter()
        cl["screens"] = set()
        cl["button_bg"] = 0
        cl["page_area"] = 0
        for m in cl["members"]:
            cl["roles"].update(m["roles"])
            cl["screens"].update(m["screens"])
            cl["button_bg"] += m["button_bg"]
            cl["page_area"] = max(cl["page_area"], m["page_area"])
        L, Ch, Hh = C.to_oklch(cl["parsed"])
        cl["L"], cl["C"], cl["H"] = L, Ch, Hh
        cl["neutral"] = Ch <= 0.05
        cl["dominant_role"] = cl["roles"].most_common(1)[0][0] if cl["roles"] else "unknown"
        cl["existing_token"] = None
        for name, t in tokens.items():
            if t.get("parsed") and C.delta(t["parsed"], cl["parsed"]) <= 0.012:
                cl["existing_token"] = name
                break

    # naming. Strong colours form hue groups first; pale tints whose hue matches a group belong to it,
    # everything else with low chroma is a neutral.
    strong = [cl for cl in clusters if cl["C"] > 0.05]
    groups: list[dict] = []

    def hue_diff(a, b):
        return abs((a - b + 180) % 360 - 180)

    def mean_hue(members):
        x = sum(math.cos(math.radians(c["H"])) * c["weight"] for c in members)
        y = sum(math.sin(math.radians(c["H"])) * c["weight"] for c in members)
        return math.degrees(math.atan2(y, x)) % 360

    for cl in sorted(strong, key=lambda c: -c["weight"]):
        best = min(groups, key=lambda g: hue_diff(cl["H"], g["H"]), default=None)
        if best and hue_diff(cl["H"], best["H"]) <= 16:
            best["members"].append(cl)
            best["H"] = mean_hue(best["members"])
        else:
            groups.append({"H": cl["H"], "members": [cl]})
    merged = True
    while merged:
        merged = False
        for i, g in enumerate(groups):
            for h in groups[i + 1:]:
                if hue_diff(g["H"], h["H"]) <= 16:
                    g["members"].extend(h["members"])
                    g["H"] = mean_hue(g["members"])
                    groups.remove(h)
                    merged = True
                    break
            if merged:
                break
    for cl in clusters:
        if cl["C"] > 0.05 or cl["C"] < 0.008 or cl["L"] < 0.9:
            continue  # only pale tints (very light, faintly coloured) join a hue group
        for g in groups:
            if abs((cl["H"] - g["H"] + 180) % 360 - 180) <= 25:
                g["members"].append(cl)
                cl["neutral"] = False
                break
    neutrals = [cl for cl in clusters if cl["neutral"]]
    used_names: Counter = Counter()

    def give(cl, name):
        used_names[name] += 1
        cl["name"] = name if used_names[name] == 1 else f"{name}-{used_names[name]}"

    def ladder(items, names, key=lambda c: c["L"]):
        for i, cl in enumerate(sorted(items, key=key)):
            give(cl, names[i] if i < len(names) else f"{names[-1]}-{int(round(cl['L'] * 100))}")

    page = max(neutrals, key=lambda c: c["page_area"], default=None)
    by_role = defaultdict(list)
    for cl in neutrals:
        if C._is_anchor(cl["parsed"]) and cl["L"] < 0.5 and cl["parsed"][3] > 0.99:
            give(cl, "black")
            continue
        if cl is page and cl["L"] > 0.85:
            give(cl, "background")
            continue
        by_role[cl["dominant_role"]].append(cl)
    for cl in sorted(by_role["text"], key=lambda c: -c["weight"]):
        give(cl, "text" if cl["L"] < 0.3 else "text-secondary" if cl["L"] < 0.5 else "text-muted" if cl["L"] < 0.65 else "text-subtle" if cl["L"] < 0.8 else "text-faint")
    ladder(by_role["border"], ["border-strong", "border", "border-subtle"], key=lambda c: c["L"] if len(by_role["border"]) > 2 else -c["weight"])
    if len(by_role["border"]) <= 2:
        # most used is plain "border"
        for i, cl in enumerate(sorted(by_role["border"], key=lambda c: -c["weight"])):
            cl["name"] = "border" if i == 0 else ("border-strong" if cl["L"] < by_role["border"][0]["L"] else "border-subtle")
    for cl in sorted(by_role["background"], key=lambda c: -c["weight"]):
        give(cl, "surface" if cl["L"] > 0.97 else "surface-muted" if cl["L"] > 0.85 else "surface-strong")
    for cl in by_role["shadow"]:
        give(cl, "shadow")
    for cl in by_role["outline"]:
        give(cl, "focus-ring")
    for role, items in by_role.items():
        if role not in ("text", "border", "background", "shadow", "outline"):
            for cl in items:
                give(cl, f"neutral-{int(round(cl['L'] * 100))}")
    primary = max(groups, key=lambda g: (sum(c["button_bg"] for c in g["members"]), sum(c["weight"] for c in g["members"])), default=None)
    for g in groups:
        base = "primary" if g is primary else hue_group_name(g["H"])
        bases = sorted((c for c in g["members"] if c["button_bg"] or (c["dominant_role"] == "background" and c["L"] <= 0.85)), key=lambda c: (c["existing_token"] is None, -c["button_bg"], -c["weight"]))
        if bases:
            give(bases[0], base)
            for cl in bases[1:]:
                give(cl, f"{base}-alt" if abs(cl["L"] - bases[0]["L"]) < 0.03 else f"{base}-strong" if cl["L"] < bases[0]["L"] else f"{base}-light")
        for cl in sorted(g["members"], key=lambda c: -c["weight"]):
            if cl in bases:
                continue
            role = cl["dominant_role"]
            if role == "background":
                give(cl, f"{base}-soft")
            elif role == "text":
                give(cl, f"{base}-text" if cl["L"] < 0.6 else f"{base}-text-soft")
            elif role == "border":
                give(cl, f"{base}-border")
            elif role == "outline":
                give(cl, "focus-ring")
            else:
                give(cl, f"{base}-{int(round(cl['L'] * 100))}")
        g["name"] = base
    # hover pairs: a strong variant of a base colour used mostly on hover is invisible in static snapshots; note only

    # a cluster named like an existing one with a numeric suffix is a near-duplicate: propose folding it
    by_name = {cl["name"]: cl for cl in clusters}
    for cl in clusters:
        m = re.match(r"^(.*)-(\d+)$", cl["name"])
        base = by_name.get(m.group(1)) if m else None
        cl["fold_into"] = None
        if base is not None and base is not cl and C.compatible(base["parsed"], cl["parsed"]) and C.delta(base["parsed"], cl["parsed"]) <= (0.1 if cl["neutral"] else 0.07) and not C._is_anchor(cl["parsed"]):
            cl["fold_into"] = base
    decisions = []
    for idx, cl in enumerate(clusters, 1):
        cid = f"C{idx}"
        cl["id"] = cid
        near = []
        for other in clusters:
            if other is cl or other.get("neutral") != cl["neutral"]:
                continue
            if C._is_anchor(cl["parsed"]) or C._is_anchor(other["parsed"]) or not C.compatible(cl["parsed"], other["parsed"]):
                continue
            d = C.delta(cl["parsed"], other["parsed"])
            if threshold < d <= 0.07:
                near.append(other)
        cl["near"] = near
    for cl in clusters:
        members = cl["members"]
        name = cl["existing_token"].lstrip("-").replace("color-", "") if cl["existing_token"] else cl["name"]
        if len(members) > 1:
            action = "merge"
            title = f"{len(members)} values that read as one colour: {C.describe(cl['parsed'])}"
            proposal = f"Use one value, {cl['hex']} (used {members[0]['count']}×), as `{name}`" + (f", the existing token {cl['existing_token']}" if cl["existing_token"] else "") + f"; replace {', '.join(m['hex'] for m in members[1:])}."
        else:
            action = "keep"
            title = f"{C.describe(cl['parsed'])} used as {cl['dominant_role']}"
            proposal = f"Keep {cl['hex']} as `{name}`" + (f" (already {cl['existing_token']})" if cl["existing_token"] else "") + "."
        if cl["fold_into"] is not None:
            action = "fold"
            proposal = f"{cl['hex']} ({cl['weight']}× as {cl['dominant_role']}) is a near-duplicate of `{cl['fold_into']['name']}` {cl['fold_into']['hex']}; use that instead." + (f" It also absorbs {', '.join(m['hex'] for m in members[1:])}." if len(members) > 1 else "")
        elif cl["near"]:
            proposal += " Close to " + ", ".join(f"{o['id']} ({o['hex']})" for o in cl["near"][:3]) + ": decide whether these are two steps of a scale or one colour."
        decisions.append({
            "id": cl["id"], "area": "color", "action": action, "title": title, "proposal": proposal,
            "fold_into": cl["fold_into"]["id"] if cl["fold_into"] is not None else None, "fold_into_value": cl["fold_into"]["members"][0]["value"] if cl["fold_into"] is not None else None,
            "hue_group": next((g["name"] for g in groups if cl in g["members"]), None), "L": round(cl["L"], 3),
            "name": name, "existing_token": cl["existing_token"], "survivor": members[0]["value"], "survivor_hex": cl["hex"],
            "oklch": C.to_oklch_string(cl["parsed"]), "role": cl["dominant_role"], "roles": dict(cl["roles"]), "count": cl["weight"], "screens": sorted(cl["screens"]),
            "near": [o["id"] for o in cl["near"]],
            "members": [{k: v for k, v in m.items() if k != "parsed"} for m in members],
            "approved": None, "note": "",
        })
    meta = {"neutral_count": len(neutrals), "chromatic_count": len(clusters) - len(neutrals), "hue_groups": [{"name": g["name"], "hue": round(g["H"]), "clusters": [c["id"] for c in g["members"]]} for g in groups]}
    return decisions, meta


# ------------------------------------------------------------------ typography

def analyze_typography(screens: list[Screen]) -> tuple[list[dict], dict]:
    sizes: dict[float, dict] = {}
    families: dict[str, dict] = {}
    weights: Counter = Counter()
    headings: dict[str, dict[tuple, dict]] = defaultdict(dict)
    styles: dict[tuple, dict] = {}
    text_total = 0
    for sc in screens:
        for e in sc.elements:
            if not e.get("txt") and e.get("t") not in ("input", "textarea", "select"):
                continue
            st = sc.style(e)
            size = px(st.get("font-size"))
            if size is None:
                continue
            text_total += 1
            fam = short_family(st.get("font-family"))
            weight = st.get("font-weight", "400")
            lh = st.get("line-height", "")
            s = sizes.setdefault(size, {"px": size, "count": 0, "screens": set(), "samples": [], "weights": Counter(), "tags": Counter()})
            s["count"] += 1
            s["screens"].add(sc.name)
            s["weights"][weight] += 1
            s["tags"][e.get("t")] += 1
            if len(s["samples"]) < SAMPLE_LIMIT:
                s["samples"].append(sample_of(sc, e))
            f = families.setdefault(fam, {"family": fam, "count": 0, "screens": set(), "samples": [], "tags": Counter()})
            f["count"] += 1
            f["screens"].add(sc.name)
            f["tags"][e.get("t")] += 1
            if len(f["samples"]) < SAMPLE_LIMIT:
                f["samples"].append(sample_of(sc, e))
            weights[weight] += 1
            key = (fam, size, weight, lh)
            ts = styles.setdefault(key, {"family": fam, "size": size, "weight": weight, "line_height": lh, "count": 0, "tags": Counter(), "screens": set()})
            ts["count"] += 1
            ts["tags"][e.get("t")] += 1
            ts["screens"].add(sc.name)
            if e.get("t") in ("h1", "h2", "h3", "h4", "h5", "h6"):
                hk = (size, weight, color_key(st.get("color", "")), st.get("letter-spacing", "normal"))
                hh = headings[e["t"]].setdefault(hk, {"size": size, "weight": weight, "color": color_key(st.get("color", "")), "letter_spacing": st.get("letter-spacing", "normal"), "count": 0, "screens": set(), "samples": []})
                hh["count"] += 1
                hh["screens"].add(sc.name)
                if len(hh["samples"]) < SAMPLE_LIMIT:
                    hh["samples"].append(sample_of(sc, e))

    decisions = []
    n = 0
    size_list = sorted(sizes.values(), key=lambda s: s["px"])
    for s in size_list:
        if s["px"] in TW_SIZES or s["px"] < 10:
            continue
        n += 1
        neighbours = sorted(((abs(s["px"] - o["px"]), -o["count"], o["px"]) for o in size_list if o["px"] in TW_SIZES), key=lambda t: (t[0], t[1]))
        target = neighbours[0][2] if neighbours else min(TW_SIZES, key=lambda t: abs(t - s["px"]))
        tcount = sizes.get(target, {}).get("count", 0)
        decisions.append({
            "id": f"T{n}", "area": "font_size", "action": "snap", "title": f"{fmt_px(s['px'])} text is off the type scale",
            "proposal": f"Use {fmt_px(target)} (used {tcount}×) instead of {fmt_px(s['px'])} ({s['count']}× on {', '.join(sorted(s['screens']))}).",
            "from": s["px"], "to": target, "count": s["count"], "screens": sorted(s["screens"]), "samples": s["samples"], "weights": dict(s["weights"]), "approved": None, "note": "",
        })
    hn = 0
    for level in ("h1", "h2", "h3", "h4", "h5", "h6"):
        combos = sorted(headings.get(level, {}).values(), key=lambda c: (-c["count"], c["size"] not in TW_SIZES, -c["size"]))
        if len(combos) > 1:
            hn += 1
            top = combos[0]
            others = "; ".join(f"{fmt_px(c['size'])}/{c['weight']} on {', '.join(sorted(c['screens']))}" for c in combos[1:])
            decisions.append({
                "id": f"H{hn}", "area": "heading", "action": "merge", "title": f"{level} has {len(combos)} different looks",
                "proposal": f"Use {fmt_px(top['size'])} / weight {top['weight']} / {top['color']} for every {level} ({top['count']}× on {', '.join(sorted(top['screens']))}). Others: {others}.",
                "level": level, "survivor": {"size": top["size"], "weight": top["weight"], "color": top["color"], "letter_spacing": top["letter_spacing"]},
                "members": [{"size": c["size"], "weight": c["weight"], "color": c["color"], "letter_spacing": c["letter_spacing"], "count": c["count"], "screens": sorted(c["screens"]), "samples": c["samples"]} for c in combos],
                "approved": None, "note": "",
            })
    fn = 0
    fam_list = sorted(families.values(), key=lambda f: -f["count"])
    for f in fam_list[1:]:
        share = f["count"] / max(1, text_total)
        if share < 0.08:
            fn += 1
            decisions.append({
                "id": f"F{fn}", "area": "font_family", "action": "review", "title": f"{f['family']} appears on only {f['count']} text elements",
                "proposal": f"Decide whether {f['family']} is intentional (code, numbers) or a stray; the main face is {fam_list[0]['family']} ({fam_list[0]['count']}×).",
                "family": f["family"], "count": f["count"], "screens": sorted(f["screens"]), "samples": f["samples"], "tags": dict(f["tags"]), "approved": None, "note": "",
            })
    meta = {
        "text_elements": text_total,
        "sizes": [{"px": s["px"], "count": s["count"], "on_scale": s["px"] in TW_SIZES, "weights": dict(s["weights"]), "tags": dict(s["tags"].most_common(4))} for s in size_list],
        "families": [{"family": f["family"], "count": f["count"], "tags": dict(f["tags"].most_common(5))} for f in fam_list],
        "weights": dict(weights.most_common()),
        "styles": sorted(({"family": v["family"], "size": v["size"], "weight": v["weight"], "line_height": v["line_height"], "count": v["count"], "tags": dict(v["tags"].most_common(3))} for v in styles.values()), key=lambda v: (-v["count"])),
        "headings": {lvl: [{"size": c["size"], "weight": c["weight"], "color": c["color"], "count": c["count"], "screens": sorted(c["screens"])} for c in sorted(v.values(), key=lambda c: -c["count"])] for lvl, v in headings.items()},
    }
    return decisions, meta


# ------------------------------------------------------------------ spacing, radius, shadow

def analyze_spacing(screens: list[Screen]) -> tuple[list[dict], dict]:
    values: dict[float, dict] = {}
    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            for prop in ("padding-top", "padding-right", "padding-bottom", "padding-left", "row-gap", "column-gap", "margin-top", "margin-bottom", "margin-left", "margin-right"):
                v = px(st.get(prop))
                if v is None or v == 0:
                    continue
                v = abs(v)
                if prop.startswith("margin") and v > 200:
                    continue
                d = values.setdefault(v, {"px": v, "count": 0, "props": Counter(), "screens": set(), "samples": []})
                d["count"] += 1
                d["props"][prop.split("-")[0]] += 1
                d["screens"].add(sc.name)
                if len(d["samples"]) < SAMPLE_LIMIT:
                    d["samples"].append(sample_of(sc, e))
    total = sum(v["count"] for v in values.values()) or 1
    decisions = []
    n = 0
    for v in sorted(values.values(), key=lambda d: d["px"]):
        if on_grid(v["px"]):
            continue
        n += 1
        target = snap_grid(v["px"])
        decisions.append({
            "id": f"S{n}", "area": "spacing", "action": "snap", "title": f"{fmt_px(v['px'])} spacing is off the 4px grid",
            "proposal": f"Use {fmt_px(target)} instead of {fmt_px(v['px'])} ({v['count']}× as {', '.join(v['props'])} on {', '.join(sorted(v['screens']))}).",
            "from": v["px"], "to": target, "count": v["count"], "screens": sorted(v["screens"]), "samples": v["samples"], "approved": None, "note": "",
        })
    on4 = sum(v["count"] for v in values.values() if on_grid(v["px"]))
    on8 = sum(v["count"] for v in values.values() if abs(v["px"] / 8 - round(v["px"] / 8)) < 1e-6)
    meta = {"scale": [{"px": v["px"], "count": v["count"], "props": dict(v["props"])} for v in sorted(values.values(), key=lambda d: d["px"])], "share_on_4px_grid": round(on4 / total, 3), "share_on_8px_grid": round(on8 / total, 3)}
    return decisions, meta


def analyze_radius(screens: list[Screen]) -> tuple[list[dict], dict]:
    values: dict[str, dict] = {}
    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            r = st.get("border-radius")
            if not r:
                continue
            h = (e.get("r") or [0, 0, 0, 0])[3]
            parts = r.split()
            if len(parts) > 1:
                key = "mixed:" + r
            else:
                v = px(r)
                if v is None or v == 0:
                    key = "full" if "%" in r else None
                elif v >= 999 or (h and v >= h / 2 and v > 12):
                    key = "full"
                else:
                    key = f"{v:g}"
            if not key:
                continue
            d = values.setdefault(key, {"key": key, "px": None if key in ("full",) or key.startswith("mixed") else float(key), "count": 0, "screens": set(), "samples": [], "tags": Counter()})
            d["count"] += 1
            d["screens"].add(sc.name)
            d["tags"][e.get("t")] += 1
            if len(d["samples"]) < SAMPLE_LIMIT:
                d["samples"].append(sample_of(sc, e))
    numeric = sorted((v for v in values.values() if v["px"] is not None), key=lambda v: -v["count"])
    total = sum(v["count"] for v in numeric) or 1
    keep, cum = [], 0
    for v in numeric:
        if len(keep) >= 4 or (cum / total >= 0.8 and v["count"] / total < 0.1):
            break
        keep.append(v)
        cum += v["count"]
    keep_px = sorted(v["px"] for v in keep)
    decisions = []
    n = 0
    for v in sorted(numeric, key=lambda v: v["px"]):
        if v in keep:
            continue
        n += 1
        target = min(keep_px, key=lambda k: abs(k - v["px"])) if keep_px else v["px"]
        decisions.append({
            "id": f"R{n}", "area": "radius", "action": "merge", "title": f"{fmt_px(v['px'])} radius is a one-off", "tags": dict(v["tags"].most_common(3)),
            "proposal": f"Use {fmt_px(target)} instead ({v['count']}× on {', '.join(sorted(v['screens']))}, mostly <{v['tags'].most_common(1)[0][0]}>). Scale would be {', '.join(fmt_px(k) for k in keep_px)}" + (" + full" if "full" in values else "") + ".",
            "from": v["px"], "to": target, "count": v["count"], "screens": sorted(v["screens"]), "samples": v["samples"], "approved": None, "note": "",
        })
    meta = {"scale": [{"radius": v["key"], "px": v["px"], "count": v["count"], "tags": dict(v["tags"].most_common(4)), "kept": v in keep or v["px"] is None} for v in sorted(values.values(), key=lambda v: (v["px"] is None, v["px"] or 0))], "proposed_scale": [fmt_px(k) for k in keep_px] + (["full"] if "full" in values else [])}
    return decisions, meta


def normalize_shadow(s: str) -> str:
    """Hex colours, and without the empty `0 0 #0000` layers Tailwind emits for ring/inset-ring slots."""
    def repl(m):
        c = C.parse(m.group(0))
        return C.to_hex(c) if c else m.group(0)
    s = re.sub(r"(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^)]*\)", repl, s).replace(" ,", ",")
    layers = [l.strip() for l in re.split(r",(?![^(]*\))", s)]
    kept = [l for l in layers if not (re.search(r"#[0-9a-f]{6}00\b", l) and not re.search(r"(?<![\d.])[1-9]\d*(?:\.\d+)?px", l))]
    return ", ".join(kept) if kept else "none"


def shadow_blur(s: str) -> float:
    nums = [px(x) for x in re.findall(r"-?\d*\.?\d+px", s.split(",")[0])]
    nums = [n for n in nums if n is not None]
    return nums[2] if len(nums) >= 3 else (nums[-1] if nums else 0)


def analyze_shadow(screens: list[Screen]) -> tuple[list[dict], dict]:
    values: dict[str, dict] = {}
    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            s = st.get("box-shadow")
            if not s or s == "none":
                continue
            key = normalize_shadow(s)
            if key == "none":
                continue
            d = values.setdefault(key, {"shadow": key, "raw": s, "count": 0, "screens": set(), "samples": [], "tags": Counter(), "blur": shadow_blur(s)})
            d["count"] += 1
            d["screens"].add(sc.name)
            d["tags"][e.get("t")] += 1
            if len(d["samples"]) < SAMPLE_LIMIT:
                d["samples"].append(sample_of(sc, e))
    ordered = sorted(values.values(), key=lambda v: -v["count"])
    total = sum(v["count"] for v in ordered) or 1
    keep = [v for i, v in enumerate(ordered) if i < 2 or v["count"] / total >= 0.2]
    decisions, n = [], 0
    for v in ordered:
        if v in keep:
            continue
        n += 1
        target = min(keep, key=lambda k: abs(k["blur"] - v["blur"]))
        decisions.append({
            "id": f"D{n}", "area": "shadow", "action": "merge", "title": "A one-off shadow",
            "proposal": f"Use `{target['shadow']}` ({target['count']}×) instead of `{v['shadow']}` ({v['count']}× on {', '.join(sorted(v['screens']))}).",
            "from": v["raw"], "from_normalized": v["shadow"], "to": target["raw"], "to_normalized": target["shadow"], "count": v["count"], "screens": sorted(v["screens"]), "samples": v["samples"], "approved": None, "note": "",
        })
    meta = {"scale": [{"shadow": v["shadow"], "count": v["count"], "blur": v["blur"], "tags": dict(v["tags"].most_common(3)), "kept": v in keep} for v in ordered]}
    return decisions, meta


# ------------------------------------------------------------------ components by signature

def radius_label(v: str | None, height: float | None = None) -> str | None:
    if not v:
        return None
    parts = v.split()
    n = px(parts[0])
    if n is None:
        return v
    if n >= 999 or (height and n >= height / 2 and n > 12):
        return "full"
    return v


def sig_style(st: dict, keys: tuple[str, ...], height: float | None = None) -> dict:
    out = {}
    for k in keys:
        v = st.get(k)
        if v is None:
            continue
        if k in ("color", "background-color", "border-color", "outline-color"):
            v = color_key(v)
        if k == "border-radius":
            v = radius_label(v, height)
        out[k] = v
    return out


BUTTON_KEYS = ("background-color", "color", "border-width", "border-color", "border-radius", "font-size", "font-weight", "padding-top", "padding-right", "padding-bottom", "padding-left", "box-shadow", "text-transform", "letter-spacing")
INPUT_KEYS = ("background-color", "color", "border-width", "border-color", "border-radius", "font-size", "padding-left", "padding-right", "padding-top", "padding-bottom", "box-shadow")
CARD_KEYS = ("background-color", "border-width", "border-color", "border-radius", "box-shadow", "padding-top", "padding-right", "padding-bottom", "padding-left")
BADGE_KEYS = ("border-radius", "font-size", "font-weight", "padding-top", "padding-right", "padding-bottom", "padding-left", "text-transform", "letter-spacing", "border-width")


def collect_signatures(screens: list[Screen], kind: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            w, h = (e.get("r") or [0, 0, 0, 0])[2:4]
            tag = e.get("t")
            if kind == "button":
                if not is_buttonish(sc, e, st) or w < 16 or h < 16:
                    continue
                keys = BUTTON_KEYS
                sig = sig_style(st, keys, h)
                sig["height"] = f"{round(h)}px"
                label = sc.text_of(e)
                bgc = C.parse(st.get("background-color", ""))
                if e.get("role") == "switch" or (not label and sig.get("border-radius") == "full" and w >= 1.6 * h):
                    family = "switch"
                    sig = {k: v for k, v in sig.items() if k not in ("background-color", "color", "border-color")}
                    sig["width"] = f"{round(w)}px"
                elif not label and w <= 48:
                    family = "icon"
                elif not bgc or bgc[3] < 0.05:
                    family = "ghost"
                else:
                    family = sig.get("background-color")
            elif kind == "input":
                if tag == "input" and e.get("type") in INPUT_TYPES_SKIP:
                    continue
                if tag not in ("input", "textarea", "select"):
                    continue
                keys = INPUT_KEYS
                sig = sig_style(st, keys, h)
                sig["height"] = f"{round(h)}px" if tag != "textarea" else "auto"
                family = tag
            elif kind == "card":
                if tag in ("button", "a", "input", "nav", "header", "footer", "body", "html", "main", "ul", "ol", "li", "table", "tr", "td", "th", "svg", "img", "select", "textarea"):
                    continue
                bg = C.parse(st.get("background-color", ""))
                has_border = bool(st.get("border-width") and px(st["border-width"]))
                has_shadow = bool(st.get("box-shadow"))
                radius = px(st.get("border-radius", "0px").split()[0]) or 0
                if not bg or bg[3] < 0.05 or not (has_border or has_shadow) or radius < 4 or w < 180 or h < 56 or len(sc.children.get(e["i"], [])) < 2:
                    continue
                keys = CARD_KEYS
                sig = sig_style(st, keys, h)
                family = "card"
            elif kind == "badge":
                if tag in ("button", "a", "input", "select", "textarea", "svg") or not e.get("txt"):
                    continue
                bg = C.parse(st.get("background-color", ""))
                radius = px(st.get("border-radius", "0px").split()[0])
                size = px(st.get("font-size"))
                if not bg or bg[3] < 0.05 or h > 30 or w > 180 or radius is None or radius < 3 or size is None or size > 13.5:
                    continue
                keys = BADGE_KEYS
                sig = sig_style(st, keys, h)
                family = "badge"
            else:
                continue
            key = json.dumps(sig, sort_keys=True)
            g = groups.setdefault(key, {"signature": sig, "family": family, "count": 0, "screens": set(), "samples": [], "components": Counter(), "classes": Counter(), "texts": [], "style": st, "colors": Counter()})
            g["count"] += 1
            g["screens"].add(sc.name)
            if e.get("rc"):
                g["components"][e["rc"][0]] += 1
            if e.get("dc"):
                g["components"][e["dc"]] += 1
            if e.get("cls"):
                g["classes"][e["cls"][:160]] += 1
            label_text = sc.text_of(e) if kind in ("button", "badge") else e.get("txt")
            if label_text and label_text not in g["texts"] and len(g["texts"]) < 4:
                g["texts"].append(label_text)
            if kind == "badge":
                g["colors"][(color_key(st.get("background-color", "")), color_key(st.get("color", "")))] += 1
            if len(g["samples"]) < SAMPLE_LIMIT:
                g["samples"].append(sample_of(sc, e))
    out = []
    for g in groups.values():
        g["screens"] = sorted(g["screens"])
        g["components"] = dict(g["components"].most_common(4))
        g["classes"] = [c for c, _ in g["classes"].most_common(3)]
        g["colors"] = [list(k) + [v] for k, v in g["colors"].most_common(6)]
        out.append(g)
    out.sort(key=lambda g: -g["count"])
    return out


def family_decisions(kind: str, prefix: str, groups: list[dict], color_names: dict[str, str]) -> list[dict]:
    """Group signatures into families (same background colour for buttons, same tag for inputs) and
    propose one survivor per family."""
    fams: dict[str, list[dict]] = defaultdict(list)
    for g in groups:
        fam = g["family"]
        if kind == "button" and fam not in ("ghost", "switch", "icon"):
            fam = color_names.get(fam, fam)
        if kind == "badge":
            # shape families: ignore colour, group every badge together
            fam = "badge"
        fams[fam].append(g)
    decisions, n = [], 0
    for fam, items in sorted(fams.items(), key=lambda kv: -sum(g["count"] for g in kv[1])):
        items.sort(key=lambda g: (-len(g["screens"]), -g["count"]))
        n += 1
        top = items[0]
        label = {"button": "button", "input": "input", "card": "card", "badge": "badge"}[kind]
        fam_label = (fam if fam in ("switch", "icon") else f"{fam} {label}") if kind == "button" else f"{fam}" if kind == "input" else label
        if fam == "icon":
            fam_label = "icon button"
        if len(items) > 1:
            action = "merge"
            title = f"{fam_label}: {len(items)} variants that should probably be one"
            proposal = f"Make every {fam_label} look like variant 1 ({describe_sig(kind, top['signature'])}, {top['count']}× on {', '.join(top['screens'])}); " + "; ".join(f"variant {i + 2} ({describe_sig(kind, g['signature'])}, {g['count']}× on {', '.join(g['screens'])})" for i, g in enumerate(items[1:])) + " follow it. Counts include repeats inside lists; variant 1 is the one seen on most screens."
        else:
            action = "keep"
            title = f"{fam_label}: one consistent look"
            proposal = f"Keep as is ({describe_sig(kind, top['signature'])}, {top['count']}× on {', '.join(top['screens'])})."
        decisions.append({
            "id": f"{prefix}{n}", "area": kind, "action": action, "title": title, "proposal": proposal, "family": fam,
            "survivor": {k: v for k, v in top.items() if k not in ("style",)},
            "variants": [{k: v for k, v in g.items() if k not in ("style",)} for g in items],
            "render": [render_style(g["style"], kind) for g in items],
            "approved": None, "note": "",
        })
    return decisions


def describe_sig(kind: str, sig: dict) -> str:
    bits = []
    if sig.get("background-color"):
        bits.append(f"bg {sig['background-color']}")
    if sig.get("border-width") and sig.get("border-color"):
        bits.append(f"border {sig['border-width']} {sig['border-color']}")
    if sig.get("border-radius"):
        bits.append(f"radius {sig['border-radius']}")
    if sig.get("font-size"):
        bits.append(f"{sig['font-size']}/{sig.get('font-weight', '')}".rstrip("/"))
    pad = [sig.get(f"padding-{s}") for s in ("top", "right", "bottom", "left")]
    if any(pad):
        bits.append("padding " + " ".join(p or "0" for p in pad))
    if sig.get("height") and kind in ("button", "input"):
        bits.append(f"h {sig['height']}")
    if sig.get("box-shadow"):
        bits.append("shadow")
    if sig.get("text-transform") and sig["text-transform"] != "none":
        bits.append(sig["text-transform"])
    return ", ".join(bits)


RENDER_PROPS = ("color", "background-color", "border-width", "border-color", "border-top-style", "border-radius", "font-family", "font-size", "font-weight", "line-height", "letter-spacing", "text-transform", "padding-top", "padding-right", "padding-bottom", "padding-left", "box-shadow", "display", "align-items", "justify-content", "column-gap")


def render_style(st: dict, kind: str) -> str:
    css = []
    for k in RENDER_PROPS:
        v = st.get(k)
        if not v:
            continue
        if k == "border-radius" and radius_label(v) == "full":
            v = "999px"
        if k == "border-top-style":
            css.append(f"border-style:{v}")
            continue
        if k == "display" and v not in ("inline-flex", "flex", "inline-block", "block"):
            continue
        css.append(f"{k}:{v}")
    if st.get("border-width") and not st.get("border-top-style"):
        css.append("border-style:solid")
    if kind == "card":
        css.append("min-width:220px;min-height:72px")
    if kind == "input":
        css.append("min-width:200px")
        if not st.get("background-color"):
            css.append("background:#fff")
    css.append("box-sizing:border-box")
    if kind in ("button", "badge"):
        css.append("display:inline-flex;align-items:center;justify-content:center;width:max-content;white-space:nowrap")
    elif kind == "input":
        css.append("display:inline-block;width:240px")
    else:
        css.append("display:block;width:260px")
    return ";".join(css)


# ------------------------------------------------------------------ drift

def parse_css_tokens(paths: list[str]) -> dict[str, str]:
    decls: dict[str, str] = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;{}]+);", text):
            decls.setdefault(m.group(1), m.group(2).strip())
    # resolve var() one or two levels, then simple calc() of lengths
    for _ in range(2):
        for k, v in list(decls.items()):
            def rep(m):
                return decls.get(m.group(1), m.group(0))
            decls[k] = re.sub(r"var\((--[\w-]+)(?:,[^)]*)?\)", rep, v)
    for k, v in list(decls.items()):
        m = re.match(r"^calc\(\s*(-?\d*\.?\d+)(px|rem)\s*([-+])\s*(-?\d*\.?\d+)(px|rem)\s*\)$", v)
        if m:
            a = float(m.group(1)) * (16 if m.group(2) == "rem" else 1)
            b = float(m.group(4)) * (16 if m.group(5) == "rem" else 1)
            decls[k] = f"{a + b if m.group(3) == '+' else a - b:g}px"
    return decls


def analyze_drift(screens: list[Screen], allowed_css: list[str]) -> dict:
    decls = parse_css_tokens(allowed_css)
    colors: list[tuple[str, C.Color]] = []
    radii: dict[float, str] = {}
    shadows: dict[str, str] = {}
    sizes: dict[float, str] = {}
    for name, val in decls.items():
        c = C.parse(val)
        if c:
            colors.append((name, c))
            continue
        v = px(val)
        if v is None and re.match(r"^-?\d*\.?\d+rem$", val):
            v = float(val[:-3]) * 16
        if name.startswith("--radius") and v is not None:
            radii[v] = name
        elif name.startswith("--text-") and "--line-height" not in name and v is not None:
            sizes[v] = name
        elif name.startswith("--shadow") or name.startswith("--inset-shadow"):
            shadows[normalize_shadow(val)] = name
    def nearest(c):
        if C._is_anchor(c):
            return (0.0, "white/black")
        best = min(((C.delta(c, tc), name) for name, tc in colors if abs(tc[3] - c[3]) < 0.05), default=(9, None))
        return best

    found: dict[str, dict] = {}

    def flag(kind, value, display, screen, e, hint):
        key = f"{kind}:{display}"
        d = found.setdefault(key, {"kind": kind, "value": display, "count": 0, "screens": set(), "samples": [], "nearest": hint})
        d["count"] += 1
        d["screens"].add(screen.name)
        if len(d["samples"]) < SAMPLE_LIMIT:
            d["samples"].append(sample_of(screen, e))

    for sc in screens:
        for e in sc.elements:
            st = sc.style(e)
            checks = []
            if e.get("txt") or e.get("t") in ("input", "textarea", "select"):
                checks.append(("text colour", st.get("color")))
            checks.append(("background", st.get("background-color")))
            if st.get("border-width"):
                checks.append(("border colour", st.get("border-color")))
            for kind, val in checks:
                c = C.parse(val or "")
                if not c or c[3] < 0.05:
                    continue
                d, name = nearest(c)
                if d > 0.012:
                    flag(kind, val, C.to_hex(c), sc, e, f"nearest token {name} (Δ {d:.3f})" if name and d < 0.08 else "no token nearby")
            if radii:
                r = st.get("border-radius")
                v = px(r.split()[0]) if r else None
                h = (e.get("r") or [0, 0, 0, 0])[3]
                if v and v < 999 and not (h and v >= h / 2 and v > 12) and not any(abs(v - k) <= 0.5 for k in radii):
                    flag("radius", r, f"{v:g}px", sc, e, f"nearest {radii[min(radii, key=lambda k: abs(k - v))]}")
            if shadows and st.get("box-shadow"):
                ns = normalize_shadow(st["box-shadow"])
                if ns not in shadows:
                    flag("shadow", st["box-shadow"], ns, sc, e, "not a declared shadow token")
            if sizes and (e.get("txt")):
                v = px(st.get("font-size"))
                if v and not any(abs(v - k) <= 0.5 for k in sizes):
                    flag("font size", st.get("font-size"), f"{v:g}px", sc, e, f"nearest {sizes[min(sizes, key=lambda k: abs(k - v))]}")
    items = sorted(found.values(), key=lambda d: -d["count"])
    for d in items:
        d["screens"] = sorted(d["screens"])
    return {"allowed_files": allowed_css, "tokens_parsed": len(decls), "items": items, "total": sum(d["count"] for d in items)}


# ------------------------------------------------------------------ grouping

def hexes(d: dict) -> str:
    return ", ".join(m["hex"] for m in d["members"])


def build_groups(decisions: list[dict], meta: dict, tokens: dict) -> list[dict]:
    """Fold granular decisions into the handful of questions a person actually answers."""
    groups: list[dict] = []
    by_area = defaultdict(list)
    for d in decisions:
        by_area[d["area"]].append(d)
    colors = by_area["color"]
    by_id = {d["id"]: d for d in decisions}

    def add(key, title, proposal, members, visual):
        if not members and visual != "info":
            return
        groups.append({"id": f"G{len(groups) + 1}", "key": key, "title": title, "proposal": proposal, "decisions": [m["id"] for m in members], "approved": None, "note": ""})

    # greys
    neutral_ids = {cid for g in meta["colors"]["hue_groups"] for cid in g["clusters"]}
    greys = [d for d in colors if d["id"] not in neutral_ids and d["role"] != "shadow"]
    grey_merges = [d for d in greys if d["action"] in ("merge", "fold")]
    grey_values = sum(len(d["members"]) for d in greys)
    tw_names = Counter()
    for d in greys:
        for m in d["members"]:
            for t in m.get("tailwind", [])[:1]:
                fam = t.split("-")[0]
                if fam in ("gray", "zinc", "slate", "neutral", "stone", "mauve", "mist", "olive", "taupe"):
                    tw_names[fam] += m["count"]
    if grey_merges or len(tw_names) > 1:
        final = [d for d in greys if d["action"] != "fold"]
        scale = ", ".join(f"`{d['name']}` {d['survivor_hex']}" for d in sorted(final, key=lambda d: d["L"]))
        fam_txt = f" from {len(tw_names)} palette families ({', '.join(tw_names)})" if len(tw_names) > 1 else ""
        add("greys", "One grey scale", f"{grey_values} grey values{fam_txt} do the job of {len(final)}. Use one scale: {scale}. The {len(grey_merges)} replacements are listed under details.", grey_merges or greys, "swatches")

    # accent and other hues
    for g in meta["colors"]["hue_groups"]:
        items = [by_id[c] for c in g["clusters"] if c in by_id]
        if not items:
            continue
        merges = [d for d in items if d["action"] in ("merge", "fold")]
        strong = [d for d in items if d["role"] == "background" and d["L"] <= 0.85]
        near_pairs = sorted({tuple(sorted((d["id"], n))) for d in items for n in d.get("near", []) if n in g["clusters"]})
        pair_txt = "; ".join(f"{by_id[a]['survivor_hex']} and {by_id[b]['survivor_hex']} ({by_id[a]['role']}) are nearly the same" for a, b in near_pairs[:3])
        if g["name"] == "primary":
            if len(strong) > 1 or merges or near_pairs:
                lst = "; ".join(f"{d['survivor_hex']} `{d['name']}` ({d['count']}× {d['role']})" for d in sorted(items, key=lambda d: d["L"]))
                add("accent", "One accent colour", f"The accent appears as {len(items)} values: {lst}. " + (pair_txt + ". " if pair_txt else "") + f"Keep one `primary` for buttons and links, one darker hover, one pale tint for selected and info backgrounds.", items, "swatches")
            else:
                add("accent", "Accent", f"One accent, `{items[0]['name']}` {items[0]['survivor_hex']}, used consistently. Nothing to decide.", [], "info")
        elif merges or near_pairs:
            lst = "; ".join(f"{d['survivor_hex']} `{d['name']}`" for d in sorted(items, key=lambda d: d["L"]))
            add(f"hue-{g['name']}", f"One {g['name']} colour", f"{g['name']} is used as {len(items)} values ({lst}). " + (pair_txt + ". " if pair_txt else "") + "Keep one strong, one for text, one soft tint.", items, "swatches")
    status = [g for g in meta["colors"]["hue_groups"] if g["name"] != "primary"]
    if status and not any(gr["key"].startswith("hue-") for gr in groups):
        add("status", "Status colours", f"{', '.join(g['name'] for g in status)} are used for badges and notes and are internally consistent. Nothing to decide.", [], "info")

    # type
    t = by_area["font_size"]
    h = by_area["heading"]
    f = by_area["font_family"]
    if t or h or f:
        bits = []
        if t:
            bits.append("sizes " + ", ".join(f"{fmt_px(d['from'])}→{fmt_px(d['to'])}" for d in t) + " are off the scale")
        for d in h:
            bits.append(f"{d['level']} differs per screen ({len(d['members'])} looks), use {fmt_px(d['survivor']['size'])}/{d['survivor']['weight']}")
        for d in f:
            bits.append(f"{d['family']} appears only {d['count']}× ({', '.join(d['tags'])}), keep or drop")
        sizes = ", ".join(fmt_px(x["px"]) for x in meta["typography"]["sizes"] if x["on_scale"])
        add("type", "One type scale", f"Scale would be {sizes}. " + "; ".join(bits) + ".", t + h + f, "type")

    # spacing
    sp = by_area["spacing"]
    if sp:
        add("spacing", "Spacing on the scale", ", ".join(f"{fmt_px(d['from'])}→{fmt_px(d['to'])} ({d['count']}×)" for d in sp) + f". {int(meta['spacing']['share_on_4px_grid'] * 100)}% of spacing is already on Tailwind's scale.", sp, "none")

    # radii
    r = by_area["radius"]
    if r:
        add("radii", "Fewer corner radii", f"Keep {', '.join(meta['radius']['proposed_scale'])}; " + ", ".join(f"{fmt_px(d['from'])}→{fmt_px(d['to'])} ({d['count']}× on {', '.join(f'<{t}>' for t in d.get('tags', {}))})" for d in r) + ".", r, "radii")

    # shadows
    dsh = by_area["shadow"]
    if dsh:
        add("shadows", "One shadow", "; ".join(f"replace `{d['from_normalized']}` ({d['count']}×) with `{d['to_normalized']}`" for d in dsh) + ".", dsh, "shadows")

    # components
    for area, key, title in (("button", "buttons", "One look per button kind"), ("input", "inputs", "One input look"), ("card", "cards", "One card"), ("badge", "badges", "One badge shape")):
        items = [d for d in by_area[area] if d["action"] == "merge"]
        if not items:
            continue
        lines = []
        for d in items:
            fam = f"{d['family']} button" if area == "button" else area
            comps = sorted({c for v in d["variants"] for c in v["components"]})
            lines.append(f"{fam}: {len(d['variants'])} looks" + (f" ({', '.join(comps)} and inline markup)" if comps else " (inline markup)") + f", use variant 1 ({describe_sig(area, d['survivor']['signature'])})")
        add(key, title, "; ".join(lines) + ".", items, "components")
    return groups


# ------------------------------------------------------------------ outputs

def build_summary(title: str, screens: list[Screen], result: dict) -> str:
    groups = result["groups"]
    dec = {d["id"]: d for d in result["decisions"]}
    lines = [f"# Design catalog proposal: {title}", ""]
    lines.append(f"Measured {len(screens)} screens: {', '.join(s.name for s in screens)}.")
    asks = [g for g in groups if g["decisions"]]
    lines.append(f"{len(asks)} decisions to take. Answer by ID (\"G1 yes\", \"G4 keep the pills\"). Details per decision below; visual page with --html.")
    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    for g in groups:
        tag = "" if g["decisions"] else " (nothing to decide)"
        lines.append(f"- **{g['id']} {g['title']}**{tag}: {g['proposal']}")
    lines.append("")
    lines.append("## Details")
    lines.append("")
    for g in groups:
        if not g["decisions"]:
            continue
        lines.append(f"### {g['id']} {g['title']}")
        for did in g["decisions"]:
            d = dec[did]
            lines.append(f"- {did}: {d['proposal']}")
        lines.append("")
    if result.get("drift"):
        dr = result["drift"]
        lines.append(f"## Drift: {dr['total']} values on screen outside the tokens declared in {', '.join(dr['allowed_files'])}")
        lines.append("")
        for d in dr["items"][:25]:
            lines.append(f"- {d['kind']} `{d['value']}` {d['count']}× on {', '.join(d['screens'])}; {d['nearest']}")
        if len(dr["items"]) > 25:
            lines.append(f"- ... {len(dr['items']) - 25} more in drift.md")
        lines.append("")
    return "\n".join(lines) + "\n"


CSS = """
:root{--bg:#f6f6f7;--card:#fff;--ink:#1a1a1f;--muted:#6b6b76;--line:#e4e4e8;--accent:#3b5bdb;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 32px 80px}h1{font-size:20px;margin:0 0 4px}.lead{color:var(--muted);margin:0 0 20px}
.g{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:12px 0}
.g header{display:flex;gap:12px;align-items:center;margin-bottom:4px}.id{font:600 12px/1 var(--mono);background:#eef1fb;color:var(--accent);border-radius:6px;padding:5px 7px}h2{margin:0;font-size:16px}
.prop{margin:0 0 14px;color:#333}
.row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-end;margin:8px 0}.cl{display:flex;flex-direction:column;gap:4px;font-size:12px;color:var(--muted)}.cl .sws{display:flex}.sw{width:44px;height:36px;border:1px solid rgba(0,0,0,.12)}.sw:first-child{border-radius:8px 0 0 8px}.sw:last-child{border-radius:0 8px 8px 0}.sw:only-child{border-radius:8px}
.cl b{color:var(--ink);font-weight:500}.mono{font-family:var(--mono);font-size:11.5px}
.samples{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-start}.sample{display:flex;flex-direction:column;gap:6px;font-size:12.5px;color:var(--muted);max-width:320px}.sample .box{display:inline-flex;align-items:center}
.step{display:inline-flex;flex-direction:column;align-items:center;gap:6px;font-size:12px;color:var(--muted);margin:0 14px 6px 0}
"""


def build_visual(title: str, result: dict) -> str:
    dec = {d["id"]: d for d in result["decisions"]}
    meta = result["meta"]
    parts = [f"<!doctype html><html lang=en><meta charset=utf-8><title>Design catalog proposal: {esc(title)}</title><style>{CSS}</style><body><main>"]
    parts.append(f"<h1>Design catalog proposal · {esc(title)}</h1><p class=lead>One card per decision. Answer by ID in the conversation. Nothing changes until you say so.</p>")
    for g in result["groups"]:
        if not g["decisions"]:
            continue
        items = [dec[i] for i in g["decisions"]]
        body = ""
        key = g["key"]
        if key in ("greys", "accent") or key.startswith("hue-"):
            cards = []
            for d in sorted(items, key=lambda d: -d["count"]):
                sws = "".join(f"<span class=sw style='background:{esc(m['hex'])}' title='{esc(m['hex'])} {m['count']}×'></span>" for m in d["members"])
                cards.append(f"<div class=cl><div class=sws>{sws}</div><b>{esc(d['name'])}</b><span class=mono>{esc(hexes(d))}</span><span>{d['count']}× · {esc(d['role'])}</span></div>")
            body = f"<div class=row>{''.join(cards)}</div>"
        elif key == "type":
            steps = "".join(f"<span class=step><span style='font-size:{min(x['px'], 34)}px;line-height:1;color:{'#1a1a1f' if x['on_scale'] else '#b4540a'}'>Aa</span>{fmt_px(x['px'])}{'' if x['on_scale'] else ' ✕'}</span>" for x in meta["typography"]["sizes"])
            heads = ""
            for d in items:
                if d["area"] == "heading":
                    heads += f"<div class=row>" + "".join(f"<span class=step><span style='font-size:{min(m['size'], 34)}px;font-weight:{esc(m['weight'])};color:{esc(m['color'])};line-height:1.1'>{esc(d['level'])} title</span>{fmt_px(m['size'])}/{esc(m['weight'])} · {esc(', '.join(m['screens']))}</span>" for m in d["members"]) + "</div>"
            body = f"<div class=row>{steps}</div>{heads}"
        elif key == "radii":
            body = "<div class=row>" + "".join(f"<span class=step><span style='display:inline-block;width:40px;height:40px;border:2px solid {'#3b5bdb' if x['kept'] else '#b4540a'};border-radius:{'999px' if x['px'] is None else str(x['px']) + 'px'}'></span>{esc(x['radius'] if x['px'] is None else fmt_px(x['px']))} · {x['count']}×{'' if x['kept'] else ' ✕'}</span>" for x in meta["radius"]["scale"]) + "</div>"
        elif key == "shadows":
            body = "<div class=row>" + "".join(f"<span class=step><span style='display:inline-block;width:90px;height:50px;background:#fff;border-radius:8px;box-shadow:{esc(x['shadow'])}'></span>{x['count']}×{'' if x['kept'] else ' ✕'}</span>" for x in meta["shadow"]["scale"]) + "</div>"
        elif key in ("buttons", "inputs", "cards", "badges"):
            blocks = []
            for d in items:
                cards = []
                for i, (v, css) in enumerate(zip(d["variants"], d["render"])):
                    text = v["texts"][0] if v.get("texts") else {"button": "Button", "input": "", "card": "", "badge": "Badge"}[d["area"]]
                    if d["area"] == "input":
                        box = f"<input class=box style='{esc(css)}' value='{esc(text or 'Input text')}' readonly>"
                    elif d["area"] == "card":
                        box = f"<div class=box style='{esc(css)};display:block'><div style='font-weight:600;margin-bottom:4px'>Card title</div><div style='font-size:13px;color:#666'>Supporting text</div></div>"
                    else:
                        box = f"<span class=box style='{esc(css)}'>{esc(text)}</span>"
                    comp = next(iter(v["components"]), None)
                    cards.append(f"<div class=sample>{box}<span><b>variant {i + 1}</b>{' ← keep' if i == 0 else ''} · {v['count']}× · {esc(', '.join(v['screens']))}" + (f" · {esc(comp)}" if comp else "") + "</span></div>")
                fam = d["family"] if d["area"] == "button" else d["area"]
                blocks.append(f"<div style='margin-bottom:14px'><div style='font-size:13px;color:var(--muted);margin-bottom:6px'>{esc(fam)}</div><div class=samples>{''.join(cards)}</div></div>")
            body = "".join(blocks)
        parts.append(f"<section class=g id='{esc(g['id'])}'><header><span class=id>{esc(g['id'])}</span><h2>{esc(g['title'])}</h2></header><p class=prop>{esc(g['proposal'])}</p>{body}</section>")
    parts.append("</main></body></html>")
    return "".join(parts)


# ------------------------------------------------------------------ main

def analyze(snapshots_dir: str, scan_path: str | None, out_dir: str, threshold: float, title: str | None, allowed: list[str], html: bool = False) -> dict:
    screens = load_screens(snapshots_dir)
    if not screens:
        raise SystemExit(f"no snapshots (version 1 JSON) found in {snapshots_dir}")
    scan = load_scan(scan_path)
    title = title or (scan or {}).get("project", {}).get("name") or os.path.basename(os.path.abspath(os.path.join(snapshots_dir, "..", "..")))
    tokens = existing_tokens(screens, scan)
    src_index = source_color_index(scan)
    color_dec, color_meta = analyze_colors(screens, scan, tokens, threshold, src_index)
    for t in tokens.values():
        t["measured_uses"] = sum(d["count"] for d in color_dec if d.get("existing_token") == t["name"])
    type_dec, type_meta = analyze_typography(screens)
    sp_dec, sp_meta = analyze_spacing(screens)
    r_dec, r_meta = analyze_radius(screens)
    sh_dec, sh_meta = analyze_shadow(screens)
    color_names = {}
    for d in color_dec:
        fam = d.get("hue_group") or ("surface" if d["L"] > 0.9 else "dark" if d["L"] < 0.4 else "neutral")
        for m in d["members"]:
            color_names[m["hex"]] = fam
    comp_dec = []
    for kind, prefix in (("button", "B"), ("input", "I"), ("card", "K"), ("badge", "P")):
        comp_dec.extend(family_decisions(kind, prefix, collect_signatures(screens, kind), color_names))
    decisions = color_dec + type_dec + sp_dec + r_dec + sh_dec + comp_dec
    meta = {"colors": color_meta, "typography": type_meta, "spacing": sp_meta, "radius": r_meta, "shadow": sh_meta}
    groups = build_groups(decisions, meta, tokens)
    result = {
        "version": 1,
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
        "title": title,
        "threshold": threshold,
        "screens": [{"name": s.name, "path": s.path, "viewport": s.viewport, "scheme": s.scheme, "elements": len(s.elements), "file": os.path.relpath(s.file, out_dir)} for s in screens],
        "tokens_existing": {k: {kk: vv for kk, vv in v.items() if kk != "parsed"} for k, v in tokens.items()},
        "groups": groups,
        "decisions": decisions,
        "meta": meta,
    }
    if allowed:
        result["drift"] = analyze_drift(screens, allowed)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "proposals.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(build_summary(title, screens, result))
    if html:
        with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as fh:
            fh.write(build_visual(title, result))
    if allowed:
        with open(os.path.join(out_dir, "drift.json"), "w", encoding="utf-8") as fh:
            json.dump(result["drift"], fh, indent=1)
        with open(os.path.join(out_dir, "drift.md"), "w", encoding="utf-8") as fh:
            dr = result["drift"]
            fh.write(f"# Drift report\n\n{dr['total']} element values outside the tokens declared in {', '.join(dr['allowed_files'])}.\n\n" + "\n".join(f"- {d['kind']} `{d['value']}` {d['count']}× on {', '.join(d['screens'])}; {d['nearest']}" + "".join(f"\n  - {s['screen']}: {s.get('component', '')} {s['sel'][-60:]}" for s in d["samples"][:3]) for d in dr["items"]) + "\n")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Analyse design-catalog snapshots into consolidation proposals.")
    ap.add_argument("--snapshots", default=".design-catalog/snapshots")
    ap.add_argument("--scan", default=None, help="scan.json from scan_source.py (default: <out>/scan.json if present)")
    ap.add_argument("--out", default=None, help="output folder (default: parent of --snapshots)")
    ap.add_argument("--threshold", type=float, default=0.03, help="OKLab distance under which two colours count as one (default 0.03)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--allowed", nargs="*", default=[], help="CSS files declaring the app's tokens; adds a drift report of values outside them")
    ap.add_argument("--html", action="store_true", help="also write report.html, a one-page visual of the decisions")
    ap.add_argument("--print", action="store_true", help="print summary.md to stdout")
    args = ap.parse_args(argv)
    out = args.out or os.path.dirname(os.path.abspath(args.snapshots.rstrip("/")))
    scan = args.scan or (os.path.join(out, "scan.json") if os.path.exists(os.path.join(out, "scan.json")) else None)
    result = analyze(args.snapshots, scan, out, args.threshold, args.title, args.allowed, args.html)
    if args.print:
        with open(os.path.join(out, "summary.md"), encoding="utf-8") as fh:
            print(fh.read())
    asks = [g for g in result["groups"] if g["decisions"]]
    print(f"{len(result['screens'])} screens, {len(asks)} decisions ({len(result['decisions'])} details) -> {out}/summary.md, proposals.json" + (", report.html" if args.html else "") + (f", drift.md ({result['drift']['total']} values)" if args.allowed else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
