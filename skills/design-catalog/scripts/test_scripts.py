#!/usr/bin/env python3
"""Tests for the design-catalog scripts. Run: python3 skills/design-catalog/scripts/test_scripts.py

Standard library only. Builds a tiny fake project and synthetic snapshots in a temp dir, then
exercises scan_source, dc_colors, analyze and compare end to end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import analyze  # noqa: E402
import compare  # noqa: E402
import dc_colors as C  # noqa: E402
import scan_source  # noqa: E402


def write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def fake_project(root: str):
    write(os.path.join(root, "package.json"), json.dumps({
        "name": "fixture-app", "dependencies": {"next": "16.0.0", "react": "19.0.0", "lucide-react": "0.5.0", "class-variance-authority": "0.7.0"},
        "devDependencies": {"tailwindcss": "^4.1.0", "typescript": "5.0.0"}, "scripts": {"dev": "next dev", "build": "next build"},
    }))
    write(os.path.join(root, "src/app/globals.css"), '@import "tailwindcss";\n@theme {\n  --color-brand: #4f46e5;\n  --radius-card: 0.75rem;\n}\n:root { --shadow-card: 0 1px 3px rgba(0,0,0,0.1); }\n.legacy { color: #6b7280; padding: 18px; border-radius: 10px; }\n')
    write(os.path.join(root, "src/app/page.tsx"), 'import { Card } from "@/components/Card";\nexport default function Home() {\n  return <main className="bg-gray-50 p-6 mt-[22px]"><h1 className="text-3xl font-bold text-gray-900">Hi</h1><p className="text-gray-500 text-[15px]">x</p><button className="bg-indigo-500 text-white rounded-lg px-5 py-2.5 hover:bg-indigo-600">Go</button><Card /><span style={{ color: "#6b7280" }}>f</span></main>;\n}\n')
    write(os.path.join(root, "src/app/tasks/page.tsx"), 'import { Button } from "@/components/ui/button";\nexport default function Tasks() {\n  return <div className="bg-zinc-50 text-zinc-500 border-zinc-200 border-[#e5e7eb] shadow-[0_1px_3px_rgba(0,0,0,0.08)] rounded-[10px]"><Button>Add</Button><Button variant="outline">x</Button></div>;\n}\n')
    write(os.path.join(root, "src/app/tasks/[id]/page.tsx"), 'export default function Task() { return <div className="text-slate-500 text-neutral-500 p-[18px]" />; }\n')
    write(os.path.join(root, "src/components/Card.tsx"), 'export function Card() { return <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm" />; }\n')
    write(os.path.join(root, "src/components/ProjectCard.tsx"), 'export function ProjectCard() { return <div className="rounded-2xl bg-white p-5 shadow-md" />; }\n')
    write(os.path.join(root, "src/components/ui/button.tsx"), 'import { cva } from "class-variance-authority";\nconst v = cva("rounded-md h-9 px-4 text-sm font-medium", { variants: { variant: { default: "bg-indigo-600 text-white hover:bg-indigo-700", outline: "border border-zinc-200", ghost: "hover:bg-zinc-100" }, size: { sm: "h-8", default: "h-9" } } });\nexport function Button(props: any) { return <button className={v(props)} {...props} />; }\n')
    write(os.path.join(root, "node_modules/junk/index.js"), 'const x = "bg-red-500";\n')


def snapshot(label: str, path: str, elements: list[dict], styles: list[dict], root_vars=None) -> dict:
    return {"version": 1, "url": "http://x" + path, "path": path, "title": label, "viewport": {"width": 1280, "height": 800}, "dpr": 1, "colorScheme": "light", "label": label, "rootVars": root_vars or {"--color-brand": "#4f46e5"}, "fonts": ["Geist"], "styles": styles, "elements": elements}


BASE_TEXT = {"color": "rgb(24, 24, 27)", "font-family": "Geist, sans-serif", "font-size": "14px", "font-weight": "400", "line-height": "20px", "display": "block"}


def el(i, p, t, sel, r, txt, s, **kw):
    e = {"i": i, "p": p, "t": t, "sel": sel, "r": r, "txt": txt, "s": s}
    e.update(kw)
    return e


def fake_snapshots(folder: str):
    os.makedirs(folder, exist_ok=True)
    styles_home = [
        {"background-color": "rgb(250, 250, 251)", "color": "rgb(24, 24, 27)", "font-family": "Geist", "font-size": "16px", "font-weight": "400", "display": "block"},
        dict(BASE_TEXT, **{"font-size": "30px", "font-weight": "700", "color": "rgb(16, 24, 40)"}),
        dict(BASE_TEXT, **{"color": "rgb(107, 114, 128)", "font-size": "15px"}),
        {"color": "rgb(255, 255, 255)", "background-color": "rgb(99, 102, 241)", "font-family": "Geist", "font-size": "16px", "font-weight": "500", "padding-top": "10px", "padding-bottom": "10px", "padding-left": "20px", "padding-right": "20px", "border-radius": "8px", "display": "inline-flex"},
        {"background-color": "rgb(255, 255, 255)", "color": "rgb(24, 24, 27)", "font-family": "Geist", "font-size": "16px", "font-weight": "400", "border-width": "1px", "border-color": "rgb(229, 231, 235)", "border-top-style": "solid", "border-radius": "12px", "padding-top": "24px", "padding-right": "24px", "padding-bottom": "24px", "padding-left": "24px", "box-shadow": "rgba(0, 0, 0, 0.05) 0px 1px 2px 0px", "display": "block"},
        dict(BASE_TEXT, **{"color": "rgb(107, 114, 128)", "margin-top": "22px"}),
        dict(BASE_TEXT, **{"font-size": "16px", "font-weight": "600"}),
    ]
    home = [
        el(0, -1, "body", "body", [0, 0, 1280, 800], "", 0),
        el(1, 0, "h1", "body > h1", [40, 40, 400, 36], "Dashboard", 1, rc=["HomePage"]),
        el(2, 0, "p", "body > p", [40, 90, 400, 20], "Welcome back", 2),
        el(3, 0, "button", "body > button", [40, 130, 140, 44], "Add a task", 3),
        el(4, 0, "div", "body > div", [40, 200, 600, 200], "", 4, rc=["Card"]),
        el(5, 4, "h3", "body > div > h3", [64, 224, 200, 24], "Today", 6),
        el(6, 4, "p", "body > div > p", [64, 260, 500, 20], "Three tasks due", 5),
        el(7, 4, "p", "body > div > p:nth-of-type(2)", [64, 290, 500, 20], "Nothing overdue", 5),
    ]
    styles_tasks = [
        {"background-color": "rgb(250, 250, 250)", "color": "rgb(24, 24, 27)", "font-family": "Geist", "font-size": "16px", "font-weight": "400", "display": "block"},
        dict(BASE_TEXT, **{"font-size": "28px", "font-weight": "600", "color": "rgb(24, 24, 27)"}),
        dict(BASE_TEXT, **{"color": "rgb(113, 113, 122)", "font-size": "13px"}),
        {"color": "rgb(255, 255, 255)", "background-color": "rgb(79, 70, 229)", "font-family": "Geist", "font-size": "14px", "font-weight": "500", "padding-left": "16px", "padding-right": "16px", "border-radius": "6px", "display": "inline-flex"},
        {"background-color": "rgb(255, 255, 255)", "color": "rgb(24, 24, 27)", "font-family": "Geist", "font-size": "16px", "font-weight": "400", "border-width": "1px", "border-color": "rgb(228, 228, 231)", "border-top-style": "solid", "border-radius": "16px", "padding-top": "20px", "padding-right": "20px", "padding-bottom": "20px", "padding-left": "20px", "box-shadow": "rgba(0, 0, 0, 0.1) 0px 4px 6px -1px", "display": "block"},
        dict(BASE_TEXT, **{"color": "rgb(100, 116, 139)", "padding-left": "13px"}),
        {"color": "rgb(185, 28, 28)", "background-color": "rgb(254, 226, 226)", "font-family": "Geist", "font-size": "12px", "font-weight": "500", "padding-top": "2px", "padding-bottom": "2px", "padding-left": "8px", "padding-right": "8px", "border-radius": "9999px", "display": "inline-flex"},
        {"color": "rgb(24, 24, 27)", "background-color": "rgb(255, 255, 255)", "font-family": "Geist", "font-size": "14px", "font-weight": "400", "border-width": "1px", "border-color": "rgb(228, 228, 231)", "border-top-style": "solid", "border-radius": "6px", "padding-left": "12px", "padding-right": "12px", "display": "block"},
    ]
    tasks = [
        el(0, -1, "body", "body", [0, 0, 1280, 800], "", 0),
        el(1, 0, "h1", "body > h1", [40, 40, 400, 34], "Tasks", 1, rc=["TasksPage"]),
        el(2, 0, "p", "body > p", [40, 90, 400, 18], "8 open", 2),
        el(3, 0, "button", "body > button", [40, 130, 100, 36], "Add task", 3, rc=["Button", "TasksPage"]),
        el(4, 0, "div", "body > div", [40, 200, 600, 200], "", 4, rc=["ProjectCard"]),
        el(5, 4, "p", "body > div > p", [64, 224, 500, 20], "Website redesign", 5),
        el(6, 4, "p", "body > div > p:nth-of-type(2)", [64, 254, 500, 20], "Due Friday", 5),
        el(7, 0, "span", "body > span", [40, 420, 48, 20], "High", 6),
        el(8, 0, "input", "body > input", [40, 460, 300, 36], "Search", 7, type="text"),
    ]
    with open(os.path.join(folder, "home__1280.json"), "w") as fh:
        json.dump(snapshot("home__1280", "/", home, styles_home), fh)
    with open(os.path.join(folder, "tasks__1280.json"), "w") as fh:
        json.dump(snapshot("tasks__1280", "/tasks", tasks, styles_tasks), fh)


class ColorTests(unittest.TestCase):
    def test_parse_all_syntaxes(self):
        for v, expected in [("#6b7280", "#6b7280"), ("rgb(107, 114, 128)", "#6b7280"), ("rgba(0, 0, 0, 0.5)", "#00000080"), ("hsl(220 9% 46%)", "#6b7280"), ("oklch(55.1% 0.027 264.364)", "#6a7282"), ("color(srgb 0.42 0.447 0.502)", "#6b7280"), ("lab(92.243% 10.2865 3.83865)", "#ffe2e2"), ("white", "#ffffff"), ("transparent", "#00000000")]:
            c = C.parse(v)
            self.assertIsNotNone(c, v)
            self.assertEqual(C.to_hex(c), expected, v)
        self.assertIsNone(C.parse("currentcolor"))
        self.assertIsNone(C.parse("not a colour"))

    def test_distance_and_palette(self):
        self.assertLess(C.delta(C.parse("#6b7280"), C.parse("#71717a")), 0.03)
        self.assertGreater(C.delta(C.parse("#f3f4f6"), C.parse("#e5e7eb")), 0.03)
        names = [h["name"] for h in C.nearest_tailwind(C.parse("#4f46e5"))]
        self.assertIn("indigo-600", names)

    def test_cluster_rules(self):
        cl = C.cluster([("#ffffff", 100), ("#f9fafb", 50), ("#fafafa", 20), ("#6b7280", 40), ("#71717a", 30), ("#e5e7eb", 10), ("#e0e7ff", 5), ("#111827", 20), ("#18181b", 10)])
        groups = [sorted(m["hex"] for m in c["members"]) for c in cl]
        self.assertIn(["#f9fafb", "#fafafa"], groups)
        self.assertIn(["#6b7280", "#71717a"], groups)
        self.assertIn(["#111827", "#18181b"], groups)
        self.assertIn(["#ffffff"], groups)  # white never merges
        self.assertIn(["#e0e7ff"], groups)  # tint never merges with a grey
        self.assertIn(["#e5e7eb"], groups)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fake_project(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scan(self):
        r = scan_source.scan(self.tmp)
        p = r["project"]
        self.assertEqual(p["framework"], "next")
        self.assertEqual(p["tailwind_version"], "4")
        self.assertIn("src/app/globals.css", p["tailwind_v4_theme_files"])
        self.assertIn("lucide-react", p["icon_libraries"])
        paths = {x["path"] for x in r["routes"]}
        self.assertEqual(paths, {"/", "/tasks", "/tasks/:id"})
        names = {c["name"]: c for c in r["components"]}
        self.assertIn("Button", names)
        self.assertEqual(names["Button"]["usages"], 2)
        self.assertEqual(sorted(names["Button"]["variants"]), ["default", "ghost", "outline"])
        self.assertIn("button", r["drift_signals"]["duplicate_component_kinds"]) if "PrimaryButton" in names else None
        self.assertIn("card", r["drift_signals"]["duplicate_component_kinds"])
        greys = r["drift_signals"]["grey_families"]
        self.assertEqual(set(greys), {"gray", "zinc", "slate", "neutral"})
        self.assertIn("p-[18px]", r["drift_signals"]["off_grid_spacing"])
        self.assertIn("mt-[22px]", r["drift_signals"]["off_grid_spacing"])
        self.assertIn("--color-brand", r["custom_props"])
        self.assertIn("--color-brand", r["drift_signals"]["semantic_tokens_defined"])
        self.assertEqual(len(r["inline_styles"]), 1)
        colors = r["tailwind"]["by_category"]["color"]
        self.assertEqual(colors["text-gray-500"]["kind"], "palette")
        self.assertEqual(colors["border-[#e5e7eb]"]["kind"], "arbitrary")
        self.assertEqual(colors["bg-brand"]["kind"] if "bg-brand" in colors else "token", "token")
        self.assertNotIn("bg-red-500", colors)  # node_modules skipped
        self.assertIn("border", r["tailwind"]["by_category"])
        self.assertIn("#6b7280", r["css"]["colors"])
        md = scan_source.to_markdown(r)
        self.assertIn("Grey families mixed: 4", md)

    def test_classify_tokens(self):
        c = scan_source.classify_token
        self.assertEqual(c("hover:bg-indigo-700")["variants"], ["hover"])
        self.assertEqual(c("text-sm")["category"], "font_size")
        self.assertEqual(c("text-[15px]")["category"], "font_size")
        self.assertEqual(c("text-gray-500/50")["category"], "color")
        self.assertEqual(c("shadow-sm")["category"], "shadow")
        self.assertEqual(c("shadow-[0_1px_3px_rgba(0,0,0,0.08)]")["category"], "shadow")
        self.assertEqual(c("border-t")["category"], "border")
        self.assertEqual(c("border-zinc-200")["category"], "color")
        self.assertEqual(c("rounded-[10px]")["kind"], "arbitrary")
        self.assertEqual(c("gap-[14px]")["category"], "spacing")
        self.assertEqual(c("w-full")["category"], "sizing")
        self.assertEqual(c("font-semibold")["category"], "font_weight")
        self.assertEqual(c("font-mono")["category"], "font_family")
        self.assertEqual(c("duration-150")["category"], "motion")
        self.assertIsNone(c("flex"))
        self.assertIsNone(c("bg-gradient-to-r"))
        self.assertIsNone(c("items-center"))


class AnalyzeCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fake_project(self.tmp)
        self.snaps = os.path.join(self.tmp, ".design-catalog", "snapshots")
        fake_snapshots(self.snaps)
        scan_source.main([self.tmp, "--quiet"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_analyze_groups_and_outputs(self):
        out = os.path.join(self.tmp, ".design-catalog")
        result = analyze.analyze(self.snaps, os.path.join(out, "scan.json"), out, 0.03, "Test", [os.path.join(self.tmp, "src/app/globals.css")], html=True)
        for f in ("proposals.json", "summary.md", "report.html", "drift.md", "drift.json"):
            self.assertTrue(os.path.exists(os.path.join(out, f)), f)
        keys = {g["key"] for g in result["groups"]}
        self.assertIn("greys", keys)
        self.assertIn("type", keys)
        self.assertIn("spacing", keys)
        self.assertIn("buttons", keys)
        self.assertIn("cards", keys)
        # grey text values merge into one cluster
        grey = next(d for d in result["decisions"] if d["area"] == "color" and any(m["hex"] == "#6b7280" for m in d["members"]))
        self.assertEqual(grey["action"], "merge")
        self.assertIn("#71717a", [m["hex"] for m in grey["members"]])
        self.assertTrue(grey["name"].startswith("text"))
        # existing token recognised
        brand = next(d for d in result["decisions"] if d["survivor_hex"] == "#4f46e5")
        self.assertEqual(brand["existing_token"], "--color-brand")
        # type sizes off scale
        sizes = {d["from"] for d in result["decisions"] if d["area"] == "font_size"}
        self.assertEqual(sizes, {13.0, 15.0, 28.0})
        # spacing off grid
        sp = {d["from"] for d in result["decisions"] if d["area"] == "spacing"}
        self.assertEqual(sp, {13.0, 22.0})
        # headings differ
        self.assertTrue(any(d["area"] == "heading" and d["level"] == "h1" for d in result["decisions"]))
        # components
        btn = [d for d in result["decisions"] if d["area"] == "button"]
        self.assertTrue(any(len(d["variants"]) == 2 for d in btn))
        card = next(d for d in result["decisions"] if d["area"] == "card")
        self.assertEqual(len(card["variants"]), 2)
        self.assertTrue(any(d["area"] == "badge" for d in result["decisions"]))
        self.assertTrue(any(d["area"] == "input" for d in result["decisions"]))
        # drift lists colours not in the token file
        self.assertGreater(result["drift"]["total"], 0)
        with open(os.path.join(out, "summary.md"), encoding="utf-8") as fh:
            summary = fh.read()
        self.assertIn("## Decisions", summary)
        self.assertIn("G1", summary)

    def test_compare_classifies_changes(self):
        out = os.path.join(self.tmp, ".design-catalog")
        result = analyze.analyze(self.snaps, os.path.join(out, "scan.json"), out, 0.03, "Test", [], html=False)
        # approve the grey group
        for g in result["groups"]:
            if g["key"] == "greys":
                g["approved"] = True
        with open(os.path.join(out, "proposals.json"), "w") as fh:
            json.dump(result, fh, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        grey = next(d for d in result["decisions"] if d["area"] == "color" and any(m["hex"] == "#6b7280" for m in d["members"]))
        survivor = grey["survivor"]
        self.assertEqual(C.to_hex(C.parse(survivor)), "#6b7280")  # the most used grey wins
        # after: on /tasks the zinc grey (a retired member) became the survivor (approved), the button radius
        # changed (unapproved), the h1 moved (layout); home untouched
        after = os.path.join(self.tmp, ".design-catalog", "after")
        shutil.copytree(self.snaps, after)
        with open(os.path.join(after, "tasks__1280.json")) as fh:
            tasks = json.load(fh)
        tasks["styles"][2]["color"] = survivor
        tasks["styles"][3]["border-radius"] = "8px"
        tasks["elements"][1]["r"] = [40, 44, 400, 34]
        with open(os.path.join(after, "tasks__1280.json"), "w") as fh:
            json.dump(tasks, fh)
        mapping = compare.Mapping(result, False)
        self.assertIn(grey["id"], mapping.approved_ids)
        before = compare.load(self.snaps)
        aft = compare.load(after)
        r = compare.compare_screen("tasks", before["tasks__1280.json"], aft["tasks__1280.json"], mapping, 1.0)
        self.assertEqual(len(r["approved"]), 1, r)
        self.assertEqual(r["approved"][0]["decision"], grey["id"])
        self.assertEqual(len(r["unapproved"]), 1)
        self.assertEqual(r["unapproved"][0]["prop"], "border-radius")
        self.assertEqual(len(r["layout"]), 1)
        r2 = compare.compare_screen("home", before["home__1280.json"], aft["home__1280.json"], mapping, 1.0)
        self.assertEqual((len(r2["approved"]), len(r2["unapproved"]), len(r2["layout"])), (0, 0, 0))
        # CLI exit codes
        rc = compare.main([self.snaps, self.snaps, "--mapping", os.path.join(out, "proposals.json"), "--out", os.path.join(out, "c.md")])
        self.assertEqual(rc, 0)
        rc = compare.main([self.snaps, after, "--mapping", os.path.join(out, "proposals.json"), "--out", os.path.join(out, "c.md")])
        self.assertEqual(rc, 1)

    def test_scripts_run_from_anywhere(self):
        env = dict(os.environ)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "scan_source.py"), self.tmp, "--md", "--quiet"], capture_output=True, text=True, cwd="/", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("# Source scan", r.stdout)
        r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "analyze.py"), "--snapshots", self.snaps], capture_output=True, text=True, cwd="/", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["node", "--check", os.path.join(HERE, "receive.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["node", "--check", os.path.join(HERE, "snapshot.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(process.argv[1],'utf8'))", os.path.join(HERE, "collect-styles.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
