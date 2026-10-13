# Settings a human makes

The agent fills in this checklist with the project's values and hands it over. Items are in the order that works; each takes a minute or two. Nothing here can be done by the agent, except setting repository secrets with `gh secret set` when the user asks.

## 1. GitHub App, for sign-in

Organisation (or user) settings → Developer settings → GitHub Apps → New GitHub App.

- **Name:** `<Site name> editor`
- **Homepage URL:** the live site
- **Callback URLs** (add both): `https://<live site>/api/site-edit/auth/callback` and `http://localhost:<dev port>/api/site-edit/auth/callback`
- **Expire user authorization tokens:** off (the session lasts 30 days)
- **Request user authorization (OAuth) during installation:** on
- **Webhook:** off
- **Repository permissions:** Contents: read and write (to merge); Issues: read and write; Pull requests: read and write; Metadata: read
- **Account permissions:** Email addresses: read (for the preview email)
- **Where can this app be installed:** only on this account

Create it, note the **Client ID**, generate a **client secret**, then **Install App** on the site's repository only. Anyone with write access to that repository can then sign in; nobody else can.

## 2. Secrets and variables

**Site host (Vercel → Project → Settings → Environment Variables, all environments):**

```text
SITE_EDIT_REPO=<owner/name>
SITE_EDIT_GITHUB_CLIENT_ID=<from step 1>
SITE_EDIT_GITHUB_CLIENT_SECRET=<from step 1>
SITE_EDIT_SECRET=<any long random string, e.g. openssl rand -base64 48>
SITE_EDIT_SITE_URL=https://<live site>
SITE_EDIT_PREVIEW_PREFIX=<the Vercel project name; preview hostnames start with it>
```

The same six go in `.env.local` for local development. Redeploy after adding them.

**Repository secrets (GitHub → Settings → Secrets and variables → Actions):**

```text
CLAUDE_CODE_OAUTH_TOKEN   from `claude setup-token` (a Claude subscription); or ANTHROPIC_API_KEY with the workflow changed to `anthropic_api_key`
SITE_EDIT_SECRET          the same value as on the host, so the email script can open the sealed address
RESEND_API_KEY            from Resend, restricted to the sending domain
EDIT_FROM_EMAIL           the sender, e.g. `Site <notifications@example.com>`, on a domain verified in Resend
EDIT_REPLY_TO             optional, where replies to the email go
EDIT_NOTIFY_EMAILS        optional, fallback addresses for issues written by hand on GitHub
```

With `gh`: `gh secret set NAME` reads the value from stdin or `--body`.

## 3. Claude on GitHub

Install the Claude GitHub app on the repository: in a Claude Code session, `/install-github-app`, or from https://github.com/apps/claude. It is what lets the workflow run with the subscription token.

## 4. Let Actions open pull requests

GitHub → repository → Settings → Actions → General → Workflow permissions → tick **Allow GitHub Actions to create and approve pull requests**. In an organisation, the organisation's own Actions settings gate the repository's: enable it there first (Organisation → Settings → Actions → General). Without this, the agent's branch is pushed but no PR appears.

## 5. Vercel

- Project → Settings → Deployment Protection: off for preview deployments, so editors and the screenshot script can open previews without a Vercel login.
- Previews must be enabled for pull-request branches (the default). Vercel reports them to GitHub as deployments, which is what the email workflow listens to.

## 6. Resend

- Add and verify the sending domain (Resend → Domains); a subdomain such as `mail.example.com` keeps it separate from the main domain's mail. Put the DNS records where the domain is hosted.
- Create an API key restricted to that domain; that is `RESEND_API_KEY`.
- `EDIT_FROM_EMAIL` must be an address on the verified domain.

## 7. Branch protection (optional)

Protect the default branch so changes land only through pull requests. Branch protection needs a public repository or a paid plan; until then, the agent only pushes to `claude/` branches and the site's Ship is the only path from them to the default branch.

## First run

1. On the live site, Alt+right-click on any text (desktop) or hold with two fingers (phone). Sign in with GitHub.
2. Drop one note, Send. The tray links to the issue.
3. Watch the Claude workflow run (GitHub → Actions). A pull request appears, then a preview, then the email.
4. Open the preview from the email, look, then **Ship it**. The live site updates in a couple of minutes.
