#!/usr/bin/env python3
"""Structural validator for a Product Map folder (default: ./product).

Dependency-free (Python 3.8+). Checks the contract described in
references/format.md:

  - README.md, features.md and flows/*.md exist
  - feature IDs are present, well-formed and unique
  - flow frontmatter has id, title, features, status; id matches the file name
  - every feature ID referenced by a flow exists
  - relative links and #anchors between Product Map files resolve
  - each flow has one Mermaid flowchart with sane syntax
  - likely duplicated flows are flagged

Usage:
    python3 validate.py [path/to/product] [--json]

With no path it validates ./product, or, when this file has been copied into
the Product Map folder itself (product/validate.py), that folder.

Exit code 1 when there are errors, 0 otherwise (warnings do not fail).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STATUS_VALUES = {"active", "planned", "deprecated"}
MERMAID_RESERVED = {"end", "graph", "subgraph", "style", "class", "click", "default", "linkStyle", "classDef"}
UNCLEAR = "⚠️ Behavior unclear from the current implementation."
DISAGREE = "⚠️ UI and code disagree:"
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Mermaid node shapes: longer delimiters first so `([` is not read as `(`.
# The asymmetric shape `A>text]` only counts when `>` directly follows an id, so `-->` is not an opener.
SHAPE_OPEN = r"(?:\(\[|\[\(|\[/|\[\\|\[\[|\(\(|\{\{|\[|\(|\{|(?<=\w)>)"
SHAPE_CLOSE = r"(?:\]\)|\)\]|/\]|\\\]|\]\]|\)\)|\}\}|\]|\)|\})"
SHAPE_LABEL_RE = re.compile(SHAPE_OPEN + r"([^\]\)\}]*?)" + SHAPE_CLOSE)
NODE_DEF_RE = re.compile(r"([A-Za-z_][\w-]*)\s*" + SHAPE_OPEN)
MERMAID_KEYWORD_RE = re.compile(r"^(subgraph|end|style|classDef|class|linkStyle|click|direction)(?![\w-])")
EDGE_RE = re.compile(r"(-->|---|-\.->|==>|-\.-|--|==|\.-)")


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def _add(self, level: str, path: str, msg: str, line: int | None = None) -> None:
        self.items.append({"level": level, "path": path, "line": line, "message": msg})

    def error(self, path, msg, line=None):
        self._add("error", path, msg, line)

    def warn(self, path, msg, line=None):
        self._add("warning", path, msg, line)

    def info(self, path, msg, line=None):
        self._add("info", path, msg, line)

    @property
    def errors(self):
        return [i for i in self.items if i["level"] == "error"]

    @property
    def warnings(self):
        return [i for i in self.items if i["level"] == "warning"]


# ---------------------------------------------------------------- helpers

def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def slugify(heading: str) -> str:
    """GitHub-style heading anchor."""
    text = heading.strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\- ]", "", text)
    return text.strip().replace(" ", "-")


def heading_anchors(md: str) -> set[str]:
    anchors: set[str] = set()
    counts: Counter = Counter()
    for line in strip_fences(md).splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            base = slugify(m.group(2))
            n = counts[base]
            counts[base] += 1
            anchors.add(base if n == 0 else f"{base}-{n}")
    return anchors


def parse_frontmatter(md: str):
    """Tiny YAML subset: scalars, inline lists, block lists. Returns (dict, body_start_line)."""
    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0
    data: dict = {}
    key = None
    for i, raw in enumerate(lines[1:], start=2):
        if raw.strip() == "---":
            return data, i
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m_item = re.match(r"^\s*-\s*(.*)$", raw)
        if m_item and key is not None and isinstance(data.get(key), list):
            data[key].append(_scalar(m_item.group(1)))
            continue
        m_kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if m_kv:
            key, val = m_kv.group(1), m_kv.group(2).strip()
            if val == "":
                data[key] = []
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                data[key] = [_scalar(v) for v in inner.split(",")] if inner else []
            else:
                data[key] = _scalar(val)
            continue
        # unknown line inside frontmatter; ignore
    return None, 0  # no closing ---


def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def strip_fences(md: str) -> str:
    out, fence = [], None
    for line in md.splitlines():
        m = re.match(r"^(`{3,}|~{3,})", line)
        if m:
            if fence is None:
                fence = m.group(1)[0] * len(m.group(1))
            elif line.startswith(fence):
                fence = None
            out.append("")
            continue
        out.append("" if fence else line)
    return "\n".join(out)


def mermaid_blocks(md: str) -> list[tuple[int, str]]:
    blocks, cur, start = [], None, 0
    for n, line in enumerate(md.splitlines(), start=1):
        if cur is None and re.match(r"^`{3,}\s*mermaid\s*$", line):
            cur, start = [], n
        elif cur is not None and re.match(r"^`{3,}\s*$", line):
            blocks.append((start, "\n".join(cur)))
            cur = None
        elif cur is not None:
            cur.append(line)
    return blocks


def section(md: str, title: str) -> str | None:
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", md, re.M | re.S)
    return m.group(1) if m else None


# ---------------------------------------------------------------- checks

def check_links(rep: Report, product: str, rel: str, md: str, flows_dir_name="flows") -> None:
    path = os.path.join(product, rel)
    base = os.path.dirname(path)
    for n, line in enumerate(strip_fences(md).splitlines(), start=1):
        for text, target in LINK_RE.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("//"):
                continue  # external
            file_part, _, anchor = target.partition("#")
            if file_part == "":
                target_path = path
            else:
                target_path = os.path.normpath(os.path.join(base, file_part))
            if not os.path.exists(target_path):
                inside = os.path.abspath(target_path).startswith(os.path.abspath(product))
                if inside or file_part.endswith(".md"):
                    rep.error(rel, f"broken link: [{text}]({target}) -> {os.path.relpath(target_path, product)} does not exist", n)
                else:
                    rep.warn(rel, f"link target not found (outside /product, maybe a repo path): {target}", n)
                continue
            if anchor and target_path.endswith(".md"):
                if anchor not in heading_anchors(read(target_path)):
                    rep.error(rel, f"broken anchor: [{text}]({target}) has no heading matching #{anchor}", n)


def check_mermaid(rep: Report, rel: str, start_line: int, code: str) -> None:
    lines = [l for l in code.splitlines() if l.strip() and not l.strip().startswith("%%")]
    if not lines:
        rep.error(rel, "mermaid block is empty", start_line)
        return
    header = lines[0].strip()
    if not re.match(r"^(flowchart|graph)\s+(TD|TB|LR|RL|BT)\b", header):
        rep.error(rel, f"mermaid block must start with 'flowchart TD' (or LR); found '{header}'", start_line)
        return
    defined: set[str] = set()
    referenced: set[str] = set()
    token_re = re.compile(r"(?<![\w\"'\[\]{}()|/\\>-])([A-Za-z_][\w-]*)(?![\w-])")
    for off, raw in enumerate(lines[1:], start=1):
        ln = start_line + off + 1
        s = raw.strip()
        if MERMAID_KEYWORD_RE.match(s):
            continue
        # Bracket balance (ignoring quoted text)
        unq = re.sub(r'"[^"]*"', '""', s)
        for o, c in ("[]", "()", "{}"):
            if unq.count(o) != unq.count(c):
                rep.error(rel, f"mermaid: unbalanced '{o}{c}' in line: {s}", ln)
        # Unquoted special characters inside labels
        for m in SHAPE_LABEL_RE.finditer(unq):
            label = m.group(1)
            if '""' in label:
                continue
            if re.search(r"[()\[\]{}|#;<>]", label):
                rep.warn(rel, f"mermaid: a label in '{s}' contains ( ) [ ] {{ }} | # ; < or >; quote it, e.g. A[\"Export (PDF)\"]", ln)
                break
        # Node ids
        for m in NODE_DEF_RE.finditer(unq):
            defined.add(m.group(1))
        # Strip labels and edge labels, then collect bare identifiers as references
        stripped = re.sub(r"\|[^|]*\|", "|", unq)
        stripped = SHAPE_LABEL_RE.sub("", stripped)
        stripped = EDGE_RE.sub(" ", stripped)
        stripped = re.sub(r"&", " ", stripped)
        for m in token_re.finditer(stripped):
            tok = m.group(1)
            referenced.add(tok)
            if tok in MERMAID_RESERVED:
                rep.error(rel, f"mermaid: '{tok}' is a reserved word and cannot be a node id", ln)
    only_ref = {t for t in referenced - defined if t not in MERMAID_RESERVED}
    for t in sorted(only_ref):
        rep.warn(rel, f"mermaid: node '{t}' is used but never given a label (typo, or an unlabeled node)", start_line)
    node_count = len(defined | referenced)
    if node_count > 20:
        rep.warn(rel, f"mermaid: {node_count} nodes; consider splitting into another flow or subflow (target 6-15)", start_line)
    if node_count < 3:
        rep.warn(rel, f"mermaid: only {node_count} nodes; a flow usually needs a few steps and at least one decision or outcome", start_line)


def validate(product: str) -> Report:
    rep = Report()
    if not os.path.isdir(product):
        rep.error(product, "Product Map folder does not exist")
        return rep

    readme_p = os.path.join(product, "README.md")
    features_p = os.path.join(product, "features.md")
    flows_d = os.path.join(product, "flows")
    for p, label in ((readme_p, "README.md"), (features_p, "features.md")):
        if not os.path.isfile(p):
            rep.error(label, "required file is missing")
    if not os.path.isdir(flows_d):
        rep.error("flows/", "required folder is missing")
    if rep.errors:
        return rep

    # ---- Feature Map
    features_md = read(features_p)
    feature_ids: dict[str, int] = {}
    feature_flows: dict[str, set[str]] = defaultdict(set)
    area_count = 0
    current_feature = None
    current_line = 0
    awaiting_id = False
    for n, line in enumerate(strip_fences(features_md).splitlines(), start=1):
        if line.startswith("## "):
            area_count += 1
        if line.startswith("### "):
            if awaiting_id and current_feature:
                rep.error("features.md", f"feature '{current_feature}' has no **ID:** line", current_line)
            current_feature, current_line, awaiting_id = line[4:].strip(), n, True
            continue
        m = re.match(r"^\*\*ID:\*\*\s*`?([^`\s]+)`?\s*$", line)
        if m and current_feature:
            fid = m.group(1)
            awaiting_id = False
            if not ID_RE.match(fid):
                rep.error("features.md", f"feature ID '{fid}' is not kebab-case", n)
            if fid in feature_ids:
                rep.error("features.md", f"duplicate feature ID '{fid}' (first defined line {feature_ids[fid]})", n)
            else:
                feature_ids[fid] = n
            current_fid = fid
            continue
        m = re.match(r"^\*\*Status:\*\*\s*`?([^`\s]+)`?", line)
        if m and current_feature and m.group(1) not in STATUS_VALUES:
            rep.error("features.md", f"feature status '{m.group(1)}' must be one of {sorted(STATUS_VALUES)}", n)
        m = re.match(r"^\*\*Flows:\*\*\s*(.*)$", line)
        if m and current_feature and not awaiting_id:
            for _, target in LINK_RE.findall(m.group(1)):
                fname = os.path.basename(target.split("#")[0])
                if fname.endswith(".md"):
                    feature_flows[current_fid].add(fname[:-3])
    if awaiting_id and current_feature:
        rep.error("features.md", f"feature '{current_feature}' has no **ID:** line", current_line)
    if not feature_ids:
        rep.error("features.md", "no features found (expected '### Name' headings each followed by an **ID:** line)")
    if area_count == 0:
        rep.warn("features.md", "no '## Area' headings; group features into product areas so the map is scannable")
    check_links(rep, product, "features.md", features_md)

    # ---- Flows
    flow_files = sorted(f for f in os.listdir(flows_d) if f.endswith(".md"))
    if not flow_files:
        rep.error("flows/", "no flow files found")
    flow_ids: dict[str, str] = {}
    flow_titles: dict[str, list[str]] = defaultdict(list)
    flow_feature_sets: dict[frozenset, list[str]] = defaultdict(list)
    flow_features: dict[str, set[str]] = {}
    for fname in flow_files:
        rel = f"flows/{fname}"
        md = read(os.path.join(flows_d, fname))
        fm, body_start = parse_frontmatter(md)
        stem = fname[:-3]
        if fm is None:
            rep.error(rel, "missing or unterminated YAML frontmatter (--- ... ---)", 1)
            fm = {}
        for key in ("id", "title", "features", "status"):
            if key not in fm or fm[key] in ("", []) and key != "features":
                rep.error(rel, f"frontmatter is missing required key '{key}'", 1)
        fid = str(fm.get("id", stem))
        if fm.get("id") and fid != stem:
            rep.error(rel, f"frontmatter id '{fid}' must match the file name '{stem}'", 1)
        if not ID_RE.match(fid):
            rep.error(rel, f"flow id '{fid}' is not kebab-case", 1)
        if fid in flow_ids:
            rep.error(rel, f"duplicate flow id '{fid}' (also in {flow_ids[fid]})", 1)
        flow_ids[fid] = rel
        status = str(fm.get("status", ""))
        if status and status not in STATUS_VALUES:
            rep.error(rel, f"status '{status}' must be one of {sorted(STATUS_VALUES)}", 1)
        feats = fm.get("features", [])
        if isinstance(feats, str):
            feats = [feats]
            rep.error(rel, "'features' must be a list (use '- feature-id' lines)", 1)
        feats = [str(f) for f in feats]
        if not feats:
            rep.warn(rel, "flow lists no features; link it to the Feature Map entries it exercises", 1)
        for f in feats:
            if f not in feature_ids:
                rep.error(rel, f"references unknown feature '{f}' (not defined in features.md)", 1)
        flow_features[fid] = set(feats)
        title = str(fm.get("title", "")).strip()
        if title:
            flow_titles[title.lower()].append(rel)
        if len(feats) >= 2:
            flow_feature_sets[frozenset(feats)].append(rel)

        body = md
        if section(body, "Goal") is None:
            rep.warn(rel, "missing '## Goal' section")
        flow_sec = section(body, "Flow")
        if flow_sec is None:
            rep.error(rel, "missing '## Flow' section with the Mermaid diagram")
        blocks = mermaid_blocks(body)
        if not blocks:
            rep.error(rel, "no ```mermaid block found; the flowchart is the primary artifact")
        elif flow_sec is not None and not mermaid_blocks(flow_sec):
            rep.error(rel, "the mermaid diagram must be inside the '## Flow' section, not under another heading")
        else:
            if len(blocks) > 1:
                rep.warn(rel, f"{len(blocks)} mermaid blocks; a flow should have one diagram (split into another flow if needed)")
            for start, code in blocks:
                check_mermaid(rep, rel, start, code)
        if UNCLEAR.split(" ", 1)[1] in body and UNCLEAR not in body:
            rep.warn(rel, f"unclear-behavior marker should be written exactly as: {UNCLEAR}")
        check_links(rep, product, rel, body)

    # ---- Cross references
    for fid, flows in feature_flows.items():
        for fl in flows:
            if fl in flow_features and fid not in flow_features[fl]:
                rep.warn("features.md", f"feature '{fid}' links to flow '{fl}' but that flow's frontmatter does not list '{fid}'")
    referenced_by_flows = set().union(*flow_features.values()) if flow_features else set()
    for fid in feature_ids:
        if fid not in referenced_by_flows and fid not in feature_flows:
            rep.info("features.md", f"feature '{fid}' is not part of any flow (fine for settings-like features)", feature_ids[fid])
    for title, rels in flow_titles.items():
        if len(rels) > 1:
            rep.warn("flows/", f"flows with the same title '{title}': {', '.join(rels)} (duplicate flow?)")
    for fs, rels in flow_feature_sets.items():
        if len(rels) > 1:
            rep.warn("flows/", f"flows with identical feature sets {sorted(fs)}: {', '.join(rels)} (duplicate or mergeable flow?)")

    # ---- README
    readme_md = read(readme_p)
    check_links(rep, product, "README.md", readme_md)
    linked = {os.path.basename(t.split("#")[0]) for _, t in LINK_RE.findall(strip_fences(readme_md))}
    for fname in flow_files:
        if fname not in linked:
            rep.warn("README.md", f"does not link to flows/{fname}; every major flow should be reachable from the README")
    if "features.md" not in {t.split("#")[0] for _, t in LINK_RE.findall(strip_fences(readme_md))}:
        rep.warn("README.md", "does not link to features.md")
    if len(readme_md.splitlines()) > 90:
        rep.warn("README.md", "is long; it should be readable in under a minute")

    # ---- Summary info
    all_text = "".join(read(os.path.join(product, p)) for p in ["README.md", "features.md"] + [f"flows/{f}" for f in flow_files])
    rep.info("product/", f"{len(feature_ids)} features, {len(flow_files)} flows, {all_text.count(UNCLEAR)} unclear-behavior markers, {all_text.count(DISAGREE)} UI/code disagreements")
    return rep


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if args:
        product = args[0]
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        # Default: ./product, or the folder this script was copied into (product/validate.py).
        product = "product" if os.path.isdir("product") else (here if os.path.isfile(os.path.join(here, "features.md")) else "product")
    rep = validate(product)
    if as_json:
        print(json.dumps({"errors": len(rep.errors), "warnings": len(rep.warnings), "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        for it in rep.items:
            loc = f"{it['path']}:{it['line']}" if it["line"] else it["path"]
            print(f"{it['level']:<7} {loc}: {it['message']}")
        print()
        print(f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
        print("Product Map is structurally valid." if not rep.errors else "Product Map has errors.")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
