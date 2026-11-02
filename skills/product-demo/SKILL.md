---
name: product-demo
description: Create and keep up to date demo videos of product flows, generated from the repository instead of recorded by hand. Each demo is a small YAML script in /product/demos next to the Product Map; @nuthinking/product-demo replays it against the app in a seeded demo mode, captures keyframes and an event log as the deterministic source, and renders videos in three styles (neutral, in a device, or in 3D perspective) on built-in wallpapers, with intro and outro cards, captions, per-step camera zoom and voice-over. A manifest records which source files each demo depends on, so CI re-records only the demos a change can affect. Use this skill whenever someone wants demo, walkthrough, tutorial or feature videos for docs or marketing, asks to automate screen recordings or keep videos in sync with the code, mentions product-demo, @nuthinking/product-demo, demo styles or themes, keyframes or voice-over for demos, or asks why a demo is stale or how to regenerate it. Also use it when changing a flow in a repo that has /product/demos, so the demo is checked in the same change.
---

# Product demo

A demo is a flow with a script. The script lives in the repo next to the Product Map. CI replays it against the app in demo mode, keeps keyframes and an event log as the source, renders a video from them in a style on a background, and uploads everything to a store the docs site reads. When code a demo depends on changes, the demo is regenerated, and only then. Nothing generated is committed.

```text
/product/demos/<id>.yaml ──▶ record ──▶ keyframes + events + manifest ──▶ render ──▶ video ──▶ store ──▶ index.json
                            Playwright                                 frame by frame   production/ or pr-<n>/   docs site
                                                                           ▲
                                   style: neutral | device | perspective · background: a wallpaper · cards, captions, zoom per step
```

Why it is built this way, and what the app must do to be recordable: [references/how-it-works.md](references/how-it-works.md). Read it before installing and whenever you explain the pipeline. The file contract: [references/format.md](references/format.md). Styles, backgrounds and settings: [references/styles.md](references/styles.md). Commands: [references/cli.md](references/cli.md). The workflow and the store: [references/ci.md](references/ci.md).

**What it needs.** A web app that runs locally from the repo with a command; Node for the package; a way to seed a known state; a test account when the app has a login. A Product Map (`product-map` skill) is recommended, since demos point at flows and borrow their labels and implementation references, but a demo can be written without one. Narration works with no key through the local provider. Publishing needs an S3-compatible bucket (Cloudflare R2 recommended) and its credentials in CI; without one, videos stay local.

**Principles.** The source of a video is keyframes plus an event log, never a screen recording. The app is made repeatable through a demo mode, not through retries. Videos are derived, never edited. A demo is regenerated when the code it depends on changed, decided from file hashes, never from pixels. CI records and publishes; local runs are for looking.

## Choose a mode

| Situation | Mode |
|---|---|
| The repo has no `/product/demos` | **Install** |
| A flow should get a video | **Add demo** |
| Code changed, `check` or CI reports stale demos | **Regenerate** |
| Recording fails, a video looks wrong, CI fails | **Diagnose** |
| New look, brand background, different voice | **Restyle** |

## Install

1. **Learn the repo.** Package manager (from lockfiles and `packageManager`; use only that one). How the app builds and runs, and on which port. How users sign in, and whether a password login exists. Whether `/product` exists (if not, say that the `product-map` skill would give demos their flows, and continue). Existing fixtures, seeds or test data; existing Playwright config and `data-testid` conventions. Where dates, random values, analytics and third-party widgets enter the UI. Whether the repo has design tokens. The docs site that will embed the videos, if any. Whether `AGENTS.md` or `CLAUDE.md` exists.

2. **Install the package** as a dev dependency with the repo's package manager: `npm install -D @nuthinking/product-demo`, then `npx playwright install chromium`. Add a `product-demo` script to `package.json`. If the install fails, stop and say so.

3. **Add demo mode to the app.** Under an environment variable named the way the repo names such things (`DEMO_MODE`, `APP_ENV=demo`), make the app repeatable: seeded data with fixed IDs through a `setup` command, including the test account with a fixed name and avatar; a frozen clock for server-rendered dates; no random content; analytics and external widgets off; self-hosted fonts; browser source maps on in the production build. Add a `demo` script that builds and starts the app with demo mode on. Put each switch where the app already reads configuration; keep it small and list every source of nondeterminism you found and what you did about it. Do not change behavior users see outside demo mode.

4. **Write `product/demos/config.json`** from the facts above (keys in format.md section 2): `product`, `serve` (the `demo` script), `url`, `ready`, `setup`, `env`, `auth`, `viewport`, `defaults`, `narration`, `store`. Choose `ready` as something that only appears after hydration. For `auth`, use `form` with the test account's login steps when a password login exists; otherwise write a `script` that produces a signed-in state and explain what it needs. Start with `defaults: { style: device, theme: light }`, `narration.provider: local`, `store.target: none`; the user fills the store when the bucket exists. If the repo has design tokens, write `product/demos/themes/<brand>.json` from them (styles.md) and use it as the default theme.

5. **Make targets findable.** The demos will click things; make sure they have accessible names or `data-testid` attributes (format.md section 5). Add attributes only to elements a demo uses.

6. **Add the first demos** with the *Add demo* mode, for one to three of the flows the Product Map README lists as major, or the ones the user names.

7. **Git.** Ignore `product/demos/.cache/`.

8. **Workflow.** Copy the package's template (`product-demo templates`) or the one in ci.md to `.github/workflows/product-demo.yml` and fill every `PRODUCT-DEMO` line: Node version, package manager, install, a database service if the app needs one. If a workflow with that name exists, read it and merge.

9. **Agent rules.** Append the section in [references/agent-instructions.md](references/agent-instructions.md) to `AGENTS.md` (and `CLAUDE.md` when it holds the real instructions), with the run command filled in.

10. **Verify locally.** `validate` passes. `record <id>` succeeds and `record <id> --repeat 3` reports no unstable steps; open the keyframes in `.cache/local/<id>/frames/` and look at every one. `render <id>` produces a video; watch it. Stop servers you started; the only diff should be the files above, the lockfile and the demo-mode changes.

11. **Hand over the settings.** The bucket (public read, a lifecycle rule for `pr-*/`, a custom domain for `baseUrl`), the secrets the workflow needs (store key and secret; the test account for `form`; a narration key only for a cloud voice), and the `store` block to fill in config.

12. **Report** with the completion checklist at the end of this file.

## Add demo

1. **Read the flow** in `/product/flows/<id>.md`. A demo shows one path through the diagram, usually the happy path, in 4 to 12 steps. Alternative paths worth showing become their own demos (`<flow-id>-<variant>`). Without a Product Map, ask the user for the goal and the starting page, and write the steps from the app.

2. **Walk it in the app** in demo mode with the seeded state, signed in as the test account, and pick a target for every action (format.md section 5): role and name first, then test ID, then text, CSS last. Note where data arrives late after an action.

3. **Write `product/demos/<id>.yaml`** (format.md sections 3 and 4). Step labels are the Mermaid node labels, verbatim. `start` is the page the flow begins on. `watch` lists the flow's server-side *Implementation references* as globs. Narration (`say`) comes from the flow's *Behavior details*: one or two sentences per step in the user's words, present tense, about what happens and why, never about the pointer; under about 20 words; all steps or none. Give `zoom` to the two or three steps that deserve a closer look, a number for the acted element or a target for a panel that opened, and leave the rest without. Use `capture: video` only for a step whose in-app motion is the point.

4. **Record and look.** `validate`, then `record <id>`. Open every keyframe. A frame that shows a loading state needs `settle` or a `wait`; a frame with a leftover tooltip needs `settle`; a wrong element means a wrong target. Then `record <id> --repeat 3` must report no unstable steps.

5. **Look at it in the studio** (`studio <id>`): preview, fix labels, narration and zoom there and save, then **render and watch**. Narration that runs past its step means a `say` line to split; a camera on the wrong thing means a `zoom` target; a step that needs no camera gets no `zoom`.

6. **Commit** the demo file only. CI records, renders and publishes it. Do not edit the flow file; the demo points at the flow, not the other way round.

## Regenerate

1. `check` lists stale demos, whether each is stale for `record` or only `render`, and the files that changed. Say which demos and why before doing anything.
2. For each stale-for-record demo, `record <id>` locally and look at the keyframes. If a step fails or shows the wrong thing because the product changed, update the demo script to follow the new behavior, and, in a repo with a Product Map, make sure the flow file was updated in the same change (the `product-map` skill's Update mode). Record again.
3. Do not try to publish from a laptop; CI regenerates stale demos on the pull request and comments with the keyframes and preview videos, then overwrites production on merge.
4. In the pull request description, add a `## Demos` section naming the affected demos and what changed in them, in user terms.

## Diagnose

Reproduce from the evidence first: the command's output, the workflow log (`gh run view <id> --log-failed`), the keyframes in the PR comment. Then match:

| Symptom | Cause and fix |
|---|---|
| `record` fails at a step: target not found | The target changed; the element is not rendered yet (add a `wait` on it, or raise `settle` on the previous step); the seed did not create it (`setup` failed or demo mode is off); the recorder is not signed in (check `auth` and the credentials). Run with `--headed` to watch. |
| `record` fails before the first step | Sign-in failed: wrong `auth.path`, a login step's target changed, credentials missing from the environment, or a `script` that did not write the state file. |
| `--repeat` reports unstable steps | Nondeterminism in the app: a live date, a random value, an external image, data arriving after the keyframe, a hover or focus state carried over. See how-it-works.md, *Determinism is the app's job too*. Fix it in demo mode; do not paper over it with retries. |
| `check` says stale after an unrelated change | The dependency set is too broad: source maps are missing from the production build, so coverage resolved to bundle chunks. Turn browser source maps on in demo mode. A change to a shared layout module making every demo stale is correct. A theme or `defaults` change making every demo stale for render is correct too. |
| `check` missed a change that did affect a demo | Server-side code or data the browser never executes. Add it to the demo's `watch` globs. |
| `check` says every demo is stale on a fresh branch | No manifests in the store's `production/` folder yet, or the store credentials are missing so `check` cannot read them. Run the workflow on the default branch once. |
| Keyframes show a fallback font, missing text, or a devtools button | A font from a CDN, `ready` fires before hydration, or the app was recorded from the dev server. Self-host the font; point `ready` at an element that appears after hydration; make `serve` a production build. |
| Video text is blurry when zoomed | `deviceScaleFactor` is 1. Set it to 2 in config (the default). |
| Narration out of sync or cut off | A `say` line is too long for its step: split it. A stale cache after changing voice: `render --no-cache`. |
| `publish` fails | Store credentials missing or wrong, the bucket not public, or the PR comes from a fork (expected: the recording is attached as an artifact instead). |
| Production videos changed after a PR merged, though the PR did not touch them | Correct when the PR changed a shared dependency. Otherwise compare the `deps` in the two manifests; a build that is not reproducible (hashed chunk names in `deps`) means source maps are off. |
| CI run too slow | Lower `output.scale` or `output.fps` in `defaults`; raise `timeout-minutes`; split the workflow per demo group with `product-demo record <ids>`. |

Report what the evidence shows, the cause, and the fix; apply the fix when it is in the repo, hand it over when it is a setting.

## Restyle

A look change re-renders without re-recording. Open the studio on a representative demo (`studio <id>`), try styles, backgrounds and settings there, and save; for a default that should apply to every demo, move the keys it wrote into `config.defaults` instead. The built-in wallpapers cover light and dark apps; for a brand image, put it under `product/demos/assets/` and set it as `defaults.background` in config or `background` on the demos that want it (styles.md). Then `render` one demo locally and watch it before committing; CI re-renders the rest on the pull request. Changing the voice or provider regenerates all narration; pin the provider's model version in config once it sounds right. Changing `theme` (the app's colour scheme), a viewport or a device that changes layout is a re-record, not a restyle.

## Completion checklist

End an install or a batch of new demos with a short report that covers:

- Where config and the demo files are, and the run command
- What demo mode switches on, the `demo` script, and the sources of nondeterminism found and how each was handled
- How the recorder signs in, and what the test account is
- Which elements gained accessible names or test IDs
- The demos written: id, flow, steps, style and background, narration on or off
- The workflow file and what was adapted; the bucket and secrets the user must set up, and what cannot be tested until they exist
- Whether `AGENTS.md` / `CLAUDE.md` gained the rules section
- What was verified locally: validate, record, repeat stability, render
- What to try first: change one line of copy a demo shows, open a pull request, read the comment with the keyframes
