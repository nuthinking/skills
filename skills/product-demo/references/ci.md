# CI for product demos

The workflow keeps demos current without anyone remembering to, and nothing it produces is committed. On pull requests it re-records stale demos into the PR's own folder in the store and comments with what changed; on the default branch it overwrites production; when a PR closes it deletes the PR folder.

## Flow

```text
pull request ──▶ check against production ──▶ record + render stale ──▶ publish to pr-<n> ──▶ comment: keyframes + preview links
push to main ──▶ check against production ──▶ record + render stale ──▶ publish to production (index.json updated)
PR closed    ──▶ clean pr-<n>
```

## Template

Copy from the package (`product-demo templates`) when it ships one; otherwise start here and adapt the `PRODUCT-DEMO` lines.

```yaml
name: Product demos

on:
  pull_request:
    types: [opened, synchronize, reopened, closed]
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      all:
        description: Re-record every demo
        type: boolean
        default: false

concurrency:
  group: product-demo-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: write

env:
  PRODUCT_DEMO_ENV: ${{ github.event_name == 'pull_request' && format('pr-{0}', github.event.pull_request.number) || 'production' }}
  PRODUCT_DEMO_STORE_KEY: ${{ secrets.PRODUCT_DEMO_STORE_KEY }}
  PRODUCT_DEMO_STORE_SECRET: ${{ secrets.PRODUCT_DEMO_STORE_SECRET }}

jobs:
  clean:
    if: github.event_name == 'pull_request' && github.event.action == 'closed'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }                 # PRODUCT-DEMO: the project's Node version
      - run: npm ci                                # PRODUCT-DEMO: the project's install
      - run: npx product-demo clean "$PRODUCT_DEMO_ENV"

  demos:
    if: github.event_name != 'pull_request' || github.event.action != 'closed'
    runs-on: ubuntu-latest
    timeout-minutes: 45
    services: {}                                   # PRODUCT-DEMO: a database service if the app needs one
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22                         # PRODUCT-DEMO: the project's Node version
          cache: npm                               # PRODUCT-DEMO: the project's package manager
      - run: npm ci                                # PRODUCT-DEMO: the project's install
      - run: npx playwright install --with-deps chromium

      - name: Find stale demos
        id: check
        run: |
          if [ "${{ inputs.all }}" = "true" ]; then echo "ids=" >> "$GITHUB_OUTPUT"; echo "stale=true" >> "$GITHUB_OUTPUT"; exit 0; fi
          npx product-demo check --json > check.json || true
          echo "ids=$(jq -r '[.stale[].id] | join(" ")' check.json)" >> "$GITHUB_OUTPUT"
          echo "stale=$(jq -r '.stale | length > 0' check.json)" >> "$GITHUB_OUTPUT"

      - name: Record and render
        if: steps.check.outputs.stale == 'true'
        env:
          DEMO_MODE: "1"                           # PRODUCT-DEMO: same as config.env, for the build
          PRODUCT_DEMO_USER: ${{ secrets.PRODUCT_DEMO_USER }}          # PRODUCT-DEMO: only with the form login strategy
          PRODUCT_DEMO_PASSWORD: ${{ secrets.PRODUCT_DEMO_PASSWORD }}
          PRODUCT_DEMO_TTS_KEY: ${{ secrets.PRODUCT_DEMO_TTS_KEY }}    # PRODUCT-DEMO: only with a cloud narration provider
        run: |
          npx product-demo record ${{ steps.check.outputs.ids }}
          npx product-demo render ${{ steps.check.outputs.ids }}

      - name: Publish
        if: steps.check.outputs.stale == 'true' && (github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository)
        run: npx product-demo publish ${{ steps.check.outputs.ids }}

      - name: Attach recording (fork)
        if: steps.check.outputs.stale == 'true' && github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name != github.repository
        uses: actions/upload-artifact@v4
        with:
          name: product-demos
          path: product/demos/.cache

      - name: Comment
        if: steps.check.outputs.stale == 'true' && github.event_name == 'pull_request'
        run: |
          npx product-demo pr-comment ${{ steps.check.outputs.ids }} > comment.md
          gh pr comment ${{ github.event.pull_request.number }} --body-file comment.md
        env:
          GH_TOKEN: ${{ github.token }}
```

## Adapting it

- **Starting the app.** `record` runs `config.serve`, a production build with demo mode on. If the app needs a database, add a service container and make `setup` seed it. Source maps must be on in that build or coverage resolves to bundle chunks.
- **Secrets.** Store credentials always; the test account only for the `form` login strategy; a narration key only for a cloud voice. With the local voice and `store.target: none`, the workflow needs no secrets and only produces artifacts.
- **Forks.** A pull request from a fork has no secrets. The template skips `publish` and attaches the cache as an artifact instead, and the comment step still runs with whatever `pr-comment` can link.
- **Loops.** Nothing is pushed to the branch, so nothing re-triggers the workflow. The `concurrency` group cancels a superseded run on the same branch.
- **Cost.** Recording is seconds per demo, rendering well under a minute at 30 fps on a hosted runner. A change to a shared module re-records every demo; for a repo with many demos, lower `output.scale` or `output.fps` in `defaults`, or raise `timeout-minutes`.
- **The bucket.** Public read on objects, since the docs site and the PR comments load from it directly. A lifecycle rule expiring `pr-*/` after 30 days catches pull requests that never fired the close event. With Cloudflare R2, connect a custom domain for `store.baseUrl`.
- **The docs site.** It reads `<baseUrl>/production/index.json` at build time or at runtime and embeds each entry's `video`, `poster` and `captions`.
