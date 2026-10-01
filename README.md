# nuthinking/skills

Agent skills by [nuthinking](https://github.com/nuthinking). They work with Claude Code, Codex, Cursor and any other agent that reads the `SKILL.md` convention.

## Install

Any agent that reads `SKILL.md` (Claude Code, Codex, Cursor, and others). This symlinks the skills into your project, or into your user directory with `-g`:

```bash
npx skills@latest add nuthinking/skills
```

Update later with `npx skills update`.

Claude Code, as a managed plugin that updates with `claude plugin update`. Inside a session:

```text
/plugin install nuthinking-skills --marketplace nuthinking/skills
```

Or from your shell, where the first command registers this repo as a plugin source and the second installs from it:

```bash
claude plugin marketplace add nuthinking/skills
claude plugin install nuthinking-skills@nuthinking
```

## Skills

| Skill | What it does |
|---|---|
| [`product-map`](skills/product-map) | Creates and maintains a Product Map in `/product`: a sitemap for what your software does. A Feature Map (what capabilities exist) plus Mermaid Product Flows (how the product behaves), kept in the repo so humans and agents share one model. Pairs with the `@nuthinking/product-map` viewer. |

## Layout

```text
skills/<skill-name>/
  SKILL.md        Frontmatter (name, description) + instructions
  README.md       Human-facing explanation
  references/     Longer docs the agent loads on demand
  scripts/        Helper scripts the agent can run
```

## License

MIT
# skills
