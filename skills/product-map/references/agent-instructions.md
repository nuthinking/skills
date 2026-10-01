# Agent instructions section

Add this section to `AGENTS.md` and/or `CLAUDE.md` (see SKILL.md, *Agent instructions*, for which file). Append it, or replace an existing `## Product Map` section. Replace `<validation command>` with the one that actually works in this repo, in this order of preference:

1. The package script, when the viewer is installed and provides validation (check first), for example `npm run product-map -- validate`.
2. Otherwise the copied validator: `python3 product/validate.py` (SKILL.md, *Validation*, says when to copy it into the repo).

Never write a machine-specific absolute path (for example under your home directory or a plugin cache) into a shared instruction file.

```md
## Product Map

The current product capabilities and behavior are documented in `/product`.

Before implementing or modifying user-facing behavior:

1. Read `/product/README.md`.
2. Check `/product/features.md` for the relevant capabilities.
3. Read the relevant files in `/product/flows/`.

When a change modifies product behavior, navigation, available capabilities,
conditions, outcomes, or major failure states, update the affected Product Map
files as part of the same change. Do not update them for purely internal
changes that leave observable behavior identical.

Keep Product Map documentation focused on observable product behavior rather
than implementation details.

When writing a pull request description for a change that touches `/product`,
add a `## Product behavior` section: one to three "before → after" bullets in
user terms, links to the affected flow files on the branch, and the updated
Mermaid diagram inline (GitHub renders it in the PR body, not in the diff).

Run the Product Map validation command before completing behavior-changing work:
`<validation command>`
```

When creating `AGENTS.md` from scratch, start the file with a `# Agent instructions` heading and put this section under it.

Keep it this short. These files point agents to `/product`; they must not duplicate the map's content.
