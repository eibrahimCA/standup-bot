# Standup Bot

Generates a daily standup Slack message from your GitHub activity. Every morning it:

1. Fetches all PRs merged the previous day across your repos
2. Analyzes the **code diffs** (not PR descriptions) with AI to produce plain-English summaries per team member
3. Cross-references open Linear issues against the day's PRs and posts actionable suggestions with interactive buttons — close an issue, document a PR assignment, or create a missing issue — all without leaving Slack

Interactive button callbacks are handled by a lightweight Cloudflare Worker (deploy once, no running service).

---

## How it looks in Slack

```
📋 Daily Standup — May 28, 2026
─────────────────────────────────────────
👤 alice
• Refactored JWT auth middleware to support refresh token rotation, eliminating session drops on mobile
• Fixed race condition in session expiry handler that caused intermittent 401 errors

👤 bob
• Added cursor-based pagination to the /users endpoint to handle large result sets efficiently

─────────────────────────────────────────
Linear — Action Items

Ready to close:
  LIN-123  Fix login timeout bug  →  PR #45       [Close Issue ✓]

In progress:
  LIN-456  Dark mode support      →  PR #89       [Document Assignment]

No issue found — suggested new issues:
  PR #90 — "Add rate limiting to public API endpoints"  [Create Issue]
```

---

## Setup

### 1. Install dependencies

```bash
git clone https://github.com/eibrahimCA/standup-bot
cd standup-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
```

### 2. GitHub token

- Go to **GitHub → Settings → Developer settings → Personal access tokens → Generate new token (classic)**
- Scopes needed: `repo`
- Add to `.env` as `GITHUB_TOKEN`

### 3. Slack app

- Go to **https://api.slack.com/apps → Create New App → From scratch**
- **OAuth & Permissions** → add bot scopes: `chat:write`, `chat:write.public`
- Install the app to your workspace → copy the **Bot User OAuth Token** → `SLACK_BOT_TOKEN`
- **Basic Information** → copy **Signing Secret** → `SLACK_SIGNING_SECRET`
- **Interactivity & Shortcuts** → enable Interactivity → paste your Cloudflare Worker URL (after step 5)
- Find your channel ID: right-click the channel in Slack → View channel details → copy ID at the bottom → `SLACK_CHANNEL_ID`

### 4. Linear API key

- Go to **Linear → Settings → API → Create new API key** → `LINEAR_API_KEY`
- Find your Team ID: **Settings → Teams** → click your team → copy the ID from the URL → `LINEAR_TEAM_ID`

### 5. AI provider

Set `AI_MODEL` and the matching API key. Pick any provider:

| Provider | `AI_MODEL` | Key var |
|---|---|---|
| OpenAI (default) | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini/gemini-1.5-flash` | `GEMINI_API_KEY` |
| Groq | `groq/llama3-70b-8192` | `GROQ_API_KEY` |
| Local (Ollama) | `ollama/llama3` | *(none)* |

### 6. Deploy the Cloudflare Worker (for Slack buttons)

```bash
cd worker
npm install -g wrangler
wrangler login
wrangler secret put SLACK_SIGNING_SECRET
wrangler secret put LINEAR_API_KEY
wrangler secret put LINEAR_TEAM_ID
wrangler secret put GITHUB_TOKEN
wrangler deploy
```

Copy the deployed URL (e.g. `https://standup-worker.your-name.workers.dev`) and paste it into your Slack App under **Interactivity → Request URL**.

---

## Usage

```bash
# Dry run — prints the Slack Block Kit JSON without posting
python standup.py --dry-run

# Live run — posts to Slack
python standup.py
```

### Schedule it (optional)

Run automatically at 8am every weekday:

```bash
crontab -e
# Add:
0 8 * * 1-5 cd /path/to/standup-bot && .venv/bin/python standup.py
```

---

## Project structure

```
standup-bot/
├── .env.example        # credential template
├── requirements.txt
├── standup.py          # entrypoint
├── analyzer.py         # AI diff summarization + Linear cross-reference
├── clients/
│   ├── github.py       # fetches yesterday's merged PRs and diffs
│   ├── linear.py       # queries/closes/creates Linear issues
│   └── slack.py        # builds Block Kit message and posts to Slack
└── worker/
    ├── wrangler.toml   # Cloudflare Worker config
    └── src/index.js    # handles Slack button callbacks
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | ✅ | Personal access token with `repo` scope |
| `GITHUB_ORG` | ✅ | GitHub organization or username |
| `GITHUB_REPOS` | ✅ | Comma-separated repo names, e.g. `api,frontend` |
| `SLACK_BOT_TOKEN` | ✅ | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_CHANNEL_ID` | ✅ | Channel to post to |
| `SLACK_SIGNING_SECRET` | ✅ | Used by the Worker to verify button payloads |
| `LINEAR_API_KEY` | ✅ | Linear personal API key |
| `LINEAR_TEAM_ID` | ✅ | Linear team ID |
| `AI_MODEL` | ✅ | LiteLLM model string (see table above) |
| `OPENAI_API_KEY` | depends | Required if using an OpenAI model |
| `ANTHROPIC_API_KEY` | depends | Required if using a Claude model |
| `GEMINI_API_KEY` | depends | Required if using Gemini |
| `GROQ_API_KEY` | depends | Required if using Groq |
