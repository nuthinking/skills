# nuthinking/skills

Agent skills by [nuthinking](https://github.com/nuthinking). They work with Claude Code, Codex, Cursor and any other agent that reads the `SKILL.md` convention.

## Install

Claude Code:

```bash
claude plugins install nuthinking-skills
```

Or from inside a session:

```text
/plugin install nuthinking-skills
```

Codex and other agents, or editable copies in your own repo:

```bash
npx skills@latest add nuthinking/skills
```

Update later with `npx skills update`.

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
