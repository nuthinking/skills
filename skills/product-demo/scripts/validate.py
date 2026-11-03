#!/usr/bin/env python3
"""Structural validator for a product demos folder (default: ./product/demos).

Dependency-free (Python 3.8+). Checks the contract described in
references/format.md:

  - demo files parse (the YAML subset the format allows)
  - id, title, start and steps are present; id matches the file name
  - every step has a known action with the keys that action needs
  - targets are not positional unless the step says so in its label
  - the referenced flow exists, and step labels match its Mermaid node labels
  - style, device, theme, background, intro, outro, output, captions and cursor settings are well-formed
  - narration is all or nothing
  - config.json parses: url, serve, auth, store, defaults

Usage:
    python3 validate.py [path/to/product/demos | path/to/product] [--json]

With no path it validates ./product/demos, or, when this file has been copied
into the demos folder itself (product/demos/validate.py), that folder.

Exit code 1 when there are errors, 0 otherwise (warnings do not fail).
"""
from __future__ import annotations

import json
import os
import re
import sys

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VIEWPORT_RE = re.compile(r"^\d{3,4}x\d{3,4}$")
STYLES = {"neutral", "device", "perspective"}
DEVICES = {"browser", "laptop", "phone"}
THEMES = {"light", "dark"}
# Keep in step with WALLPAPERS in the package (src/render/look.ts and src/validate.ts).
WALLPAPERS = ["clay", "dusk", "dusk-2", "ember", "harbour", "heather", "lagoon", "mesh", "mist", "moss", "plum", "sage", "sand", "steel", "tide"]
COLOR_RE = re.compile(r"^(#[0-9a-fA-F]{3,8}|(rgb|hsl)a?\(.*\))$")
LOOK_KEYS = ["style", "device", "theme", "background", "intro", "outro", "output", "captions", "cursor", "highlight", "address"]
TOP_KEYS = {"id", "title", "flow", "description", "viewport", "setup", "start", "watch", "narration", "steps", *LOOK_KEYS}
OUTPUT_KEYS = {"width": int, "height": int, "scale": int, "fps": int, "quality": ("draft", "good", "high"), "format": ("mp4", "webm", "gif"), "loop": bool}
AUTH_STRATEGIES = {"form", "script", "state"}
STORE_TARGETS = {"none", "s3"}
STEP_COMMON = {"do", "label", "say", "settle", "zoom", "highlight"}
ACTIONS = {
    # action: (required keys, one-of groups, optional keys)
    "click": ({"target"}, [], set()),
    "type": ({"target", "text"}, [], set()),
    "press": ({"key"}, [], set()),
    "hover": ({"target"}, [], set()),
    "scroll": (set(), [{"target", "to"}], set()),
    "navigate": ({"url"}, [], set()),
    "wait": (set(), [{"target", "ms"}], set()),
    "select": ({"target", "value"}, [], set()),
    "upload": ({"target", "file"}, [], set()),
}
POSITIONAL_RE = re.compile(r"nth-child|nth-of-type|>>\s*nth=|\bnth=\d|:nth\(")
MAX_STEPS = 25
MAX_SAY_WORDS = 28

# Mermaid node shapes, same regexes as the product-map validator.
SHAPE_OPEN = r"(\(\[|\[\(|\[/|\[\\|\[\[|\(\(|\{\{|\[|\(|\{|(?<=\w)>)"
SHAPE_CLOSE = r"(?:\]\)|\)\]|/\]|\\\]|\]\]|\)\)|\}\}|\]|\)|\})"
NODE_RE = re.compile(r"([A-Za-z_][\w-]*)\s*" + SHAPE_OPEN + r"([^\]\)\}]*?)" + SHAPE_CLOSE)


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


# ---------------------------------------------------------------- YAML subset

class YamlError(Exception):
    def __init__(self, msg: str, line: int) -> None:
        super().__init__(msg)
        self.line = line


KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$")


def _strip_comment(v: str) -> str:
    if v[:1] in ("'", '"'):
        return v
    return re.split(r"\s+#", v, maxsplit=1)[0].rstrip()


def _scalar(v: str, line: int):
    v = _strip_comment(v.strip())
    if v == "" or v in ("~", "null"):
        return None
    if v[:1] in ("'", '"'):
        q = v[0]
        m = re.match(r'"((?:[^"\\]|\\.)*)"' if q == '"' else r"'((?:[^']|'')*)'", v)
        if not m:
            raise YamlError(f"unterminated quoted string: {v}", line)
        tail = v[m.end():].strip()
        if tail and not tail.startswith("#"):
            raise YamlError(f"unexpected text after quoted string: {tail}", line)
        inner = m.group(1)
        return inner.replace('\\"', '"') if q == '"' else inner.replace("''", "'")
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x, line) for x in inner.split(",")] if inner else []
    if v.startswith("{") or v.startswith("&") or v.startswith("*") or v in ("|", ">"):
        raise YamlError(f"unsupported YAML ('{v[:1]}'): use plain scalars, block lists and block maps", line)
    low = v.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def parse_yaml(text: str):
    """Parses the subset the format allows. Returns a dict/list/scalar, or raises YamlError."""
    lines: list[list] = []
    for no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip(" ").startswith("\t"):
            raise YamlError("tabs are not allowed for indentation", no)
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append([indent, raw.strip(), no])
    if not lines:
        return None
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YamlError(f"unexpected line: {lines[i][1]}", lines[i][2])
    return value


def _is_item(s: str) -> bool:
    return s == "-" or s.startswith("- ")


def _parse_block(lines, i, indent):
    if _is_item(lines[i][1]):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out: dict = {}
    while i < len(lines) and lines[i][0] == indent and not _is_item(lines[i][1]):
        _, s, ln = lines[i]
        m = KEY_RE.match(s)
        if not m:
            raise YamlError(f"expected 'key: value', got '{s}'", ln)
        key, val = m.group(1), m.group(2)
        if key in out:
            raise YamlError(f"duplicate key '{key}'", ln)
        i += 1
        if val is None or _strip_comment(val.strip()) == "":
            if i < len(lines) and lines[i][0] > indent:
                out[key], i = _parse_block(lines, i, lines[i][0])
            else:
                out[key] = None
        else:
            out[key] = _scalar(val, ln)
    if i < len(lines) and lines[i][0] > indent:
        raise YamlError(f"bad indentation: {lines[i][1]}", lines[i][2])
    return out, i


def _parse_list(lines, i, indent):
    out: list = []
    while i < len(lines) and lines[i][0] == indent and _is_item(lines[i][1]):
        ind, s, ln = lines[i]
        rest = s[1:].strip()
        if rest == "":
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                v, i = _parse_block(lines, i, lines[i][0])
                out.append(v)
            else:
                out.append(None)
            continue
        if KEY_RE.match(rest):
            key_indent = ind + (len(s) - len(rest))
            lines[i] = [key_indent, rest, ln]
            v, i = _parse_map(lines, i, key_indent)
            out.append(v)
        else:
            out.append(_scalar(rest, ln))
            i += 1
    if i < len(lines) and lines[i][0] > indent:
        raise YamlError(f"bad indentation: {lines[i][1]}", lines[i][2])
    return out, i


def key_line(text: str, key: str, nth: int = 0) -> int | None:
    """Line number of the nth top-level-or-nested `key:` occurrence, for messages."""
    hits = [no for no, raw in enumerate(text.splitlines(), start=1) if re.match(r"^\s*(?:-\s+)?" + re.escape(key) + r":", raw)]
    return hits[nth] if nth < len(hits) else None


# ---------------------------------------------------------------- helpers

def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def mermaid_labels(md: str) -> tuple[set[str], set[str]]:
    """(all node labels, rectangle labels) from the first mermaid block of a flow file."""
    m = re.search(r"```mermaid\s*\n(.*?)```", md, re.S)
    if not m:
        return set(), set()
    all_labels: set[str] = set()
    rects: set[str] = set()
    for raw in m.group(1).splitlines():
        s = raw.strip()
        if not s or s.startswith("%%") or re.match(r"^(flowchart|graph|subgraph|end|style|classDef|class|linkStyle|click|direction)\b", s):
            continue
        s = re.sub(r"\|[^|]*\|", "|", s)
        for mm in NODE_RE.finditer(s):
            opener, label = mm.group(2), mm.group(3).strip().strip('"').strip()
            if not label:
                continue
            all_labels.add(label)
            if opener == "[":
                rects.add(label)
    return all_labels, rects


def step_loc(text: str, idx: int) -> int | None:
    return key_line(text, "do", idx)


# ---------------------------------------------------------------- checks

def check_step(rep: Report, rel: str, text: str, idx: int, step, flow_labels: set[str] | None) -> tuple[bool, str | None]:
    """Returns (has_say, label)."""
    ln = step_loc(text, idx)
    n = idx + 1
    if not isinstance(step, dict):
        rep.error(rel, f"step {n} must be a map with 'do:' and its keys", ln)
        return False, None
    do = step.get("do")
    if do not in ACTIONS:
        known = ", ".join(sorted(ACTIONS))
        rep.error(rel, f"step {n}: unknown action '{do}'; one of {known}", ln)
        return isinstance(step.get("say"), str), step.get("label")
    required, one_of, _ = ACTIONS[do]
    allowed = STEP_COMMON | required | {k for g in one_of for k in g}
    for k in sorted(required):
        if not isinstance(step.get(k), str) or not step[k].strip():
            rep.error(rel, f"step {n} ({do}): '{k}' is required", ln)
    for group in one_of:
        present = [k for k in group if step.get(k) not in (None, "")]
        if len(present) != 1:
            rep.error(rel, f"step {n} ({do}): exactly one of {', '.join(sorted(group))} is required", ln)
    for k in step:
        if k not in allowed:
            rep.warn(rel, f"step {n} ({do}): unknown key '{k}' is ignored", ln)
    label = step.get("label")
    if label is not None and not isinstance(label, str):
        rep.error(rel, f"step {n}: 'label' must be text", ln)
        label = None
    target = step.get("target")
    if isinstance(target, str) and POSITIONAL_RE.search(target):
        if not label or not re.search(r"\b(first|second|third|last|\d+(st|nd|rd|th))\b", label, re.I):
            rep.warn(rel, f"step {n}: positional target '{target}'; prefer role, test id or text, or say the position in the label", ln)
    settle = step.get("settle")
    if settle is not None and (not isinstance(settle, int) or isinstance(settle, bool) or settle < 0 or settle > 10000):
        rep.error(rel, f"step {n}: 'settle' must be milliseconds between 0 and 10000", ln)
    zoom = step.get("zoom")
    if zoom is not None and not (isinstance(zoom, (int, float)) and not isinstance(zoom, bool) and 1 < zoom <= 3) and not (isinstance(zoom, str) and zoom.strip()):
        rep.error(rel, f"step {n}: 'zoom' must be a scale between 1 and 3 or a target to move in on", ln)
    if "highlight" in step and not isinstance(step["highlight"], bool):
        rep.error(rel, f"step {n}: 'highlight' must be true or false", ln)
    say = step.get("say")
    has_say = False
    if say is not None:
        if not isinstance(say, str) or not say.strip():
            rep.error(rel, f"step {n}: 'say' must be a sentence", ln)
        else:
            has_say = True
            if len(say.split()) > MAX_SAY_WORDS:
                rep.warn(rel, f"step {n}: narration is {len(say.split())} words; keep lines under about 20 so pacing stays brisk", ln)
            if re.match(r"^\s*(now |then |next, )?(click|tap)\b", say, re.I):
                rep.warn(rel, f"step {n}: narration describes the pointer ('{say.split()[0]}…'); say what happens and why instead", ln)
    if label and flow_labels is not None and label not in flow_labels:
        rep.warn(rel, f"step {n}: label '{label}' is not a node label in the flow diagram", ln)
    return has_say, label


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_look(rep: Report, rel: str, data: dict, demos: str, line) -> None:
    output = data.get("output")
    if output is not None:
        if not isinstance(output, dict):
            rep.error(rel, "output must be a map of width, height, scale, fps, quality, format, loop", line("output"))
        else:
            for k, v in output.items():
                rule = OUTPUT_KEYS.get(k)
                if rule is None:
                    rep.warn(rel, f"output: unknown key '{k}' is ignored", line("output"))
                elif rule is int and (not _is_int(v) or v <= 0):
                    rep.error(rel, f"output.{k} must be a positive integer", line("output"))
                elif rule is bool and not isinstance(v, bool):
                    rep.error(rel, f"output.{k} must be true or false", line("output"))
                elif isinstance(rule, tuple) and v not in rule:
                    rep.error(rel, f"output.{k} must be one of {', '.join(rule)}", line("output"))
    style = data.get("style")
    if style is not None and not (isinstance(style, str) and style in STYLES):
        rep.error(rel, "style must be one of neutral, device, perspective", line("style"))
    device = data.get("device")
    if device is not None and not (isinstance(device, str) and device in DEVICES):
        rep.error(rel, "device must be one of browser, laptop, phone", line("device"))
    theme = data.get("theme")
    if theme is not None and not (isinstance(theme, str) and theme in THEMES):
        rep.error(rel, "theme must be light or dark: the colour scheme the app is recorded in", line("theme"))
    bg = data.get("background")
    if bg is not None:
        if not isinstance(bg, str) or not bg.strip():
            rep.error(rel, "background must be a wallpaper name, a CSS colour, or an image path under demos/", line("background"))
        elif bg not in WALLPAPERS and not COLOR_RE.match(bg):
            if re.search(r"[/.]", bg):
                if not os.path.exists(os.path.join(demos, bg)):
                    rep.error(rel, f"background: demos/{bg} does not exist", line("background"))
            else:
                rep.error(rel, f"background '{bg}' is not a built-in wallpaper ({', '.join(WALLPAPERS)}), a CSS colour, or an image path under demos/", line("background"))
    for k in ("intro", "outro"):
        v = data.get(k)
        if v is None or isinstance(v, bool):
            continue
        if not isinstance(v, dict):
            rep.error(rel, f"{k} must be true, false, or a map with title, subtitle, durationMs, fade", line(k))
            continue
        for kk in v:
            if kk not in ("title", "subtitle", "durationMs", "fade"):
                rep.warn(rel, f"{k}: unknown key '{kk}' is ignored", line(k))
        if "durationMs" in v and (not _is_int(v["durationMs"]) or v["durationMs"] <= 0):
            rep.error(rel, f"{k}.durationMs must be a positive integer", line(k))
        if "fade" in v and not isinstance(v["fade"], bool):
            rep.error(rel, f"{k}.fade must be true or false", line(k))
    captions = data.get("captions")
    if captions is not None and not isinstance(captions, bool):
        if not isinstance(captions, dict):
            rep.error(rel, "captions must be true, false, or a map of position, size, radius, color, background, font", line("captions"))
        else:
            for k in captions:
                if k not in ("position", "size", "radius", "color", "background", "font"):
                    rep.warn(rel, f"captions: unknown key '{k}' is ignored", line("captions"))
            if captions.get("position") is not None and captions["position"] not in ("bottom", "top", "below"):
                rep.error(rel, "captions.position must be bottom, top or below", line("captions"))
            if captions.get("size") is not None and (not _is_int(captions["size"]) or captions["size"] <= 0):
                rep.error(rel, "captions.size must be a positive integer (pixels)", line("captions"))
            for k in ("radius", "color", "background", "font"):
                if captions.get(k) is not None and not isinstance(captions[k], str):
                    rep.error(rel, f"captions.{k} must be a CSS value", line("captions"))
    cursor = data.get("cursor")
    if cursor is not None and not isinstance(cursor, bool) and not (isinstance(cursor, dict) and cursor.get("style") in (None, "arrow", "dot") and (cursor.get("size") is None or _is_int(cursor["size"]))):
        rep.error(rel, "cursor must be true, false, or { style: arrow | dot, size }", line("cursor"))
    if "highlight" in data and data["highlight"] is not None and not isinstance(data["highlight"], bool):
        rep.error(rel, "highlight must be true or false", line("highlight"))
    if "address" in data and data["address"] is not None and not isinstance(data["address"], (bool, str)):
        rep.error(rel, "address must be text, true or false", line("address"))


def check_demo(rep: Report, demos: str, fname: str, flows_dir: str | None, ids: dict) -> None:
    rel = fname
    path = os.path.join(demos, fname)
    text = read(path)
    try:
        data = parse_yaml(text)
    except YamlError as e:
        rep.error(rel, f"cannot parse: {e}", e.line)
        return
    if not isinstance(data, dict):
        rep.error(rel, "the file must be a map of keys (id, title, start, steps, …)")
        return
    stem = re.sub(r"\.ya?ml$", "", fname)
    for k in data:
        if k not in TOP_KEYS:
            rep.warn(rel, f"unknown key '{k}' is ignored", key_line(text, k))

    did = data.get("id")
    if not isinstance(did, str) or not ID_RE.match(did):
        rep.error(rel, "id is required and must be kebab-case", key_line(text, "id"))
    else:
        if did != stem:
            rep.error(rel, f"id '{did}' must equal the file name '{stem}'", key_line(text, "id"))
        if did in ids:
            rep.error(rel, f"duplicate id '{did}' (also in {ids[did]})", key_line(text, "id"))
        ids[did] = rel

    if not isinstance(data.get("title"), str) or not data["title"].strip():
        rep.error(rel, "title is required", key_line(text, "title"))

    start = data.get("start")
    if not isinstance(start, str) or not start.strip():
        rep.error(rel, "start is required: the path the demo begins on", key_line(text, "start"))
    elif not start.startswith("/"):
        rep.warn(rel, f"start '{start}' should be a path beginning with '/', joined to config.url", key_line(text, "start"))

    vp = data.get("viewport")
    if vp is not None and not (isinstance(vp, str) and VIEWPORT_RE.match(vp)):
        rep.error(rel, "viewport must look like 1440x900", key_line(text, "viewport"))

    check_look(rep, rel, data, demos, lambda k: key_line(text, k))

    watch = data.get("watch")
    if watch is not None and (not isinstance(watch, list) or not all(isinstance(w, str) and w for w in watch)):
        rep.error(rel, "watch must be a list of globs", key_line(text, "watch"))

    narration = data.get("narration")
    if narration is not None and not isinstance(narration, bool):
        rep.error(rel, "narration must be true or false", key_line(text, "narration"))

    flow_labels: set[str] | None = None
    rect_labels: set[str] = set()
    flow = data.get("flow")
    if flow is not None:
        if not isinstance(flow, str) or not ID_RE.match(flow):
            rep.error(rel, "flow must be a flow id", key_line(text, "flow"))
        elif flows_dir is None:
            rep.warn(rel, f"flow '{flow}' given but there is no product/flows folder (no Product Map)", key_line(text, "flow"))
        else:
            fpath = os.path.join(flows_dir, flow + ".md")
            if not os.path.isfile(fpath):
                rep.error(rel, f"flow '{flow}' does not exist in product/flows", key_line(text, "flow"))
            else:
                flow_labels, rect_labels = mermaid_labels(read(fpath))
                if not flow_labels:
                    flow_labels = None
    elif flows_dir is not None:
        rep.warn(rel, "no 'flow': the demo is not linked to a Product Map flow", key_line(text, "id"))

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        rep.error(rel, "steps is required and must be a non-empty list", key_line(text, "steps"))
        return
    if len(steps) > MAX_STEPS:
        rep.warn(rel, f"{len(steps)} steps; split the demo (target 4 to 12)", key_line(text, "steps"))
    says = 0
    used_labels: set[str] = set()
    for idx, step in enumerate(steps):
        has_say, label = check_step(rep, rel, text, idx, step, flow_labels)
        says += has_say
        if label:
            used_labels.add(label)
    if 0 < says < len(steps) and narration is not False:
        rep.warn(rel, f"narration on {says} of {len(steps)} steps; narrate all or none, or set narration: false", key_line(text, "steps"))
    if flow_labels is not None and used_labels:
        for lbl in sorted(rect_labels - used_labels):
            rep.info(rel, f"flow node '{lbl}' is not shown by any step (fine if it is on another path)")


def check_config(rep: Report, demos: str) -> None:
    path = os.path.join(demos, "config.json")
    if not os.path.isfile(path):
        rep.warn("config.json", "missing; the recorder needs serve and url (see references/format.md section 2)")
        return
    try:
        cfg = json.loads(read(path))
    except ValueError as e:
        rep.error("config.json", f"not valid JSON: {e}")
        return
    if not isinstance(cfg, dict):
        rep.error("config.json", "must be an object")
        return
    if not isinstance(cfg.get("url"), str) or not re.match(r"^https?://", cfg.get("url") or ""):
        rep.error("config.json", "url is required and must be an http(s) URL")
    if "serve" in cfg and (not isinstance(cfg["serve"], str) or not cfg["serve"].strip()):
        rep.error("config.json", "serve must be a command")
    if "viewport" in cfg and not (isinstance(cfg["viewport"], str) and VIEWPORT_RE.match(cfg["viewport"])):
        rep.error("config.json", "viewport must look like 1440x900")
    defaults = cfg.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            rep.error("config.json", "defaults must be a map of style, device, theme, background, intro, outro, output, captions, cursor")
        else:
            for k in defaults:
                if k not in LOOK_KEYS:
                    rep.warn("config.json", f"defaults: unknown key '{k}' is ignored")
            check_look(rep, "config.json", defaults, demos, lambda k: None)
    if "preset" in cfg:
        rep.error("config.json", "preset is gone: use defaults.style, defaults.background and defaults.device")
    store = cfg.get("store")
    if store is not None:
        if not isinstance(store, dict) or store.get("target") not in STORE_TARGETS:
            rep.error("config.json", "store.target must be one of none, s3")
        elif store.get("target") == "s3":
            for k in ("bucket", "baseUrl"):
                if not isinstance(store.get(k), str) or not store[k]:
                    rep.error("config.json", f"store.{k} is required with target s3")
            for k in ("key", "secret", "accessKeyId", "secretAccessKey", "password", "token"):
                if k in store:
                    rep.error("config.json", f"store.{k}: credentials belong in the environment, not in config")
    else:
        rep.warn("config.json", "no store: videos stay in .cache/ and CI cannot publish (see references/format.md section 8)")
    auth = cfg.get("auth")
    if auth is not None:
        if not isinstance(auth, dict) or auth.get("strategy") not in AUTH_STRATEGIES:
            rep.error("config.json", "auth.strategy must be one of form, script, state")
        else:
            st = auth["strategy"]
            if st == "form":
                steps = auth.get("steps", [])
                if not isinstance(steps, list):
                    rep.error("config.json", "auth.steps must be a list of steps (empty when opening auth.path alone signs in)")
                else:
                    for i, step in enumerate(steps, start=1):
                        if not isinstance(step, dict) or step.get("do") not in ACTIONS:
                            rep.error("config.json", f"auth.steps[{i}] must be a step with a known action")
                        elif step.get("do") == "type" and isinstance(step.get("text"), str) and not step["text"].startswith("$") and re.search(r"[@.]", step["text"]) and ("pass" in str(step.get("target", "")).lower() or "@" in step["text"]):
                            rep.warn("config.json", f"auth.steps[{i}] types a literal value; use $PRODUCT_DEMO_USER / $PRODUCT_DEMO_PASSWORD so credentials stay out of the repo")
                if not isinstance(auth.get("path"), str):
                    rep.error("config.json", "auth.path is required with the form strategy")
            elif st == "script" and not isinstance(auth.get("command"), str):
                rep.error("config.json", "auth.command is required with the script strategy")
            elif st == "state":
                if not isinstance(auth.get("path"), str):
                    rep.error("config.json", "auth.path is required with the state strategy")
                else:
                    rep.warn("config.json", "auth.strategy state is for local use only; CI needs form or script")
    if "setup" not in cfg:
        rep.warn("config.json", "no setup command: without a seed the recorded state depends on whatever the app has")


def validate(demos: str) -> Report:
    rep = Report()
    if not os.path.isdir(demos):
        rep.error(demos, "demos folder not found")
        return rep
    product = os.path.dirname(os.path.abspath(demos))
    flows_dir = os.path.join(product, "flows")
    flows_dir = flows_dir if os.path.isdir(flows_dir) else None
    check_config(rep, demos)
    files = sorted(f for f in os.listdir(demos) if re.search(r"\.ya?ml$", f))
    if not files:
        rep.warn(demos, "no demo files (*.yaml)")
    ids: dict = {}
    for fname in files:
        check_demo(rep, demos, fname, flows_dir, ids)
    return rep


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__.strip())
        return 0
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if args:
        demos = args[0]
        if os.path.basename(os.path.normpath(demos)) != "demos" and os.path.isdir(os.path.join(demos, "demos")):
            demos = os.path.join(demos, "demos")
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        demos = here if os.path.basename(here) == "demos" and os.path.isfile(os.path.join(here, "config.json")) else os.path.join("product", "demos")
    rep = validate(demos)
    if as_json:
        print(json.dumps({"errors": len(rep.errors), "warnings": len(rep.warnings), "items": rep.items}, indent=2, ensure_ascii=False))
    else:
        for it in rep.items:
            loc = f"{it['path']}:{it['line']}" if it["line"] else it["path"]
            print(f"{it['level']:<7} {loc}: {it['message']}")
        print()
        print(f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
        print("Demos are structurally valid." if not rep.errors else "Demos have errors.")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
