#!/usr/bin/env python3
"""design-catalog: scan an app's source for its stack, routes, components and every design value.

Usage:
    python3 scan_source.py [app-root] [--out .design-catalog/scan.json] [--md] [--quiet]

Writes a JSON inventory (default .design-catalog/scan.json under the app root) and, with --md,
prints a Markdown summary for reading. Standard library only; runs from any directory.

What it finds
- project: framework, versions, styling systems, UI/icon libraries, fonts, package manager,
  Tailwind version and config, shadcn, Storybook, AGENTS.md / CLAUDE.md / DESIGN.md, workspaces
- routes: file-based routes (Next app/pages, Remix/React Router, Astro, SvelteKit, Nuxt) and
  paths found in router config
- components: exported PascalCase components, where they live, how often they are used, likely kind
- tailwind: every utility of interest with counts and files, classified (color, spacing, sizing,
  radius, shadow, font_size, font_weight, font_family, leading, tracking, border, ring, opacity,
  z, motion) and variants used (hover, dark, breakpoints)
- css: colours, lengths, radii, shadows, font families, durations from stylesheets, <style> blocks,
  styled-components/emotion templates and @apply; custom properties declared and used
- inline_styles: style={{ }} and style="" occurrences with their values
- drift_signals: grey palette families mixed, arbitrary values, off-grid spacing, duplicate
  component kinds, raw palette use next to defined tokens, dark mode presence
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {
    "node_modules", ".git", ".next", "dist", "build", "out", ".turbo", ".cache", "coverage", ".vercel",
    ".design-catalog", "storybook-static", ".svelte-kit", ".nuxt", ".astro", "vendor", "__pycache__",
    ".output", "target", ".parcel-cache", ".expo", "ios", "android", "public", ".storybook",
}
CODE_EXT = {".tsx", ".jsx", ".ts", ".js", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".html", ".mdx"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
ALL_EXT = CODE_EXT | STYLE_EXT

PALETTE_FAMILIES = {
    "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime", "green",
    "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose",
    "mauve", "mist", "olive", "taupe",
}
GREY_FAMILIES = {"slate", "gray", "zinc", "neutral", "stone", "mauve", "mist", "olive", "taupe"}
SHADES = {"50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"}
TEXT_SIZES = {"xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl", "7xl", "8xl", "9xl"}
TEXT_NON_COLOR = TEXT_SIZES | {"left", "center", "right", "justify", "start", "end", "wrap", "nowrap", "balance", "pretty", "ellipsis", "clip"}
BORDER_NON_COLOR = {"0", "2", "4", "8", "solid", "dashed", "dotted", "double", "hidden", "none", "collapse", "separate", "spacing"}
SHADOW_SIZES = {"2xs", "xs", "sm", "md", "lg", "xl", "2xl", "none", "inner"}
RING_NON_COLOR = {"0", "1", "2", "4", "8", "inset"}
OUTLINE_NON_COLOR = {"none", "hidden", "0", "1", "2", "4", "8", "dashed", "dotted", "double", "solid"}
BG_NON_COLOR = {"none", "cover", "contain", "auto", "fixed", "local", "scroll", "repeat", "no-repeat", "repeat-x", "repeat-y", "repeat-round", "repeat-space", "center", "top", "bottom", "left", "right", "clip-border", "clip-padding", "clip-content", "clip-text", "origin-border", "origin-padding", "origin-content", "blend-normal"}
WEIGHTS = {"thin", "extralight", "light", "normal", "medium", "semibold", "bold", "extrabold", "black"}
COLOR_PREFIXES = ("bg", "text", "border", "border-x", "border-y", "border-t", "border-r", "border-b", "border-l", "border-s", "border-e", "ring", "ring-offset", "outline", "fill", "stroke", "from", "via", "to", "decoration", "accent", "caret", "divide", "placeholder", "shadow", "inset-ring", "inset-shadow")
SPACING_PREFIXES = ("p", "px", "py", "pt", "pr", "pb", "pl", "ps", "pe", "m", "mx", "my", "mt", "mr", "mb", "ml", "ms", "me", "gap", "gap-x", "gap-y", "space-x", "space-y", "inset", "inset-x", "inset-y", "top", "right", "bottom", "left", "start", "end", "indent", "scroll-m", "scroll-p")
SIZING_PREFIXES = ("w", "h", "size", "min-w", "max-w", "min-h", "max-h", "basis")
COLOR_FUNC_RE = re.compile(r"(#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^)]*\))")
LENGTH_RE = re.compile(r"(?<![\w.-])(-?\d*\.?\d+)(px|rem|em)\b")
DURATION_RE = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b")
STRING_RE = re.compile(r"\"((?:[^\"\\\n]|\\.)*)\"|'((?:[^'\\\n]|\\.)*)'|`((?:[^`\\]|\\.)*)`", re.S)
CLASS_TOKEN_RE = re.compile(r"^!?-?[a-z][a-z0-9]*(?:-[a-z0-9.%/]+|-\[[^\]]+\]|-\([^)]+\))*(?:/[0-9a-z.\[\]]+)?$")
COMPONENT_DIR_RE = re.compile(r"(^|/)(components?|ui|design-system|primitives|elements|atoms|molecules|organisms|shared|common|lib/ui)(/|$)")
KIND_RE = [
    ("button", re.compile(r"Button|Btn|CTA$", re.I)), ("input", re.compile(r"^(Text)?Input$|TextField|^Field$", re.I)),
    ("textarea", re.compile(r"Textarea|TextArea", re.I)), ("select", re.compile(r"Select|Combobox|Dropdown(?!Menu)", re.I)),
    ("checkbox", re.compile(r"Checkbox", re.I)), ("radio", re.compile(r"Radio", re.I)), ("switch", re.compile(r"Switch|Toggle", re.I)),
    ("menu", re.compile(r"Menu", re.I)), ("dialog", re.compile(r"Dialog|Modal|Sheet|Drawer", re.I)), ("popover", re.compile(r"Popover", re.I)),
    ("tooltip", re.compile(r"Tooltip", re.I)), ("card", re.compile(r"Card|Panel|Tile", re.I)), ("badge", re.compile(r"Badge|Pill|Chip|Tag$", re.I)),
    ("tabs", re.compile(r"Tabs?$", re.I)), ("nav", re.compile(r"Nav|Sidebar|Header|TopBar|AppBar|Breadcrumb", re.I)), ("table", re.compile(r"Table|DataGrid", re.I)),
    ("list", re.compile(r"List$|ListItem", re.I)), ("avatar", re.compile(r"Avatar", re.I)), ("alert", re.compile(r"Alert|Banner|Callout|Notice", re.I)),
    ("toast", re.compile(r"Toast|Snackbar|Notification", re.I)), ("spinner", re.compile(r"Spinner|Loader|Loading", re.I)),
    ("empty", re.compile(r"Empty", re.I)), ("skeleton", re.compile(r"Skeleton", re.I)), ("form", re.compile(r"Form|Label|Fieldset", re.I)),
    ("layout", re.compile(r"Layout|Container|Section|Stack|Grid|Page(Wrapper|Shell)?$|Footer", re.I)), ("heading", re.compile(r"Heading|Title|^H[1-6]$", re.I)),
    ("progress", re.compile(r"Progress|Meter", re.I)), ("link", re.compile(r"Link", re.I)), ("icon", re.compile(r"Icon", re.I)),
]


def rel(root: str, path: str) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def walk(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") or d in (".storybook",)]
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in ALL_EXT and not f.endswith(".d.ts") and not f.endswith(".min.js"):
                yield os.path.join(dirpath, f)


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def strip_comments(text: str, css: bool = False) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    if not css:
        text = re.sub(r"(?m)(^|[^:\\\"'`])//[^\n]*", lambda m: m.group(1), text)
    return text


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# ---------------------------------------------------------------- project facts

def load_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def detect_project(root: str, files: list[str]) -> dict:
    pkg = load_json(os.path.join(root, "package.json")) or {}
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pkg.get(key) or {})
    workspaces = pkg.get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    pnpm_ws = os.path.exists(os.path.join(root, "pnpm-workspace.yaml"))
    ws_packages = []
    patterns = list(workspaces or [])
    if pnpm_ws:
        for line in read(os.path.join(root, "pnpm-workspace.yaml")).splitlines():
            m = re.match(r"\s*-\s*['\"]?([^'\"#]+)", line)
            if m:
                patterns.append(m.group(1).strip())
    for pat in patterns:
        base = pat.split("*")[0].rstrip("/")
        d = os.path.join(root, base)
        if pat.endswith("*") and os.path.isdir(d):
            for sub in sorted(os.listdir(d)):
                if os.path.exists(os.path.join(d, sub, "package.json")):
                    ws_packages.append(f"{base}/{sub}")
        elif os.path.exists(os.path.join(root, pat, "package.json")):
            ws_packages.append(pat)

    def has(*names):
        return next((n for n in names if n in deps), None)

    def ver(name):
        v = deps.get(name)
        return re.sub(r"^[\^~>=<\s]*", "", v) if isinstance(v, str) else None

    framework = None
    for name, label in (("next", "next"), ("@remix-run/react", "remix"), ("react-router", "react-router"), ("gatsby", "gatsby"), ("astro", "astro"), ("@tanstack/react-start", "tanstack-start"), ("@sveltejs/kit", "sveltekit"), ("nuxt", "nuxt"), ("vue", "vue"), ("svelte", "svelte"), ("expo", "expo"), ("react-native", "react-native"), ("vite", "vite")):
        if name in deps:
            framework = label
            break
    if framework == "react-router" and "react-router-dom" in deps and "vite" in deps:
        framework = "vite+react-router"
    if framework is None and "react-scripts" in deps:
        framework = "create-react-app"
    if framework is None and "react" in deps:
        framework = "react"

    styling = []
    if "tailwindcss" in deps or "@tailwindcss/vite" in deps or "@tailwindcss/postcss" in deps:
        styling.append("tailwind")
    if has("styled-components"):
        styling.append("styled-components")
    if has("@emotion/react", "@emotion/styled"):
        styling.append("emotion")
    if has("@vanilla-extract/css"):
        styling.append("vanilla-extract")
    if has("sass", "sass-embedded", "node-sass"):
        styling.append("sass")
    if has("less"):
        styling.append("less")
    if has("@stitches/react"):
        styling.append("stitches")
    if has("@pandacss/dev"):
        styling.append("panda")
    if any(".module.css" in f or ".module.scss" in f for f in files):
        styling.append("css-modules")
    if not styling or (styling == ["css-modules"]):
        if any(f.endswith(".css") for f in files):
            styling.append("css")

    ui_libs = [n for n in deps if re.match(r"^(@radix-ui/|@base-ui|react-aria|@react-aria|react-aria-components|@headlessui/|@mantine/|@mui/|@chakra-ui/|antd$|@ant-design/|@nextui-org/|@heroui/|@shadcn|@ark-ui/|@kobalte/|bits-ui|vaul|cmdk|sonner|react-hot-toast|@tremor/|flowbite|daisyui|@park-ui|primereact|@fluentui/|@blueprintjs/)", n)]
    icon_libs = [n for n in deps if re.match(r"^(lucide-react|lucide|@heroicons/|@tabler/icons|react-icons|@phosphor-icons/|@radix-ui/react-icons|@iconify/|@fortawesome/|iconoir-react|@remixicon/)", n)]
    helpers = [n for n in deps if n in ("class-variance-authority", "clsx", "classnames", "tailwind-merge", "tailwind-variants", "cva")]
    motion = [n for n in deps if n in ("framer-motion", "motion", "@react-spring/web", "gsap", "auto-animate", "@formkit/auto-animate")]
    fonts = [n for n in deps if n.startswith("@fontsource") or n in ("geist", "@vercel/geist", "next/font")]

    tailwind_version = None
    tw = ver("tailwindcss")
    if tw:
        tailwind_version = tw.split(".")[0] if tw[0].isdigit() else tw
    tailwind_config = [rel(root, os.path.join(root, f)) for f in os.listdir(root) if re.match(r"tailwind\.config\.(js|cjs|mjs|ts)$", f)] if os.path.isdir(root) else []

    pm = "npm"
    for lock, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"), ("package-lock.json", "npm")):
        if os.path.exists(os.path.join(root, lock)):
            pm = name
            break
    if isinstance(pkg.get("packageManager"), str):
        pm = pkg["packageManager"].split("@")[0]

    shadcn = load_json(os.path.join(root, "components.json"))
    src_dir = "src" if os.path.isdir(os.path.join(root, "src")) else "."
    storybook = os.path.isdir(os.path.join(root, ".storybook")) or any(n.startswith("@storybook/") or n == "storybook" for n in deps)
    scripts = pkg.get("scripts") or {}

    return {
        "name": pkg.get("name"),
        "framework": framework,
        "framework_version": ver({"next": "next", "vite+react-router": "vite", "vite": "vite", "remix": "@remix-run/react", "react-router": "react-router", "astro": "astro", "gatsby": "gatsby", "sveltekit": "@sveltejs/kit", "nuxt": "nuxt", "vue": "vue", "svelte": "svelte", "expo": "expo", "react-native": "react-native", "tanstack-start": "@tanstack/react-start", "create-react-app": "react-scripts", "react": "react"}.get(framework or "", "")),
        "react": ver("react"),
        "typescript": "typescript" in deps or os.path.exists(os.path.join(root, "tsconfig.json")),
        "styling": styling,
        "tailwind_version": tailwind_version,
        "tailwind_config": tailwind_config,
        "shadcn": {"present": shadcn is not None, "style": (shadcn or {}).get("style"), "css": (shadcn or {}).get("tailwind", {}).get("css"), "base_color": (shadcn or {}).get("tailwind", {}).get("baseColor"), "css_variables": (shadcn or {}).get("tailwind", {}).get("cssVariables"), "aliases": (shadcn or {}).get("aliases")} if shadcn is not None else {"present": False},
        "ui_libraries": sorted(ui_libs),
        "icon_libraries": sorted(icon_libs),
        "class_helpers": sorted(helpers),
        "motion_libraries": sorted(motion),
        "font_packages": sorted(fonts),
        "storybook": storybook,
        "testing": sorted(n for n in deps if n in ("vitest", "jest", "@playwright/test", "playwright", "cypress", "@testing-library/react")),
        "browser_drivers": sorted(n for n in deps if n in ("playwright", "playwright-core", "@playwright/test", "puppeteer", "puppeteer-core")),
        "package_manager": pm,
        "scripts": {k: scripts[k] for k in ("dev", "build", "start", "lint", "typecheck", "test", "check") if k in scripts},
        "src_dir": src_dir,
        "workspaces": ws_packages,
        "docs": {k: os.path.exists(os.path.join(root, k)) for k in ("AGENTS.md", "CLAUDE.md", "DESIGN.md", "README.md", "product/README.md", ".cursorrules", ".github/copilot-instructions.md")},
        "git": os.path.isdir(os.path.join(root, ".git")),
    }


# ---------------------------------------------------------------- routes

def detect_routes(root: str, files: list[str], project: dict) -> list[dict]:
    routes = []
    seen = set()

    def add(path, file, kind):
        key = (path, file)
        if key in seen:
            return
        seen.add(key)
        routes.append({"path": path, "file": file, "kind": kind})

    for f in files:
        r = rel(root, f)
        m = re.match(r"(?:src/)?app/(.*?)(?:/)?(page|layout|loading|error|not-found)\.(tsx|jsx|js|mdx)$", r)
        if m and project.get("framework") in ("next", None, "react"):
            if m.group(2) != "page":
                continue
            segs = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")")) and not s.startswith("@")]
            path = "/" + "/".join(re.sub(r"^\[\.\.\.(.+)\]$", r"*\1", re.sub(r"^\[\[?(.+?)\]?\]$", r":\1", s)) for s in segs)
            add(path.replace("//", "/"), r, "next-app")
            continue
        m = re.match(r"(?:src/)?pages/(.*)\.(tsx|jsx|js|mdx|vue|astro)$", r)
        if m and not m.group(1).startswith("api/") and not m.group(1).split("/")[-1].startswith("_"):
            segs = m.group(1).split("/")
            if segs[-1] == "index":
                segs = segs[:-1]
            path = "/" + "/".join(re.sub(r"^\[\.\.\.(.+)\]$", r"*\1", re.sub(r"^\[(.+)\]$", r":\1", s)) for s in segs)
            kind = "astro-pages" if r.endswith(".astro") else "nuxt-pages" if r.endswith(".vue") else "next-pages"
            add(path, r, kind)
            continue
        m = re.match(r"app/routes/(.*)\.(tsx|jsx|js|mdx)$", r)
        if m:
            name = m.group(1)
            if name.startswith("_") and "." not in name:
                continue
            path = "/" + re.sub(r"\$(\w+)", r":\1", name.replace("._index", "").replace("_index", "").replace(".", "/"))
            add(path.rstrip("/") or "/", r, "remix")
            continue
        m = re.match(r"src/routes/(.*?)(?:/)?\+page\.svelte$", r)
        if m:
            path = "/" + re.sub(r"\[(\w+)\]", r":\1", m.group(1))
            add(path.rstrip("/") or "/", r, "sveltekit")
            continue
    # router config paths (react-router / vue-router / tanstack)
    for f in files:
        if not f.endswith((".tsx", ".jsx", ".ts", ".js")):
            continue
        text = read(f)
        if "createBrowserRouter" in text or "<Route" in text or "createRouter(" in text or "createFileRoute" in text:
            for m in re.finditer(r"path\s*[:=]\s*[\"'`]([^\"'`]+)[\"'`]", text):
                add(m.group(1), rel(root, f), "router-config")
            for m in re.finditer(r"createFileRoute\([\"'`]([^\"'`]+)[\"'`]\)", text):
                add(m.group(1), rel(root, f), "tanstack-router")
    routes.sort(key=lambda r: (r["path"].count("/"), r["path"]))
    return routes


# ---------------------------------------------------------------- tailwind classes

def split_variants(token: str) -> tuple[list[str], str]:
    parts, depth, cur = [], 0, ""
    for ch in token:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == ":" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts[:-1], parts[-1]


def classify_color_value(prefix: str, val: str) -> tuple[str, str] | None:
    """Return (category, kind) for a value after a colour-capable prefix, or None if not ours."""
    base = val.split("/")[0]
    if base.startswith("[") and base.endswith("]"):
        inner = base[1:-1]
        if re.match(r"^(#|rgb|hsl|oklch|oklab|lab|lch|color\(|var\(|--)", inner):
            return ("color", "arbitrary")
        if prefix == "shadow" or prefix == "inset-shadow":
            return ("shadow", "arbitrary")
        if prefix == "text":
            return ("font_size", "arbitrary")
        if prefix in ("border", "border-x", "border-y", "border-t", "border-r", "border-b", "border-l", "border-s", "border-e", "divide", "ring", "outline", "decoration", "stroke"):
            return ("border", "arbitrary")
        return None
    if base.startswith("(") and base.endswith(")"):
        return ("color", "token")
    fam_shade = re.match(r"^([a-z]+)-(\d{2,3})$", base)
    if fam_shade and fam_shade.group(1) in PALETTE_FAMILIES and fam_shade.group(2) in SHADES:
        return ("color", "palette")
    if base in ("white", "black", "transparent", "current", "inherit"):
        return ("color", "named")
    if prefix == "text":
        if base in TEXT_NON_COLOR:
            return ("font_size", "scale") if base in TEXT_SIZES else None
        return ("color", "token")
    if prefix in ("border", "border-x", "border-y", "border-t", "border-r", "border-b", "border-l", "border-s", "border-e", "divide"):
        if base in BORDER_NON_COLOR:
            return ("border", "scale") if base[0].isdigit() else None
        return ("color", "token")
    if prefix in ("shadow", "inset-shadow"):
        if base in SHADOW_SIZES:
            return ("shadow", "scale")
        return ("color", "token")
    if prefix in ("ring", "inset-ring", "ring-offset"):
        if base in RING_NON_COLOR:
            return ("ring", "scale")
        return ("color", "token")
    if prefix == "outline":
        if base in OUTLINE_NON_COLOR:
            return ("ring", "scale") if base[0].isdigit() else None
        return ("color", "token")
    if prefix == "bg":
        if base in BG_NON_COLOR or base.startswith(("gradient-", "linear-", "radial", "conic", "size-", "position-", "clip-", "origin-", "blend-")):
            return None
        if "-" in base and base.split("-")[0] in ("left", "right", "top", "bottom", "center"):
            return None
        return ("color", "token")
    if prefix in ("from", "via", "to"):
        if re.match(r"^\d+%$", base):
            return None
        return ("color", "token")
    if prefix in ("fill", "stroke"):
        if base == "none" or base.isdigit():
            return None
        return ("color", "token")
    if prefix == "decoration":
        if base.isdigit() or base in ("solid", "double", "dotted", "dashed", "wavy", "auto", "from-font"):
            return None
        return ("color", "token")
    if prefix in ("accent", "caret", "placeholder"):
        return ("color", "token")
    return None


def classify_token(token: str) -> dict | None:
    """Classify a Tailwind utility. Returns {category, kind, prefix, value, variants} or None."""
    variants, base = split_variants(token)
    base = base.lstrip("!")
    neg = base.startswith("-")
    if neg:
        base = base[1:]
    if not CLASS_TOKEN_RE.match(base) and not re.match(r"^[a-z][a-z0-9-]*$", base):
        return None
    m = re.match(r"^border(?:-([xytrblse]))?(?:-(0|2|4|8|\[\d[^\]]*\]|\(--[^)]+\)))?$", base)
    if m:
        val = m.group(2) or "DEFAULT"
        return {"category": "border", "kind": "arbitrary" if val.startswith("[") else "token" if val.startswith("(") else "scale", "prefix": "border" + ("-" + m.group(1) if m.group(1) else ""), "value": val, "variants": variants}
    # longest prefix first
    for prefix in sorted(COLOR_PREFIXES, key=len, reverse=True):
        if base.startswith(prefix + "-"):
            val = base[len(prefix) + 1 :]
            res = classify_color_value(prefix, val)
            if res:
                return {"category": res[0], "kind": res[1], "prefix": prefix, "value": val, "variants": variants}
            if prefix in ("text", "bg", "border", "shadow", "ring", "outline", "from", "via", "to", "fill", "stroke", "decoration", "divide", "accent", "caret", "placeholder", "border-x", "border-y", "border-t", "border-r", "border-b", "border-l", "border-s", "border-e", "ring-offset", "inset-ring", "inset-shadow"):
                break
    if base in ("shadow", "ring", "border", "outline", "inset-ring", "inset-shadow"):
        return {"category": {"shadow": "shadow", "inset-shadow": "shadow", "ring": "ring", "inset-ring": "ring", "border": "border", "outline": "ring"}[base], "kind": "scale", "prefix": base, "value": "DEFAULT", "variants": variants}
    m = re.match(r"^rounded(?:-(t|r|b|l|tl|tr|br|bl|s|e|ss|se|es|ee))?(?:-(.+))?$", base)
    if m:
        val = m.group(2) or "DEFAULT"
        kind = "arbitrary" if val.startswith("[") else "token" if val.startswith("(") else "scale"
        return {"category": "radius", "kind": kind, "prefix": "rounded" + ("-" + m.group(1) if m.group(1) else ""), "value": val, "variants": variants}
    for prefix in sorted(SPACING_PREFIXES, key=len, reverse=True):
        if base.startswith(prefix + "-"):
            val = base[len(prefix) + 1 :]
            if val in ("auto", "px", "full", "reverse") or re.match(r"^\d+(\.\d+)?$", val) or re.match(r"^\d+/\d+$", val) or val.startswith("[") or val.startswith("("):
                kind = "arbitrary" if val.startswith("[") else "token" if val.startswith("(") else "px" if val == "px" else "auto" if val in ("auto", "reverse") else "fraction" if "/" in val else "scale"
                return {"category": "spacing", "kind": kind, "prefix": prefix, "value": ("-" if neg else "") + val, "variants": variants}
            break
    for prefix in sorted(SIZING_PREFIXES, key=len, reverse=True):
        if base.startswith(prefix + "-"):
            val = base[len(prefix) + 1 :]
            if re.match(r"^\d+(\.\d+)?$", val) or re.match(r"^\d+/\d+$", val) or val.startswith("[") or val.startswith("(") or val in ("px", "full", "screen", "fit", "min", "max", "auto", "dvh", "svh", "lvh", "dvw", "svw", "lvw", "prose", "none") or val in TEXT_SIZES:
                kind = "arbitrary" if val.startswith("[") else "token" if val.startswith("(") else "scale"
                return {"category": "sizing", "kind": kind, "prefix": prefix, "value": val, "variants": variants}
            break
    m = re.match(r"^font-(.+)$", base)
    if m:
        val = m.group(1)
        if val in WEIGHTS or re.match(r"^\[\d+\]$", val):
            return {"category": "font_weight", "kind": "arbitrary" if val.startswith("[") else "scale", "prefix": "font", "value": val, "variants": variants}
        if val.startswith("(") or val.startswith("[") or val in ("sans", "serif", "mono") or re.match(r"^[a-z][a-z0-9-]*$", val) and not val.startswith(("stretch", "feature", "variant", "optical", "synthesis")):
            return {"category": "font_family", "kind": "arbitrary" if val.startswith("[") else "scale" if val in ("sans", "serif", "mono") else "token", "prefix": "font", "value": val, "variants": variants}
    m = re.match(r"^leading-(.+)$", base)
    if m:
        return {"category": "leading", "kind": "arbitrary" if m.group(1).startswith("[") else "scale", "prefix": "leading", "value": m.group(1), "variants": variants}
    m = re.match(r"^tracking-(.+)$", base)
    if m:
        return {"category": "tracking", "kind": "arbitrary" if m.group(1).startswith("[") else "scale", "prefix": "tracking", "value": m.group(1), "variants": variants}
    m = re.match(r"^opacity-(.+)$", base)
    if m:
        return {"category": "opacity", "kind": "scale", "prefix": "opacity", "value": m.group(1), "variants": variants}
    m = re.match(r"^z-(.+)$", base)
    if m:
        return {"category": "z", "kind": "arbitrary" if m.group(1).startswith("[") else "scale", "prefix": "z", "value": m.group(1), "variants": variants}
    m = re.match(r"^(duration|ease|delay|animate|transition)(?:-(.+))?$", base)
    if m:
        return {"category": "motion", "kind": "arbitrary" if (m.group(2) or "").startswith("[") else "scale", "prefix": m.group(1), "value": m.group(2) or "DEFAULT", "variants": variants}
    return None


def extract_strings(text: str) -> list[tuple[str, int]]:
    out = []
    for m in STRING_RE.finditer(text):
        s = m.group(1) if m.group(1) is not None else m.group(2) if m.group(2) is not None else m.group(3)
        if s is None:
            continue
        if m.group(3) is not None:
            s = re.sub(r"\$\{[^}]*\}", " ", s)
        out.append((s, line_of(text, m.start())))
    return out


def scan_tailwind(text: str, is_markup: bool) -> list[tuple[dict, str, int]]:
    """Yield (classification, token, line) for every utility in the file's strings."""
    results = []
    candidates: list[tuple[str, int]] = []
    if is_markup:
        for m in re.finditer(r"\bclass(?:Name)?\s*=\s*(\"[^\"]*\"|'[^']*'|\{[^}]*\})", text):
            candidates.append((m.group(1).strip("\"'{}"), line_of(text, m.start())))
        for m in re.finditer(r"class:list=\{([^}]*)\}", text):
            candidates.append((m.group(1), line_of(text, m.start())))
        for m in re.finditer(r"@apply\s+([^;]+);", text):
            candidates.append((m.group(1), line_of(text, m.start())))
    candidates.extend(extract_strings(text))
    for m in re.finditer(r"@apply\s+([^;]+);", text):
        candidates.append((m.group(1), line_of(text, m.start())))
    for s, line in candidates:
        if len(s) > 4000:
            continue
        for tok in s.split():
            if "://" in tok or tok.startswith(("http", "/", "./", "../", "@/")):
                continue
            c = classify_token(tok)
            if c:
                results.append((c, tok, line))
    return results


# ---------------------------------------------------------------- css values

CSS_COLOR_PROPS = {"color", "background", "background-color", "border-color", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color", "outline-color", "fill", "stroke", "caret-color", "accent-color", "text-decoration-color", "border", "border-top", "border-right", "border-bottom", "border-left", "box-shadow", "outline", "text-shadow", "background-image"}
CSS_SPACING_PROPS = {"padding", "padding-top", "padding-right", "padding-bottom", "padding-left", "padding-inline", "padding-block", "margin", "margin-top", "margin-right", "margin-bottom", "margin-left", "margin-inline", "margin-block", "gap", "row-gap", "column-gap", "inset", "top", "right", "bottom", "left"}
CSS_RADIUS_PROPS = {"border-radius", "border-top-left-radius", "border-top-right-radius", "border-bottom-right-radius", "border-bottom-left-radius"}
CSS_SIZING_PROPS = {"width", "height", "min-width", "max-width", "min-height", "max-height"}


def scan_css_text(text: str, where: str) -> dict:
    """Extract design values from CSS-like text. where: 'stylesheet' | 'style-block' | 'css-in-js' | 'inline'."""
    found = {"colors": [], "spacing": [], "radius": [], "font_size": [], "line_height": [], "letter_spacing": [], "border_width": [], "shadow": [], "font_family": [], "duration": [], "sizing": [], "custom_props": [], "var_uses": [], "font_weight": []}
    clean = strip_comments(text, css=True)
    for m in re.finditer(r"(?<![\w-])((?:--)?[a-zA-Z][\w-]*)\s*:\s*([^;{}]+?)\s*(?=;|\}|$)", clean, flags=re.M):
        prop, val, line = m.group(1).lower(), m.group(2).strip(), line_of(clean, m.start())
        if not val or val.startswith("{"):
            continue
        if prop.startswith("--"):
            found["custom_props"].append((prop, val, line))
            for c in COLOR_FUNC_RE.findall(val):
                found["colors"].append((c, line, prop))
            continue
        for v in re.findall(r"var\((--[\w-]+)", val):
            found["var_uses"].append((v, line, prop))
        if prop in CSS_COLOR_PROPS:
            for c in COLOR_FUNC_RE.findall(val):
                found["colors"].append((c, line, prop))
            if re.search(r"\b(white|black)\b", val):
                for c in re.findall(r"\b(white|black)\b", val):
                    found["colors"].append((c, line, prop))
        if prop in ("box-shadow", "text-shadow") and not val.startswith("var("):
            found["shadow"].append((val, line))
        if prop in CSS_SPACING_PROPS:
            for n, u in LENGTH_RE.findall(val):
                found["spacing"].append((n + u, line, prop))
        if prop in CSS_RADIUS_PROPS:
            for n, u in LENGTH_RE.findall(val):
                found["radius"].append((n + u, line, prop))
            if "%" in val:
                found["radius"].append((val, line, prop))
        if prop == "font-size":
            for n, u in LENGTH_RE.findall(val):
                found["font_size"].append((n + u, line))
        if prop == "line-height":
            found["line_height"].append((val, line))
        if prop == "letter-spacing":
            found["letter_spacing"].append((val, line))
        if prop == "font-weight":
            found["font_weight"].append((val, line))
        if prop in ("border", "border-width", "border-top", "border-bottom", "border-left", "border-right", "outline-width", "outline"):
            for n, u in LENGTH_RE.findall(val):
                found["border_width"].append((n + u, line))
        if prop == "font-family" or prop == "font":
            fam = val.split(",")[0].strip().strip("\"'") if prop == "font-family" else None
            if fam and not fam.startswith("var("):
                found["font_family"].append((fam, line))
        if prop in ("transition", "transition-duration", "animation", "animation-duration"):
            for n, u in DURATION_RE.findall(val):
                found["duration"].append((n + u, line))
        if prop in CSS_SIZING_PROPS:
            for n, u in LENGTH_RE.findall(val):
                found["sizing"].append((n + u, line, prop))
    return found


def scan_inline_styles(text: str, path: str) -> list[dict]:
    out = []
    for m in re.finditer(r"style\s*=\s*\{\{(.*?)\}\}", text, flags=re.S):
        body = m.group(1)
        if len(body) > 600:
            body = body[:600]
        out.append({"file": path, "line": line_of(text, m.start()), "snippet": re.sub(r"\s+", " ", body.strip())[:160], "values": re.findall(r"(?:#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch)\([^)]*\)|\b\d+(?:\.\d+)?(?:px|rem|em)\b|(?<=:\s)\d+(?=\s*[,}]))", body)})
    for m in re.finditer(r"\sstyle\s*=\s*\"([^\"]{3,})\"", text):
        out.append({"file": path, "line": line_of(text, m.start()), "snippet": m.group(1)[:160], "values": re.findall(r"(?:#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch)\([^)]*\)|\b\d+(?:\.\d+)?(?:px|rem|em)\b)", m.group(1))})
    return out


# ---------------------------------------------------------------- components

def find_components(root: str, files: list[str]) -> list[dict]:
    comps: dict[tuple[str, str], dict] = {}
    code_files = [f for f in files if f.endswith((".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".astro"))]
    texts = {f: read(f) for f in code_files}
    for f, text in texts.items():
        r = rel(root, f)
        names = set()
        if f.endswith((".vue", ".svelte", ".astro")):
            name = os.path.splitext(os.path.basename(f))[0]
            if name[0].isupper() or f.endswith(".vue"):
                names.add(name[0].upper() + name[1:])
        else:
            clean = strip_comments(text)
            for m in re.finditer(r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Z][A-Za-z0-9_]*)", clean):
                names.add(m.group(1))
            for m in re.finditer(r"export\s+(?:default\s+)?(?:const|let)\s+([A-Z][A-Za-z0-9_]*)\s*(?::[^=]+)?=", clean):
                names.add(m.group(1))
            for m in re.finditer(r"export\s*\{([^}]*)\}", clean):
                for part in m.group(1).split(","):
                    nm = part.strip().split(" as ")[-1].strip()
                    if re.match(r"^[A-Z][A-Za-z0-9_]*$", nm):
                        names.add(nm)
            for m in re.finditer(r"export\s+default\s+([A-Z][A-Za-z0-9_]*)\s*;?", clean):
                names.add(m.group(1))
            if not names:
                continue
            # keep only names that look like components (JSX in file or React import)
            if "<" not in clean or not re.search(r"</?[A-Za-z]", clean):
                if "React" not in clean and "forwardRef" not in clean:
                    continue
        in_component_dir = bool(COMPONENT_DIR_RE.search(os.path.dirname(r) + "/"))
        for n in names:
            if n in ("Page", "Layout", "Loading", "Error", "NotFound", "Head", "App", "Document", "RootLayout", "Providers", "Template", "Default", "Metadata") and not in_component_dir:
                continue
            if re.match(r"(?:src/)?app/(?:.*/)?(page|layout|loading|error|not-found|template|default)\.(tsx|jsx)$", r) or re.match(r"(?:src/)?pages/", r):
                continue
            kind = next((k for k, rx in KIND_RE if rx.search(n)), None)
            comps[(n, r)] = {"name": n, "file": r, "kind": kind, "in_component_dir": in_component_dir, "uses_cva": "cva(" in text or "tv(" in text, "forward_ref": "forwardRef" in text, "as_child": "asChild" in text, "usages": 0, "used_in": [], "variants": sorted(set(re.findall(r"variant\s*:\s*\{([^}]*)\}", text)))[:1]}
    # usage counts
    for (n, r), comp in comps.items():
        tag = re.compile(r"<" + re.escape(n) + r"(?![A-Za-z0-9_.])")
        for f, text in texts.items():
            fr = rel(root, f)
            if fr == r:
                continue
            cnt = len(tag.findall(text))
            if cnt:
                comp["usages"] += cnt
                comp["used_in"].append(fr)
        comp["used_in"] = sorted(comp["used_in"])
        if comp["variants"]:
            comp["variants"] = sorted(set(re.findall(r"(?:^|[{,\n])\s*([a-z][A-Za-z0-9]*)\s*:", comp["variants"][0])))
    out = sorted(comps.values(), key=lambda c: (-c["usages"], c["file"]))
    return out


# ---------------------------------------------------------------- scan

def scan(root: str) -> dict:
    root = os.path.abspath(root)
    files = sorted(walk(root))
    project = detect_project(root, [rel(root, f) for f in files])
    routes = detect_routes(root, files, project)
    tw: dict[str, dict] = {}
    variants = Counter()
    css_found = defaultdict(lambda: defaultdict(lambda: {"count": 0, "locations": []}))
    custom_props: dict[str, list] = defaultdict(list)
    var_uses = Counter()
    inline = []
    v4_theme_files, v3_directives, imports_tailwind = [], [], []
    fonts_next = []

    def add_tw(c, tok, path, line):
        key = tok
        e = tw.setdefault(key, {"token": tok, "category": c["category"], "kind": c["kind"], "prefix": c["prefix"], "value": c["value"], "variants": c["variants"], "count": 0, "files": {}, "lines": []})
        e["count"] += 1
        e["files"][path] = e["files"].get(path, 0) + 1
        if len(e["lines"]) < 8:
            e["lines"].append(f"{path}:{line}")
        for v in c["variants"]:
            variants[v] += 1

    def add_css(found, path):
        for cat, items in found.items():
            if cat == "custom_props":
                for prop, val, line in items:
                    custom_props[prop].append({"value": val, "file": path, "line": line})
                continue
            if cat == "var_uses":
                for v, line, prop in items:
                    var_uses[v] += 1
                continue
            for item in items:
                val, line = item[0], item[1]
                prop = item[2] if len(item) > 2 else None
                e = css_found[cat][val]
                e["count"] += 1
                if len(e["locations"]) < 8:
                    e["locations"].append(f"{path}:{line}" + (f" ({prop})" if prop else ""))

    for f in files:
        path = rel(root, f)
        ext = os.path.splitext(f)[1].lower()
        text = read(f)
        if not text:
            continue
        if ext in STYLE_EXT:
            if "@theme" in text:
                v4_theme_files.append(path)
            if re.search(r"@tailwind\s+(base|components|utilities)", text):
                v3_directives.append(path)
            if re.search(r"@import\s+[\"']tailwindcss[\"']", text):
                imports_tailwind.append(path)
            add_css(scan_css_text(text, "stylesheet"), path)
            for c, tok, line in scan_tailwind(text, is_markup=False):
                if "@apply" in text:
                    add_tw(c, tok, path, line)
            continue
        is_markup = ext in (".vue", ".svelte", ".astro", ".html", ".mdx")
        for c, tok, line in scan_tailwind(text, is_markup):
            add_tw(c, tok, path, line)
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, flags=re.S):
            add_css(scan_css_text(m.group(1), "style-block"), path)
        if re.search(r"\b(styled|css|keyframes|createGlobalStyle)(\.[a-zA-Z0-9]+|\([^)]*\))?`", text):
            for m in re.finditer(r"\b(?:styled|css|createGlobalStyle)(?:\.[a-zA-Z0-9]+|\([^)]*\))?`((?:[^`\\]|\\.)*)`", text, flags=re.S):
                add_css(scan_css_text(re.sub(r"\$\{[^}]*\}", "0", m.group(1)), "css-in-js"), path)
        for item in scan_inline_styles(text, path):
            inline.append(item)
        for m in re.finditer(r"from\s+[\"']next/font/(google|local)[\"']", text):
            for fm in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*[\"']next/font/google[\"']", text):
                fonts_next.extend(n.strip() for n in fm.group(1).split(",") if n.strip())
            if m.group(1) == "local":
                fonts_next.append("local font (next/font/local)")

    components = find_components(root, files)

    # categories summary
    by_cat: dict[str, dict] = defaultdict(dict)
    for tok, e in tw.items():
        by_cat[e["category"]][tok] = e

    def family_of(e):
        m = re.match(r"^([a-z]+)-(\d{2,3})(?:/.*)?$", e["value"])
        return m.group(1) if m else None

    grey_families = Counter()
    palette_families = Counter()
    for tok, e in by_cat.get("color", {}).items():
        fam = family_of(e)
        if fam:
            palette_families[fam] += e["count"]
            if fam in GREY_FAMILIES:
                grey_families[fam] += e["count"]
    arbitrary = {cat: {tok: e["count"] for tok, e in toks.items() if e["kind"] == "arbitrary"} for cat, toks in by_cat.items()}
    arbitrary = {k: v for k, v in arbitrary.items() if v}

    def off_grid(value: str) -> bool:
        m = re.match(r"^\[(-?\d*\.?\d+)(px|rem)\]$", value)
        if not m:
            return False
        n, unit = float(m.group(1)), m.group(2)
        px = n if unit == "px" else n * 16
        return abs(px / 4 - round(px / 4)) > 1e-6 and px not in (1, 2)

    off_grid_spacing = {tok: e["count"] for tok, e in by_cat.get("spacing", {}).items() if off_grid(e["value"])}
    off_grid_css = {val: e["count"] for val, e in css_found.get("spacing", {}).items() if off_grid(f"[{val}]")}
    kinds = defaultdict(list)
    for c in components:
        if c["kind"]:
            kinds[c["kind"]].append(c)
    duplicate_kinds = {k: [{"name": c["name"], "file": c["file"], "usages": c["usages"]} for c in v] for k, v in kinds.items() if len(v) > 1 and k not in ("layout", "form", "icon", "link", "nav", "list", "heading")}
    token_colors = {tok: e["count"] for tok, e in by_cat.get("color", {}).items() if e["kind"] == "token"}
    palette_colors = sum(e["count"] for e in by_cat.get("color", {}).values() if e["kind"] == "palette")
    arbitrary_colors = sum(e["count"] for e in by_cat.get("color", {}).values() if e["kind"] == "arbitrary")
    semantic_props = {k: v for k, v in custom_props.items() if not re.match(r"^--(color|font|text|spacing|radius|shadow|breakpoint|container|leading|tracking|ease|animate|blur|perspective|aspect|default|inset-shadow|drop-shadow)-(red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d+$", k)}
    tw_version = project.get("tailwind_version")
    if tw_version is None and (v4_theme_files or imports_tailwind):
        tw_version = "4"
    if tw_version is None and v3_directives:
        tw_version = "3"

    return {
        "version": 1,
        "root": root,
        "files_scanned": len(files),
        "project": {**project, "tailwind_version": tw_version, "tailwind_v4_theme_files": v4_theme_files, "tailwind_v3_directive_files": v3_directives, "tailwind_import_files": imports_tailwind, "next_fonts": sorted(set(fonts_next))},
        "routes": routes,
        "components": components,
        "tailwind": {
            "by_category": {cat: dict(sorted(toks.items(), key=lambda kv: -kv[1]["count"])) for cat, toks in by_cat.items()},
            "variants": dict(variants.most_common()),
            "palette_families": dict(palette_families.most_common()),
        },
        "css": {cat: dict(sorted(vals.items(), key=lambda kv: -kv[1]["count"])) for cat, vals in css_found.items()},
        "custom_props": {k: v for k, v in sorted(custom_props.items())},
        "var_uses": dict(var_uses.most_common()),
        "inline_styles": inline,
        "drift_signals": {
            "grey_families": dict(grey_families.most_common()),
            "palette_families": dict(palette_families.most_common()),
            "arbitrary_values": arbitrary,
            "off_grid_spacing": {**off_grid_spacing, **off_grid_css},
            "radius_values": sorted({e["value"] for e in by_cat.get("radius", {}).values()} | set(css_found.get("radius", {}).keys())),
            "shadow_values": sorted({e["value"] for e in by_cat.get("shadow", {}).values()} | set(css_found.get("shadow", {}).keys())),
            "font_sizes": sorted({e["value"] for e in by_cat.get("font_size", {}).values()} | set(css_found.get("font_size", {}).keys())),
            "font_weights": sorted({e["value"] for e in by_cat.get("font_weight", {}).values()} | set(css_found.get("font_weight", {}).keys())),
            "duplicate_component_kinds": duplicate_kinds,
            "semantic_tokens_defined": sorted(semantic_props.keys()),
            "semantic_token_classes": token_colors,
            "raw_palette_color_uses": palette_colors,
            "arbitrary_color_uses": arbitrary_colors,
            "inline_style_count": len(inline),
            "dark_variant_uses": variants.get("dark", 0),
            "breakpoint_variant_uses": {k: v for k, v in variants.items() if k in ("sm", "md", "lg", "xl", "2xl") or k.startswith("max-") or k.startswith("min-")},
            "state_variant_uses": {k: v for k, v in variants.items() if k in ("hover", "focus", "focus-visible", "active", "disabled", "group-hover", "focus-within", "aria-selected", "data-[state=open]")},
        },
    }


# ---------------------------------------------------------------- markdown

def to_markdown(scan_result: dict) -> str:
    p = scan_result["project"]
    d = scan_result["drift_signals"]
    tw = scan_result["tailwind"]["by_category"]
    lines = []
    a = lines.append
    a(f"# Source scan: {p.get('name') or os.path.basename(scan_result['root'])}")
    a("")
    a(f"Files scanned: {scan_result['files_scanned']}")
    a("")
    a("## Project")
    a("")
    a(f"- Framework: {p.get('framework')} {p.get('framework_version') or ''}; React {p.get('react') or 'n/a'}; TypeScript: {p.get('typescript')}")
    a(f"- Styling: {', '.join(p.get('styling') or []) or 'none detected'}; Tailwind v{p.get('tailwind_version') or '?'}" + (f" (@theme in {', '.join(p['tailwind_v4_theme_files'])})" if p.get("tailwind_v4_theme_files") else "") + (f" (config: {', '.join(p['tailwind_config'])})" if p.get("tailwind_config") else ""))
    a(f"- shadcn/ui: {'yes, style ' + str(p['shadcn'].get('style')) + ', css ' + str(p['shadcn'].get('css')) if p['shadcn'].get('present') else 'no'}")
    a(f"- UI libraries: {', '.join(p.get('ui_libraries') or []) or 'none'}; icons: {', '.join(p.get('icon_libraries') or []) or 'none'}; class helpers: {', '.join(p.get('class_helpers') or []) or 'none'}; motion: {', '.join(p.get('motion_libraries') or []) or 'none'}")
    a(f"- Fonts: {', '.join(p.get('next_fonts') or []) or 'no next/font'}; packages: {', '.join(p.get('font_packages') or []) or 'none'}; CSS font-family values: {', '.join(list(scan_result['css'].get('font_family', {}).keys())[:6]) or 'none'}")
    a(f"- Package manager: {p.get('package_manager')}; scripts: {', '.join(f'{k}: `{v}`' for k, v in (p.get('scripts') or {}).items())}")
    a(f"- Storybook: {p.get('storybook')}; browser drivers: {', '.join(p.get('browser_drivers') or []) or 'none'}; testing: {', '.join(p.get('testing') or []) or 'none'}")
    a(f"- Docs present: {', '.join(k for k, v in p['docs'].items() if v) or 'none'}; workspaces: {', '.join(p.get('workspaces') or []) or 'none'}")
    a("")
    a("## Routes")
    a("")
    routes = scan_result["routes"]
    if routes:
        for r in routes[:60]:
            a(f"- `{r['path']}` ({r['file']})")
        if len(routes) > 60:
            a(f"- ... {len(routes) - 60} more")
    else:
        a("- none detected from files; look at the router configuration by hand")
    a("")
    a("## Components")
    a("")
    comps = scan_result["components"]
    a(f"{len(comps)} exported components. Most used:")
    a("")
    a("| Component | File | Uses | Files | Kind | Notes |")
    a("|---|---|---|---|---|---|")
    for c in comps[:40]:
        notes = ", ".join(x for x in (("cva" if c["uses_cva"] else ""), ("forwardRef" if c["forward_ref"] else ""), ("variants: " + ", ".join(c["variants"]) if c["variants"] else "")) if x)
        a(f"| {c['name']} | {c['file']} | {c['usages']} | {len(c['used_in'])} | {c['kind'] or ''} | {notes} |")
    if len(comps) > 40:
        a(f"\n... {len(comps) - 40} more in the JSON.")
    if d["duplicate_component_kinds"]:
        a("")
        a("Several implementations of the same kind:")
        a("")
        for kind, items in d["duplicate_component_kinds"].items():
            a(f"- **{kind}**: " + "; ".join(f"{i['name']} ({i['file']}, {i['usages']} uses)" for i in items))
    a("")
    a("## Tailwind usage")
    a("")
    if not tw:
        a("No Tailwind utilities found.")
    else:
        colors = tw.get("color", {})
        a(f"- Colour utilities: {sum(e['count'] for e in colors.values())} uses, {len(colors)} distinct. Raw palette: {d['raw_palette_color_uses']}; arbitrary: {d['arbitrary_color_uses']}; semantic tokens: {sum(d['semantic_token_classes'].values())} ({', '.join(list(d['semantic_token_classes'])[:8])})")
        a(f"- Palette families: {', '.join(f'{k} {v}' for k, v in d['palette_families'].items())}")
        a(f"- Grey families mixed: {len(d['grey_families'])} ({', '.join(f'{k} {v}' for k, v in d['grey_families'].items())})")
        top = sorted(colors.items(), key=lambda kv: -kv[1]["count"])[:25]
        a("- Top colour classes: " + ", ".join(f"`{t}` {e['count']}" for t, e in top))
        a(f"- Font sizes: {', '.join(d['font_sizes'])}")
        a(f"- Font weights: {', '.join(d['font_weights'])}")
        a(f"- Radii: {', '.join(d['radius_values'])}")
        a(f"- Shadows: {', '.join(d['shadow_values'])}")
        sp = tw.get("spacing", {})
        a(f"- Spacing utilities: {sum(e['count'] for e in sp.values())} uses, {len(sp)} distinct; off-grid: {', '.join(f'`{k}` {v}' for k, v in d['off_grid_spacing'].items()) or 'none'}")
        a(f"- Variants: dark {d['dark_variant_uses']}; breakpoints {d['breakpoint_variant_uses']}; states {d['state_variant_uses']}")
        if d["arbitrary_values"]:
            a("- Arbitrary values:")
            for cat, toks in d["arbitrary_values"].items():
                a(f"  - {cat}: " + ", ".join(f"`{t}` {n}" for t, n in sorted(toks.items(), key=lambda kv: -kv[1])[:20]))
    a("")
    a("## CSS values")
    a("")
    css = scan_result["css"]
    if any(css.values()):
        for cat in ("colors", "spacing", "radius", "font_size", "shadow", "font_family", "duration", "border_width"):
            vals = css.get(cat, {})
            if vals:
                a(f"- {cat}: " + ", ".join(f"`{v}` {e['count']}" for v, e in list(vals.items())[:15]))
    else:
        a("- none outside Tailwind classes")
    cp = scan_result["custom_props"]
    a("")
    a(f"## Custom properties ({len(cp)} declared)")
    a("")
    semantic = d["semantic_tokens_defined"]
    if semantic:
        for k in semantic[:60]:
            locs = cp[k]
            a(f"- `{k}`: {locs[0]['value'][:60]} ({locs[0]['file']}:{locs[0]['line']}" + (f", +{len(locs) - 1} more" if len(locs) > 1 else "") + f"; used {scan_result['var_uses'].get(k, 0)}x via var())")
        if len(semantic) > 60:
            a(f"- ... {len(semantic) - 60} more")
    else:
        a("- no semantic tokens declared")
    a("")
    a(f"## Inline styles ({len(scan_result['inline_styles'])})")
    a("")
    for i in scan_result["inline_styles"][:20]:
        a(f"- {i['file']}:{i['line']}: `{i['snippet'][:100]}`")
    a("")
    a("## Drift signals")
    a("")
    a(f"- Grey palette families mixed: {len(d['grey_families'])}")
    a(f"- Arbitrary values: {sum(len(v) for v in d['arbitrary_values'].values())} distinct")
    a(f"- Off-grid spacing values: {len(d['off_grid_spacing'])}")
    a(f"- Distinct radii: {len(d['radius_values'])}; shadows: {len(d['shadow_values'])}; font sizes: {len(d['font_sizes'])}; font weights: {len(d['font_weights'])}")
    a(f"- Component kinds with several implementations: {', '.join(d['duplicate_component_kinds']) or 'none'}")
    a(f"- Semantic tokens defined: {len(semantic)}; raw palette colour uses: {d['raw_palette_color_uses']}; arbitrary colour uses: {d['arbitrary_color_uses']}; inline styles: {d['inline_style_count']}")
    a(f"- Dark mode variants used: {d['dark_variant_uses']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scan an app's source for design values, components and stack facts.")
    ap.add_argument("root", nargs="?", default=".", help="app root (default: current directory)")
    ap.add_argument("--out", help="JSON output path (default: <root>/.design-catalog/scan.json)")
    ap.add_argument("--md", action="store_true", help="print a Markdown summary")
    ap.add_argument("--quiet", action="store_true", help="do not print the output path")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    result = scan(root)
    out = args.out or os.path.join(root, ".design-catalog", "scan.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    if args.md:
        print(to_markdown(result))
    if not args.quiet:
        print(f"scan written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
