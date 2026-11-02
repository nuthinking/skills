# Applying the decisions to the app

Apply makes the app follow the catalog. It changes real screens, so it works in small verified steps: one decision, one re-measure, one check. The user chose either **all at once** (every approved decision, no pauses, still verified at each step, stop only on a failure) or **batches** (one group at a time, report, wait for "next"). The mechanics are the same.

## Before the first change

- All decisions being applied are approved in `proposals.json` (group or individual). Anything else waits.
- The working tree is clean, or the user knows what else is uncommitted. Note the current commit so a batch can be reverted with one command.
- The before snapshots exist for every screen (`.design-catalog/snapshots/`). Copy them to `.design-catalog/before/` so re-measuring does not overwrite them: `cp -r .design-catalog/snapshots .design-catalog/before`.
- The project's checks are known: typecheck, lint, tests, build. Run them once now so you know what already fails.

## Order of work

1. **Tokens** (greys, accent, status colours, radii, shadows): declare them per [tokens.md](tokens.md). Declaring changes nothing visible. Typecheck and build.
2. **Colour replacements**, one approved group at a time: replace retired classes and literals with the token classes, over the files the scan lists. Re-measure, compare, check. These are the safest changes: with correct tokens nothing moves and every colour change is in the approved mapping.
3. **Type, spacing and radius snaps**: off-scale sizes to the scale, off-grid padding to the grid, retired radii to the kept ones. These do move layout boxes by a pixel or two; that is the expected effect of the decision, so compare will report layout changes. Check that the only moved elements are the ones carrying the changed value and that nothing wrapped or overflowed; screenshot the screen and look.
4. **Components**, one family at a time: make the surviving variant the shared component (extend the existing `Button`/`Card`/`Input` with the missing variant rather than creating a new file when one exists), migrate each usage of the other variants to it, delete the retired component file only when the scan shows zero usages. Re-measure after each migrated screen.
5. **Catalog page** ([catalog-page.md](catalog-page.md)) once the components are settled, then `DESIGN.md` and the `AGENTS.md` section ([agent-rules.md](agent-rules.md)).

In batches mode, a batch is one group from the summary (`G1`), reported when done. In all-at-once mode, run through the whole order without pausing, but keep the per-step checks; stop and report at the first failure you cannot fix in place.

## The check after every step

```bash
# re-measure the affected screens into .design-catalog/snapshots (receiver or snapshot.mjs, same viewports as before)
python3 <skill>/scripts/compare.py .design-catalog/before .design-catalog/snapshots --mapping .design-catalog/proposals.json --out .design-catalog/compare.md
```

`compare.py` pairs every element of every screen across the two snapshots and classifies each difference:

- **approved**: a colour, radius, spacing, size or shadow went from a retired value to the survivor of an approved decision. Expected.
- **unapproved**: any other style change. A wrong replacement, a cascade you did not foresee, a component that lost a class.
- **layout**: a bounding box moved or resized beyond the tolerance. For token and colour steps this must be zero. For spacing, radius and type snaps it lists exactly the elements carrying the changed value; anything else moved is a regression.
- **added / removed**: DOM changed. Normal when a component is replaced; read the list to make sure nothing disappeared.

Exit code 1 means unapproved or layout changes. Read `compare.md`, fix or revert, re-measure, and only then continue. Do not continue past a failing compare because "it is probably fine", and do not report visual verification you did not run.

Also after each step: the project's typecheck and lint; after component steps, the tests and a production build. Hover and focus states are not in the snapshots: after migrating a button or input family, hover and focus one instance in the browser and confirm the ring and hover shade match what `DESIGN.md` says.

## Replacement mechanics

Work from the scan's locations (`tailwind.by_category`, `css.colors`, `inline_styles`), not from a global search-and-replace. For each retired value:

- Tailwind classes: anchored replacements that respect variant prefixes and ignore alpha modifiers you have not mapped (`text-gray-500` is not `text-gray-500/60`). Handle `hover:`, `focus:`, `dark:` prefixed forms explicitly; a `hover:bg-indigo-700` maps to `hover:bg-primary-hover`, not to `hover:bg-primary`.
- `cva()`, `clsx()`, `cn()` and template literals: same strings, same rules.
- Arbitrary values (`bg-[#4f46e5]`, `p-[18px]`, `rounded-[10px]`): replace by the token class or scale class.
- Inline `style={{ color: "#6b7280" }}`: replace by a class, or by `var(--color-text-muted)` when it must stay inline.
- CSS files: replace the literal with `var(--...)`.

Keep each replacement commit-sized and reversible. If the project uses Prettier or a formatter, run it on touched files so the diff is only the change.

## Component migration

For a family with variants A (survivor), B and C:

1. Make sure the shared component renders A exactly: compare its measured signature in `proposals.json` with the component's classes; add a variant or size if A is not expressible yet.
2. For each usage of B or C (the scan's `components[].used_in` and the inline markup the snapshots point at via class strings): replace with the shared component and the right variant. Preserve behaviour: handlers, `type="submit"`, `disabled`, `aria-*`, `data-*`, links via `asChild` or the app's link pattern.
3. Re-measure the screens touched; compare. Expected: approved style changes on those elements (the B→A differences the decision listed), possibly a height change if A is a different size, which the decision also listed; nothing else.
4. When no usage of B remains (grep the import and the JSX tag), delete B's file. Never delete first.

What must not change in a component migration: text, order of elements, keyboard behaviour, form submission, focus management. If migrating a variant would change behaviour (a `<a>` styled as button becoming a `<button>`), keep the element type and style it, or use the component's link form.

## Two things that bite on the first step

- **Stale CSS.** After editing the theme file, confirm the dev server recompiled it before measuring: fetch the page's stylesheet and look for one new utility (`.text-text-muted`) or token (`--color-text-muted`). Turbopack and some Vite setups keep serving the old CSS after a file written by a script; the symptom in `compare.md` is every replaced element going to `rgb(0, 0, 0)` or losing its background. Restart the dev server with a clean cache (`rm -rf .next`, then start) and re-measure; do not "fix" the tokens.
- **Conflicting classes resolved by cascade order.** `clsx("text-zinc-900", done && "text-zinc-400")` rendered dark before only because `text-zinc-900` happened to come later in the generated CSS; after renaming one of them the order flips and the element changes colour. `compare.py` reports it as an unapproved change on exactly those elements. Fix the source (make the classes mutually exclusive, or use `tailwind-merge` via the app's `cn()`), never by adding `!important`.

## When a check fails

- Unapproved colour change on an element you did not touch: a shared class or a CSS cascade changed. Find the rule, scope the replacement, re-run.
- Layout change on a colour step: a replacement changed a class that carried size as well (`border` vs `border-2`, a `rounded-*` with a different radius). Revert that replacement, map it separately.
- Added/removed elements after a token step: the DOM should not change; a component probably crashed or a conditional flipped. Check the console and the dev server output.
- Typecheck failure after a component migration: a prop the old component had is missing on the shared one. Add it as a proper prop or variant, do not spread unknown props to the DOM.

Revert the step (`git checkout -- <files>` or reset to the noted commit) when a fix is not obvious within a few minutes, report it, and continue with the next group; a skipped step is reported, not hidden.

## Finishing a batch

Report per batch, briefly: what changed (groups applied, files touched), the compare result (approved count, zero unapproved, layout changes and why), checks run and their results, and what is next. In all-at-once mode, one report at the end with the same content per group. Update the `Decisions` table in `DESIGN.md` with what was applied, and `.gitignore` with `.design-catalog/` if not yet there. Do not commit; show the user the diff summary and let them commit.
