# Product Map

> A Product Map is like a sitemap for what your software **does**, not just where its pages are.

A sitemap lists pages and navigation. A Product Map describes the product as users experience it, and it lives in your repository so humans and coding agents share the same product-level model.

It has two parts:

**Feature Map** (`/product/features.md`)
What capabilities exist? User-visible features, grouped by product area, each with a stable ID.

**Product Flows** (`/product/flows/*.md`)
How does the product behave? One Mermaid flowchart per major user goal: actions, decisions, branches, failures users notice, outcomes.

```text
Product Map
├── Feature Map
│   └── What capabilities exist?
│
└── Product Flows
    └── How does the product behave?
```

A feature can take part in many flows. A flow can use many features. Neither is architecture documentation: files, components and APIs appear only as secondary evidence, so the map stays true across refactors and stays readable by people who never open the code.

## Why keep it in the repo?

- The next agent entering the repo reads `/product/README.md` and knows what the product is in a minute.
- Behavior changes and map changes ship in the same PR, so the map does not rot.
- Reviewers can check a diagram instead of reverse-engineering a diff. When behavior changes, the PR description carries the updated flow diagram, which GitHub renders inline.
- It is plain Markdown. No build step, no Node requirement, works in any editor and on GitHub.

## Workflow

```text
Install Product Map skill
        ↓
Ask agent to map the product
        ↓
Agent explores app + code
        ↓
/product is created
        ↓
@nuthinking/product-map is configured
        ↓
Agent launches viewer when possible
        ↓
Otherwise recommends:
npm run product-map
        ↓
Browse the Product Map locally
```

## Install

Any agent that reads `SKILL.md`:

```bash
npx skills@latest add nuthinking/skills
```

Claude Code, as a managed plugin, from inside a session:

```text
/plugin install nuthinking-skills --marketplace nuthinking/skills
```

Or from your shell:

```bash
claude plugin marketplace add nuthinking/skills
claude plugin install nuthinking-skills@nuthinking
```

Or copy the `product-map` folder into your agent's skills directory (for example `.claude/skills/product-map`).

## Use

Then ask your agent, in its own words:

- "Map this product." or "Create a Product Map for this app." (Create)
- "I changed how sharing works. Update the Product Map." (Update)
- "Does `/product` still match the app?" (Review)

The skill:

1. Explores the running app like a user when it can, then reads routes, handlers, models and tests to fill in conditions and failures.
2. Writes `/product/README.md`, `/product/features.md` and one file per major flow (usually 5 to 15).
3. Adds a short pointer section to `AGENTS.md` / `CLAUDE.md` so future agents read and maintain the map.
4. In Node projects, installs `@nuthinking/product-map` as a dev dependency with your existing package manager and adds a `product-map` script.
5. Validates the result with the viewer's validator when available, and always with the skill's own `scripts/validate.py` (Python 3, no dependencies). When the viewer is not set up, it copies that script to `product/validate.py` so teammates and CI can run `python3 product/validate.py`.
6. Launches the graphical viewer, or tells you the exact command to run.

## The viewer

`@nuthinking/product-map` is a separate npm package that reads `/product`, validates its structure and serves a local graphical browser for features and flows.

```bash
npm run product-map        # when configured by the skill
npx @nuthinking/product-map  # one-off, any repo with Node available
```

The Markdown is always the source of truth. The viewer only renders it. Until the package is available, the Mermaid diagrams render on GitHub and in most Markdown previews, so `product/README.md` is a fine starting point on its own.

## What is in this folder

```text
product-map/
  SKILL.md                         The skill: modes, discovery rules, what good looks like
  references/
    format.md                      The file format contract (frontmatter, IDs, Mermaid rules)
    feature-map-example.md         A worked features.md
    flow-example.md                A worked flow file
    agent-instructions.md          The section added to AGENTS.md / CLAUDE.md
    pr-section.md                  The "Product behavior" section for PR descriptions
  scripts/
    validate.py                    Structural validator, Python 3, no dependencies
    test_validate.py               Regression tests for the validator
```
