#!/usr/bin/env python3
"""Regression tests for validate.py. Run: python3 scripts/test_validate.py"""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

FLOW = textwrap.dedent("""\
    ---
    id: add-task
    title: Add a task
    features:
      - add-task
    status: active
    ---

    # Add a task

    ## Flow

    ```mermaid
    flowchart TD
        A[Open quick add] --> B[Type task text]
        B --> C{Anything recognized?}
        C -->|Yes| D[Show as removable chips]
        C -->|No| E[Keep as plain text]
        D --> F[Save]
        E --> F
        F --> G([Task appears in its project])
    ```
    """)

DEMO = textwrap.dedent("""\
    id: add-task
    title: Add a task
    flow: add-task
    style: device
    viewport: 1440x900
    start: /inbox
    watch:
      - src/server/tasks/**
    steps:
      - label: Open quick add
        do: click
        target: role=button[name="Add task"]
        say: Press the plus button, or hit Q from anywhere.
      - label: Type task text
        do: type
        target: "[data-testid=quick-add-input]"   # the input
        text: Call the dentist tomorrow 9am
        say: Dates and times are recognised as you type.
      - label: Save
        do: press
        key: Enter
        settle: 800
        say: The task lands in Inbox, scheduled for tomorrow.
    """)

CONFIG = {"serve": "npm run demo", "url": "http://127.0.0.1:3000", "setup": "npm run seed:demo", "defaults": {"style": "device", "theme": "light"}, "store": {"target": "none"}}


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.product = os.path.join(self.root, "product")
        self.demos = os.path.join(self.product, "demos")
        os.makedirs(os.path.join(self.product, "flows"))
        os.makedirs(self.demos)
        self.write("flows/add-task.md", FLOW)
        self.write("demos/config.json", json.dumps(CONFIG))
        self.write("demos/add-task.yaml", DEMO)

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, content):
        path = os.path.join(self.product, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def run_validate(self):
        return validate.validate(self.demos)

    def messages(self, rep, level=None):
        return [i["message"] for i in rep.items if level is None or i["level"] == level]

    def assertHas(self, rep, needle, level=None):
        self.assertTrue(any(needle in m for m in self.messages(rep, level)), f"expected '{needle}' in {self.messages(rep, level)}")

    def assertNotHas(self, rep, needle, level=None):
        self.assertFalse(any(needle in m for m in self.messages(rep, level)), f"did not expect '{needle}' in {self.messages(rep, level)}")


class YamlTests(unittest.TestCase):
    def test_parses_demo(self):
        data = validate.parse_yaml(DEMO)
        self.assertEqual(data["id"], "add-task")
        self.assertEqual(data["watch"], ["src/server/tasks/**"])
        self.assertEqual(len(data["steps"]), 3)
        self.assertEqual(data["steps"][1]["target"], "[data-testid=quick-add-input]")
        self.assertEqual(data["steps"][2]["settle"], 800)
        self.assertEqual(data["steps"][0]["target"], 'role=button[name="Add task"]')

    def test_scalars_and_inline_lists(self):
        data = validate.parse_yaml("a: true\nb: 12\nc: [x, y]\nd: 'it''s'\ne:\nf: \"q\\\"\"\n")
        self.assertEqual(data, {"a": True, "b": 12, "c": ["x", "y"], "d": "it's", "e": None, "f": 'q"'})

    def test_colon_inside_value(self):
        data = validate.parse_yaml("say: Note: dates are recognised\n")
        self.assertEqual(data["say"], "Note: dates are recognised")

    def test_nested_list_items(self):
        data = validate.parse_yaml("steps:\n  -\n    do: click\n    target: a\n  - do: press\n    key: Enter\n")
        self.assertEqual(data["steps"], [{"do": "click", "target": "a"}, {"do": "press", "key": "Enter"}])

    def test_errors(self):
        with self.assertRaises(validate.YamlError):
            validate.parse_yaml("a:\n\tb: 1\n")
        with self.assertRaises(validate.YamlError):
            validate.parse_yaml("a: 1\n  b: 2\n")
        with self.assertRaises(validate.YamlError):
            validate.parse_yaml("a: 1\na: 2\n")
        with self.assertRaises(validate.YamlError):
            validate.parse_yaml("a: &x 1\n")
        with self.assertRaises(validate.YamlError):
            validate.parse_yaml("a: |\n  text\n")


class ValidatorTests(Base):
    def test_valid(self):
        rep = self.run_validate()
        self.assertEqual(rep.errors, [], self.messages(rep))
        self.assertEqual(rep.warnings, [], self.messages(rep))
        self.assertHas(rep, "'Show as removable chips' is not shown", "info")

    def test_id_mismatch_and_missing(self):
        self.write("demos/add-task.yaml", DEMO.replace("id: add-task", "id: other"))
        self.assertHas(self.run_validate(), "must equal the file name", "error")
        self.write("demos/add-task.yaml", DEMO.replace("id: add-task\n", ""))
        self.assertHas(self.run_validate(), "id is required", "error")

    def test_required_top_keys(self):
        self.write("demos/add-task.yaml", DEMO.replace("title: Add a task\n", "").replace("start: /inbox\n", ""))
        rep = self.run_validate()
        self.assertHas(rep, "title is required", "error")
        self.assertHas(rep, "start is required", "error")

    def test_unknown_action_and_missing_keys(self):
        self.write("demos/add-task.yaml", DEMO.replace("do: press", "do: tap").replace("    text: Call the dentist tomorrow 9am\n", ""))
        rep = self.run_validate()
        self.assertHas(rep, "unknown action 'tap'", "error")
        self.assertHas(rep, "step 2 (type): 'text' is required", "error")

    def test_one_of(self):
        self.write("demos/add-task.yaml", DEMO + "  - do: wait\n    say: Waiting.\n")
        self.assertHas(self.run_validate(), "exactly one of ms, target", "error")

    def test_unknown_step_key_warns(self):
        self.write("demos/add-task.yaml", DEMO.replace("settle: 800", "settle: 800\n    delay: 3"))
        self.assertHas(self.run_validate(), "unknown key 'delay'", "warning")

    def test_positional_target(self):
        self.write("demos/add-task.yaml", DEMO.replace('role=button[name="Add task"]', "li:nth-child(3) button"))
        self.assertHas(self.run_validate(), "positional target", "warning")
        self.write("demos/add-task.yaml", DEMO.replace('role=button[name="Add task"]', "li:nth-child(3) button").replace("label: Open quick add", "label: Open the third task"))
        rep = self.run_validate()
        self.assertNotHas(rep, "positional target")
        self.assertHas(rep, "'Open the third task' is not a node label", "warning")

    def test_flow_missing(self):
        self.write("demos/add-task.yaml", DEMO.replace("flow: add-task", "flow: nope"))
        self.assertHas(self.run_validate(), "flow 'nope' does not exist", "error")

    def test_no_flow_warns_when_map_exists(self):
        self.write("demos/add-task.yaml", DEMO.replace("flow: add-task\n", ""))
        self.assertHas(self.run_validate(), "not linked to a Product Map flow", "warning")

    def test_no_product_map(self):
        shutil.rmtree(os.path.join(self.product, "flows"))
        rep = self.run_validate()
        self.assertEqual(rep.errors, [], self.messages(rep))
        self.assertHas(rep, "no product/flows folder", "warning")

    def test_look(self):
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: fancy\ntheme: brand\ndevice: tv\nintro:\n  title: Hi\n  length: 3"))
        rep = self.run_validate()
        self.assertHas(rep, "style must be one of", "error")
        self.assertHas(rep, "theme must be light or dark", "error")
        self.assertHas(rep, "device must be one of", "error")
        self.assertHas(rep, "intro: unknown key 'length'", "warning")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: device\noutro:\n  fade: maybe"))
        self.assertHas(self.run_validate(), "outro.fade must be true or false", "error")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: device\nbackground: brand"))
        self.assertHas(self.run_validate(), "background 'brand' is not a built-in wallpaper", "error")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: device\nbackground: assets/bg.jpg"))
        self.assertHas(self.run_validate(), "background: demos/assets/bg.jpg does not exist", "error")
        self.write("demos/assets/bg.jpg", "x")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: device\ntheme: dark\nbackground: assets/bg.jpg"))
        rep = self.run_validate()
        self.assertNotHas(rep, "background")
        self.assertNotHas(rep, "theme")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "style: device\nbackground: '#101418'"))
        self.assertNotHas(self.run_validate(), "background")
        self.write("demos/add-task.yaml", DEMO.replace("do: click", "do: click\n    zoom: 7"))
        self.assertHas(self.run_validate(), "'zoom' must be a scale between 1 and 3", "error")
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "captions:\n  size: 9\n  radius: 4px\n  weight: bold\noutput:\n  loop: yes"))
        rep = self.run_validate()
        self.assertHas(rep, "captions: unknown key 'weight'", "warning")
        self.assertEqual(rep.errors, [], self.messages(rep))

    def test_narration_gap_and_pointer_talk(self):
        self.write("demos/add-task.yaml", DEMO.replace("    say: The task lands in Inbox, scheduled for tomorrow.\n", ""))
        self.assertHas(self.run_validate(), "narration on 2 of 3 steps", "warning")
        self.write("demos/add-task.yaml", DEMO.replace("say: Press the plus button, or hit Q from anywhere.", "say: Click the plus button."))
        self.assertHas(self.run_validate(), "describes the pointer", "warning")

    def test_narration_off_silences_gap(self):
        self.write("demos/add-task.yaml", DEMO.replace("style: device", "narration: false").replace("    say: The task lands in Inbox, scheduled for tomorrow.\n", ""))
        self.assertNotHas(self.run_validate(), "narration on")

    def test_settle(self):
        self.write("demos/add-task.yaml", DEMO.replace("settle: 800", "settle: 99999\n    capture: video"))
        rep = self.run_validate()
        self.assertHas(rep, "'settle' must be milliseconds", "error")
        self.assertHas(rep, "unknown key 'capture'", "warning")

    def test_viewport(self):
        self.write("demos/add-task.yaml", DEMO.replace("viewport: 1440x900", "viewport: wide"))
        self.assertHas(self.run_validate(), "viewport must look like", "error")

    def test_too_many_steps(self):
        extra = "".join(f"  - do: press\n    key: Tab\n    say: Step {i}.\n" for i in range(30))
        self.write("demos/add-task.yaml", DEMO + extra)
        self.assertHas(self.run_validate(), "split the demo", "warning")

    def test_parse_error_reported_with_line(self):
        self.write("demos/add-task.yaml", "id: add-task\n  title: x\n")
        rep = self.run_validate()
        self.assertHas(rep, "cannot parse", "error")
        self.assertEqual(rep.errors[0]["line"], 2)

    def test_duplicate_ids(self):
        self.write("demos/add-task-2.yaml", DEMO)
        self.assertHas(self.run_validate(), "must equal the file name", "error")
        self.assertHas(self.run_validate(), "duplicate id 'add-task'", "error")

    def test_config(self):
        self.write("demos/config.json", "{")
        self.assertHas(self.run_validate(), "not valid JSON", "error")
        self.write("demos/config.json", json.dumps({"serve": "x"}))
        self.assertHas(self.run_validate(), "url is required", "error")
        self.write("demos/config.json", json.dumps({"url": "http://x", "store": {"target": "ftp"}}))
        rep = self.run_validate()
        self.assertHas(rep, "store.target must be", "error")
        self.assertHas(rep, "no setup command", "warning")
        os.remove(os.path.join(self.demos, "config.json"))
        self.assertHas(self.run_validate(), "missing; the recorder needs", "warning")

    def test_output(self):
        self.write("demos/add-task.yaml", DEMO.replace("viewport: 1440x900", "viewport: 1440x900\noutput:\n  fps: 30\n  quality: high\n  format: mp4"))
        rep = self.run_validate()
        self.assertEqual(rep.errors, [], self.messages(rep))
        self.write("demos/add-task.yaml", DEMO.replace("viewport: 1440x900", "viewport: 1440x900\noutput:\n  fps: fast\n  quality: best\n  codec: h264"))
        rep = self.run_validate()
        self.assertHas(rep, "output.fps must be a positive integer", "error")
        self.assertHas(rep, "output.quality must be one of", "error")
        self.assertHas(rep, "unknown key 'codec'", "warning")

    def test_store(self):
        self.write("demos/config.json", json.dumps({"url": "http://x", "setup": "s", "store": {"target": "s3", "bucket": "b"}}))
        rep = self.run_validate()
        self.assertHas(rep, "store.baseUrl is required", "error")
        self.write("demos/config.json", json.dumps({"url": "http://x", "setup": "s", "store": {"target": "s3", "bucket": "b", "baseUrl": "https://d", "secret": "x"}}))
        self.assertHas(self.run_validate(), "credentials belong in the environment", "error")
        self.write("demos/config.json", json.dumps({"url": "http://x", "setup": "s"}))
        self.assertHas(self.run_validate(), "no store", "warning")

    def test_auth(self):
        base = {"url": "http://x", "setup": "s", "store": {"target": "none"}}
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "sso"}}))
        self.assertHas(self.run_validate(), "auth.strategy must be one of", "error")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "form", "path": "/login", "steps": [{"do": "type", "target": "role=textbox[name=Password]", "text": "hunter2.x"}, {"do": "tap"}]}}))
        rep = self.run_validate()
        self.assertHas(rep, "auth.steps[1] types a literal value", "warning")
        self.assertHas(rep, "auth.steps[2] must be a step", "error")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "form", "path": "/auth/demo"}}))
        self.assertNotHas(self.run_validate(), "auth.steps")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "form", "path": "/auth/demo", "steps": "none"}}))
        self.assertHas(self.run_validate(), "auth.steps must be a list", "error")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "form", "path": "/login", "steps": [{"do": "type", "target": "role=textbox[name=Email]", "text": "$PRODUCT_DEMO_USER"}, {"do": "press", "key": "Enter"}]}}))
        rep = self.run_validate()
        self.assertEqual(rep.errors, [], self.messages(rep))
        self.assertNotHas(rep, "literal value")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "script"}}))
        self.assertHas(self.run_validate(), "auth.command is required", "error")
        self.write("demos/config.json", json.dumps({**base, "auth": {"strategy": "state", "path": "state.json"}}))
        self.assertHas(self.run_validate(), "local use only", "warning")

    def test_main_accepts_product_dir(self):
        self.assertEqual(validate.main([self.product]), 0)
        self.assertEqual(validate.main([self.demos]), 0)
        self.write("demos/add-task.yaml", DEMO.replace("do: press", "do: tap"))
        self.assertEqual(validate.main([self.product, "--json"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
