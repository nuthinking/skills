# The config file

`.ui-tweaks/config.json` at the app root lists the panel's controls. The preview serves it to the panel, the panel re-reads it every 1.5 seconds, and `preview.mjs --check` validates it. Bad controls are reported and skipped; the rest still work.

## Shape

```json
{
  "title": "Taskflow dashboard",
  "groups": [
    { "label": "Space", "controls": [ ... ] },
    { "label": "Type", "controls": [ ... ] },
    { "label": "Shape", "controls": [ ... ] },
    { "label": "Contrast", "controls": [ ... ] }
  ]
}
```

| Field | Meaning |
|---|---|
| `title` | What is being polished, for the panel's accessible label. Optional. |
| `groups` | Sections of the panel, in order. Each has a `label` and `controls`. |
| `palette` | Swatches for `color` controls, which are only used on request. Optional. |

## Controls

Every control has:

| Field | Meaning |
|---|---|
| `id` | Stable, unique. Saved values are keyed by it. Defaults to the label, slugged. |
| `label` | What and where, in the designer's words: "Card padding", "Heading tracking", "Borders". |
| `type` | `number`, `shade` or `choice` for craft; `color` and `scale` when the person asks for brand-level controls. |
| `value` | The code's current value. Changes are measured against it. |
| `targets` | Where the value goes (below). One or more. |
| `source` | The file where the value lives, or a list of files, for the copied message: `src/components/Card.tsx`. |
| `hint` | Optional. The small grey line under the label: the class or token, and its reach when it is wide (`stat cards · p-6`, `border · app-wide`). Defaults to the first target. Keep it under about 28 characters (22 on shade rows); longer hints are cut, and show in full on hover. |

By type:

- **`number`**: `value` is a number (or a string such as `"16px"` or `"150ms"`, from which the unit is taken). `unit` is `px`, `em`, `rem`, `ms`, `%`, or empty for unitless values like line height. `snaps` lists the app's scale values; the slider settles on them and on the starting value, and shows them as ticks. `min`, `max` and `step` default to about ±50% around the value with a step chosen by unit (1px, 0.005em, 0.0625rem, 0.01 unitless, 10ms); set them from the table in [picking.md](picking.md) for tighter control.
- **`shade`**: a lighter ↔ darker slider for a colour, keeping its hue; the track shows the actual colours. `value` is the code's colour (any CSS colour). `steps` lists the app's neighbouring shades, as `{ "value", "code" }` or plain colours; include the current one so it carries its name. Steps become ticks, landing on one gives exactly that colour, and the copied message names it (`#d1d5dc (border-strong)`). Between steps the slider keeps the code colour's hue, so a step from another grey family (zinc next to gray) jumps slightly in hue when landed on; that is expected. `range` (optional) is how far the slider reaches in OKLCH lightness, 0 to 0.5; by default it covers the steps plus a little.
- **`choice`**: `options` is a list of `{ "label", "value", "code" }`. `value` is the CSS that gets written; `code` is what the source would say (`font-bold`, `shadow-md`) and appears in the copied message; `"code": ""` means nothing in the source (no border), so a change to or from it reads as `(add …)` or `(remove …)`. The control's `value` must equal one option's `value`, and two options with the same CSS are flagged (the first one wins). Up to four short options render as a segmented control, more as a pop-up menu. Give every option real CSS, including the current one: after the agent applies a change, a different option becomes the starting point.
- **`color`** (on request): `value` is any CSS colour; a colour well, a hex field and swatches from `palette` or `swatches`. The copied message keeps the original as written. No alpha.
- **`scale`** (on request): a knob that multiplies a family of tokens (all radii, the whole text scale). `value` is the multiplier, usually 1, shown as a percentage; `min` and `max` default to 0.5 and 1.5, `step` to 0.01. Every target needs a `base` (that token's current value); the copied message lists each token's new value.

## Targets

A target says which CSS gets the control's value.

| Field | Meaning |
|---|---|
| `var` | A CSS custom property, set on `:root` (or on `selector` / `class` if given). Everything that reads the variable follows. |
| `property` | A CSS property, set on the elements matching `selector` or `class`. The usual target for one element. |
| `selector` | Any CSS selector, written as you would in a stylesheet. |
| `class` | A single class name, unescaped (`md:p-8`, `bg-[#f4f4f5]`); the panel escapes it. |
| `media` | Optional media query wrapping the rule, for responsive classes: `(min-width: 768px)`. |
| `base` | For `scale` controls: the current value of this target. |

Overrides are written only for controls that differ from their starting value, as `!important` declarations in a stylesheet the panel owns, so they beat the app's own rules (unless the app uses `!important` itself, as in Tailwind's `!` prefix). One control can have several targets, for example an icon size that sets both `width` and `height`.

```json
{ "selector": ".mt-8.grid > *", "property": "padding" }
{ "selector": ".mt-8.grid + section > .bg-white > div", "property": "padding-block" }
{ "selector": ".mt-8.grid + section", "property": "margin-top" }
{ "var": "--color-border" }
{ "var": "--border", "selector": ".dark" }
{ "class": "border-gray-200", "property": "border-color" }
{ "selector": ".stats > div", "property": "padding", "media": "(min-width: 768px)" }
```

Anchor selectors on classes that will not change when a value is applied (layout and structure, component classes), not on the class that carries the value (`.p-6`), which changes the moment the agent applies it.

## A full example

The dashboard of a Next.js + Tailwind v4 app: tokens declared in `@theme` in `globals.css`, stat cards from `Card.tsx` in a grid, the Today list and its rows inline in the page. Selectors hang on the layout (`.mt-8.grid`, `section`), so they still match after the agent applies a change; the two contrast controls are app-wide tokens and say so.

```json
{
  "title": "Taskflow dashboard",
  "groups": [
    {
      "label": "Space",
      "controls": [
        {
          "id": "card-padding", "label": "Stat card padding", "type": "number", "value": 24, "unit": "px",
          "min": 16, "max": 32, "snaps": [16, 20, 24, 28, 32],
          "targets": [{ "selector": ".mt-8.grid > *", "property": "padding" }],
          "hint": "stat cards · p-6", "source": "src/components/Card.tsx"
        },
        {
          "id": "row-padding", "label": "Task row padding", "type": "number", "value": 16, "unit": "px",
          "min": 8, "max": 24, "snaps": [8, 10, 12, 14, 16, 20, 24],
          "targets": [{ "selector": ".mt-8.grid + section > .bg-white > div", "property": "padding-block" }],
          "hint": "Today rows · py-4", "source": "src/app/(app)/page.tsx"
        },
        {
          "id": "today-spacing", "label": "Space above Today", "type": "number", "value": 22, "unit": "px",
          "min": 12, "max": 36, "snaps": [16, 20, 24, 28, 32],
          "targets": [{ "selector": ".mt-8.grid + section", "property": "margin-top" }],
          "hint": "Today · mt-[22px]", "source": "src/app/(app)/page.tsx"
        }
      ]
    },
    {
      "label": "Type",
      "controls": [
        {
          "id": "greeting-tracking", "label": "Greeting tracking", "type": "number", "value": -0.025, "unit": "em",
          "min": -0.05, "max": 0.01, "snaps": [-0.05, -0.025, 0],
          "targets": [{ "selector": "h1.text-3xl", "property": "letter-spacing" }],
          "hint": "h1 · tracking-tight", "source": "src/app/(app)/page.tsx"
        }
      ]
    },
    {
      "label": "Shape",
      "controls": [
        {
          "id": "card-corners", "label": "Card corners", "type": "number", "value": 12, "unit": "px",
          "min": 6, "max": 20, "snaps": [8, 12, 16],
          "targets": [
            { "selector": ".mt-8.grid > *", "property": "border-radius" },
            { "selector": ".mt-8.grid + section > .bg-white", "property": "border-radius" }
          ],
          "hint": "cards · rounded-xl", "source": ["src/components/Card.tsx", "src/app/(app)/page.tsx"]
        },
        {
          "id": "card-shadow", "label": "Stat card shadow", "type": "choice",
          "value": "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
          "options": [
            { "label": "None", "value": "none", "code": "shadow-none" },
            { "label": "Faint", "value": "0 1px 2px 0 rgb(0 0 0 / 0.05)", "code": "shadow-xs" },
            { "label": "Soft", "value": "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)", "code": "shadow-sm" },
            { "label": "Raised", "value": "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)", "code": "shadow-md" }
          ],
          "targets": [{ "selector": ".mt-8.grid > *", "property": "box-shadow" }],
          "hint": "stat cards · shadow-sm", "source": "src/components/Card.tsx"
        }
      ]
    },
    {
      "label": "Contrast",
      "controls": [
        {
          "id": "borders", "label": "Borders and dividers", "type": "shade", "value": "#e5e7eb",
          "steps": [
            { "value": "#f3f4f6", "code": "gray-100" },
            { "value": "#e5e7eb", "code": "border" },
            { "value": "#d1d5dc", "code": "border-strong" }
          ],
          "targets": [{ "var": "--color-border" }],
          "hint": "border · app-wide", "source": "src/app/globals.css"
        },
        {
          "id": "secondary-text", "label": "Secondary text", "type": "shade", "value": "#71717b",
          "steps": [
            { "value": "#9f9fa9", "code": "text-subtle" },
            { "value": "#71717b", "code": "text-muted" },
            { "value": "#4a5565", "code": "text-secondary" }
          ],
          "targets": [{ "var": "--color-text-muted" }],
          "hint": "text-muted · app-wide", "source": "src/app/globals.css"
        }
      ]
    }
  ]
}
```

## What the panel keeps

Changed values are saved in the browser's local storage for the preview address, so reloads and hot reloads keep them. A saved value is dropped when its control's starting value (or a scale target's `base`, or a shade's `steps`) changes in the config, which is how an applied change becomes the new starting point. The panel's position and collapsed state are saved too.
