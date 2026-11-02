# The `product-demo` CLI

The contract of `@nuthinking/product-demo`. The skill drives these commands; a package that implements them is interchangeable. Run through the package script (`npm run product-demo -- <command>`) or `npx product-demo <command>`. All commands read `product/demos/config.json` and take `--demos <path>` to point elsewhere.

The environment is `production` on the default branch, `pr-<number>` on a pull request, and `local` otherwise; `--env` overrides. Locally everything is written to `product/demos/.cache/<env>/`; with a store configured and credentials present, `publish` uploads from there.

| Command | Does | Exit code |
|---|---|---|
| `validate` | The same checks as `scripts/validate.py`: file structure, step keys, targets, flow and preset references, config. | 1 on errors |
| `check [id…]` | Compares every demo with its manifest in the store's `production/` folder (or the local cache with `store.target: none`). Prints each stale demo, whether it is stale for `record` or `render`, and the files that changed. A demo with no manifest is stale. `--json` for workflows. | 1 when anything is stale |
| `record [id…]` | Runs `setup`, starts `serve` (unless `--no-serve`), signs in per `auth`, performs the steps, writes the recording. `--repeat N` records N times and reports unstable steps. `--headed` shows the browser. | 1 on a failed step |
| `render [id…]` | Renders videos from the recordings in the cache. `--style`, `--background` and `--device` override the demo's look for this render (`--theme` too, but a theme change needs a re-record to show in the app). Writes the video, poster and captions. `--no-cache` regenerates narration. `--concurrency N`. | 1 on a render error |
| `publish [id…]` | Uploads the cache for the current environment to the store and rewrites that environment's `index.json`. `--dry-run` prints what would change. | 1 on upload error |
| `clean <env>` | Deletes an environment's folder from the store. The workflow runs it when a pull request closes. | |
| `pr-comment [id…]` | Prints the Markdown for the pull request comment: per re-recorded demo, the before and after keyframes of each step (store URLs), the changed dependencies, and the preview video link. | |
| `studio [id]` | The editor. Serves a local page (`--port`, default 4791) listing the demos with their status (not recorded, needs a recording, needs a render, up to date) and, per demo, a preview from the recording with controls for style, background, cards, captions, cursor, output, and each step's label, narration, zoom and settle. Save writes the demo file, keeping everything else in it as written; Record and Render run the CLI from the page and stream the log. With an `id` it opens that demo. Needs the same environment as `record` (test account, `PRODUCT_DEMO_ENV`). | |
| `preview <id>` | The composition page alone with a scrubber, for the current settings. | |
| `templates` | Prints the path of the package's `templates/` folder (workflow, agent rules, gitignore lines, the `demo` script). | |

Conventions

- IDs given on the command line limit the run; none means every demo.
- `record` and `render` write nothing on failure; a half-written recording is never left behind.
- Every command prints one line per demo and a summary, machine-readable with `--json`.
- Credentials are read from the environment: `PRODUCT_DEMO_USER` and `PRODUCT_DEMO_PASSWORD` for the `form` login strategy; `PRODUCT_DEMO_TTS_KEY` for a cloud narration provider; `PRODUCT_DEMO_STORE_KEY` and `PRODUCT_DEMO_STORE_SECRET` for the store (or the AWS variables).
- The recorder uses Playwright's bundled Chromium. `npx playwright install chromium` once per machine and in the workflow. Encoding uses the package's `ffmpeg-static`.
