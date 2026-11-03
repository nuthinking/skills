# Applying pasted tweaks

The person pressed Copy and pasted something like:

```text
Apply these UI tweaks with the ui-tweaks skill (4 changes):

Stat card padding     24px → 20px                                 stat cards · p-6 · src/components/Card.tsx
Space above Today     22px → 24px                                 Today · mt-[22px] · src/app/(app)/page.tsx
Greeting tracking     -0.025em → -0.035em                         h1 · tracking-tight · src/app/(app)/page.tsx
Borders and dividers  #e5e7eb (border) → #d1d5dc (border-strong)  border · app-wide · src/app/globals.css
```

Each row is a label, `old → new`, then the hint (class or token) and the source file. Read `.ui-tweaks/config.json` too: it has the exact targets for every row, which tell you the level the change belongs at.

Before editing, copy each file you are about to touch into `.ui-tweaks/before/` (keeping its path). The person's repo may have other uncommitted work in the same files; `diff -u .ui-tweaks/before/<file> <file>` shows only your edits.

## 1. Change the code, at the level the control targeted

- **A selector target** (one element or kind of element): change that element's classes or styles in the source file, and nothing else. "Stat card padding 24px → 20px" on `.mt-8.grid > *` means `p-6` → `p-5` in `Card.tsx`, not every `p-6` in the app. `padding-block` is `py-*`, `padding-inline` is `px-*`.
- **A `var` target** (a token declared in the app's CSS): change the token where it is declared. Everything that reads it follows; say so in your report ("all borders are now…").
- **Tailwind values**: a value on the scale becomes the scale class (20px → `p-5`, 24px → `mt-6`, 12px corners → `rounded-xl`, −0.05em → `tracking-tighter`); a value between steps becomes an arbitrary value (`p-[22px]`, `tracking-[-0.035em]`) or, for a token, its new value in the token's unit (`--radius-card: 0.875rem`). Pixel values from the panel convert to the file's unit (16px = 1rem unless the app changes the root size). Defaults for comparison are in `node_modules/tailwindcss/theme.css`.
- **Choices with a `code`**: swap the class (`font-semibold` → `font-bold`, `shadow-sm` → `shadow-md`) on the element in the named file. `(add border border-border)` and `(remove border border-border)` mean exactly that: an option with nothing in the source was involved.
- **Shades that landed on a named step** (`#d1d5dc (border-strong)`): use the named token or class, not the raw value. For a token-level control, point the token at it (`--color-border: var(--color-border-strong)`) or, when the person was polishing specific elements, switch those elements' classes (`border-border` → `border-border-strong`). If it is unclear which they meant, ask in one line. Pointing one token at another makes the two identical; tell the person.
- **Shades between steps** (`→ #60606a`): for a token, write the new value in the token's format; a hex from the panel becomes oklch if the file uses oklch (the snippet below converts exactly). For a shade targeted at an element, use an arbitrary class (`border-[#eff1f5]`) and say in your report that it is a colour outside the app's palette, which could become a token if it sticks.
- **On-request controls**: a `color` row changes the token, or every hard-coded use of that colour in that role (with `hover:`, `focus:` and other variants); a `scale` row lists each token's new value on indented lines; a font `choice` changes the `font-family` declaration (ask before removing the old font's loading code).

Change only what the message lists. If a row cannot be applied cleanly (the value is computed in JS, the selector covered more than the intended element), say so instead of guessing.

## 2. Check the page took it

Before moving the starting point, make sure the running app now produces the new values: with a browser, `uiTweaks.reset()` then `uiTweaks.check()` on the preview address. Each applied row's `computed` should be the new value, so it reports `matches: false` (the config still holds the old one) until you move the starting point, and `true` after. (Your browser does not have the person's tweaks; check computed values, not the change count.)

Class edits hot-reload. Theme and token edits sometimes do not: Tailwind v4 under Turbopack can keep serving the old `@theme` values. If a token change does not show in the page, check the served CSS, restart the dev server, and tell the person to reload once. Do not move the starting point until the change shows, or the person's tweak is dropped from the panel while the page still shows the old value, and their change looks undone.

## 3. Move the starting point

Update `.ui-tweaks/config.json` so that what was just applied is now the code's value:

- `number`, `choice`, `shade`, `color`: set `value` to the new value.
- `scale`: set each target's `base` to its new value and leave `value` at `1`.
- **Re-target, don't just rename.** Search the whole config for every class you changed: any control whose selector or `class` used it (not only the control you applied) now matches nothing. Re-anchor it on something stable rather than the new value's class (an arbitrary class like `tracking-[-0.035em]` changes on every apply), then `uiTweaks.check()` to confirm each control still reaches the same elements.
- **Choice options**: the current option's `code` must be what the source now says. An option that described the old one-off value (an arbitrary shadow that no longer exists) goes; replace it with the app's next step if the list needs one.
- **Shade steps**: keep each step's name true. If `--color-border` now points at `border-strong`, the old `#e5e7eb` step is no longer `border`; rename it (`gray-200`).
- `hint` and `source` lines that are no longer true: fix them.

The panel re-reads the config within two seconds. Controls whose starting value changed drop their saved value, so the person's change count goes down and the page looks the same, because the code now produces what the override did. Leave the preview running; the person keeps going from there.

## 4. Report

- `node <skill>/scripts/preview.mjs --check`, plus typecheck and lint if you touched code that has them.
- In a few lines: each row and what changed for it, file by file, anything that now reaches further than the element (a token), any two tokens that became identical, anything you could not apply and why, and whether the person needs to reload. Show your own edits (the diff against `.ui-tweaks/before/`), not the whole `git diff`, which may include their other work. Never commit.

## Exact hex to oklch

```bash
python3 - '#60606a' <<'EOF'
import sys, math
h = sys.argv[1].lstrip('#'); r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
r, g, b = lin(r), lin(g), lin(b)
l = (0.4122214708*r + 0.5363325363*g + 0.0514459929*b) ** (1/3)
m = (0.2119034982*r + 0.6806995451*g + 0.1073969566*b) ** (1/3)
s = (0.0883024619*r + 0.2817188376*g + 0.6299787005*b) ** (1/3)
L = 0.2104542553*l + 0.7936177850*m - 0.0040720468*s
A = 1.9779984951*l - 2.4285922050*m + 0.4505937099*s
B = 0.0259040371*l + 0.7827717662*m - 0.8086757660*s
C = math.hypot(A, B); H = math.degrees(math.atan2(B, A)) % 360
print(f"oklch({L:.3f} {C:.3f} {H:.1f})" if C > 0.0005 else f"oklch({L:.3f} 0 0)")
EOF
```

Match the file's notation (percent lightness, number of decimals) when you write it.
