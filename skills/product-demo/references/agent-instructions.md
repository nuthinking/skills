# Agent instructions section

Add this section to `AGENTS.md` and/or `CLAUDE.md`, after the `## Product Map` section when there is one. Append it, or replace an existing `## Product demos` section. Replace `<run>` with the way the package runs in this repo (`npm run product-demo --`, `pnpm product-demo`, …).

```md
## Product demos

Demo videos of product flows are generated from `/product/demos`. Each
`<id>.yaml` is a script of steps against the app in demo mode. Videos are
recorded and rendered in CI and stored outside the repository; nothing
generated is committed. Local runs write to `product/demos/.cache/` only.

When a change touches a flow in `/product/flows` or code a demo depends on,
run `<run> check` before completing the work. For each stale demo:

1. Run `<run> record <id>` locally and look at the keyframes in
   `product/demos/.cache/local/<id>/frames/`. If a step fails or shows the
   wrong thing because the product changed, update the demo script so it
   follows the new behavior, then record again.
2. Add a `## Demos` section to the pull request description naming the
   affected demos and what changed in them. CI re-records them and comments
   on the pull request with the keyframes and preview videos.

Do not change `product/demos/config.json`, backgrounds or demo mode in the app
unless the task is about demos.
```

When creating `AGENTS.md` from scratch, start the file with a `# Agent instructions` heading and put this section under it.

Keep it this short. The file points agents to `/product/demos` and the commands; it must not duplicate the format.
