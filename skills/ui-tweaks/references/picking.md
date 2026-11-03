# Picking the controls

ui-tweaks is for craft: refining the design that already exists, by eye, in small steps. Pick what a designer polishing this screen would reach for, tie each control to the element it shapes, and make it precise.

## What counts as craft

| Group | Controls (examples) | Type |
|---|---|---|
| Space | Card padding, Row padding, Gap between items, Section spacing, Button padding | number (px) |
| Type | Body line height, Heading tracking, Heading or stat weight, Meta text size, Paragraph width | number (unitless, em, px, ch), choice for weights |
| Shape | Card or badge corners, Card shadow, List outline, Icon size, Icon stroke | number (px), choice for shadows and outlines |
| Contrast | Borders, Dividers, Secondary text, Placeholder, Hover background | shade |
| Motion | Hover speed, Panel transition speed | number (ms), only for CSS transitions |

Six to eight controls; twelve is the ceiling. Every control should visibly change the screen the person is looking at.

**Not craft, so not offered:** accent or brand colour, font family, the type scale, overall density, light or dark theme, layout and content. Those are design decisions. If the person asks for one by name ("let me try brand colours"), add it: `color` with the app's palette as swatches, `choice` for fonts that are already loaded, `scale` for a family of tokens. Do not suggest them yourself.

## Tie each control to an element

Start from what the person is polishing: the screen or component they named, or the main screen's most visible pieces. For each element, read the classes or styles that set its values, then:

- **Label** the property and where: "Stat card padding", "Row padding, top + bottom", "Space above Today". Name what you change, not its effect ("Row padding", not "Row height", or "16px → 12px" reads as a 12px row).
- **Hint**: the class or token and its reach (`stat cards · p-6`, `border · app-wide`), nothing else. It also appears in the copied message, so keep commentary for your message to the person. Under about 28 characters (22 on shade rows), or it is cut; `--check` warns.
- **Target** exactly that element. Prefer, in order:
  1. A selector anchored on classes that will not change when a value is applied: structure and layout (`.mt-8.grid > *` for the stat cards, `.mt-8.grid + section > .bg-white > div` for the task rows, `.mt-8.grid + section`), component classes, `[class*="Card_root"]` for CSS modules. Avoid anchoring on the class that carries a value in the config (`.p-6`, `.rounded-xl`, `.shadow-sm`): it changes when that value is applied, and every control using it stops matching. When such a class is the only handle (a Tailwind v3 colour class), use it and re-target after applying.
  2. A token declared in the app's own CSS and used only by that kind of element (`--radius-card`).
  3. A token declared in the app's own CSS that is shared (`--color-border`). Say in the hint and your message what else follows it ("app-wide").

  Tailwind's default tokens (`--tracking-tight`, `--radius-xl` when the app does not redeclare them) work live, but applying would mean adding a token to the app, so target the element instead.
- **One kind, different values.** A control has one starting value. When elements of the same kind differ (stat cards with `shadow-sm`, the list card with its own shadow), split them into separate controls or target the most visible one and say so in the label ("Stat card shadow").
- **Something missing.** A choice may offer what the element lacks when its siblings have it (a border on a list whose cards have one). The current state is an option ("None") with `"code": ""`, meaning nothing in the source; the copied message then reads `(add border border-border)` or `(remove border border-border)`.
- **Name options for how they look** (None, Faint, Soft, Raised), not "Current": after applying, the current one changes.
- **Unused tokens.** A declared token that nothing uses (`--radius-card` with no `rounded-card` anywhere) does nothing when overridden, so do not target it. In Tailwind v4 it still creates its utility, though: when a choice option has the same value (`--shadow-card` equals `shadow-sm`), give the token's class as that option's `code` (`shadow-card`), so applying lands on the design system's name, unless a sibling already uses the default class for the same look (the stat cards are `shadow-sm`): then consistency wins, and the token is a note for your message. Mention the unused token in your message if it looks like what the design meant.
- **Check the reach** with a browser: `uiTweaks.check()` in the page gives each control's matched elements and computed starting value. The computed value comes from the first match, so a selector that also matches an element without the value (the first row, which has no divider) reads wrong; narrow it (`div + div`). If nothing isolates the element without a code change, offer the nearest honest scope (all cards) and say so.

## Precision

Ranges hug the code's value, steps are small, and ticks mark the app's own scale so the slider settles where a token or class exists.

| Value | Range | Step | Ticks (`snaps`) |
|---|---|---|---|
| Padding, gap, margin (px) | about ⅔× to 1⅓× | 1 | the spacing scale: 8, 12, 16, 20, 24, 32… |
| Corner radius (px) | about ½× to 1⅔× | 1 | the radius tokens: 4, 6, 8, 12, 16 |
| Line height (unitless) | ±0.3 | 0.01 | 1.25, 1.375, 1.5, 1.625 |
| Letter-spacing (em) | −0.05 to +0.02 for headings | 0.005 | tighter −0.05, tight −0.025, normal 0 |
| Font size (px) | ±3 | 1 | the text scale |
| Weight | a choice: the app's weights in use | | |
| Icon size (px) | ±6 | 1 | 14, 16, 18, 20, 24 |
| Duration (ms) | about ½× to 2× | 10 | 100, 150, 200, 300 |

Without `min`, `max` and `step`, a number control defaults to about ±50% around its value, with a step chosen by unit (1px, 0.005em, 0.01 unitless, 10ms).

**Contrast is a shade, not a colour.** For borders, dividers, secondary text, placeholders and hover tints, use a `shade` control: a lighter ↔ darker slider that keeps the hue, with the app's neighbouring shades as `steps` (for a `gray-200` border: `gray-100`, `gray-200`, `gray-300`, `gray-400`, or the app's own tokens such as `border` and `border-strong`). Give each step its token or class name as `code`; when the slider lands on one, the copied message names it and the agent can use the token instead of a raw value.

**Depth is a choice.** Offer the app's own shadow steps (`None`, `Faint` = `shadow-xs`, `Soft` = `shadow-sm`, `Raised` = `shadow-md`) with the `code` of each, named for how they feel.

## Reaching the value, per styling system

### Tailwind v4

Theme tokens live in `@theme`, and utilities read them as variables, so a `var` target moves every class that uses the token.

- Starting values: Tailwind's defaults are in `node_modules/tailwindcss/theme.css` (shadows, radii, tracking, the palette in oklch). v4 only emits the theme variables a class uses, so reading an unused one from the page (`--shadow-sm`, `--color-zinc-600`) returns nothing. A computed `box-shadow` also lists four transparent ring layers first; ignore them when comparing.
- Radius: `rounded-xl` reads `--radius-xl`, which every `rounded-xl` in the app follows (buttons and dialogs too, not just cards). Target the element's `border-radius` unless the app declares a token for that kind of element.
- Tracking and leading: `tracking-tight` reads `--tracking-tight`; `leading-6` is `calc(var(--spacing) * 6)`. Target the element's `letter-spacing` or `line-height`.
- Spacing utilities (`p-6`, `gap-4`) are `calc(var(--spacing) * n)`. Never target `--spacing` for craft: it also resizes widths, heights and icons. Target the element's `padding`, `padding-block`, `gap`.
- Colours: `border-border` reads `--color-border`; a hard-coded `border-gray-200` reads `--color-gray-200`, which every gray-200 in the app follows, so prefer the element's selector with `border-color` when the shade is shared with unrelated things.
- Shadows: `shadow-*` utilities carry their values inline (not through `--shadow-*`), so target the element's `box-shadow`: `{ "selector": ".mt-8.grid > *", "property": "box-shadow" }`. Targeting the class `.shadow-sm` reaches every element with it across the app.
- Transitions: `transition-colors` uses `--default-transition-duration` (150ms) unless the element has `duration-*`.
- `@theme inline` copies values into the utilities, so overriding the token does nothing; target the variable it points at (shadcn) or the element.

### shadcn/ui

Colours are variables on `:root` with a dark set on `.dark` (`--border`, `--muted-foreground`, `--input`, `--ring`), often in oklch. A shade control on `--border` or `--muted-foreground` is the natural contrast control. It applies to both themes because the override beats both; for one theme only, use `"selector": ":root:not(.dark)"` or `".dark"`. Corners: `--radius` is the base the others derive from, so a control on it moves every radius; for one component, target its selector.

### Tailwind v3

Utilities are compiled to literal values, so targets are the element's selector or, when nothing else reaches it, its classes:

```json
{ "selector": ".stats > div", "property": "padding" }
{ "class": "border-gray-200", "property": "border-color" }
{ "selector": ".stats > div", "property": "padding", "media": "(min-width: 768px)" }
```

### CSS variables, plain CSS, CSS modules

Variables: target them when they belong to the element. Hard-coded values: target the selector that sets them (`.card`, `.list-row`). CSS modules hash class names (`Card_root__a1b2c`); match the stable part with `[class*="Card_root"]`.

### CSS-in-JS (styled-components, Emotion, vanilla-extract)

Values are JavaScript and class names are generated. If the theme also emits CSS variables, target those; otherwise most values cannot be reached without code changes, so say so and offer what is plain CSS.

## Leave out

- Values set in JavaScript: Motion or Framer Motion props, react-spring configs, chart colours passed as props, canvas and WebGL.
- Anything not visible on the screens the person is polishing.
- Controls that would move other, unrelated elements without saying so.
