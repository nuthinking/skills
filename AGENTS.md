# Agent notes for this repository

This repo publishes agent skills. Each skill is a folder under `skills/` with a `SKILL.md` (frontmatter `name` + `description`, then instructions), an optional `README.md` for humans, `references/` for longer docs the agent loads on demand, and `scripts/` for helpers.

When adding or changing a skill:

- Keep `SKILL.md` lean (well under 500 lines). Move long templates, schemas and examples into `references/` and link to them with a sentence on when to read them.
- Register new skills in `.claude-plugin/plugin.json` (`skills` array) and in the table in `README.md`.
- Skills must work for any agent that reads `SKILL.md` (Claude Code, Codex, Cursor), so avoid agent-specific tool names in instructions.
- Scripts must be dependency-free where possible (Python 3 standard library) and runnable from any working directory.
- Test a skill against a realistic repo before changing its instructions substantially.
