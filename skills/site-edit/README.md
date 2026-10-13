# Site edit

> Edit a website from the website.

Editors sign in with GitHub, drop pins and notes on the live site or on a preview, and send them. A GitHub Actions workflow runs Claude Code, which makes the change and opens a pull request. Vercel builds a preview; an email arrives with screenshots of where each note pointed, the agent's replies, and a **Ship** link that merges to the live site. More notes on the preview go back to the same pull request.

Nothing technical reaches the editors. The developer sets it up once, and this skill does the setup: it installs [`@nuthinking/site-edit`](https://www.npmjs.com/package/@nuthinking/site-edit), mounts the widget and the handlers, copies and adapts the workflows, writes the rules the agent follows, and hands over the checklist of settings only a human can make.

## What it looks like

![A note on the headline: the pin's box names the component and the element, quotes its text, and takes the note](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/note.png)

| Notes across pages, in the tray | On a preview: the agent's replies, Ship and Discard |
|---|---|
| ![The tray lists the batch grouped by page, with Send](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/tray.png) | ![The review panel in the tray on a pull request's preview](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/review.png) |

| On a phone: the note as a bottom sheet | The tray as a sheet | The approve page the email links to |
|---|---|---|
| ![The note box as a bottom sheet with the keyboard](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/phone-note.png) | ![The tray as a bottom sheet](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/phone-tray.png) | ![The approve page: title, replies, Ship](https://raw.githubusercontent.com/nuthinking/site-edit/main/docs/screenshots/approve.png) |

The pictures come from the package's Storybook, which wraps the widget in a fake site; on a real site the widget inherits the site's font and colours.

## What the skill does

```text
Install the skill
      ↓
Ask the agent to set up site editing
      ↓
Agent installs the package, mounts widget + handlers + approve page,
marks components, copies the workflows, writes the agent rules
      ↓
You create the GitHub App, set the secrets, flip the Actions switch
      ↓
Sign in on the site, drop a note, Send, ship from the email
```

It also diagnoses the loop when a step fails (the table in `SKILL.md` lists the failures met in practice and their fixes) and updates the setup when the site changes.

## Files

```text
SKILL.md                     Instructions for the agent
references/how-it-works.md   Each piece of the loop, and why it is built that way
references/setup.md          The settings a human makes: GitHub App, secrets, Vercel, Resend, Actions
```

The templates (workflows, email script, Next route and approve page, agent rules) ship with the package under `node_modules/@nuthinking/site-edit/templates/`, so they always match the installed version.

## Requirements

A GitHub repository, a React site (Next.js App Router has a ready-made entry), a host that deploys previews per branch as GitHub deployments (Vercel), a Resend account for the email, and a Claude subscription or API key for the GitHub Action.
