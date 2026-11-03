# Styles, backgrounds and settings

How a rendered video looks is a **style** (how the recording is staged), a **background** (what sits behind the device), and **settings** (cards, captions, cursor, output). They are independent: the same recording renders in any combination, so restyling is a render, not a re-record. The one look key that is not a render setting is the app **theme**, because the app is recorded in it. Judge looks in the studio (`product-demo studio <id>`), which previews any combination from the recording without rendering.

## Styles

| Style | What it is |
|---|---|
| `neutral` | The page itself. No device, no background. For reference documentation and READMEs. |
| `device` | The page inside a device on a background: a browser window, a laptop or a phone (`device`). For help pages and product pages. |
| `perspective` | The device style with a 3D tilt that follows the pointer, and a background that moves at a different rate (parallax). For launches and social posts. |

## App theme

`theme` is `light` (default) or `dark`: the colour scheme the recorder gives the browser (`prefers-color-scheme`), so an app that follows the system scheme is recorded in it. An app with its own theme switch needs to honour that media query in demo mode, or the demo is recorded light. The device chrome follows the app theme; nothing else does. Changing `theme` re-records.

## Backgrounds

`background` applies to the `device` and `perspective` styles and is one of:

- A built-in wallpaper name. Fifteen square abstract images ship with the package, soft colour fields that stay calm behind a product, from bright to deep, so one suits a light or a dark app: `clay`, `dusk` (default), `dusk-2`, `ember`, `harbour`, `heather`, `lagoon`, `mesh`, `mist`, `moss`, `plum`, `sage`, `sand`, `steel`, `tide`. See them in the studio.
- A CSS colour: `"#101418"`, `"rgb(16,20,24)"`. Quote it in YAML.
- An image path under `product/demos/`, for example `assets/brand.jpg`. Square images crop to either orientation from the centre; the video shows the middle band, so keep the interest off the corners and the centre calm.

The background does not follow the app theme. Intro and outro text picks light or dark from the brightness of the background it sits on.

## Settings

Defaults go in `config.json` under `defaults`; any demo file overrides any of them. A demo without overrides renders with the defaults; the defaults themselves default to `neutral`, `browser`, `light`, `dusk`, no cards, captions and cursor on, 1280×720 at scale 2, 30 fps, MP4.

| Key | Values | Meaning |
|---|---|---|
| `style` | `neutral`, `device`, `perspective` | See above. |
| `device` | `browser`, `laptop`, `phone` | The device for the staged styles. A phone expects a phone viewport in the demo. |
| `theme` | `light`, `dark` | The app's colour scheme at recording time. See above. |
| `background` | a wallpaper name, a colour, or an image path | Behind the device. See above. |
| `intro`, `outro` | `true`, `false`, or `{ title, subtitle, durationMs, fade }` | Cards before and after the demo, in any style. Templates: `{{title}}`, `{{description}}`, `{{product}}`. Intro defaults to the title over the product name; outro to the product name over the description; 1.8 s each. `fade` (default `true`) animates the card: the intro opens on its backdrop, its text fades in, and the whole card fades out into the first frame; the outro fades in over the last frame and stays. `fade: false` cuts. |
| `captions` | `true`, `false`, or `{ position, size, radius, color, background, font }` | Captions from the `say` lines. Defaults: below the device in the staged styles, over the bottom of the page in `neutral`, 18px, dark text on a translucent light band for a light app and the reverse for a dark one. Any key given overrides that. |
| `cursor` | `true`, `false`, or `{ style: arrow \| dot, size }` | The drawn cursor. |
| `highlight` | `true`, `false` | The ring around clicked elements. |
| `address` | `true`, `false`, or text | The browser bar's text in the browser frame. `true` (default) shows the recorded path, which is often an internal URL with ids; text such as `app.example.com/tables` shows that instead; `false` leaves the bar empty. |
| `output` | `{ width, height, scale, fps, quality, format, loop }` | Size in CSS pixels and a scale (2 is retina); `quality` is `draft`, `good` or `high`; `format` is `mp4`, `webm` or `gif`; `loop` drops the end pause for clips that repeat. A portrait size (`1080x1920`) with `device: phone` makes a vertical video. |

Zoom is not a setting: it belongs to the step (format.md section 4).

## The studio

`product-demo studio` is the local editor. Its home page lists the demos with a poster, duration and status: not recorded, needs a recording (and why), needs a render, or up to date. Each demo opens on the composition from its recording with a scrubber and play, and controls for every setting above (the cards with their fade), the wallpapers as thumbnails, and each step's label, narration, zoom and settle. Changes show immediately; nothing is rendered. **Save** writes the demo file: look keys that equal the defaults are left out, the rest of the file (comments, order, quoting) stays as written, and `theme` is never touched. **Record** and **Render** queue a run of the CLI: one record at a time, since a record reseeds the app, and up to two renders at once; a record is followed by its render, so one click gives a video; the demo's card shows the state, the latest log line and a folded log, and refreshes when the run ends. The studio needs the same environment as the CLI (the test account variables, `PRODUCT_DEMO_ENV`). The device and background controls appear only for the staged styles. The studio does not write new demos: that is the agent's job with this skill.
