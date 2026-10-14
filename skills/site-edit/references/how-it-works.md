# How site edit works

Each piece of the loop, what it does, and why it is built that way. The code is in `@nuthinking/site-edit`; the repository-side files are its `templates/`.

## The loop

1. **Notes on the page.** Signed in, Alt+right-click (desktop) drops a numbered pin on an element and opens a box for the note. On a phone, a two-finger hold anywhere enters comment mode and opens the tray, whose hint says that one finger drops the note; in comment mode a one-finger hold on an element drops the pin, and the note form takes the full screen (the one surface with a keyboard, so nothing sits under it) while the sign-in box, an open note and the tray are bottom panels, plain CSS with no sheet library; the form's buttons are "Add more" and "Request change", which sends the batch with that note, and the labels say changes rather than notes (not once something is typed: then only Cancel or Add closes it). Browsing keeps working; pins and comment mode survive navigation and reloads (localStorage, keyed by deployment). A tray at the bottom left shows the batch, grouped by page. Request change posts the whole batch at once.
2. **Bridge.** `POST <basePath>/request` checks the session and the user's write access against GitHub again, then creates a GitHub issue with the batch, labelled `site-notes`, mentioning `@claude`, with the user's own token so the issue is theirs. On a preview deployment it comments on that PR instead, so the agent updates the same branch. The body is a numbered list with each note's context.
3. **Agent.** `.github/workflows/claude.yml` runs Claude Code (`anthropics/claude-code-action`) on any `@claude` mention. It follows `AGENTS.md`, makes the change on a `claude/` branch, and answers each numbered note in its report: done, done with a note, or a question. The action only pushes the branch for an issue, so the workflow's last step opens the PR with that report as the description and `Closes #N`, then starts the preview email. It does this through the GitHub API, because the action replaces the checkout's git credentials and removes them when done.
4. **Preview.** Vercel deploys the PR branch. Deployment protection must be off for previews, since editors and the screenshot script open them without a Vercel login.
5. **Email.** `.github/workflows/preview-email.yml` runs on a successful preview deployment, and when the Claude workflow dispatches it right after opening the PR (Vercel builds the branch the moment it is pushed, before the PR exists, so that event finds no PR; the dispatched run waits for the preview). A `concurrency` group serialises runs and a marker comment on the PR keeps it to one email per commit. The script screenshots each noted page on the preview, scrolled to the element each note pointed at, at 1440 and 390 wide in every language, and sends through Resend to whoever sent the notes: the title, the replies rendered, **See the preview** (a plain link: looking asks nothing of anyone), **Add notes** (through sign-in, since each preview address is new to the browser; lands in comment mode), **Ship it** (the approve page on the live site), and the PR on GitHub.
6. **Round two.** Pins dropped on the preview post to the same PR, and steps 3 to 5 repeat.

## What a pin carries

Precise context is what makes the agent find the right line without guessing. The browser sends things that are searchable in the source, not React internals.

| Field | Why |
|---|---|
| Page path and locale | Which page file and which language file. |
| `data-component` name of the nearest marked ancestor, and which instance of it on the page | The component's file name; the third card, not the first. |
| Tag, class string, text, selected text, image `src` | Class lists are literal in most source: a line number in disguise. |
| Up to four ancestors, briefly | Where in the layout it sits. |
| Viewport size | Desktop and phone requests differ. |
| A CSS path from the component root (hidden in an HTML comment) | For putting the pin back after navigation, and for the email's screenshots. |

Language rule on a localised site: a note on a source-language page changes all languages; on another language's page only that one. A checkbox on the note overrides it, and the note's own words override both.

## Sign-in

Same gestures as editing. Without a session, Alt+right-click (desktop) or a two-finger hold (phone) shows a small box: "Editing this site needs write access to its repository", with Sign in with GitHub. Sign-in goes through a GitHub App of the site's own, installed on this repository only. The callback exchanges the code for a user token, asks GitHub whether that user has write (`push`) access to the repository, and refuses with a plain message if not. The session is a sealed cookie (AES-256-GCM through WebCrypto, keyed from `SITE_EDIT_SECRET`) holding the token and login for 30 days; `site-edit-ui` carries the login for the widget. Write access is checked against GitHub again every time a batch is sent or a PR is reviewed. Log out clears the cookies; revoking someone's repository access locks them out at the next send.

Previews run on `*.vercel.app` addresses, which are not registered callback URLs, so a preview sends the sign-in to the live site with its own URL as the return; the live site's callback then redirects back to the preview's `<basePath>/auth/accept` with a sealed one-minute grant bound to that origin. Only origins matching `SITE_EDIT_PREVIEW_PREFIX` (or the `previewOrigin` option) are accepted.

The two-finger hold is listened to for every visitor: nothing native uses it, so it takes nothing from anyone, and it is the phone's sign-in and its way into comment mode. The one-finger hold only exists in comment mode, so outside it everyone keeps their native long-press menus and text selection; in comment mode on a phone, text selection and the iOS link callout are off, so a hold is only a hold. Both holds are 450ms, under the ~500ms at which iOS opens its link and image previews.

## Approval

The result is reviewed where it can be seen. On a PR's preview, the tray shows the pull request: its title, the agent's replies to the numbered notes (its description, rendered with the action's header and trailers removed), and **Ship** and **Discard**, each behind a second tap there. Ship squash-merges to the default branch under the editor's own GitHub token (one commit per request) and deletes the branch; it carries the commit the editor was shown, and GitHub refuses if the branch has moved since, so nothing ships unseen; production deploys from there. Discard closes the PR unmerged and deletes the branch; the issue stays open. Only `claude/` branches can be shipped or discarded this way, so nothing else in the repository can be merged from the site. The approve page is the same panel on its own page, for the email link: it merges only on the button, never on opening the page, since mail clients open links on their own. There, Ship is a single tap, since arriving from the email is the intention; Discard keeps its second tap.

## The agent's report

The PR description is read by editors on the review panel and in the email, so the rules tell the agent to write it as plain sentences about the site (which page and section changed, the old text and the new), without file paths, keys, commands or "checks pass". The widget renders it from Markdown with raw HTML escaped.

## Things learned the hard way

- GitHub Actions cannot open pull requests until the repository (and organisation) setting "Allow GitHub Actions to create and approve pull requests" is on. The symptom is a branch with no PR.
- Two triggers for the email can fire seconds apart (the dispatch and Vercel's deployment event); without serialising, both send before either leaves its marker.
- Full-page screenshots stretch the viewport and anything sized in `vh` with it; the script captures the viewport scrolled to the element instead.
- Reveal-on-scroll animations leave text invisible until hydration; the script waits for the widget to mount, which only happens after hydration, then scrolls through the page once.
- A site that branches its markup on `prefers-reduced-motion` between server and client gets hydration mismatches that leave text hidden in headless Chromium. Keep SSR and client markup identical and let the motion library handle reduced motion.
- An unset repository secret reaches a workflow as an empty string, not as undefined; treat empty as unset.
- The GitHub API fails now and then for no reason of the workflow's (`gh` reports "unexpected end of JSON input"), and a failure in the PR step loses the pull request while the branch is already pushed. The PR step retries each call three times; a run that still fails is recovered by opening the PR by hand and dispatching the email workflow for it.
