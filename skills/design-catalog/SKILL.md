---
name: design-catalog
description: Extract the design system a vibe-coded app already has and make every screen follow it. Measures the running app screen by screen (computed colours, type, spacing, radii, shadows, button/input/card/badge shapes), scans the source for where each value is written, groups the drift into about ten plain-language decisions the owner answers one by one, then writes semantic tokens into the app's own styling system (Tailwind v4 @theme, v3 config, shadcn tokens, CSS variables), consolidates duplicate components, migrates screens in small verified steps, and leaves a /design-catalog page rendering the real components plus a DESIGN.md and an AGENTS.md section so people and coding agents keep it consistent. Use whenever someone wants to extract, build, document or clean up a design system, design tokens or style guide from an existing app; complains that screens, buttons, colours or spacing look inconsistent or drifted; asks for a DESIGN.md, a component catalog or a design-system page; or asks whether the app still follows its design system. Also use it when changing shared UI in a repo that already has DESIGN.md.
---

# Design catalog

A vibe-coded app has a design language; it just was never written down, so every generation drifted a little: four greys for secondary text, three button shapes, a 10px radius here and 16px there. This skill measures what the app actually renders, asks the owner a handful of decisions about what was intended, and makes the app, its tokens, a catalog page and `DESIGN.md` agree.

```text
running app ──measure──▶ snapshots ──analyse──▶ ~10 decisions ──the owner answers──▶ tokens in the app's CSS
source ──scan──▶ where each value lives                                            ▶ screens migrated, verified by re-measuring
                                                                                    ▶ /design-catalog page + DESIGN.md + AGENTS.md rules
```

**Preserve, do not redesign.** The most-used value wins by default; nothing is made "nicer". **Measure, do not guess.** Colours are judged from computed styles, not class names. **Ask about intent, decide about accident.** Consistent across screens is intent; varying without reason is accident, and the owner confirms. **The code is the catalog.** The page renders the real components; no Storybook, no copies. **Small verified steps.** Every change is re-measured and compared before the next.

Optimised for React + Tailwind (+ shadcn), the usual vibe-coding stack. Measurement works on any web app; token and component steps adapt to the styling system found ([references/tokens.md](references/tokens.md)).

## Choose a mode

| Situation | Mode |
|---|---|
| No `DESIGN.md` and no catalog page | **Extract** |
| Catalog exists, screens still use retired values or components | **Apply** |
| You are changing shared UI, tokens or components in a repo with `DESIGN.md` | **Update** |
| Someone asks whether the app still follows its design, or you suspect drift | **Review** |

Working files go in `.design-catalog/` at the app root (add it to `.gitignore`). Only `DESIGN.md`, the catalog page, the tokens, the `AGENTS.md` section and the migrated code are meant to be committed. Never commit yourself; show the diff.

## Extract

1. **Learn the app.** Run the scanner and read its summary: framework, styling system and Tailwind version, shadcn, UI and icon libraries, routes, components with usage counts, existing tokens, drift signals.

   ```bash
   python3 <skill>/scripts/scan_source.py <app-root> --md
   ```

   In a monorepo run it on the app package. If semantic tokens or a component library already exist, the job is to map strays onto them, not to invent a parallel system.

2. **Measure every screen** of the running dev server at 1280×800 (and 390×844 for the two or three main screens if responsive; both colour schemes if the app has dark mode): one snapshot per screen type, including login, settings, empty and error states you can reach. Start the receiver, open each screen with your browser tool, evaluate `scripts/collect-styles.js` in the page; or use `scripts/snapshot.mjs` when Playwright or Puppeteer is already available. Take a screenshot of each screen as well. Details, states and the no-browser fallback: [references/measuring.md](references/measuring.md).

3. **Analyse.**

   ```bash
   python3 <skill>/scripts/analyze.py --snapshots .design-catalog/snapshots --allowed <css files declaring tokens> --print
   ```

   It clusters perceptually identical colours, names them by role (`text-muted`, `border`, `primary`, `danger-soft`), reuses existing tokens where values match, finds off-scale type sizes, off-grid spacing, one-off radii and shadows, and groups buttons, inputs, cards and badges by their measured shape. It writes `summary.md` (grouped decisions `G1`…, with the per-value details below them), `proposals.json` (every decision, `approved: null`) and, with `--allowed`, `drift.md`. Add `--html` for `report.html`, a one-page visual with swatches and the rendered variants side by side; open it when a decision needs eyes.

4. **Read before relaying.** Rename clusters to the app's vocabulary in `proposals.json` if the suggested names are off, check that counts are not one list rendered forty times, and snapshot any screen you missed. [references/deciding.md](references/deciding.md) is the judgement guide: intent versus accident, reusing what exists, when two components are one.

5. **Put the decisions to the owner, one at a time**, in the plain words of the summary's `## Decisions` list, with your recommendation on each. Offer the details and the visual page rather than pasting them. Record every answer in `proposals.json` (`approved`, `name`, `note`). Unanswered means not approved.

6. **Ask how to apply**: all at once (no pauses, still verified at each step, stop on the first failure) or in batches (one group per round, report, wait). Then run **Apply** for the approved groups.

7. **Catalog page** at `/design-catalog`, rendering every token and shared component from the real code, shipped with `noindex` and outside the product shell (no app nav or footer, so it reads as an internal reference): [references/catalog-page.md](references/catalog-page.md). Open it, screenshot it, fix what renders wrong.

8. **`DESIGN.md`** at the app root, under 200 lines: the look in a paragraph, token tables, component table, patterns, rules, decisions log, open items. Format and a full example: [references/design-md.md](references/design-md.md).

9. **Agent rules**: add the `## Design catalog` section from [references/agent-rules.md](references/agent-rules.md) to `AGENTS.md` (and `CLAUDE.md` when it holds the real instructions).

10. **Report** with the completion checklist below.

## Apply

The owner approved decisions; make the app follow them. Full mechanics in [references/apply.md](references/apply.md); the shape:

1. Copy the current snapshots to `.design-catalog/before/`. Note the current commit. Run the project's checks once to know what already fails.
2. **Tokens first**: declare the approved tokens in the app's own system ([references/tokens.md](references/tokens.md)). Nothing visible changes. Typecheck.
3. **Replacements, one group at a time**: retired classes and literals to token classes, over the files the scan lists, with anchored replacements that respect variant prefixes and alpha modifiers. Then type, spacing and radius snaps. Then **components**, one family at a time: the surviving variant becomes (or extends) the shared component, usages migrate screen by screen preserving behaviour, the retired component is deleted only at zero usages.
4. **After every step**: re-measure the affected screens and compare.

   ```bash
   python3 <skill>/scripts/compare.py .design-catalog/before .design-catalog/snapshots --mapping .design-catalog/proposals.json --out .design-catalog/compare.md
   ```

   It pairs every element across the two measurements and classifies each difference as approved (in the mapping), unapproved, or a layout change. Token and colour steps must produce zero unapproved and zero layout changes; snaps and component swaps move exactly the elements that carry the changed value and nothing else. Exit code 1 means fix or revert before continuing. Also run typecheck and lint after each step, tests and a build after component steps, and hover and focus one instance of each migrated interactive component by hand.
5. Report per batch (or once at the end for all-at-once): groups applied, files touched, compare result, checks, what is next. Update the decisions table in `DESIGN.md`.

Never remove a component before its usages are gone, never change behaviour (handlers, element types, keyboard, forms) while changing looks, never widen a step because the previous one went well.

## Update

You are adding or changing shared UI in a repo that already has `DESIGN.md`.

1. Read `DESIGN.md` and open `/design-catalog` before writing UI. Use an existing component or variant when one fits.
2. If you add a token, component or variant: add it to the tokens file, the catalog page and `DESIGN.md` in the same change. If you change one, check it on the catalog page and on one real screen.
3. Keep the rules: semantic tokens only, scale values only, no new palette family, font, icon set or radius.
4. If the change is a redesign the owner asked for (a new primary colour), change the token value, not the usages, and record it in the decisions table.

## Review

Someone asks whether the app still follows its design system, or you suspect drift.

1. Measure the screens again (same list and viewports as the last extraction when known) and run the analysis with `--allowed` pointing at the token files. `drift.md` lists every colour, radius, shadow and font size on screen that matches no declared token, with counts, screens and the nearest token.
2. Read `DESIGN.md`'s component table against the scan: new components not in the table, retired ones that came back, usages of inline markup where a shared component exists (duplicate kinds in the scan's drift signals).
3. Report the drift as a list with evidence (screen, element, value, nearest token) and a suggested fix for each, plus hygiene: `AGENTS.md` section present, catalog page still renders, `DESIGN.md` tables still true.
4. Only change things if asked; then follow **Apply** for the fixes.

## Rules of evidence

- Computed styles are the truth for what a colour is; the source is the truth for where it is written. Report both.
- Snapshots see the resting state. Hover, focus, open menus and modals need to be triggered and captured with a filter, or checked by eye; say which you did.
- Counts include every list row. Say "the project card, rendered six times", not "six cards".
- When the scan and the snapshots disagree (a class in the source never appears on screen), the code path is dead or unreached; note it, do not count it.
- Without a browser, work from the scan alone and say that colours were not measured and nothing was visually verified.
- Leave no traces: stop servers you started, revert lockfiles an install rewrote, keep `.design-catalog/` out of git.

## Completion checklist

End an extract (and any apply round) with a short report that covers:

- Screens measured, and any screen type you could not reach
- The decisions taken (group IDs, outcome) and the ones left open
- Tokens declared: file, how many, and which existing ones were reused
- Components consolidated: survivor, what migrated into it, what was deleted
- Compare results per step: approved, unapproved (should be zero), layout changes and why they were expected
- Checks run (typecheck, lint, tests, build) and their results
- The catalog page URL on the dev server, and that it was screenshotted and looks right
- `DESIGN.md` written or updated; `AGENTS.md` section added
- Known gaps: states not captured, screens not measured, things left under "Open" in `DESIGN.md`
- The diff summary for the owner to review and commit
