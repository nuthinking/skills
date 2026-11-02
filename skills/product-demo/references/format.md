# Product demo format

The contract for `/product/demos`. Humans write the demo files; `@nuthinking/product-demo` and `scripts/validate.py` parse them. Keep to it so tooling keeps working.

Contents
1. What lives where
2. `config.json`
3. `<demo-id>.yaml` (demo script)
4. Steps and actions
5. Targets
6. Narration
7. What the recorder and renderer produce
8. The store: environments, manifests, `index.json`

---

## 1. What lives where

The repository holds only what people write. Everything generated lives in the store (section 8) or in a git-ignored cache.

```text
/product
  README.md, features.md, flows/      The Product Map (product-map skill), recommended
  demos/
    config.json                       How to run the app, how to sign in, defaults, the store
    <demo-id>.yaml                    One demo script per video
    assets/                           Your own background images and fonts (see styles.md)
    .cache/                           Git-ignored. Local recordings, renders, narration audio
```

Demo IDs are kebab-case and equal the file name without `.yaml`. A demo of a flow uses the flow's ID; a second demo of the same flow adds a suffix: `add-task`, `add-task-offline`.

## 2. `config.json`

```json
{
  "product": "Taskly",
  "serve": "npm run demo",
  "url": "http://127.0.0.1:3000",
  "ready": "[data-app-ready]",
  "setup": "npm run seed:demo",
  "env": { "DEMO_MODE": "1" },
  "auth": { "strategy": "form", "path": "/login", "steps": [
    { "do": "type", "target": "role=textbox[name=\"Email\"]", "text": "$PRODUCT_DEMO_USER" },
    { "do": "type", "target": "role=textbox[name=\"Password\"]", "text": "$PRODUCT_DEMO_PASSWORD" },
    { "do": "press", "key": "Enter" },
    { "do": "wait", "target": "[data-app-ready]" }
  ] },
  "viewport": "1440x900",
  "deviceScaleFactor": 2,
  "defaults": { "style": "device", "device": "browser", "background": "dusk", "intro": false, "outro": false },
  "narration": { "provider": "local", "voice": "en-GB-neutral", "language": "en" },
  "deps": { "root": "", "ignore": ["**/*.test.*", "**/*.stories.*"] },
  "store": { "target": "s3", "endpoint": "https://<account>.r2.cloudflarestorage.com", "bucket": "demos", "prefix": "taskly", "baseUrl": "https://demos.example.com/taskly" }
}
```

| Key | Meaning |
|---|---|
| `product` | The product's name, for intro and outro cards. |
| `serve` | Command that builds and starts the app for recording, a production build with demo mode on. The skill adds a `demo` script to the repo for this. Started once per `record` run with `env` applied, stopped at the end. Omit when `url` is already up. |
| `url` | Base URL the app answers on. Demo `start` paths are joined to it. |
| `ready` | Selector (or `networkidle`) the recorder waits for after every navigation before acting. Pick something that appears only after hydration. |
| `setup` | Command that puts the app in its seeded state. Runs before every demo unless the demo overrides it. Must be idempotent. |
| `env` | Environment for `serve` and `setup`. This is where demo mode is switched on. |
| `auth` | How the recorder signs in before a demo, when the app needs it. See below. Omit for apps without login. |
| `viewport`, `deviceScaleFactor` | Defaults for all demos. Scale factor 2 keeps text crisp when the camera zooms. |
| `defaults` | Default look for every demo: `style`, `device`, `theme`, `background`, `intro`, `outro`, `captions`, `cursor`, `highlight`, `output`. See styles.md. A demo file overrides any of them. |
| `narration` | Provider: `local` (bundled model, no key, default), `openai`, `elevenlabs`. `voice` and `language` are provider-specific. `false` turns narration off everywhere. |
| `deps` | `ignore`: globs dropped from the discovered dependency set. `root`: the folder the app is served from, relative to the repo root, for bundlers whose source maps give sources relative to the map file (Vite, plain bundles); empty when that is the repo root. |
| `store` | Where recordings and videos go (section 8). `target`: `s3` for any S3-compatible store (AWS S3, Cloudflare R2, Backblaze, MinIO), or `none` to keep everything in `.cache/`. `endpoint` is omitted for AWS. `baseUrl` is the public prefix written into the index. Credentials come from the environment, never from this file. |

`auth.strategy` is one of:

| Strategy | Meaning |
|---|---|
| `form` | The recorder opens `path` and performs `steps`, the same step format as a demo. `$NAME` in a `text` value is replaced by that environment variable, so credentials stay out of the file. Default names: `PRODUCT_DEMO_USER`, `PRODUCT_DEMO_PASSWORD`. |
| `script` | `command` runs with `url` and a path in `PRODUCT_DEMO_STATE`, and must write a Playwright storage state file there. For apps without a password form, for example one that mints a magic link through an admin API and opens it. |
| `state` | `path` to a committed-nowhere storage state file. Local use only; CI fails with a clear message. |

Signing in happens once per `record` run, after `setup`, and the state is reused for every demo in the run.

## 3. `<demo-id>.yaml` (demo script)

```yaml
id: add-task
title: Add a task
flow: add-task
description: Quick add recognises dates as you type and files the task in Inbox.
style: device
background: plum
intro: true
outro:
  title: Taskly
  subtitle: taskly.app
  fade: false
captions:
  size: 20
  radius: 6px
viewport: 1440x900
output:
  fps: 30
  quality: high
setup: npm run seed:demo -- --scenario empty-inbox
start: /inbox
watch:
  - src/server/tasks/**
  - prisma/seed-demo.ts
steps:
  - label: Open quick add
    do: click
    target: role=button[name="Add task"]
    zoom: 1.4
    say: Press the plus button, or hit Q from anywhere.
  - label: Type task text
    do: type
    target: "[data-testid=quick-add-input]"
    zoom: "[data-testid=quick-add]"
    text: Call the dentist tomorrow 9am
    say: Dates and times are recognised as you type and shown as chips.
  - label: Save
    do: press
    key: Enter
    settle: 800
    say: The task lands in Inbox, scheduled for tomorrow at nine.
```

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Equals the file name. |
| `title` | yes | Shown in the index and on the intro card. |
| `flow` | no | A flow ID from `/product/flows`. Must exist when `/product/flows` exists. |
| `description` | no | One line for the index. |
| `style`, `device`, `background`, `intro`, `outro`, `captions`, `cursor`, `highlight` | no | The look, overriding `config.defaults`. Changing any of them re-renders. See styles.md. On a step, `label`, `say` and a scale `zoom` also only re-render; everything else in a step re-records. |
| `theme` | no | `light` (default) or `dark`: the colour scheme the app is recorded in. Changing it re-records. |
| `viewport` | no | `WxH` the app is recorded at. Overrides the config default. Use a phone size with `device: phone`. |
| `output` | no | Render settings, overriding `config.defaults.output`: `width`, `height`, `scale`, `fps`, `quality` (`draft`, `good`, `high`), `format` (`mp4`, `webm`, `gif`), `loop`. |
| `setup` | no | Overrides the config `setup` for this demo. |
| `start` | yes | Path the demo begins on, joined to `config.url`. |
| `watch` | no | Globs, relative to the repo root, for code the browser never executes but that shapes the demo: server handlers, seed data, migrations. Seed them from the flow's *Implementation references*. |
| `narration` | no | `false` turns narration off for this demo even when steps have `say` lines. |
| `steps` | yes | 1 to about 25 steps. Above that, split the demo. |

The file is a strict subset of YAML: scalars, block lists, block maps, inline lists like `[a, b]`, quoted strings. No anchors, no multi-line scalars, no flow-style maps. The validator parses exactly this subset.

## 4. Steps and actions

Every step is a map with `do` and the keys that action needs. Common optional keys:

| Key | Meaning |
|---|---|
| `label` | The Mermaid node label this step shows, verbatim. Lets the viewer link node and keyframe, and lets the validator find flow nodes the demo never shows. |
| `say` | Narration for this step. See section 6. |
| `settle` | Milliseconds to wait after the action before the `after` keyframe, on top of the `ready` wait. Default 400. Raise it for data that arrives late; do not use it to wait for elements, use `wait`. |
| `zoom` | The camera for this step. Omitted: no camera move. A number from 1 to 3: the camera moves in on the acted element by that scale during the action and back out after. A target: the camera moves in on that element (at scale 1.3), for example the panel a click opened rather than the button. Works in every style. |
| `highlight` | `true` draws the accent ring on the target. Default `true` for `click`, `false` otherwise. |

Actions:

| `do` | Needs | Notes |
|---|---|---|
| `click` | `target` | |
| `type` | `target`, `text` | Clicks the target first. The renderer types at a fixed cadence; the recorder types instantly and captures the end state. |
| `press` | `key` | A Playwright key: `Enter`, `Escape`, `Meta+K`. |
| `hover` | `target` | |
| `scroll` | `target` or `to` | `to` is a pixel offset; `target` scrolls the element into view. |
| `navigate` | `url` | A path joined to `config.url`. Waits for `ready`. |
| `wait` | `target` or `ms` | Waits for the element to be visible, or a fixed time. Produces no keyframes unless it has `say`. |
| `select` | `target`, `value` | Native `<select>`. For custom dropdowns use `click` twice. |
| `upload` | `target`, `file` | Path relative to `demos/`. |

Around every action the recorder takes a keyframe before and after, with the acted element's rectangle and the pointer position. Before each keyframe it settles the page: finite CSS animations and transitions are jumped to their end, infinite ones (spinners) are paused at a fixed phase, the pointer is parked, the caret is hidden. The renderer synthesises the motion between keyframes.

## 5. Targets

A target is a Playwright locator string. In order of preference:

1. Role and name: `role=button[name="Add task"]`, `role=textbox[name="Email"]`. Survives restyles and copies what a user sees.
2. Test ID: `[data-testid=quick-add-input]`. Add the attribute when no accessible name exists.
3. Text: `text=Save changes`. Fine for buttons with stable copy.
4. CSS: `form.settings input[name=email]`. Last resort.

Never use positional selectors (`nth-child`, `nth=2`) unless the position is the point of the step ("the third card"). Say so in `label`.

## 6. Narration

`say` is one or two sentences per step, in the user's words, present tense, describing what is happening and why, not the pointer: "Dates are recognised as you type", not "Now click the input and type". Keep every line under about 20 words so pacing stays brisk; a step lasts as long as the longer of its action and its narration. Steps without `say` are silent; a demo that narrates some steps and not others gets a warning, so narrate all or none.

The same lines become captions and subtitles, so they must read well on screen.

Audio is generated per line and cached by the hash of text, provider, voice and language, locally in `.cache/narration/` and in the store under `narration/`. Only changed lines regenerate.

## 7. What the recorder and renderer produce

For each demo, `record` produces a recording and `render` produces a video from it:

```text
<demo-id>/
  events.json          Event log: every step with pointer, element rectangle, keyframe names, narration
  frames/01-before.png, 01-after.png, …
  manifest.json        Input hashes, the dependency set, platform, versions
  <demo-id>.mp4        The video (format from output)
  <demo-id>.png        Poster: the frame the docs site shows before play
  <demo-id>.vtt        Captions
```

Locally this lands in `.cache/<env>/`; in CI it is uploaded to the store under the environment (section 8). Never edit any of it by hand.

`manifest.json`:

```json
{
  "version": 1,
  "demo": "add-task",
  "recordedAt": "2026-10-14T09:12:00Z",
  "platform": "linux-x64",
  "package": "0.1.0",
  "inputs": { "demo": "sha256:…", "config": "sha256:…", "look": "sha256:…", "flow": "sha256:…" },
  "deps": {
    "src/features/quick-add/QuickAdd.tsx": "sha256:…",
    "src/lib/parse-task-text.ts": "sha256:…",
    "src/server/tasks/create.ts": "sha256:…"
  },
  "video": { "file": "add-task.mp4", "durationMs": 14200, "style": "device", "theme": "light", "background": "plum", "lookHash": "sha256:…" }
}
```

`inputs` are the files the demo is made from. `deps` is the set of repository files the recording executed (browser coverage resolved through source maps) plus the `watch` globs, each with its content hash. `check` compares every entry against the working tree; any difference makes the demo stale, and a stale demo is re-recorded, re-rendered and overwritten. There is no pixel comparison.

## 8. The store: environments, manifests, `index.json`

The store holds one folder per environment, laid out identically:

```text
<prefix>/
  production/                  Written on the default branch. The docs site reads this.
    index.json
    add-task/…                 Section 7, per demo
    narration/<hash>.mp3       Shared narration cache
  pr-123/                      Written for pull request 123. Deleted when the PR is merged or closed.
    index.json
    add-task/…
```

`check` on a branch compares against the manifests in `production/`; `check` on the default branch does too, then overwrites production. The PR folder exists so reviewers can watch the preview videos and see the keyframes without anything touching production.

`index.json`, one entry per demo:

```json
{
  "environment": "production",
  "generatedAt": "2026-10-14T09:40:00Z",
  "demos": [
    {
      "id": "add-task",
      "title": "Add a task",
      "description": "Quick add recognises dates as you type and files the task in Inbox.",
      "flow": "add-task",
      "style": "device",
      "theme": "light",
      "background": "plum",
      "durationMs": 14200,
      "video": "https://demos.example.com/taskly/production/add-task/add-task.mp4",
      "poster": "https://demos.example.com/taskly/production/add-task/add-task.png",
      "captions": "https://demos.example.com/taskly/production/add-task/add-task.vtt",
      "recordedAt": "2026-10-14T09:12:00Z"
    }
  ]
}
```

A docs page embeds a demo with a `<video>` whose `src`, `poster` and `<track>` come from here. With `store.target: none`, the index is written to `.cache/<env>/index.json` with repo-relative paths.
