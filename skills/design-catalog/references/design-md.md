# DESIGN.md: format and example

`DESIGN.md` sits at the app root (next to `package.json`; in a monorepo, at the root of the app package). It is the written layer of the design catalog: what the look is, which tokens exist, which components exist, and the rules for extending them. It is read by people and by coding agents before they touch UI, so it must stay short, concrete and true. The catalog route shows the same things rendered; `DESIGN.md` names them and says where they live.

Rules for the file:

- Under 200 lines. Tables, not prose, for tokens and components.
- Every token and component it lists exists in the code at the path given. Nothing aspirational.
- Values are the token names, not raw colours, except in the token tables themselves.
- Dates in full (`2026-10-30`), never "today" or "last week".
- Update it in the same change that adds or changes a token or component. A stale `DESIGN.md` is worse than none, because agents trust it.

## Sections, in order

1. **Title and one paragraph**: what the app is and what its look is in two or three sentences a designer would recognise (tone, density, colour temperature, radius feel, type). Then the catalog URL path and the date of the last extraction.
2. **Tokens**: one table per group that exists (colour, typography, spacing, radius, shadow, motion). Columns: token, value, use. Say where they are defined (one file path) and how to use them (the class prefix or the variable).
3. **Components**: a table of the shared components. Columns: component, file, variants, sizes, states, notes. Below it, one line on composition conventions (slots, `asChild`, `className` passthrough) if the codebase has them.
4. **Patterns**: short notes on things that are not components but must stay consistent: page layout widths, card padding, form field stacks, empty states, focus ring. Only what exists.
5. **Rules for changes**: the standing rules every agent follows (template below). Adapt wording to the stack; keep the list short.
6. **Decisions**: a table of consolidations made, with the date and the before/after values, so nobody reintroduces a retired value by accident. Add a row when a decision is applied; do not list rejected proposals.
7. **Open**: what was deliberately left alone or still varies (for example a legacy screen not yet migrated), so an agent does not "fix" it unasked.

## Rules template

```markdown
## Rules for changes

- Before building any UI, read this file and open `/design-catalog`. Use an existing component if one fits; extend it with a variant if it almost fits; create a new one only when nothing does, and add it to the catalog page and to this file in the same change.
- Use tokens, never raw values: colours only through the semantic token classes (`bg-surface`, `text-muted`, `border-border`), spacing from the scale, radii and shadows from the tokens. A one-off value needs a comment saying why.
- Buttons are `<Button>` with `variant` and `size`; cards are `<Card>`; inputs are `<Input>`/`<Textarea>`/`<Select>`. Do not write ad-hoc `className` versions of these.
- Interactive elements keep the shared focus ring and disabled style. Do not remove `focus-visible` styles.
- When you change a shared component, check it in `/design-catalog` and on one screen that uses it.
- Do not introduce a second palette family, font, icon set or radius scale. If the design needs a new colour, add it as a token first.
```

## Example

A task manager called Taskflow, after extraction and apply. Values are illustrative.

```markdown
# Taskflow design

Taskflow is a personal task manager: calm, light, dense enough for lists. One indigo accent on a cool grey scale, 6px and 12px corners, Geist for everything, soft single-layer shadows, no dark mode. Status colours (red, amber, green, sky) appear only on badges and notes, never on primary actions.

Catalog: `/design-catalog` (every token and component, rendered from the real code). Last extraction: 2026-10-30 from 6 screens.

## Tokens

Defined in `src/app/globals.css` inside `@theme`. Use them through Tailwind classes: `bg-surface`, `text-text-muted`, `border-border`, `rounded-card`, `shadow-card`.

### Colour

| Token | Value | Use |
|---|---|---|
| `--color-background` | #fafafa | Page background |
| `--color-surface` | #ffffff | Cards, inputs, nav |
| `--color-border` | #e5e7eb | Dividers, card and input borders |
| `--color-border-strong` | #d1d5dc | Input border on hover |
| `--color-text` | #18181b | Headings, primary text |
| `--color-text-secondary` | #4a5565 | Body text in lists |
| `--color-text-muted` | #71717b | Secondary text, labels, dates |
| `--color-text-subtle` | #9f9fa9 | Placeholders, disabled |
| `--color-primary` | #4f46e5 | Primary buttons, active nav, links |
| `--color-primary-strong` | #432dd7 | Primary hover |
| `--color-primary-soft` | #eef2ff | Selected chips, info pills |
| `--color-danger` | #e7000b | Destructive buttons |
| `--color-danger-soft` / `--color-danger-text` | #ffe2e2 / #c10007 | High priority badge |
| `--color-warning-soft` / `--color-warning-text` | #fef3c6 / #bb4d00 | Medium priority badge |
| `--color-success` | #00bc7d | Progress bars |
| `--color-success-soft` / `--color-success-text` | #dcfce7 / #008235 | Low priority badge, done |
| `--color-focus-ring` | #4f46e5 | Focus ring on every interactive element |

### Typography

Geist (`--font-sans`) everywhere; Geist Mono only for task IDs. Sizes: 12, 14, 16, 18, 20, 24, 30px. Weights: 400 body, 500 labels and buttons, 600 headings and card titles, 700 page titles only.

| Role | Size / weight | Use |
|---|---|---|
| Page title | 30px / 700 | One per page, `<h1>` |
| Section title | 18px / 600 | `<h2>` inside pages |
| Card title | 16px / 600 | `<h3>` in cards |
| Body | 14px / 400 | Lists, forms, descriptions |
| Caption | 12px / 500 | Badges, dates, helper text |

### Spacing, radius, shadow

Spacing on Tailwind's scale; inside cards 24px, between form fields 16px, inside list rows 12px vertical. Radii: `--radius-control` 6px (buttons, inputs, badges), `--radius-card` 12px (cards, dialogs), full for pills and avatars. Shadow: `--shadow-card` `0 1px 3px rgb(0 0 0 / .1), 0 1px 2px -1px rgb(0 0 0 / .1)` on cards only.

## Components

| Component | File | Variants | Sizes | States | Notes |
|---|---|---|---|---|---|
| Button | `src/components/ui/button.tsx` | primary, secondary, ghost, danger | sm, md | hover, focus, disabled, loading | cva; `asChild` for links |
| Input, Textarea, Select | `src/components/ui/input.tsx` … | – | md | focus, invalid, disabled | 36px tall, 6px radius |
| Card | `src/components/ui/card.tsx` | default, danger (red border) | – | – | 12px radius, border + shadow-card, 24px padding; `CardHeader`, `CardTitle`, `CardContent` |
| Badge | `src/components/ui/badge.tsx` | neutral, danger, warning, success, info | – | – | Pill, 12px/500, 2px 8px |
| Switch | `src/components/ui/switch.tsx` | – | – | on, off, disabled, focus | 44×24, full radius |
| Nav | `src/components/Nav.tsx` | – | – | active | Uses `primary` for the active link |

Composition: components accept `className` and merge it with `cn()`. Layout pages wrap content in `<main className="mx-auto max-w-5xl px-6 py-8">`.

## Patterns

- Page: `bg-background`, `max-w-5xl` centred, 32px vertical padding, `<h1>` then content.
- Form field: `<label>` 14px/500 `text-text`, control below with 6px gap, helper or error 12px below.
- Empty state: centred `text-text-muted` 14px with one secondary button.
- Focus: `focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2` on every interactive element.

## Rules for changes

(see template)

## Decisions

| Date | Decision | Before | After |
|---|---|---|---|
| 2026-10-30 | One grey scale | zinc, gray, slate, neutral mixed | tokens above, zinc values |
| 2026-10-30 | One primary button | `Button` default, `PrimaryButton`, inline indigo buttons | `Button variant="primary"` |
| 2026-10-30 | One card | `Card`, `ProjectCard`, inline bordered divs | `Card` with `CardHeader`/`CardContent` |
| 2026-10-30 | Badge shape | three pill styles | one pill, colour variants |
| 2026-10-30 | Radii | 6, 8, 10, 12, 16px | 6px controls, 12px cards |
| 2026-10-30 | Type sizes | 11, 13, 15, 28px off scale | 12, 14, 30px |

## Open

- `/login` still uses its own layout width (narrow card); intentional.
- Dark mode: none. Do not add `dark:` variants until a theme is designed.
```
