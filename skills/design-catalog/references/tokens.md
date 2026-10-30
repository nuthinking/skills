# Implementing tokens in the app's own styling system

Tokens are real only when the app's styles read them. Write them where this app already keeps its theme, in the syntax it already uses, and never alongside a second system. Then point the drifted values at them.

## Decide the shape first

From the approved decisions you have, per group: the surviving value, its semantic name, and the list of values it replaces. Before writing anything, settle three things with the user if the measurements did not:

- **Primary and its hover.** Static snapshots do not see hover. If the app uses a darker shade on hover (the scan shows `hover:bg-indigo-700` next to `bg-indigo-600`), keep that pair as `primary` and `primary-hover` (or `primary-strong`).
- **Which radius is "control" and which is "card".** Buttons, inputs and badges share one; cards, dialogs and panels share the other.
- **Whether to keep the raw palette available.** Yes, almost always: Tailwind's palette stays for one-offs and illustrations. The rule in `DESIGN.md` is that UI chrome uses semantic tokens; the palette is not deleted.

## Tailwind v4 (CSS-first)

The theme lives in the main CSS file inside `@theme`. Add semantic tokens there, next to any that exist. Tailwind v4 generates utilities from the variable name: `--color-text-muted` gives `text-text-muted`, `bg-text-muted`; `--radius-card` gives `rounded-card`; `--shadow-card` gives `shadow-card`; `--font-sans` is already the default.

```css
@import "tailwindcss";

@theme {
  /* colour: semantic names, values measured from the app */
  --color-background: #fafafa;
  --color-surface: #ffffff;
  --color-border: #e5e7eb;
  --color-border-strong: #d1d5dc;
  --color-text: #18181b;
  --color-text-secondary: #4a5565;
  --color-text-muted: #71717b;
  --color-text-subtle: #9f9fa9;
  --color-primary: #4f46e5;
  --color-primary-hover: #4338ca;
  --color-primary-soft: #eef2ff;
  --color-danger: #e7000b;
  --color-danger-soft: #ffe2e2;
  --color-danger-text: #c10007;
  --color-success: #00bc7d;
  --color-success-soft: #dcfce7;
  --color-success-text: #008235;
  --color-warning-soft: #fef3c6;
  --color-warning-text: #bb4d00;
  --color-focus-ring: #4f46e5;

  --radius-control: 0.375rem;   /* 6px: buttons, inputs, badges */
  --radius-card: 0.75rem;       /* 12px: cards, dialogs */

  --shadow-card: 0 1px 3px rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
}
```

Keep the values as the app had them (hex or oklch, whatever the file already uses). If the app already defines `--color-brand`, keep that name and alias rather than renaming: `--color-primary: var(--color-brand);` is fine in v4 when `--color-brand` is defined in the same `@theme` block; otherwise just reuse `brand` as the token name throughout.

Dark mode exists only if the app had it. Then the tokens are declared once in `@theme` with `var(--x)` indirections and the light/dark values set on `:root` and `.dark` (or the media query), exactly as the app already does it. Do not add a dark theme the app did not have.

## Tailwind v3 (config file)

The theme lives in `tailwind.config.{js,ts}` under `theme.extend`, usually pointing at CSS variables declared in the global CSS on `:root`. Follow whichever of the two the app already does:

```ts
// tailwind.config.ts
theme: {
  extend: {
    colors: {
      background: "rgb(var(--background) / <alpha-value>)",
      surface: "rgb(var(--surface) / <alpha-value>)",
      // ... or plain hex values if the app does not use variables
      primary: { DEFAULT: "#4f46e5", hover: "#4338ca", soft: "#eef2ff" },
    },
    borderRadius: { control: "0.375rem", card: "0.75rem" },
    boxShadow: { card: "0 1px 3px rgb(0 0 0 / .1), 0 1px 2px -1px rgb(0 0 0 / .1)" },
  },
},
```

Nested keys give `bg-primary`, `bg-primary-hover`, `bg-primary-soft`. Do not migrate a v3 project to v4 as part of this work.

## shadcn/ui present

shadcn already defines the semantic layer (`--background`, `--foreground`, `--card`, `--muted`, `--muted-foreground`, `--border`, `--input`, `--primary`, `--destructive`, `--ring`, `--radius`). Use those names. The drift in a shadcn app is almost always classes that bypass them (`text-gray-500` instead of `text-muted-foreground`, `bg-white` instead of `bg-card`, `rounded-lg` instead of `rounded-md` derived from `--radius`). Map strays onto the existing tokens; add new tokens only for roles shadcn lacks (`success`, `warning`, `info` tints are the usual additions), in the same file and format shadcn's `globals.css` uses, including the dark block if the app has one.

## CSS modules, plain CSS, Sass

Declare custom properties on `:root` in the global stylesheet (or the Sass variables file if that is how the app does it; prefer custom properties, they work at runtime and the catalog page can read them). Replace literal values in module files with `var(--text-muted)`. For Sass, `$text-muted: var(--text-muted);` keeps existing `$` usage working.

## styled-components, Emotion, Stitches, vanilla-extract

Put the tokens in the theme object the app already passes to its provider (`theme.colors.textMuted`), and additionally declare them as custom properties in a global style so the catalog page and any plain CSS can read them. Replace literals with `${({ theme }) => theme.colors.textMuted}` or the library's equivalent. vanilla-extract: `createGlobalTheme` with the same names.

## Pointing the app at the tokens

Replace the retired values by their semantic class or variable. The scan's `tailwind.by_category.color` and `css.colors` list every occurrence with file and line, so the replacements are mechanical. Build the replacement table from the approved decisions:

| Retired | Replacement | Why |
|---|---|---|
| `text-gray-500`, `text-zinc-500`, `text-slate-500`, `text-neutral-500`, inline `#6b7280` | `text-text-muted` | G1, C2 |
| `bg-gray-50`, `bg-zinc-50`, `bg-[#fafafa]` | `bg-background` | G1, C15 |
| `border-gray-200`, `border-zinc-200`, `border-[#e5e7eb]` | `border-border` | G1, C3 |
| `bg-indigo-600`, `bg-indigo-500`, `bg-[#4f46e5]` | `bg-primary` | G2 |
| `hover:bg-indigo-700`, `hover:bg-[#4338ca]` | `hover:bg-primary-hover` | G2 |
| `rounded-lg`, `rounded-[10px]` on controls | `rounded-control` | G6 |

Apply with careful, anchored regex replacements, one table row at a time, over the files the scan listed, never a blind `sed` across the repo: `text-gray-500` must not match `text-gray-500/50` unless the alpha variant is in the table too, and `border-gray-200` must not touch `border-b-gray-200`. Prefer word boundaries and explicit variant prefixes (`(^|[\s"'`{:])text-gray-500(?=[\s"'`}/]|$)`). Check `cva()` and `clsx()` argument strings too: they are strings like any other.

Names that collide with Tailwind's own: `text-text` is unfortunate but correct in v4 (`--color-text` gives `text-text`). If the user dislikes it, name the token `ink` or `foreground` instead; decide this before the replacements, not after.

After each table row: typecheck, then re-snapshot the affected screens and run `compare.py`, as described in [apply.md](apply.md). A replacement that changes the layout box of anything is wrong (a different padding sneaked in) and is reverted before moving on.

## Things not to do

- Do not introduce a token system in a second place (a `tokens.json`, a `theme.ts` next to an existing `@theme`). One source.
- Do not rename existing tokens the app already uses correctly.
- Do not add tokens for values no screen uses "for completeness"; a scale with unused steps invites drift back.
- Do not convert the palette to a different colour space or round values "to make them clean"; the measured value is the design.
