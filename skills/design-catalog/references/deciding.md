# Deciding what the design system is

Measurement gives clusters and counts. Deciding gives a design system: which values are the intended ones, what they are called, and which components exist. This is the step where "preserve the look" and "fix the drift" have to be told apart, and the user is the one who knows which is which. Your job is to make each decision easy to take and impossible to misunderstand.

## Intent versus accident

A vibe-coded app drifts because every generation picked a plausible value with no memory of the last one. So the rule of thumb is: **what is consistent across screens is intent; what varies between screens without a reason is accident.** Concretely:

- Four greys for secondary text on four screens: accident. Keep the most used.
- Two card paddings, one on dense list cards and one on a profile card: possibly intent. Ask.
- A red for delete buttons and a slightly different red for error badges: accident, unless they are visibly different on purpose. The visual page shows them side by side.
- An indigo for buttons and a lighter indigo for links: could be a real two-step scale. Ask, and offer "one primary plus a hover shade" as the default.
- One screen with a different page width or a different heading size: accident if it is the odd one out, intent if it is a different kind of screen (login, landing page). Say which it looks like.

Prefer the value that is most used, then the one defined in an existing token or shared component, then the one on a standard scale. Never prefer a value because it is "nicer"; that is redesign.

## Reusing what exists

If the app already has semantic tokens (shadcn's `--background`, `--primary`, `--muted-foreground`; a `@theme` block; a `tailwind.config` `extend.colors`), the system already exists and the drift is code that bypasses it. Then the decisions are "map these strays onto these existing tokens", not "invent tokens". `analyze.py` marks clusters that match an existing token. Keep the existing names even when they are not what you would have chosen; renaming a token system is churn the user did not ask for.

Likewise for components: if `components/ui/button.tsx` exists with `cva` variants, that is the button. The inline `<button className="bg-indigo-500 ...">` elsewhere migrates to it, and missing looks become variants of it. Only when no shared component exists do you create one, and then you build it from the most-used measured variant so existing screens barely move.

## Relaying decisions

The user reviews decisions one at a time, in plain words, in the conversation. `summary.md` is written for that; `report.html` (with `--html`) adds swatches and rendered variants when words are not enough.

- Lead with the grouped decisions (`G1`…), one line each, exactly as in the summary. Do not paste the details section; offer it ("say G1 details for the six individual merges").
- Translate measurements into things a person sees: "four slightly different greys for secondary text", "buttons come in a small square one and a tall rounded one", not "ΔE 0.018" or selector paths.
- Give your recommendation on each, in one clause, and say when you are unsure ("the 16px radius on project cards might be deliberate; they are the only big cards").
- When the user answers, record it: in `proposals.json` set `approved` to `true` or `false` on the group, and on individual decisions when they answer at that level. Fix the suggested `name` when they give you the app's own word ("call it `ink`, not `text`"). Put anything they said that constrains the apply in `note`.
- An unanswered decision is not approved. Ask again or leave it for a later batch; never apply it silently.
- If they want everything, "all yes" is a valid answer; set `approved: true` on every group, keep the explicit rejections.

Keep the count of questions low. Ten is normal; thirty means the grouping failed and you should fold decisions together before asking (for example all off-scale type sizes are one question).

## Naming tokens

Semantic names describe the job, not the colour: `text`, `text-muted`, `border`, `surface`, `background`, `primary`, `primary-hover`, `primary-soft`, `danger`, `danger-soft`, `success`, `warning`, `info`, `focus-ring`. Use the app's existing vocabulary first (`brand` if they already have `--color-brand`), then shadcn's names if shadcn is present (`foreground`, `muted-foreground`, `card`, `destructive`), then the list above. Avoid names that encode the value (`indigo-600`, `grey-light`): they lie as soon as the value changes.

Spacing stays Tailwind's numeric scale; do not invent `space-md`. Radii: `--radius-control` (buttons, inputs, badges) and `--radius-card` (cards, dialogs), plus `full`, cover almost every app; add a third only when the measured scale really has three steps. Shadows: `--shadow-card` and, if present, `--shadow-popover`. Type: keep Tailwind's size classes; document the roles (page title, section title, body, caption) in `DESIGN.md` rather than inventing classes.

## Components: when two things are one

Merge when the elements mean the same thing to the user and behave the same: every "primary action" button is one component with one variant; every priority badge is one component with colour variants; every container with a border, radius and padding that groups content is a card.

Do not merge when they do different jobs that happen to look similar: a nav link and a button; a stat tile and a card; a tag you can remove and a status badge. Do not merge a one-off that is correct as a one-off (the login card being wider). When a page-specific element looks like a near-miss of a shared component, the fix is usually to use the shared component, not to create a `variant="login"`.

Prefer composition over props when a component would otherwise grow a boolean for every page: `Card` with `CardHeader`/`CardContent` children, not `Card` with `title`, `subtitle`, `action`, `footer`, `compact`, `bordered`, `elevated` props. Keep APIs the app already has (shadcn's shapes) rather than inventing new ones.

## What stays out of scope

Icons, illustrations, copy tone, animation choreography and layout grids are part of a design language, but this skill measures and consolidates what computed styles can show: colour, type, spacing, radius, shadow and the component shapes built from them. Mention anything else you noticed (two icon sets, inconsistent empty states) under "Open" in `DESIGN.md` and move on.
