# Agent notes for this repository

This repo publishes agent skills. Each skill is a folder under `skills/` with a `SKILL.md` (frontmatter `name` + `description`, then instructions), an optional `README.md` for humans, `references/` for longer docs the agent loads on demand, and `scripts/` for helpers.

When adding or changing a skill:

- Keep `SKILL.md` lean (well under 500 lines). Move long templates, schemas and examples into `references/` and link to them with a sentence on when to read them.
- Register new skills in `.claude-plugin/plugin.json` (`skills` array) and in the table in `README.md`.
- Skills must work for any agent that reads `SKILL.md` (Claude Code, Codex, Cursor), so avoid agent-specific tool names in instructions.
- Scripts must be dependency-free where possible (Python 3 standard library) and runnable from any working directory.
- Test a skill against a realistic repo before changing its instructions substantially.
- After changing `skills/product-map/scripts/validate.py`, run `python3 skills/product-map/scripts/test_validate.py`.
- After changing `skills/product-demo/scripts/validate.py`, run `python3 skills/product-demo/scripts/test_validate.py`.
- After changing anything under `skills/design-catalog/scripts/`, run `python3 skills/design-catalog/scripts/test_scripts.py`, and re-run the extraction against a drifted fixture app (see `skills/design-catalog/README.md`, Testing) before changing the instructions.
- After changing anything under `skills/ui-tweaks/scripts/`, run `node skills/ui-tweaks/scripts/test_scripts.mjs`, and check the panel against a running app through `preview.mjs` (see `skills/ui-tweaks/README.md`, Testing) before changing the instructions.
