---
name: product-map
description: Create, update, or review a repo-native Product Map in /product. A Product Map is a sitemap for what the software does, not just where its pages are. It has a Feature Map (what capabilities exist) and Product Flows (Mermaid diagrams of how the product behaves), written so humans and coding agents share one product-level model. Use this skill whenever someone asks to map, document, inventory, or explain what an app or product does, wants a sitemap, feature list, user flows, or user-journey docs, asks "what does this app do", mentions a Product Map or the /product folder, or asks whether the docs still match the app. Also use it when you change user-facing behavior in a repo that already has /product, so the map is updated in the same change.
---

# Product Map

A Product Map describes a product the way a user experiences it. It lives in the repo as Markdown under `/product`, next to the code, so the next human or agent entering the repo can learn what the product does in a minute instead of re-deriving it from source.

```text
Product Map
├── Feature Map      /product/features.md     What capabilities exist?
└── Product Flows    /product/flows/*.md      How does the product behave?
```

A feature can take part in many flows. A flow can use many features.

**This is not architecture documentation.** Describe observable product behavior: what users can do, what the system does in response, important states, decisions, alternative paths, failures users notice, and how major capabilities relate. Files, components, APIs and tests are supporting evidence and go in a secondary section. If a sentence would still be true after a full rewrite in another framework, it belongs in the Product Map. If it would not, it probably does not.

The Markdown is the source of truth and must stay useful on its own. The optional viewer, the npm package `@nuthinking/product-map`, only reads, validates and renders it.

## Files

```text
/product
  README.md        One-minute mental model: what, who, major capabilities, major flows. Links everything.
  features.md      Feature Map: features grouped by product area, each with a stable ID.
  /flows
    <flow-id>.md   One file per major flow: frontmatter, Goal, Mermaid diagram, Behavior details, links.
```

Exact file formats, frontmatter, ID rules and Mermaid conventions: [references/format.md](references/format.md). Read it before writing or reviewing any Product Map file. Worked examples for create and update: [references/feature-map-example.md](references/feature-map-example.md) and [references/flow-example.md](references/flow-example.md).

## Choose a mode

| Situation | Mode |
|---|---|
| `/product` does not exist, or exists but is empty or a stub | **Create** |
| Product behavior changed, or you are about to change it | **Update** |
| Someone asks whether the map still matches the app, or you suspect drift | **Review** |

### Create

1. **Learn the product** using the running app first and the code second (see *Discovering behavior*). Keep notes on features, screens, states, decisions and failures as you go.
2. **Draft the Feature Map.** List user-visible capabilities, group them into product areas, give each a stable kebab-case ID. See *What a good feature looks like*.
3. **Pick the major flows.** Aim for roughly 5 to 15 for a normal application. Each flow is a meaningful user goal or product sequence, not a single click. See *What a good flow looks like*.
4. **Write the files** following `references/format.md`: `features.md`, one file per flow, then `README.md` last so it can link to everything.
5. **Configure the viewer** when the repo uses Node-compatible package management (see *Viewer setup*).
6. **Validate** (see *Validation*) and fix every error. If no viewer validate command works in this repo, copy the validator to `product/validate.py` as that section describes.
7. **Update agent instructions** (see *Agent instructions*), using the validation command that actually works in this repo.
8. **Launch or recommend the viewer** (see *Viewer launch*).
9. **Report** using the completion checklist at the end of this file.

### Update

1. Read `/product/README.md`, then only the features and flows plausibly affected by the change.
2. Work out what changed in *product behavior*: capabilities, entry points, navigation, conditions, permissions, states, outcomes, branches, failure handling, relationships between features. If nothing observable changed, stop; the map is fine.
3. Edit only the affected features and flows. Keep existing wording and structure where it is still correct. Do not rewrite healthy files for style.
4. Add a new flow only for a genuinely new major goal. A new branch or step belongs inside an existing flow.
5. When behavior is removed, delete the feature or flow, or set `status: deprecated` if it still ships behind a flag or for some users. Remove dangling links either way.
6. Validate. Fix every error. If the repo's validation setup is out of line with *Validation* (for example a placeholder or absolute path in `AGENTS.md`, or no `product/validate.py` where one is needed), bring it into line now; that is maintenance, not churn.
7. If the change is substantial or changes a diagram's structure (nodes, edges, branches), launch or recommend the viewer so the result can be checked visually. A relabeled node is a wording fix.
8. Make the Product Map edits part of the same commit or PR as the behavior change, and describe the change in the PR body (see *Pull requests*). If you notice a code-level follow-up while doing this (a missing migration, a test that still asserts the old behavior), mention it to the user; do not fix it unasked.

### Review

1. Read the whole `/product` folder.
2. Start where drift is likeliest: the uncommitted diff (`git status`, `git diff`) and the commits since the map was last touched. A map written at one commit can only be stale where the code changed after it.
3. Then compare it against the running app (if available), source code and tests, feature by feature and flow by flow. Look for: capabilities missing from the map, documented capabilities that no longer exist, flows whose diagram no longer matches the real sequence, wrong conditions or outcomes, stale entry points, broken links, and files marked unclear that could now be resolved. Also check hygiene: `AGENTS.md` / `CLAUDE.md` point at `/product`, the validation command is portable, and the viewer setup matches *Viewer setup*.
4. Run validation and include its errors and warnings.
5. Report discrepancies as a list, each with the evidence (screen, file, test) that shows the real behavior, followed by any hygiene items. Do not change product behavior to match the docs.
6. Only edit the map if asked to fix it. Then follow *Update*.

## Discovering behavior

Use the running application as the primary source whenever one is available, and the code to explain what you observed.

**Find or start the app.** Check the README, `package.json` scripts, Makefile, Procfile, docker-compose, or `.env.example` for how to run it. Prefer an already-running local or staging instance. Starting a dev server locally is fine. Never run discovery against production data in a way that creates, changes or deletes real records.

**Explore like a user.** If you have browser automation or computer-use tools, use them. Follow the navigation, open every major screen, submit forms, trigger validation, look at empty, loading and error states, use menus and secondary actions, follow each major flow from start to end, and try different roles or account states when there is a safe way to do so. Create and edit throwaway data in a local or test environment; do nothing irreversible. A public demo or shared staging backend counts as shared: keep throwaway data minimal and delete it when done. If verifying something would leave permanent data there (for example an account that cannot be deleted), fall back to the code for that part and say so.

**Optional services.** Many apps degrade when search, mail, queues, payments or AI providers are not configured. Document what you actually observed in that state, and separately the configured behavior as the code describes it, labeled as such. Do not spin up every external service just to confirm the code.

**Then use the code and tests** to clarify what the UI cannot show: hidden conditions, permissions, feature flags, edge cases, failures, background behavior, things that are hard to trigger by hand. Good evidence: routes, navigation config, screens, user-facing copy, UI handlers, server actions, API handlers, data models, tests, existing docs, permission checks, error handling.

**Rules of evidence**
- Never treat one file as the whole story of a feature. Cross-check at least two sources before stating a condition or outcome.
- When the code is unambiguous but you did not exercise the path, state the behavior and append "(from code, not exercised)". Reserve the unclear marker for genuinely insufficient evidence.
- When UI and code disagree, document what users actually observe and add `⚠️ UI and code disagree:` with both sides in the flow's behavior details. These are usually real bugs; report them to the user at the end.
- If you cannot determine something with reasonable confidence, write exactly `⚠️ Behavior unclear from the current implementation.` at that point and move on. An honest gap is useful; invented behavior is worse than nothing.
- Large repo? Map the big picture first (routes, nav, top-level screens), pick the flows, and only then read deeply along those flows. Do not try to read everything.
- Discovery must not leave traces. Before finishing, revert anything it changed in tracked files (lockfiles rewritten by an install, generated files, local databases) and stop servers you started. The only diff should be the Product Map, the agent instructions, and the viewer configuration.

## What a good feature looks like

A feature is a user-visible capability, named the way a user or product manager would say it.

| Good | Bad (implementation units, not features) |
|---|---|
| Generate an image | React editor component |
| Edit a document | Authentication service |
| Invite collaborators | PostgreSQL layer |
| Publish a project | API router |
| Manage a subscription | Background queue |

Each feature gets a stable ID, a name, a one or two sentence description, where the user reaches it when that helps, and links to the flows it takes part in. Add implementation references only when they materially help an agent find the code, and keep them short. Group features into product areas so the whole map is scannable. Something counts as a feature when a user would notice if it disappeared.

## What a good flow looks like

A flow is a meaningful goal or sequence of product behavior: *Create a project*, *Invite a collaborator*, *Publish a website*, *Upgrade a subscription*, *Recover a forgotten password*. Not *Click the save button*.

The Mermaid flowchart is the primary artifact. It shows user actions, meaningful system actions, major states, decisions, branches, failures that matter to users, and outcomes. Someone should understand the main path in about ten seconds. Keep it to roughly 6 to 15 nodes. If it grows past about 20, split into another flow or subflow instead of shipping an unreadable graph. Leave out internal operations; a user does not care that a cache was invalidated.

Behavior details below the diagram exist only for nodes or transitions that need more than their label: triggers, requirements, results, possible outcomes. Do not write a paragraph for every node.

Avoid dozens of tiny flows. If two flows share most of their steps, merge them and show the difference as a branch.

## Agent instructions

Future agents must know the map exists, so `AGENTS.md` and/or `CLAUDE.md` point to it. Look for both at the repo root.

- Add the short section in [references/agent-instructions.md](references/agent-instructions.md). Do not replace or reorder existing content; append or update only the `## Product Map` section.
- If both files exist, update both, unless one clearly delegates to the other (for example `CLAUDE.md` says "see AGENTS.md"). Then update the one that holds the real instructions.
- If neither exists, create `AGENTS.md` with that section, unless the repo has an established alternative (for example `.cursorrules`, `.github/copilot-instructions.md`, or a docs convention) that should be respected instead.
- Keep it short and never copy the map's content into these files. They point to `/product`; they do not duplicate it.
- Use the repo's real validation command in the section (the package script if configured, otherwise the skill's script, see *Validation*). Never write a machine-specific absolute path (such as a path under your home directory or a plugin cache) into `AGENTS.md`, `CLAUDE.md` or `product/README.md`; those files are shared with people and agents on other machines.

## Viewer setup

Configure the viewer during initial creation when the repo already uses Node-compatible package management. First run a cheap availability check, `npm view @nuthinking/product-map version`; if it fails, skip the install and go straight to the fallback below. Otherwise detect the package manager from lockfiles and the `packageManager` field, and use that one only:

| Evidence | Install command |
|---|---|
| `package-lock.json` or no lockfile | `npm install --save-dev @nuthinking/product-map` |
| `pnpm-lock.yaml` | `pnpm add -D @nuthinking/product-map` |
| `yarn.lock` | `yarn add -D @nuthinking/product-map` |
| `bun.lock` or `bun.lockb` | `bun add -d @nuthinking/product-map` |

Then add to `package.json` scripts: `"product-map": "product-map"`. If a script named `product-map` already exists, read it first and leave it alone if it does something else. In a monorepo, add the dependency and script to the root package.

If the package is unavailable or the install fails (not published yet, registry unreachable, offline), do not retry and do not add the script. Leave `package.json` and the lockfile as they were and say plainly that the viewer could not be installed. The Product Map is complete without it: the Mermaid diagrams render on GitHub and in most Markdown previews (VS Code, GitLab, Obsidian), so tell the user to start at `product/README.md` and give `npx @nuthinking/product-map` as the command to use once the package is available.

Skip installation entirely when the repo is not a Node project. Do not add a `package.json` just for the viewer and do not introduce a second package manager. Mention `npx @nuthinking/product-map` as an option if the developer has Node.

Before relying on any viewer subcommand (such as `validate`), inspect what the installed package actually provides: its README, `package.json` `bin`, or `--help` output. Do not assume commands exist.

## Validation

Run validation after every create or update, and during review.

1. If `@nuthinking/product-map` is installed and provides a validate command (check first), run it through the package script, for example `npm run product-map -- validate`.
2. Always also run the bundled structural validator; it has no dependencies beyond Python 3. Run it from the repo root, with this skill's own directory substituted for the placeholder:

```bash
python3 <path-to-this-skill>/scripts/validate.py product
```

Add `--json` for machine-readable output.

3. When no viewer validate command works in the repo, copy `scripts/validate.py` from this skill to `product/validate.py` so teammates and CI get a portable command, `python3 product/validate.py`, that does not depend on where the skill is installed. Overwrite an older copy when you update the map. Remove the copy once the viewer's validate command is configured. Never write a machine-specific absolute path into shared files.

It checks that required files and frontmatter exist, IDs are unique and well-formed, every feature referenced by a flow exists, internal links and anchors resolve, each flow has a Mermaid flowchart with sane syntax, and flags likely duplicate flows. Fix all errors. Fix warnings unless they are deliberate; say so if you leave one. Info lines are for your awareness and need not be reported; marker counts there are occurrences, so one bug noted in both `features.md` and a flow counts twice.

If neither Python nor the package is available, check the same list by hand and say that you did.

## Viewer launch

Getting the map in front of a human visually is part of the job, not an optional extra.

- **You can run commands and open or expose localhost:** run the configured script (`npm run product-map` or the package-manager equivalent) in the background, read the URL it prints, open it or expose it, and tell the user the actual URL. Never invent a port or URL.
- **You can run the process but not open a browser:** start it, report the URL the CLI printed, and ask the user to open it.
- **You cannot run or keep a local server:** finish and validate the map, then tell the user exactly what to run, using the repo's package manager, for example `pnpm product-map`. If the viewer was not installed, recommend `npx @nuthinking/product-map`.
- **The viewer is not installed and cannot be:** say so once, point the user at `product/README.md` and Mermaid-capable previews, and give the `npx` command for later. Do not present a command you know will fail as if it works.

Launch after a create, and after an update that is substantial or changes a diagram. For a small wording fix, just mention the command.

## Pull requests

Diffs of Mermaid source are unreadable, but GitHub and GitLab render ```mermaid blocks in PR descriptions. So whenever a change touches `/product` and you write or are asked to write the PR description, add a `## Product behavior` section: one to three "before → after" bullets in user terms, links to the affected flow files on the branch, and the updated diagram inline in a collapsed block (previous and updated when the structure changed). Template and rules: [references/pr-section.md](references/pr-section.md). This lets a reviewer check the behavior change at a glance before reading code. Do not open or edit a PR unless the user asked for one; if you are not writing the PR, hand the section to the user as text.

## When not to touch the Product Map

Leave it alone when only the internals changed: refactors, renamed files or components, dependency upgrades, styling that does not change what a user can do, performance work, test-only changes, logging, infrastructure. Churn makes the map less trusted. The map describes the product contract, not its machinery.

Also do not pad it: no tiny flows for single screens, no features for every button, no implementation references that duplicate what `grep` would find in seconds.

## Completion checklist

For a small update, report what changed in the map and the validation result. End a create (and any substantial update) with a short report that covers:

- Where the Product Map lives and what was created or changed
- How many features and flows were documented, when that helps
- Any `⚠️ UI and code disagree` findings (these are often real bugs the user will want to know about)
- Any `⚠️ Behavior unclear` markers and what evidence would resolve them
- Whether `AGENTS.md` / `CLAUDE.md` were updated or created
- Whether the viewer was installed and the script added, or why not
- Validation result
- The viewer URL if it is running, otherwise the exact command for the user to run, or the fallback when the viewer is unavailable

Do not finish a successful initial creation without telling the user how to look at the map: the viewer when it works, the README and rendered Mermaid when it does not.
