# How product demos work

Each piece of the pipeline, what it does, and why it is built that way. The code is in `@nuthinking/product-demo`; the repository holds the demo scripts under `/product/demos` and the workflow the skill installs.

## The pipeline

```text
demo script ──▶ record ──▶ recording (keyframes + events + manifest) ──▶ render ──▶ video ──▶ store ──▶ index.json
   yaml        Playwright                                                frame by frame        S3/R2     docs site
```

1. **Record.** The recorder starts the app (a production build with demo mode on), runs the seed, signs in if the config says how, opens `start`, and performs the steps with Playwright. Around every action it takes a screenshot before and after, and writes the acted element's rectangle, the pointer position and the step metadata to `events.json`. It also collects JavaScript and CSS coverage from the browser and, through source maps, resolves it to the repository files that executed. Those files, plus the `watch` globs, become the dependency set in `manifest.json`, each with a content hash.
2. **Render.** A composition page takes the recording and its look (style, background, settings). It shows the keyframes, draws the cursor moving between pointer positions, types the text at a fixed cadence, zooms and tilts the frame, crossfades between keyframes, overlays captions, and adds intro and outro cards. The renderer seeks that page to each frame time and screenshots it, then ffmpeg encodes the frames with the narration. Every frame is computed from the event log, so the same recording and look give the same video. The camera moves only on steps whose script asks for a `zoom`.
3. **Store.** Recording and video are uploaded to the store under the current environment, and that environment's `index.json` is rewritten. The docs site reads the production index.

## Why keyframes, not a screen recording

A screen recording captures whatever happened on that machine at that moment: dropped frames, a tooltip that appeared late, the cursor's actual path, a font that loaded a beat after the page. Two recordings of the same steps are never identical, so a changed video tells you nothing about whether the product changed.

Keyframes and an event log are the smallest thing that still holds everything the video needs. They separate what the product did from how it is shown. A restyle is a render. A brand change touches no recording. A reviewer looks at two PNGs side by side and sees what changed.

The cost is in-app motion: a drawer sliding open, a chart animating in. Between keyframes the renderer crossfades, so that motion is implied, not shown. Where that motion is the point of a step, raise its `settle` so the after keyframe shows the end state, and let the caption say what moved.

## Settling the page before a keyframe

Playwright's fake clock freezes dates and timers, but CSS animations and transitions run on the compositor and ignore it. A spinner caught at two different rotations was the first instability found in practice. So before every keyframe the recorder settles the page through the Web Animations API: finite animations and transitions (a panel fading in, a hover colour) are jumped to their end, so the keyframe shows the UI at rest; infinite ones (spinners, pulsing dots) are paused at a fixed phase. It also parks the pointer, hides the caret and scrollbars, and waits for fonts and the network. None of this is visible in the video, where all motion is synthesised; it only makes two recordings of the same product identical.

What remains after that is compositor noise: a handful of pixels on antialiased corners that differ by one level between runs. It does not matter, because nothing compares pixels (next section).

## Determinism is the app's job too

The recorder only reproduces what the app repeats. Demo mode, switched on through `config.env`, is where the repository makes itself repeatable:

- **Seeded data.** The `setup` command resets the demo state to a fixture every run: same users, same items, same order. Fixed IDs, not generated ones, so URLs do not drift.
- **Frozen time.** Relative dates ("2 hours ago", "due tomorrow") move every day. The recorder installs Playwright's clock at a fixed instant; server-rendered dates need the app to honour a `DEMO_NOW` or similar from `env`.
- **No randomness.** Random avatars, shuffled suggestions, A/B flags, "tip of the day". Seed them or pin them in demo mode.
- **No third parties.** Analytics, chat widgets, cookie banners, live maps, external images with cache-busting URLs. Off in demo mode, or they appear in a keyframe one day and not the next.
- **Self-hosted fonts.** A font from a CDN that is slow in CI renders as a fallback for one frame.
- **A production build.** The dev server adds its own overlay and devtools button to every frame, and dev-only modules to the dependency set. Demo mode runs a production build, with source maps on so coverage still resolves.
- **Animations settled** by the recorder, as above. Data that arrives late still needs `settle` or a `wait` on the element that marks completion.

`record --repeat 3` records a demo three times and reports any step whose keyframes differ by more than compositor noise; it is the test for all of the above.

## Staleness

"Regenerate when code that might influence it is touched" needs a definition of *might influence*. Guessing globs by hand goes wrong both ways: too broad and every change re-records everything, too narrow and a real change ships with an old video.

The recording discovers its own dependencies. Browser coverage says which bundled modules executed during the demo; source maps turn that into repository paths (in a Next.js app, a four-step demo resolved to about 25 source files, from the page down to the button and input components); the manifest stores each path with a content hash. Granularity is the file: a module whose top-level code ran when the bundle loaded counts, even if the demo never reached its UI, which errs on the side of re-recording. `check` hashes the same paths in the working tree and reports a demo stale when any differ, naming the files. Coverage misses code the browser never runs, server handlers, database seeds, so `watch` globs add those explicitly, and the flow's *Implementation references* in the Product Map are the natural seed for them. Framework internals, font modules and build plumbing are filtered out.

A stale demo is re-recorded, re-rendered and overwritten. There is no comparison of frames or videos: if the code a demo depends on changed, the demo is regenerated, full stop. A change to a shared module (the app shell, the router) makes every demo stale. That is right; it might have changed everything, and at roughly half a minute per demo it is affordable.

Two levels: a changed dependency, demo script, flow file, seed or app theme makes a demo stale for **recording**. A changed style, background, card, caption or output setting, or a step's label, narration or scale zoom, makes it stale for **rendering** only, which is cheap and needs no app. The demo and config hashes leave the render-only keys out, so editing a demo's look or words does not re-record it; the renderer takes those step keys from the demo file, not the recording. A target zoom stays a recording input because its rectangle is measured against the live page.

## Environments and the store

Videos are generated in CI, never committed. The store has one folder per environment. A pull request writes to its own folder, `pr-<number>`, so reviewers can watch the preview videos and see the keyframes without anything touching `production/`, which the docs site reads. The folder is deleted when the pull request is merged or closed; a lifecycle rule on the bucket expires forgotten ones. Merging to the default branch runs the same check against production and overwrites what is stale.

Nothing is committed by CI. The repository holds the demo scripts and the config; manifests live next to the recordings in the store, and `check` reads them from there. That removes bot commits, branch protection problems and the fork problem.

CI is also the canonical recorder for a second reason: fonts render differently on macOS and Linux, so a keyframe recorded on a laptop never pixel-matches the same keyframe from CI. Locally, `record` and `render` write to `.cache/` so a developer can check that a demo script works and look at the result; the store only ever receives CI output.

## Signing in

Most products hide their flows behind a login. The config's `auth` block tells the recorder how to get in, once per run: fill a login form with a test account from environment variables (`form`); run a repo script that produces a signed-in browser state, for apps whose login has no password, for example by minting a magic link through an admin API (`script`); or load a saved state file, locally only (`state`). The test account is part of the seed, with a fixed name and avatar, since it appears in the frames.

## Narration

Lines come from `say`. Text to speech runs per line, keyed by the hash of text, provider, voice and language, and cached locally and in the store, so unchanged lines never regenerate and a changed word regenerates one clip. The local provider is a bundled model, so CI needs no key and the output is stable for a given model version; cloud providers sound better and are not bit-identical between calls, which is why the cache is the unit of determinism, not the provider. Pacing comes from the audio: a step lasts as long as the longer of its synthesised action and its narration plus a short pause. Captions and the `.vtt` track are the same lines, so a demo without voice still carries them.

## Encoding

The renderer screenshots its composition page frame by frame and pipes raw frames to ffmpeg. The package ships `ffmpeg-static` because Playwright's bundled ffmpeg only encodes VP8 WebM and cannot read PNG; H.264 MP4 is what docs sites and social platforms expect. Measured on a laptop, a ten second clip at 30 fps captures in about 13 seconds and encodes in about 5.

## Review in pull requests

The pull request comment is the review surface: for each re-recorded demo, the before and after keyframes of every step with its label, and a link to the preview video in the PR folder. A change to the product shows up as a changed keyframe. Approving the PR approves the video; nobody has to watch a render to review a copy change.

## Things to watch

- Source maps must be emitted by the production build in demo mode, or coverage resolves to bundle chunks and the dependency set becomes "the whole build", which is correct but stale on every change. In Next.js that is `productionBrowserSourceMaps: true` when demo mode is on.
- Hover states leak: a pointer left over a button from the previous step changes the next `before` frame. The recorder parks the pointer, but tooltips with delays can still show. Add `settle`.
- Narration providers change voices between model versions. Pin the version in `config.narration` once it sounds right, or a provider update re-voices every demo at once.
- A pull request from a fork has no secrets, so it cannot write to the store. The workflow skips the upload and attaches the recording as a workflow artifact instead.
