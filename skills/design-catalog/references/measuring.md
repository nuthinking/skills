# Measuring the app

The design language is what the app renders, not what the source says. Vibe-coded source is the least reliable witness: the same colour appears as `text-gray-500`, `text-zinc-500` and `#6b7280`, and only the browser knows they are three values that look like one. So measurement comes first, from the running app, and the source scan explains where each value is written.

## 1. Start the app and list the screens

- Find how to run it: `package.json` scripts (`dev`), README, `.env.example`. Start the dev server (the dev build keeps React component names, which the snapshots use to point at source). Note the port it prints. Never run against production.
- Build the screen list from `scan_source.py` routes, the Product Map (`/product`) if the repo has one, and the navigation you see. Pick every distinct screen type, not every record: `/tasks` and `/tasks/101`, but not `/tasks/102` too. Include login, settings, empty and error states if they can be reached. Six to fifteen screens is typical.
- Authenticated apps: use a test account from `.env` or ask for one; sign in once in the browser tool, then snapshot. With `snapshot.mjs`, pass `--storage-state` or `--cookie`.
- Dark mode: only if the app has it (scan shows `dark:` variants or a theme toggle). Snapshot each screen in both schemes; the receiver names dark files `__dark`.
- Viewports: 1280×800 for everything. Add 390×844 for the two or three most important screens when the app is responsive; mobile spacing drift is common.

## 2. Run the source scan

```bash
python3 <skill>/scripts/scan_source.py <app-root> --md
```

Writes `.design-catalog/scan.json` and prints a summary: stack, routes, components with usage counts, Tailwind classes by category, CSS values, custom properties, inline styles, drift signals. Read the summary; it tells you the styling system, whether shadcn or another library is present, whether tokens already exist (`semantic_tokens_defined`), and which component kinds have several implementations. In a monorepo, run it on the app package, not the repo root.

Add `.design-catalog/` to `.gitignore` if it is not there (it holds working files only).

## 3. Snapshot every screen

Each snapshot is one JSON file: every visible element with its computed styles (colour, background, border, radius, shadow, font, spacing), bounding box, text, class attribute and nearest React component names. Three ways, in order of preference:

**A. Your browser tool.** Start the receiver in the background, then for each screen: open the URL at the viewport, wait for it to settle, evaluate the collector file in the page. The collector posts the snapshot to the receiver and returns a one-line confirmation, so no large payload comes back through the tool.

```bash
node <skill>/scripts/receive.mjs --out .design-catalog/snapshots   # keep running; Ctrl-C when done
```

Then in the page: evaluate the contents of `<skill>/scripts/collect-styles.js` (tools that take a file path can point at it directly; the file is a single async expression, evaluate it as a script, not as a function). Take a full-page screenshot of each screen as well and keep it next to the snapshot when the tool allows saving there (same file stem, `.png`); the report embeds it.

**B. Playwright or Puppeteer, if the project or your environment already has one.** Nothing is installed by this skill.

```bash
node <skill>/scripts/snapshot.mjs --base http://localhost:3000 --paths / /tasks /tasks/101 /settings /login --screenshot
```

Options: `--viewport 390x844` (repeatable), `--scheme dark --dark-class dark`, `--storage-state auth.json`, `--cookie name=value`, `--paths-file screens.txt`. It exits with code 2 and instructions for A when no driver is found.

**C. No browser at all.** Skip snapshots; run `analyze.py` is not possible, so work from `scan.json` alone: palette families, arbitrary values, duplicate component kinds and inline styles are still visible there. Say plainly in the report that colours were not measured and that consolidation is proposed from source only; do not claim visual verification later.

### States

Snapshots capture the resting state. For the states that matter (hover on primary buttons, focus on inputs, open menus, selected tabs), trigger the state with the browser tool, then evaluate the collector with a filter so only that element is captured:

```js
window.__dc = { filter: "main form", label: "tasks-101-input-focus" }
```

followed by the collector. Do this for a handful of elements where behaviour must be preserved (focus ring colour, hover shade); it is evidence for `DESIGN.md`, not input to the clustering.

### What the collector cannot see

Pseudo-elements, `::placeholder` styles, hover and focus unless triggered, content behind interaction (modals, menus) unless opened first, and production builds lose component names. Elements inside closed `<details>` or `display:none` are skipped by design.

## 4. Analyse

```bash
python3 <skill>/scripts/analyze.py --snapshots .design-catalog/snapshots --allowed <token css files>
```

`--allowed` takes the CSS files that declare the app's tokens (`src/app/globals.css`, `tailwind.config` is not CSS so skip it for v3; use the file with `:root { --... }`). It adds a drift section: every colour, radius, shadow and font size on screen that matches no declared token. Before extraction that list is long; after apply it should be near empty, which is how Review mode works.

Outputs in `.design-catalog/`:

- `report.html`: the page the user reviews. Open it in the browser (file URL) and screenshot the top for the conversation when you can.
- `summary.md`: the same decisions as text, for relaying in chat.
- `proposals.json`: the decisions with `approved: null`. You fill in `approved`, `name` and `note` as the user answers; `compare.py` reads the approved ones.
- `drift.md` / `drift.json` with `--allowed`.

The colour threshold (`--threshold`, default 0.03 in OKLab) merges values a person would not tell apart in a UI. Lower it to 0.02 if the app has a deliberately fine grey scale; raise to 0.04 for a very drifted app. White and black never merge with neighbours; a tint never merges with a grey; two pale tints of different hue never merge.

## 5. Read the report before showing it

Check that the clusters make sense for this app. Typical corrections:

- A colour named `primary-soft` is really a selected-row background, or `warning` is the brand orange: rename in `proposals.json` (`name`) before the user sees the report, so the conversation uses the app's vocabulary.
- A "button family" is a switch or an icon button: the analyser separates those, but check.
- Counts include every list row; a value used 40 times on one screen may be one component rendered 40 times. The report says which component.
- A screen you forgot shows up as a gap (for example no danger button measured because the delete flow was not opened). Snapshot it and re-run.

Then hand the decisions to the user as described in [deciding.md](deciding.md).
