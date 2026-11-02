# The catalog page

`/design-catalog` is a page inside the app that renders every token and every shared component from the real code. It is the visible half of the design catalog: the place a person looks to see what the system is, the page the agent screenshots to check a component after changing it, and the thing that proves `DESIGN.md` is true. No Storybook, no second build, no new dependency. It ships with the app, marked `noindex`, because a deployed URL is what makes it shareable with a designer or a friend; gating it is one line if the owner prefers.

**It renders outside the product shell.** No app navigation, no footer, no sidebar: a person landing on it must see at once that this is an internal reference, not a page of the product. The page carries its own thin header ("Design catalog · internal reference, not a product page" and a link back to the app) and nothing else around it. Only the root document (fonts, global CSS, providers the components need) is shared.

## Layout and navigation

A real app's catalog is several screens tall (a dozen colour tokens, five type roles, radii and shadows, ten to twenty-five components with their variants and states), so the page needs a way to jump, and nothing more:

- **A sticky section list on the left**: one link per section (Colours, Typography, Radius and shadow, then one per component), anchors into the page, the current section highlighted as you scroll (an `IntersectionObserver` on the section headings, ten lines). On narrow viewports it collapses to a list at the top.
- **A thin header above the content**: the app's name, "Design catalog · internal reference, not a product page", a link back to the app, the date of the last extraction. Nothing else around it: no app nav, no footer (see *Where it goes*).
- **No controls, no knobs, no per-component isolation.** This is not Storybook. Variants, sizes and reachable states are rendered as rows through real props, which is what a person needs to see what exists and what the agent screenshots after a change. The only interactive element worth having is a light/dark toggle, and only when the app already has dark mode.
- **One "Used on" line per component** linking to a screen where it appears (the scan's `components[].used_in` mapped to routes), so "where does this show up" is one click.

## What it shows, in order

1. **Header**: app name, "Design catalog", the date of the last extraction, a link to `DESIGN.md` in the repo.
2. **Colours**: one swatch per semantic token, grouped (neutrals, primary, status), each with the token name and its current value read at runtime from the CSS variable. Reading at runtime means the page cannot go stale when a value changes.
3. **Typography**: the roles from `DESIGN.md` (page title, section title, card title, body, caption) rendered in the real font with size and weight printed next to them; the families in use.
4. **Spacing, radius, shadow**: the radius tokens as squares, the shadows as cards, the spacing scale as bars. Small; one row each.
5. **Components**: one section per shared component, in the order of `DESIGN.md`'s table. Every variant, every size, and the states that can be rendered through props (disabled, loading, invalid, checked, open), each row labelled. The file path, the "Used on" links, and a one-line note when the component is being retired or extended by an open decision ("retiring: migrates to Button, decision G8"). Each section uses the real component import and realistic content ("Send invoice to Acme", not "Lorem ipsum" or "Button"). Interactive states that need a user (hover, focus) are not faked: the page says "hover and focus: try it", and the agent checks them by hand in the browser.
6. **Patterns**: a form field stack, a card with header and content, an empty state, if `DESIGN.md` lists them.

Nothing on the page is a copy of a component's styling. If a component cannot be rendered in isolation (needs a provider, a router, data), wrap the page in the same providers the app's layout uses, or pass minimal fixture data. If it still cannot be rendered, list it with a link to the screen where it appears rather than re-implementing its look.

## Where it goes

Place the page where the app places pages, and the catalog component next to the app's shared components so it can import them with the app's own aliases. Then take it out of the shell:

| Framework | Outside the shell |
|---|---|
| Next.js App Router | If the root layout holds the nav and footer, move those into a route-group layout, `app/(app)/layout.tsx`, and move the product pages into `app/(app)/`; the root layout keeps only `<html>`, `<body>`, fonts, global CSS and providers. `app/design-catalog/` sits outside the group, so it gets the document but not the shell. URLs do not change. If the app already has such a group, just place the catalog outside it. |
| Next.js Pages Router | In `_app.tsx`, skip the shell when `router.pathname === "/design-catalog"`, or adopt the per-page `getLayout` pattern and give the catalog page a bare layout. |
| Vite + React Router / Remix / TanStack | Register the catalog route as a sibling of the shell route, not a child of it (the shell is the layout route whose children are the product pages). |
| Astro / SvelteKit / Nuxt | Use a bare layout for the catalog page (Astro: a second layout component; SvelteKit: a route group `(catalog)` with its own `+layout.svelte`; Nuxt: `definePageMeta({ layout: "bare" })`). |

Moving pages into a route group is the one structural change this skill makes to an app; mention it in the report and keep it to the move, nothing else.

| Framework | Page | Component |
|---|---|---|
| Next.js App Router | `app/design-catalog/page.tsx` (under `src/` if the app uses it; under the locale segment on a localised app) with `export const metadata = { robots: { index: false, follow: false } }` | `components/design-catalog/DesignCatalog.tsx` |
| Next.js Pages Router | `pages/design-catalog.tsx` with `<Head><meta name="robots" content="noindex" /></Head>` | same |
| Vite + React Router | a route `{ path: "/design-catalog", element: <DesignCatalog /> }` in the router config; add the meta tag in the component with the app's head helper or `document.title` effect | `src/components/design-catalog/DesignCatalog.tsx` |
| Remix / React Router framework | `app/routes/design-catalog.tsx` with a `meta` export containing the robots tag | `app/components/design-catalog/` |
| Astro | `src/pages/design-catalog.astro` rendering the React component with `client:load` | `src/components/design-catalog/` |
| TanStack Start | `app/routes/design-catalog.tsx` via `createFileRoute` | `app/components/design-catalog/` |
| Vue / Nuxt / SvelteKit | the framework's page file at `/design-catalog`, with the catalog written as a component in that framework | the app's components folder |

Keep the shell (section list, header, `Section`, `Swatch`, `TypeSample`) in one file and the component sections in another under the catalog folder once the page grows past ~300 lines; keep the route file itself tiny. Adding a component later means adding one section and one entry to the section list.

## Reading tokens at runtime

Colour swatches read the variable so the page never lies:

```tsx
function Swatch({ token }: { token: string }) {
  const [value, setValue] = useState("");
  useEffect(() => {
    setValue(getComputedStyle(document.documentElement).getPropertyValue(token).trim());
  }, [token]);
  return (
    <div className="flex items-center gap-3">
      <span className="h-10 w-14 rounded-control border border-border" style={{ background: `var(${token})` }} />
      <div className="text-sm">
        <div className="font-medium text-text">{token.replace(/^--color-/, "")}</div>
        <div className="font-mono text-xs text-text-muted">{value}</div>
      </div>
    </div>
  );
}
```

The token list itself is a plain array in the catalog folder (`tokens.ts`: `[{ token: "--color-text", group: "neutral", use: "Headings, primary text" }, …]`), the same list `DESIGN.md` prints. When adding a token, both get a line; the rule in `AGENTS.md` says so.

For Tailwind v3 projects whose tokens are only in `tailwind.config`, import the resolved config (`resolveConfig` from `tailwindcss/resolveConfig`) or keep a small mirror array; say in `DESIGN.md` which one is the source.

## Rendering states

Props first: `<Button disabled>`, `<Button loading>`, `<Input aria-invalid>`, `<Switch checked>`. For shadcn-style components with `data-state`, render the open state by setting the prop that controls it (`<Dialog open>`), inside a container with `position: relative` so a portal does not cover the page, or show the trigger only and note it. Do not add catalog-only props to components to force a look; if a state cannot be reached from props, it is a hover or focus state and gets checked by hand.

## Style of the page itself

Use the app's own tokens and components for the chrome of the page (headings in the app's heading styles, sections separated by `border-border`), so the page also demonstrates them. Keep it calm: a left-aligned single column, section headings, generous spacing. No tabs, no search, no theme switcher unless the app has dark mode, in which case the page follows the app's theme like any other page.

## After creating it

- Open it in the browser and screenshot it; fix anything that renders wrong before reporting.
- Add the route to `DESIGN.md` ("Catalog: /design-catalog") and to the `AGENTS.md` section.
- Mention it in the completion report with the exact URL on the dev server.
- Tell the user how to hide it in production if they want: a `notFound()` call behind an environment check in the page, or excluding the route in the framework's config.
