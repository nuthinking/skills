---
name: ui-tweaks
description: Put a polished, draggable Tweaks panel on top of a running web app so a designer can fine-tune the craft details of a screen or component live (padding and gaps, line height, letter-spacing, weights, corner radius, border and secondary-text contrast, shadow softness, icon size, hover timing) with no change to the app's code, then paste the copied changes back so the agent applies them to the source. Reads the code to pick six to eight precise controls tied to the components the person is polishing, writes a small config, and serves the app through a local preview address that adds the panel. Use whenever someone wants to tweak, fine-tune, polish, nudge, dial in or adjust the details of a UI by eye; asks for sliders, knobs, live controls, or a tweak or tuning panel; says a screen feels cramped, heavy or slightly off; or pastes a message that starts with "Apply these UI tweaks".
---

# UI tweaks

The last 10% of a design is craft: a card that wants 20px of padding instead of 24, a heading that wants a touch tighter, borders a shade lighter, a shadow a little softer. Those are judged by eye, and asking an agent for each nudge is slow. This skill puts a Tweaks panel on top of the running app: a handful of precise controls tied to the components the person is polishing, live on every screen, and a Copy button that turns what changed into a message the agent applies to the source.

```text
code ──pick 6–8 craft controls──▶ .ui-tweaks/config.json
dev server ──preview.mjs──▶ preview address = the app + the Tweaks panel   (no change to the app)
designer nudges ──Copy──▶ "Apply these UI tweaks…" ──paste──▶ agent edits the source ──▶ new starting point, keep going
```

**Craft, not decisions.** Controls refine the design that exists: spacing, type details, corners, contrast, depth, icon size, timing. Accent colour, font family, the type scale or overall density are design decisions; offer them only when the person asks for them by name. **Local and named.** Each control belongs to a component or element ("Card padding", "Task row padding", "Heading tracking"), not to an app-wide multiplier. **Fine and anchored.** Narrow ranges around the code's value, small steps, tick marks on the app's own scale. **No code changes to tweak.** The panel overrides values in the browser; the source changes once, when the person pastes the result back. **CSS only.** Values set in JavaScript (Motion springs, chart colours passed as props, canvas) are out of scope; say so in one line when the app has them.

Works with any web app that runs in a browser; optimised for React + Tailwind (+ shadcn).

## Set up

1. **Learn the app.** Find the dev server command and port, and the styling system: Tailwind v4 `@theme`, Tailwind v3 config, shadcn variables, CSS variables, CSS modules, plain CSS, CSS-in-JS. Read the global stylesheet and the theme. If `DESIGN.md` exists (from design-catalog), use its token names and scale; otherwise the app's own token files. Start the dev server if it is not running.

2. **Find what is being polished.** The screen or component the person named. If they named nothing, the main screen and its most visible pieces: the card, the list row, the primary button, the headings, the body text.

3. **Pick the controls**: 6–8, at most 12, grouped by Space, Type, Shape, Contrast (and Motion for CSS transitions). Read each starting value from the code, target exactly the element it belongs to, and set ranges and ticks from the app's scale. What to pick, how to target it in each styling system, and the precision to use: [references/picking.md](references/picking.md).

4. **Write `.ui-tweaks/config.json`** at the app root. Schema, control types and a full example: [references/config.md](references/config.md). Keep it out of git without touching tracked files by adding `.ui-tweaks/` to `.git/info/exclude`. Then check it (run the scripts from the app root, or add `--app <app root>`):

   ```bash
   node <skill>/scripts/preview.mjs --check
   ```

5. **Start the preview** and leave it running in the background:

   ```bash
   node <skill>/scripts/preview.mjs --target http://localhost:3000
   ```

   It prints the address: `http://localhost:3999`, or the next free port if that one is taken. Every page of the app comes through it with the panel added, and hot reload keeps working. If the app cannot work at another address (a login that redirects to the original one, a host allowlist you should not change), use the fallback, one dev-only script tag: [references/fallback.md](references/fallback.md).

6. **Look at it** if you have a browser tool. Open the address and read the console for `[ui-tweaks]` warnings. In the page, `uiTweaks.check()` lists every control with the number of elements it reaches, any variable the page does not define, the computed value (read from the first matching element) and whether it `matches` the control's value. `uiTweaks.set(id, value)` moves one control (a number, an option's value, or a colour for a shade); call `uiTweaks.reset()` when you are done, so your test values don't stay in the browser. Confirm each control reaches the intended elements (and only them) and starts at what the page computes. A row that says "not on this page" matches nothing on the current screen (fine if it lives on another screen); "not defined here" means a variable has no value, so moving it does nothing. Fix the config and the panel reloads it within two seconds.

7. **Tell the person**, in a few lines: the address the preview printed, what the controls cover and why, anything that reaches further than the screen (an app-wide token), and how to use it:

   > Open http://localhost:3999 (whatever address the preview printed). The Tweaks panel (top right) covers the dashboard's details: card and row padding, heading tracking, stat weight, card corners and shadow, border and secondary-text contrast. Drag a label to scrub, hold Compare to see the original, ⌥T hides the panel. When it feels right, press Copy and paste it here.

## Apply pasted tweaks

The person pastes a message that starts with "Apply these UI tweaks". Every row is `label  old → new  where`; a shade or choice that landed on one of the app's own values names it (`#d1d5dc (border-strong)`, `font-semibold → font-bold`). Full mechanics: [references/applying.md](references/applying.md). In short:

1. Copy each file you are about to touch into `.ui-tweaks/before/`, so you can show only your own edits even where the person has other uncommitted work.
2. Change each value where the row says it lives, in the code's own terms: a Tailwind class becomes the matching scale class (or an arbitrary value when it is between steps), a token keeps its format (oklch stays oklch, rem stays rem), a named shade becomes that token or class. Change only the element the control belonged to: a control targeted at the card changes `Card.tsx`, not every `p-6` in the app.
3. Check that the page now computes the new values before going on. If a theme or token edit does not show up (Tailwind v4 under Turbopack sometimes keeps serving the old `@theme`), restart the dev server and tell the person to reload.
4. Update `.ui-tweaks/config.json` so the applied values become the new starting values, and re-target every control whose selector named a class you changed. The panel picks it up and its change count drops, so the person can keep going.
5. Run the check, plus typecheck and lint when you touched code that has them. Report what changed, file by file, and anything that now reaches further than the element (a token). Never commit; show your edits.

## Done

When the person is done, stop the preview, delete `.ui-tweaks/` and its line in `.git/info/exclude`, and remove the fallback tag and files if you used them. Nothing of ui-tweaks stays in the app.

## Rules

- Never change app code just to make something tweakable. If no CSS variable or selector reaches a value without hitting other elements, leave it out or say what else it touches. The fallback tag is the only exception, and it is temporary.
- Every `value` is the code's current value. When you can measure, make sure the page computes the same thing; if not, you read the wrong place.
- Labels say what and where, in the person's words ("Card padding", "Secondary text"); class and token names go in the hint underneath.
- Do not propose brand-level controls (accent colour, font family, type scale, density). If the person asks for one by name, add it with a `color`, `choice` or `scale` control.
- Stop the servers you started and leave no files behind.
