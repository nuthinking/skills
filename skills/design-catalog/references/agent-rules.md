# Agent rules section

Append this section to `AGENTS.md` (and to `CLAUDE.md` when it holds the real instructions rather than pointing at `AGENTS.md`). If neither exists, create `AGENTS.md` with it, unless the repo has an established alternative (`.cursorrules`, `.github/copilot-instructions.md`). Do not replace or reorder existing content; add or update only the `## Design catalog` section. Keep it this short: the rules live in `DESIGN.md`, this section only makes sure they are read.

Fill the three placeholders from the project: the path to `DESIGN.md` if not at the root, the catalog route if not `/design-catalog`, and the skill's scripts path only if the project keeps a copy (otherwise leave the Review line as a sentence, never write a machine-specific absolute path into a shared file).

```markdown
## Design catalog

This app has a design catalog: `DESIGN.md` (tokens, components, rules) and the page `/design-catalog`, which renders every token and shared component from the real code.

- Before building or changing any UI, read `DESIGN.md` and look at `/design-catalog`.
- Use an existing component when one fits; add a variant when it almost fits; create a new shared component only when nothing does, and in the same change add it to the catalog page and to `DESIGN.md`.
- Use the semantic tokens for colour, radius and shadow; spacing and type from the documented scale. No raw palette classes, hex values or arbitrary values in UI code without a comment saying why.
- When you change a shared component or a token, check the catalog page and one real screen that uses it, and update `DESIGN.md` if its tables changed.
- To check for drift, run the design-catalog skill in Review mode: it measures the running app and lists values on screen that match no token.
```
