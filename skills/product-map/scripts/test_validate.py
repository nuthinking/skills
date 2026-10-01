#!/usr/bin/env python3
"""Regression tests for validate.py. Run: python3 scripts/test_validate.py"""
import os
import shutil
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

FEATURES = textwrap.dedent("""\
    # Feature Map

    ## Area

    ### Add a task
    **ID:** `add-task`
    **Description:** Add a task.
    **Flows:** [Add a task](flows/add-task.md)
    **Status:** `active`
    """)

README = textwrap.dedent("""\
    # App

    See [Feature Map](features.md#area) and [Add a task](flows/add-task.md).
    """)


FLOW_TEMPLATE = textwrap.dedent("""\
    ---
    id: add-task
    title: Add a task
    features:
    @features@
    status: active
    ---

    # Add a task

    ## Goal

    Goal.

    @heading@

    ```mermaid
    flowchart TD
    @body@
    ```
    """)


def flow(features="  - add-task", diagram_heading="## Flow", mermaid_body="    A[Start] --> B{Ok?}\n    B -->|Yes| C([Done])\n    B -->|No| A"):
    return FLOW_TEMPLATE.replace("@features@", features).replace("@heading@", diagram_heading).replace("@body@", mermaid_body)


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.product = os.path.join(self.dir, "product")
        os.makedirs(os.path.join(self.product, "flows"))
        self.write("README.md", README)
        self.write("features.md", FEATURES)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, rel, content):
        with open(os.path.join(self.product, rel), "w", encoding="utf-8") as fh:
            fh.write(content)

    def run_validate(self):
        rep = validate.validate(self.product)
        return [i["message"] for i in rep.errors], [i["message"] for i in rep.warnings]

    def test_clean_map_passes(self):
        self.write("flows/add-task.md", flow())
        errors, warnings = self.run_validate()
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unindented_feature_list_is_parsed(self):
        self.write("flows/add-task.md", flow(features="- add-taskz"))
        errors, _ = self.run_validate()
        self.assertTrue(any("unknown feature 'add-taskz'" in e for e in errors), errors)

    def test_backticked_status_accepted_and_bad_status_rejected(self):
        self.write("flows/add-task.md", flow())
        errors, _ = self.run_validate()
        self.assertEqual(errors, [])
        self.write("features.md", FEATURES.replace("`active`", "`shipped`"))
        errors, _ = self.run_validate()
        self.assertTrue(any("status 'shipped'" in e for e in errors), errors)

    def test_diagram_outside_flow_section_is_an_error(self):
        self.write("flows/add-task.md", flow(diagram_heading="## Flow\n\n## Notes"))
        errors, _ = self.run_validate()
        self.assertTrue(any("inside the '## Flow' section" in e for e in errors), errors)

    def test_keyword_prefixed_node_ids_are_checked(self):
        self.write("flows/add-task.md", flow(mermaid_body="    style-picker[Pick style] --> end-x[Done (now)]"))
        _, warnings = self.run_validate()
        self.assertTrue(any("quote it" in w for w in warnings), warnings)

    def test_reserved_word_end_still_rejected(self):
        self.write("flows/add-task.md", flow(mermaid_body="    A[Start] --> end"))
        errors, _ = self.run_validate()
        self.assertTrue(any("'end' is a reserved word" in e for e in errors), errors)

    def test_digits_in_kebab_ids_do_not_split(self):
        self.write("flows/add-task.md", flow(mermaid_body="    add-2-cart[Add to cart] --> B{Ok?}\n    B -->|Yes| C([Done])\n    B -->|No| add-2-cart"))
        _, warnings = self.run_validate()
        self.assertEqual(warnings, [])

    def test_anchors_ignore_headings_inside_nested_fences(self):
        self.write("features.md", FEATURES + "\n````md\n### Not a feature\n```\n### Also not\n```\n````\n")
        self.write("flows/add-task.md", flow())
        errors, _ = self.run_validate()
        self.assertEqual(errors, [])
        anchors = validate.heading_anchors(open(os.path.join(self.product, "features.md")).read())
        self.assertNotIn("not-a-feature", anchors)
        self.assertNotIn("also-not", anchors)


if __name__ == "__main__":
    unittest.main(verbosity=1)
