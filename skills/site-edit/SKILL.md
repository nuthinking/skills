---
name: site-edit
description: Set up "edit the website from the website" on a site with a GitHub repository, usually Next.js on Vercel. Editors with write access sign in with GitHub, drop pins and notes on the live site or a preview, and send them; a GitHub Actions workflow runs Claude Code, which makes the change and opens a pull request; an email arrives with screenshots of where each note pointed, the agent's replies and a Ship link that merges. Use this skill whenever someone wants non-technical people to request or approve changes from the site itself, wants in-page comments, annotations or feedback that an AI agent turns into pull requests, asks to set up Claude Code GitHub Actions for site changes, or mentions site-edit, @nuthinking/site-edit, a preview email or an approve page. Also use it to diagnose that loop when a step fails, and to update the setup when the site changes.
---

# Site edit

Editors leave notes on the page; an agent makes the change; the editor ships it from an email. The developer sets it up once. This skill does that setup with the npm package `@nuthinking/site-edit`, which holds the widget and the server handlers, and the templates it ships for the workflows, the email script and the agent rules.

```text
pins and notes on the page ──▶ GitHub issue ──▶ Claude Code makes the change ──▶ pull request
        ▲                                                                              │
        │                                                                              ▼
   notes on the preview ◀── email: screenshots, replies, Ship ◀── Vercel preview deployment
```

How each piece behaves, and why: [references/how-it-works.md](references/how-it-works.md). Read it before installing, and whenever you explain the loop to the user. The settings only a human can make (GitHub App, secrets, Vercel, Resend): [references/setup.md](references/setup.md).

**What it needs.** A GitHub repository; a React site (the widget is React; Next.js App Router has a ready-made entry, other frameworks take two props); a host that deploys previews per branch and reports them as GitHub deployments (Vercel does); a Resend account for the email; a Claude subscription or API key for the GitHub Action. Without Vercel the editing and approval work, but the email script needs a GitHub deployment with a preview URL to screenshot.

## Choose a mode

| Situation | Mode |
|---|---|
| The site has no site-edit yet | **Install** |
| A step of the loop fails or behaves oddly | **Diagnose** |
| The site changed (locales, copy location, components, package manager) | **Update** |

## Install

1. **Learn the site.** Framework and router; package manager (from lockfiles and `packageManager`, use that one only); where the app lives in the repo (root or a folder); locales, if URLs start with one, and which is the source the others follow; where copy lives; where site components live and whether they carry `data-component`; the check command (types and lint); the deployment host and the project's Vercel name; whether `AGENTS.md` or `CLAUDE.md` exists. Ask the user for the live site's URL and the repository `owner/name` if not evident.

2. **Install the package** with the repo's package manager, in the app's package: `npm install @nuthinking/site-edit` (or `pnpm add`, `yarn add`, `bun add`). If the install fails, stop and say so; nothing below works without it.

3. **Mount the widget** once in the root layout, inside `<body>`, after the page content. Next.js App Router:

   ```tsx
   import { SiteEdit } from "@nuthinking/site-edit/next";
   <SiteEdit pr={process.env.NEXT_PUBLIC_VERCEL_GIT_PULL_REQUEST_ID} branch={process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_REF} locales={["en", "es"]} />
   ```

   `locales` is omitted on a single-language site. Other frameworks: `import { SiteEdit } from "@nuthinking/site-edit"` and pass `pathname` from the router and `onNavigate` for client-side navigation; without them it reads `window.location` and does full navigations. Other hosts: pass the PR number and branch from whatever the host exposes at build time.

   **Language.** The widget's own strings ship in English only; the site's other languages are yours to write. On a localised site, create `site-edit.messages.ts` next to the layout with one `Messages` object per non-English locale (`import type { Messages } from "@nuthinking/site-edit/next"`; `en` from the same entry is the source to translate, every key), and pass them: `<SiteEdit messages={{ es }} />`. The type makes the typecheck fail on a missing key, so there is nothing else to verify. Use the site's own tone and the forms of address it uses for its readers (tú or usted, du or Sie). The widget then follows the page's locale, then the browser's; `uiLocale` forces one.

   **Theme it.** The widget inherits the page's font and text colour and follows its dark mode by itself; only the accent, the radius and the mono font are its own. Find the site's tokens (a Tailwind `@theme` block, CSS variables, a theme file) and alias them in the global stylesheet, e.g. `:root { --se-accent: var(--color-brand); --se-accent-ink: var(--color-brand-dark); --se-radius: var(--radius-card); --se-mono: var(--font-mono); }`. Sites without tokens get the same values through the `theme` prop. Then look at it: open a page in the browser next to one of the site's own buttons, and adjust until the pin and the primary button could be the site's. Never leave the default blue on a site with a brand colour.

4. **Mount the handlers** on one catch-all route. Next.js: copy `node_modules/@nuthinking/site-edit/templates/next/route.ts` to `app/api/site-edit/[...path]/route.ts` and fill the `SITE-EDIT` lines: `locales`, and `pageFiles` returning the file(s) for a route so the agent starts in the right place. Other frameworks: call `createSiteEdit()` from `@nuthinking/site-edit/server` and hand its `GET`, `POST` and `DELETE` the request. If the handlers must mount somewhere other than `/api/site-edit`, pass the same `basePath` to the handlers, the widget, and the email workflow's `BASE_PATH`.

5. **Add the approve page** from `templates/next/approve-page.tsx` at `app/admin/approve/[pr]/page.tsx`, under the locale segment on a localised site (`app/[locale]/admin/approve/[pr]/page.tsx`). Style its wrapper like the site's other pages; keep `robots: noindex`.

6. **Mark the components.** Every site component's root element gets `data-component="<Name>"`, the component's file name, so a pin names the file. Pages must render inside `<main>`. Do not mark layout wrappers or primitives (Button, Section); mark the things an editor would point at: hero, nav, footer, cards, bands.

7. **Environment.** Add to `.env.example` (empty values) and `.env.local` (placeholders, never real secrets you invent): `SITE_EDIT_REPO`, `SITE_EDIT_GITHUB_CLIENT_ID`, `SITE_EDIT_GITHUB_CLIENT_SECRET`, `SITE_EDIT_SECRET`, `SITE_EDIT_SITE_URL`, `SITE_EDIT_PREVIEW_PREFIX`. The same names go in the host's settings for every environment; `references/setup.md` says where.

8. **Workflows and the email script.** Copy from `node_modules/@nuthinking/site-edit/templates/`:
   - `claude.yml` → `.github/workflows/claude.yml`. Replace the two `SITE-EDIT` setup steps with the project's runtime and install (Node version, package manager, working directory), and `--allowedTools` with the project's package manager, e.g. `"Bash(pnpm:*)"`.
   - `preview-email.yml` → `.github/workflows/preview-email.yml`. Fill `SITE_URL`, `LOCALES` (comma-separated, or empty), `APPROVE_PATH` (the approve page's path without the number, under the first locale on a localised site, e.g. `/en/admin/approve`), `BASE_PATH` if changed.
   - `preview-email.mjs` → `.github/scripts/preview-email.mjs`, and `scripts-package.json` → `.github/scripts/package.json`. Run the install there once (`npm install` in `.github/scripts`) so a lockfile exists, then make sure `.github/scripts/node_modules` is ignored.
   If a workflow with one of these names exists, read it first and merge rather than overwrite.

9. **Agent rules.** Append the section in `templates/agent-rules.md` to `AGENTS.md` (and `CLAUDE.md` when it holds the real instructions), filling every `SITE-EDIT` comment with the project's facts: where copy lives, the language rule, the check command, tone rules if the site has them. Delete comments that do not apply. Never leave a placeholder. Do not duplicate rules the file already has; extend them.

10. **Check and verify locally.** Run the project's check command and fix what it reports. Start the dev server, open a page, and confirm the widget mounted (an element with `data-site-edit` exists in the DOM, empty until sign-in) and the route answers: `GET /api/site-edit/review/1` returns 503 while unconfigured, 401 once the environment is set. Sign-in itself needs the GitHub App, which only the user can create; once they have, test it end to end on localhost with Alt+right-click (the App's callback list includes `http://localhost:<port>/api/site-edit/auth/callback`). Stop servers you started; the only diff should be the files above and the lockfile.

11. **Hand over the settings.** Give the user the checklist from `references/setup.md` with this project's values filled in: callback URLs, the repository, the secret names, the Vercel variables, the Actions switch. If `gh` is available and the user asks, set repository secrets with `gh secret set NAME` and read values back from the environment, never echo secrets. Do not create the GitHub App or change organisation settings yourself.

12. **Report** using the completion checklist at the end of this file.

## Diagnose

Reproduce from the evidence first: the workflow run's log (`gh run view <id> --log-failed`), the issue or PR body, the email. Then match:

| Symptom | Cause and fix |
|---|---|
| The agent pushed a branch but no PR appeared; log says "GitHub Actions is not permitted to create or approve pull requests" | Repository (and organisation) setting: Actions → General → Workflow permissions → "Allow GitHub Actions to create and approve pull requests". The user flips it; see setup.md. |
| PR step fails with "Invalid username or token" on `git` | The action replaces git credentials. The template uses the API (`gh api`, `gh pr create`), never git; restore that. |
| Two emails for one commit | Both triggers fired within seconds. The template's `concurrency` block serialises runs; make sure it is there. |
| The agent pushed a branch, the run failed at the PR step with "unexpected end of JSON input" or another `gh` error, no PR | A transient GitHub API failure. The template's PR step retries each call three times; make sure the `try` wrapper is there. If a run still fails, recover by hand: open the PR from the pushed branch with the report from the log as the description (`gh pr create --base <default> --head claude/<branch> --title ... --body-file ...`, plus `Closes #<issue>`), then start the email with `gh workflow run preview-email.yml -f pr=<number>`. Re-running the job would run the agent again. |
| Email workflow 403 listing deployments | `permissions: deployments: read` missing. |
| Resend 422 "domain is invalid" | `EDIT_FROM_EMAIL` not on a domain verified in Resend, or the secret arrives empty. |
| No email at all, log says no address | The batch had no notify marker (issue written by hand on GitHub) and `EDIT_NOTIFY_EMAILS` is unset; or `SITE_EDIT_SECRET` differs between Vercel and the repository secrets. |
| Screenshots at the top of the page, not at the element | The component is not marked with `data-component`, or the agent restructured it. Mark it; the script falls back to tag and class, then the component. |
| Screenshots with text missing | Reveal animations hide text until hydration; the script waits for `[data-site-edit]`. If the site branches markup on reduced motion between server and client, hydration mismatches leave styles stuck: make SSR and client markup identical and use the motion library's reduced-motion config. |
| Sign-in on a preview says "Not available here" | `SITE_EDIT_PREVIEW_PREFIX` does not match the preview hostname (`<prefix>-<hash>-<team>.vercel.app`), or Vercel deployment protection is on for previews. |
| Sign-in works but "no write access" | The user lacks push permission on the repository, or the App is not installed on it. |
| Widget never appears | The `site-edit-ui` cookie is missing: sign-in did not complete, or `basePath` differs between widget and handlers. On a phone, a two-finger hold is the way in. |
| The agent's report shows file paths and commands to editors | The rules section is missing its "read by editors" rule; add it from `templates/agent-rules.md`. |

Report what the log shows, the cause, and the fix; apply the fix when it is in the repo, hand it over when it is a setting.

## Update

When locales change: the widget's `locales`, the handlers' `locales`, the workflow's `LOCALES` and `APPROVE_PATH`, the rules' language line. When copy or components move: `pageFiles` and the rules. When the package manager or Node version changes: the Claude workflow's setup steps and `--allowedTools`. When the package updates: reinstall in the app and in `.github/scripts`, and diff the templates against the repo's copies for changes worth taking. Keep edits to the affected places; do not rewrite healthy files.

## Completion checklist

End an install with a short report that covers:

- Where the widget, the handlers and the approve page are mounted, and the `basePath`
- Which components were marked with `data-component`, and any the user should still mark
- The environment variable names added, and where they must be set
- The workflow files and the script, and what was adapted in them
- Whether `AGENTS.md` / `CLAUDE.md` gained the rules section, and which lines were filled from the project
- The check command's result, and what was verified locally
- The settings checklist for the user, with this project's values, and what cannot be tested until they are done
- What to try first once set up: sign in on the live site with Alt+right-click, drop one note, Request change, watch the issue, the PR, the email, then Ship
