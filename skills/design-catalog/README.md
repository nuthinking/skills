# Design catalog

> Extract the design system your app already has, and make every screen follow it.

Apps built by prompting drift. Each screen was generated on its own, so the "same" grey is `gray-500` here, `zinc-500` there and `#6b7280` in a third place; buttons come in three shapes; one card has a 16px radius and the next a 10px one. Nobody chose that. The design language is there, it was just never written down.

The design-catalog skill finds it and writes it down in the only places that count: the app's own tokens, the app's own components, a page in the app that renders them, and a short `DESIGN.md` that people and coding agents read before touching UI.

![The /design-catalog page of a task manager: colour tokens with their roles, the type scale, then every shared component](https://raw.githubusercontent.com/nuthinking/skills/main/docs/screenshots/design-catalog/catalog.png)

## What it does

1. **Measures the running app.** Every screen, every element, computed styles: the colour that is actually painted, not the class name. Plus a source scan that says where each value is written, which components exist and how often they are used.
2. **Finds the drift and groups it into about ten decisions.** "Four greys do the job of one; use this one." "Buttons come in three shapes; this is the most used." "Four type sizes are off the scale." Each decision is one line in plain words, answered in the conversation. A one-page visual with swatches and the rendered variants is there when words are not enough.
3. **Writes the tokens where the app keeps its theme.** Tailwind v4 `@theme`, Tailwind v3 config, shadcn's existing tokens, CSS variables, a styled-components theme: whichever the app already uses. No parallel system.
4. **Makes the screens follow, in small verified steps.** Retired values become token classes; duplicate components merge into the shared one; after every step the screens are re-measured and compared against the "before" so that only the approved changes happened and nothing moved. All at once or batch by batch, the owner's choice.
5. **Leaves a catalog.** `/design-catalog` in the app renders every token and component from the real code (no Storybook). `DESIGN.md` names them and states the rules. An `AGENTS.md` section makes sure the next agent reads both.

![The optional one-page visual: one card per decision, the values it merges as swatches, with usage counts](https://raw.githubusercontent.com/nuthinking/skills/main/docs/screenshots/design-catalog/decisions.png)

Later, **Review** mode measures again and lists everything on screen that matches no token, so drift is caught instead of accumulated.

## Why not Storybook, or a DESIGN.md generator, or a URL scraper?

Storybook is a second build most prompted apps never had and would not maintain; a page inside the app, built from the app's components, is always true and deploys with it. A `DESIGN.md` on its own documents a system that the code does not have yet. Scraping tokens from a public URL gives you someone else's design. This skill starts from your app, decides with you what was intended, and changes the app so the document is true.

## Install

Any agent that reads `SKILL.md`:

```bash
npx skills@latest add nuthinking/skills
```

Claude Code as a plugin: `/plugin install nuthinking-skills --marketplace nuthinking/skills`.

Then, in the app's repo, ask the agent to "extract the design system" or "clean up the design drift". It needs the dev server running (it will start it) and a browser tool to measure with; without one it works from the source alone and says so.

## What you get in the repo

```text
DESIGN.md                                  the look, tokens, components, rules, decisions (under 200 lines)
src/app/globals.css                        semantic tokens added to the existing theme (or the app's equivalent)
src/components/design-catalog/             the catalog page's components
src/app/design-catalog/page.tsx            the page, noindex (framework-specific location)
AGENTS.md                                  a short "Design catalog" section
.design-catalog/                           working files, gitignored: scan, snapshots, proposals, compare results
```

## Scripts

All dependency-free (Python 3 standard library, Node built-ins) and runnable from anywhere.

| Script | Does |
|---|---|
| `scan_source.py` | Stack, routes, components with usage counts, every colour/spacing/radius/shadow/type value with locations, existing tokens, drift signals. JSON plus a Markdown summary. |
| `collect-styles.js` | Evaluated in a page: every visible element with computed styles, box, text, classes and React component names. Posts to the receiver or returns JSON. |
| `receive.mjs` | Local receiver that writes posted snapshots to files, for agents that drive a browser themselves. |
| `snapshot.mjs` | Drives Playwright or Puppeteer when the project already has one; never installs anything. |
| `analyze.py` | Snapshots (+ scan) to grouped decisions: `summary.md`, `proposals.json`, optional `report.html`, and `drift.md` against declared tokens. |
| `compare.py` | Before/after snapshots to a pass/fail report: approved changes, unapproved changes, layout changes, added/removed elements. |
| `dc_colors.py`, `tailwind_palette.py` | Colour parsing for every CSS syntax a computed style can return, OKLab distances, Tailwind v3/v4 palette matching. |

## Testing

`python3 skills/design-catalog/scripts/test_scripts.py` runs unit tests on synthetic snapshots and a tiny fake project. For a realistic run, use a deliberately drifted app: a Next.js + Tailwind v4 task manager with planted inconsistencies (four grey families, three button and card implementations, off-grid spacing, off-scale type sizes, three badge styles) was used to develop the skill; `DRIFT.md` in that fixture lists what was planted so the extraction's findings can be checked against it.

## Limitations

- Snapshots capture the resting state; hover, focus and open overlays are captured only when triggered with a filter, or checked by eye.
- Component names in snapshots come from React dev builds; production builds and server components give fewer names, and the class strings are used instead.
- Pseudo-elements and `::placeholder` styling are not measured.
- Icons, illustrations, motion and copy are noted but not consolidated.
- A very fine grey scale can be over-merged at the default threshold; `analyze.py --threshold 0.02` tightens it.
