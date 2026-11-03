# UI tweaks

> Fine-tune the craft details of your running app by eye, then hand the result back to your agent.

The last 10% of a design is craft: the card that wants 20px of padding instead of 24, the heading that wants a touch tighter, the borders a shade lighter, the shadow a little softer. Asking an agent for each nudge ("a bit less… no, back a little") is slow, and every round trip changes code. This skill puts a small, draggable panel on top of the app instead. The agent reads the code, picks six to eight precise controls for the screen or component you are polishing, and you nudge them while the page updates live. When it feels right, **Copy** puts the changes on your clipboard as a message for the agent, which applies them to the source.

It is for refining a design, not redesigning it: no accent colours or font swaps unless you ask for them by name. The app's code is not touched while you play; it changes once, when you paste the result back.

![The Tweaks panel over a task manager's dashboard: stat card and row padding, space above a section, heading tracking, card corners and shadow, and border and secondary-text shades, with three changes ready to copy; the panel is dark because the page is light](https://raw.githubusercontent.com/nuthinking/skills/main/docs/screenshots/ui-tweaks/panel.png)

## How it works

1. **The agent picks the controls.** For the screen or component you name (or the main screen), it reads the classes and tokens that shape each piece and writes a short list of controls into `.ui-tweaks/config.json`: Stat card padding, Task row padding, Space above Today, Greeting tracking, Card corners, Stat card shadow, Borders and dividers, Secondary text. Each starts at the code's current value, targets exactly that element, and knows the file it lives in.
2. **You open a preview address.** A small local server sits in front of your dev server: `localhost:3999` is your app, with the panel added. Hot reload still works, and nothing in the app changes. (If your login redirects to a fixed address, the agent adds a temporary dev-only script tag instead.)
3. **You nudge.** Sliders with fine steps that settle on your app's own scale (ticks mark 16, 20, 24…), shades that go lighter or darker along a track showing the actual colours and click onto your existing tokens, segmented choices for weights and shadows, numbers you can type or scrub by dragging the label. A blue dot marks what you changed; click it to reset. Hold **Compare** to see the original. Your changes survive reloads.
4. **You copy and paste.** The message lists only what changed, old → new, and where each value lives:

   ```text
   Apply these UI tweaks with the ui-tweaks skill (3 changes):

   Stat card padding     24px → 20px                                 stat cards · p-6 · src/components/Card.tsx
   Stat card shadow      Soft → Faint (shadow-sm → shadow-xs)        stat cards · shadow-sm · src/components/Card.tsx
   Borders and dividers  #e5e7eb (border) → #d1d5dc (border-strong)  border · app-wide · src/app/globals.css
   ```

   The agent changes the code in its own terms (`p-6` → `p-5` in the card component, `shadow-sm` → `shadow-xs`, the border token pointed at `border-strong`), checks the page took it, updates the panel's starting point, and you keep going from there.

## The panel

Designed to feel like a macOS inspector: translucent material, the system font at inspector sizes, hairline separators, spring motion. It takes the opposite of the page underneath, dark over a light app and light over a dark one, so it never blends into what you are tweaking, and it flips when the app's theme does. One file, no dependencies, with its styles sealed in a shadow root and attached outside the page's body, so it cannot affect the app and the app cannot affect it.

- Drag it by the header; it remembers where you left it.
- Collapse it to a pill; **⌥T** (Alt+T) hides it entirely.
- Type numbers, use ↑↓ (Shift for ×10), or drag a label to scrub.
- Rows targeting an element that is not on the current screen say "not on this page".

## Install

Any agent that reads `SKILL.md` (Claude Code, Codex, Cursor, and others). This installs only this skill; add `-g` to install it in your user directory instead of the project:

```bash
npx skills@latest add nuthinking/skills --skill ui-tweaks
```

Claude Code as a plugin (this installs all the skills in this repo): `/plugin install nuthinking-skills --marketplace nuthinking/skills`.

Then, in the app's repo, ask the agent to "give me a tweaks panel for the dashboard", "let me fine-tune the pricing card", or "the task list feels cramped, let me play with it". It needs Node (the preview is a Node script with no dependencies) and the dev server running (it will start it).

## What stays in your repo

Nothing. Working files live in `.ui-tweaks/`, which is excluded from git through `.git/info/exclude`, and are deleted when you say you are done. Only the changes you pasted back end up in your code, for you to review.

## Scripts

Dependency-free (Node built-ins only) and runnable from anywhere.

| Script | Does |
|---|---|
| `ui-tweaks.js` | The panel. Loaded into the page by the preview (or a script tag), reads `config.json`, applies overrides, copies the message. Number, shade (OKLCH lighter/darker) and choice controls for craft; colour and scale controls on request. |
| `preview.mjs` | The preview address: forwards everything to the dev server, including hot-reload websockets, and adds the panel to HTML pages. `--check` validates a config. |
| `test_scripts.mjs` | Tests for the panel's config, CSS and copy logic, and for the preview against a fake dev server. |

## Testing

`node skills/ui-tweaks/scripts/test_scripts.mjs` runs the unit and proxy tests. For a realistic run, use a throwaway copy of a Next.js + Tailwind v4 app with tokens and some hard-coded values (the design-catalog fixture works well; `cp -cR` clones it instantly on macOS). Have a fresh agent run the skill end to end: set up the panel for a screen, then apply a message copied from the panel. Check that hot reload connects through the preview (`[HMR] connected` in the console), that `uiTweaks.check()` in the page shows every control reaching its intended elements, that Copy, Compare, collapse and reload behave, and that after applying the page keeps the values while the panel's count drops to zero.

## Limitations

- CSS only. Values set in JavaScript (Motion springs, chart colours passed as props, canvas) cannot be tweaked live.
- Colours have no alpha control; the panel works in hex and the agent converts back to the code's format.
- A control on a shared token (a border colour, a radius) moves everything that uses it; the agent says so, and targets the element itself when it can.
- Some dev servers do not hot-reload theme changes (Tailwind v4 under Turbopack can keep the old `@theme`); the agent checks, restarts the dev server when needed, and asks you to reload.
- Values are overridden with `!important`; a rule the app itself marks `!important` wins.
- The preview address is a different origin from your usual one, so the app's local storage and cookies there start empty (you may need to sign in once).
