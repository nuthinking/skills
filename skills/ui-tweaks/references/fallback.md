# Fallback: a dev-only script tag

Use this only when the app cannot work at the preview address:

- a login that redirects to a fixed URL (OAuth callbacks registered for `localhost:3000`)
- a host or origin allowlist you should not change
- a page that is not served over HTTP by a dev server (an Electron or Tauri window, a file opened from disk)

It is the one case where ui-tweaks touches the app, and every trace is removed at the end.

## Install

1. Copy the panel and the config into the app's static folder, side by side:

   ```text
   public/ui-tweaks/ui-tweaks.js      ← <skill>/scripts/ui-tweaks.js
   public/ui-tweaks/config.json       ← the config (write it here instead of .ui-tweaks/)
   ```

   The panel loads `config.json` from next to itself. To keep the config elsewhere, add `data-config="/path/to/config.json"` to the tag.

2. Add one tag, development only, marked for removal:

   **Next.js, App Router** (`app/layout.tsx`, inside `<head>`, or inside `<body>` if there is no head element):

   ```tsx
   {/* ui-tweaks: remove when done */}
   {process.env.NODE_ENV === "development" && <script src="/ui-tweaks/ui-tweaks.js" async />}
   ```

   **Next.js, Pages Router**: the same line in `pages/_document.tsx`, inside `<Head>`.

   **Vite, plain HTML, anything with an `index.html`**:

   ```html
   <!-- ui-tweaks: remove when done -->
   <script src="/ui-tweaks/ui-tweaks.js" async></script>
   ```

   **Server-rendered apps** (Rails, Django, Laravel, Phoenix): the main layout template, inside the development-environment conditional the framework provides.

3. Keep the files out of git: add `public/ui-tweaks/` to `.git/info/exclude`. The tag itself shows up in the diff; that is expected, and it goes away at the end.

4. Check it: `node <skill>/scripts/preview.mjs --check --config public/ui-tweaks/config.json`, then open the app at its usual address.

Applying works as usual; the config to update is `public/ui-tweaks/config.json`.

## Remove

When the person is done: delete the tag (find it with `ui-tweaks: remove when done`), delete `public/ui-tweaks/`, and remove the line from `.git/info/exclude`. Then `git status` should show only the changes that were applied on purpose.
