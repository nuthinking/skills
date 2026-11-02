#!/usr/bin/env python3
"""design-catalog: compare before/after snapshots of the same screens and report what changed.

Usage:
    python3 compare.py <before-dir> <after-dir> [--mapping .design-catalog/proposals.json]
                       [--all-approved] [--tolerance 1] [--out compare.md] [--json compare.json]

Pairs files by name (home__1280.json in both folders). For every element it matches across the two
snapshots it checks:
  - layout: the bounding box must be the same (within --tolerance px); a move or resize is a regression
  - text: must be the same
  - style: every changed property must be an approved change: colour A -> colour B where an approved
    decision in the mapping has A among its members and B as the survivor (or an approved existing token);
    spacing/radius/font-size/shadow from -> to likewise. Anything else is an unapproved change.
Elements present on one side only are listed as added/removed.

Exit code 0 when there are no layout regressions and no unapproved style changes, 1 otherwise.
Use --all-approved to treat every decision in the mapping as approved (when the user chose "all at once").
Standard library only.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dc_colors as C  # noqa: E402

COLOR_PROPS = {"color", "background-color", "border-color", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color", "outline-color"}
LENGTH_PROPS = {"padding-top", "padding-right", "padding-bottom", "padding-left", "margin-top", "margin-right", "margin-bottom", "margin-left", "row-gap", "column-gap", "border-radius", "font-size", "border-width", "line-height", "letter-spacing", "min-height", "max-width"}
IGNORE_PROPS = {"transition-property", "transition-duration", "transition-timing-function", "cursor"}


def px(v):
    m = re.match(r"^(-?\d*\.?\d+(?:e[-+]?\d+)?)px$", str(v).strip()) if v is not None else None
    return float(m.group(1)) if m else None


def load(folder: str) -> dict[str, dict]:
    out = {}
    for f in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("version") == 1 and "elements" in d:
            out[os.path.basename(f)] = d
    return out


class Mapping:
    """Approved before -> after values, by kind."""

    def __init__(self, proposals: dict | None, all_approved: bool):
        self.colors: list[tuple[C.Color, C.Color, str]] = []  # (from, to, decision id)
        self.lengths: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
        self.shadows: list[tuple[str, str, str]] = []
        self.allowed_colors: list[tuple[C.Color, str]] = []  # survivors / tokens: any change *to* one of these from an approved member
        self.approved_ids: list[str] = []
        if not proposals:
            return
        # a decision inherits its group's answer unless it has its own
        group_of: dict[str, dict] = {}
        for g in proposals.get("groups", []):
            for did in g.get("decisions", []):
                group_of[did] = g
        by_id = {d["id"]: d for d in proposals.get("decisions", [])}

        def approved(d: dict) -> bool:
            if d.get("approved") is True:
                return True
            if d.get("approved") is False:
                return False
            g = group_of.get(d["id"])
            if g and g.get("approved") is True:
                return True
            if g and g.get("approved") is False:
                return False
            return all_approved

        for d in proposals.get("decisions", []):
            if not approved(d):
                continue
            self.approved_ids.append(d["id"])
            area = d.get("area")
            if area == "color":
                to = C.parse(d.get("survivor") or "")
                if not to:
                    continue
                # a fold redirects the whole cluster to another cluster's survivor
                target = d
                hops = 0
                while target.get("fold_into") and target["fold_into"] in by_id and approved(by_id[target["fold_into"]]) and hops < 5:
                    target = by_id[target["fold_into"]]
                    hops += 1
                to = C.parse(target.get("survivor") or "") or to
                self.allowed_colors.append((to, d["id"]))
                for m in d.get("members", []):
                    frm = C.parse(m["value"])
                    if frm:
                        self.colors.append((frm, to, d["id"]))
            elif area in ("spacing", "radius", "font_size"):
                kind = {"spacing": "spacing", "radius": "radius", "font_size": "font-size"}[area]
                self.lengths[kind].append((float(d["from"]), float(d["to"]), d["id"]))
            elif area == "shadow":
                self.shadows.append((d.get("from_normalized") or d["from"], d.get("to_normalized") or d["to"], d["id"]))
            elif area == "heading":
                s = d.get("survivor") or {}
                for m in d.get("members", []):
                    if m.get("size") and s.get("size"):
                        self.lengths["font-size"].append((float(m["size"]), float(s["size"]), d["id"]))
                    c_from, c_to = C.parse(m.get("color") or ""), C.parse(s.get("color") or "")
                    if c_from and c_to:
                        self.colors.append((c_from, c_to, d["id"]))
            elif area in ("button", "input", "card", "badge"):
                surv = (d.get("survivor") or {}).get("signature", {})
                for v in d.get("variants", [])[1:]:
                    sig = v.get("signature", {})
                    for k in set(sig) | set(surv):
                        a, b = sig.get(k), surv.get(k)
                        if a is None or b is None or a == b:
                            continue
                        if k in COLOR_PROPS:
                            ca, cb = C.parse(a), C.parse(b)
                            if ca and cb:
                                self.colors.append((ca, cb, d["id"]))
                        elif k == "box-shadow":
                            self.shadows.append((a, b, d["id"]))
                        else:
                            pa, pb = px(a), px(b)
                            if pa is not None and pb is not None:
                                kind = "radius" if k == "border-radius" else "font-size" if k == "font-size" else "spacing"
                                self.lengths[kind].append((pa, pb, d["id"]))
                            elif k == "font-weight":
                                self.lengths["font-weight"].append((float(a), float(b), d["id"]))

    def color_ok(self, a: str, b: str) -> str | None:
        ca, cb = C.parse(a), C.parse(b)
        if not ca or not cb:
            return None
        if C.delta(ca, cb) < 0.004 and abs(ca[3] - cb[3]) < 0.02:
            return "same"
        for frm, to, did in self.colors:
            if C.delta(ca, frm) < 0.006 and C.delta(cb, to) < 0.006:
                return did
        return None

    def length_ok(self, kind: str, a: str, b: str) -> str | None:
        pa, pb = px(a), px(b)
        if pa is None or pb is None:
            return None
        if abs(pa - pb) < 0.01:
            return "same"
        for frm, to, did in self.lengths.get(kind, []):
            if abs(pa - frm) < 0.51 and abs(pb - to) < 0.51:
                return did
        return None

    def shadow_ok(self, a: str, b: str) -> str | None:
        na, nb = norm_shadow(a), norm_shadow(b)
        if na == nb:
            return "same"
        for frm, to, did in self.shadows:
            if norm_shadow(frm) == na and norm_shadow(to) == nb:
                return did
        return None


def norm_shadow(s: str) -> str:
    def repl(m):
        c = C.parse(m.group(0))
        return C.to_hex(c) if c else m.group(0)
    s = re.sub(r"(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^)]*\)", repl, s or "")
    layers = [l.strip() for l in re.split(r",(?![^(]*\))", s) if l.strip()]
    kept = [l for l in layers if not (re.search(r"#[0-9a-f]{6}00\b", l) and not re.search(r"(?<![\d.])[1-9]\d*(?:\.\d+)?px", l))]
    return ", ".join(kept) if kept else "none"


def match_elements(before: dict, after: dict, tolerance: float) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Pair elements across snapshots: by selector path first, then by tag+text+position."""
    a_by_sel = {e["sel"]: e for e in after["elements"]}
    used = set()
    pairs = []
    rest = []
    for e in before["elements"]:
        m = a_by_sel.get(e["sel"])
        if m and m["t"] == e["t"] and id(m) not in used:
            pairs.append((e, m))
            used.add(id(m))
        else:
            rest.append(e)
    remaining_after = [e for e in after["elements"] if id(e) not in used]
    still = []
    for e in rest:
        cand = None
        for m in remaining_after:
            if id(m) in used or m["t"] != e["t"]:
                continue
            if (e.get("txt") or "") != (m.get("txt") or ""):
                continue
            if all(abs(x - y) <= max(tolerance, 2) for x, y in zip(e["r"], m["r"])):
                cand = m
                break
        if cand:
            pairs.append((e, cand))
            used.add(id(cand))
        else:
            still.append(e)
    added = [e for e in after["elements"] if id(e) not in used]
    return pairs, still, added


def compare_screen(name: str, before: dict, after: dict, mapping: Mapping, tolerance: float) -> dict:
    pairs, removed, added = match_elements(before, after, tolerance)
    layout, text, approved, unapproved = [], [], [], []
    for b, a in pairs:
        if any(abs(x - y) > tolerance for x, y in zip(b["r"], a["r"])):
            layout.append({"sel": b["sel"], "tag": b["t"], "text": b.get("txt", ""), "component": " < ".join(b.get("rc", [])[:2]), "before": b["r"], "after": a["r"]})
        if (b.get("txt") or "") != (a.get("txt") or ""):
            text.append({"sel": b["sel"], "before": b.get("txt", ""), "after": a.get("txt", "")})
        sb = before["styles"][b["s"]] if 0 <= b["s"] < len(before["styles"]) else {}
        sa = after["styles"][a["s"]] if 0 <= a["s"] < len(after["styles"]) else {}
        for prop in sorted(set(sb) | set(sa)):
            if prop in IGNORE_PROPS:
                continue
            vb, va = sb.get(prop), sa.get(prop)
            if vb == va:
                continue
            verdict = None
            if prop in COLOR_PROPS:
                verdict = mapping.color_ok(vb or "rgba(0, 0, 0, 0)", va or "rgba(0, 0, 0, 0)")
            elif prop == "box-shadow":
                verdict = mapping.shadow_ok(vb or "none", va or "none")
            elif prop in LENGTH_PROPS:
                kind = "radius" if prop == "border-radius" else "font-size" if prop == "font-size" else "spacing"
                verdict = mapping.length_ok(kind, vb or "0px", va or "0px")
            elif prop == "font-weight":
                for frm, to, did in mapping.lengths.get("font-weight", []):
                    if vb and va and float(vb) == frm and float(va) == to:
                        verdict = did
            if verdict == "same":
                continue
            item = {"sel": b["sel"], "tag": b["t"], "text": b.get("txt", ""), "component": " < ".join(b.get("rc", [])[:2]), "prop": prop, "before": vb, "after": va, "decision": verdict}
            (approved if verdict else unapproved).append(item)
    return {"screen": name, "paired": len(pairs), "removed": [{"sel": e["sel"], "tag": e["t"], "text": e.get("txt", "")} for e in removed], "added": [{"sel": e["sel"], "tag": e["t"], "text": e.get("txt", "")} for e in added], "layout": layout, "text": text, "approved": approved, "unapproved": unapproved}


def summarize(results: list[dict], mapping: Mapping, before_only: list[str], after_only: list[str]) -> str:
    lines = ["# Before/after comparison", ""]
    total_layout = sum(len(r["layout"]) for r in results)
    total_un = sum(len(r["unapproved"]) for r in results)
    total_ok = sum(len(r["approved"]) for r in results)
    verdict = "PASS" if not total_layout and not total_un else "FAIL"
    lines.append(f"**{verdict}**: {total_ok} approved style changes, {total_un} unapproved, {total_layout} layout changes across {len(results)} screens. Approved decisions in mapping: {', '.join(mapping.approved_ids) or 'none'}.")
    if before_only or after_only:
        lines.append(f"Unpaired snapshot files: before only {before_only or '-'}; after only {after_only or '-'}.")
    lines.append("")
    for r in results:
        lines.append(f"## {r['screen']}: {r['paired']} elements paired, {len(r['removed'])} removed, {len(r['added'])} added")
        lines.append("")
        if r["layout"]:
            lines.append(f"### Layout changed ({len(r['layout'])})")
            for it in r["layout"][:25]:
                lines.append(f"- `{it['sel'][-80:]}` {it['component']} “{it['text'][:30]}”: {it['before']} → {it['after']}")
            if len(r["layout"]) > 25:
                lines.append(f"- ... {len(r['layout']) - 25} more")
            lines.append("")
        if r["unapproved"]:
            lines.append(f"### Unapproved style changes ({len(r['unapproved'])})")
            grouped = defaultdict(list)
            for it in r["unapproved"]:
                grouped[(it["prop"], it["before"], it["after"])].append(it)
            for (prop, b, a), items in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:30]:
                where = "; ".join(f"{it['component'] or it['tag']} “{it['text'][:20]}”" if it["text"] else (it["component"] or it["tag"]) for it in items[:3])
                lines.append(f"- {prop}: `{b}` → `{a}` ({len(items)}×: {where})")
            lines.append("")
        if r["approved"]:
            grouped = defaultdict(int)
            for it in r["approved"]:
                grouped[(it["decision"], it["prop"], it["before"], it["after"])] += 1
            lines.append(f"### Approved changes ({len(r['approved'])})")
            for (did, prop, b, a), n in sorted(grouped.items(), key=lambda kv: -kv[1])[:30]:
                lines.append(f"- {did} {prop}: `{b}` → `{a}` ({n}×)")
            lines.append("")
        if r["text"]:
            lines.append(f"### Text changed ({len(r['text'])})")
            for it in r["text"][:10]:
                lines.append(f"- `{it['sel'][-60:]}`: “{it['before'][:30]}” → “{it['after'][:30]}”")
            lines.append("")
        if r["removed"] or r["added"]:
            lines.append(f"### Structure: {len(r['removed'])} removed, {len(r['added'])} added (DOM changed; check these by eye)")
            for it in r["removed"][:8]:
                lines.append(f"- removed <{it['tag']}> “{it['text'][:30]}” `{it['sel'][-60:]}`")
            for it in r["added"][:8]:
                lines.append(f"- added <{it['tag']}> “{it['text'][:30]}” `{it['sel'][-60:]}`")
            lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare before/after design-catalog snapshots.")
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--mapping", default=None, help="proposals.json with approved decisions")
    ap.add_argument("--all-approved", action="store_true", help="treat every decision not explicitly rejected as approved")
    ap.add_argument("--tolerance", type=float, default=1.0, help="px tolerance for layout boxes (default 1)")
    ap.add_argument("--out", default=None, help="write the Markdown report here (default: print)")
    ap.add_argument("--json", default=None, help="also write machine-readable results")
    args = ap.parse_args(argv)
    before, after = load(args.before), load(args.after)
    if not before or not after:
        print("no snapshots found in one of the folders", file=sys.stderr)
        return 2
    proposals = None
    if args.mapping and os.path.exists(args.mapping):
        with open(args.mapping, encoding="utf-8") as fh:
            proposals = json.load(fh)
    mapping = Mapping(proposals, args.all_approved)
    common = sorted(set(before) & set(after))
    results = [compare_screen(n, before[n], after[n], mapping, args.tolerance) for n in common]
    md = summarize(results, mapping, sorted(set(before) - set(after)), sorted(set(after) - set(before)))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md)
        print(md.splitlines()[2])
        print(f"report written to {args.out}")
    else:
        print(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"screens": results, "approved_ids": mapping.approved_ids}, fh, indent=1)
    failed = any(r["layout"] or r["unapproved"] for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
