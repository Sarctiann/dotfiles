# Credentials

Environment variables are loaded from `.credentials` in this directory by `~/.zshrc`.

`.credentials` is gitignored — you must create it with your own values.

---

## Variables

### `GITHUB_PERSONAL_ACCESS_TOKEN`

GitHub personal access token for CLI operations. Generated dynamically via:

```zsh
gh auth token
```

---

### `OPENCODE_SERVER_USERNAME`

Username for the opencode server.

### `OPENCODE_SERVER_PASSWORD`

Password for the opencode server.

### OpenCode credentials

Workspace ID and auth cookie for the opencode quota plugin. Obtained from the web dashboard (`https://opencode.ai`).

| Var | Provider | Purpose |
|-----|----------|---------|
| `OPENCODE_WORKSPACE_ID` | OpenCode Zen | Billing (balance, monthly limit) |
| `OPENCODE_AUTH_COOKIE` | OpenCode Zen | Billing (balance, monthly limit) |
| `OPENCODE_GO_WORKSPACE_ID` | OpenCode Go | Usage (rolling, weekly, monthly) |
| `OPENCODE_GO_AUTH_COOKIE` | OpenCode Go | Usage (rolling, weekly, monthly) |

> Both pairs use the same values — the workspace ID and auth cookie are shared between Zen and Go.

---

### `JIRA_API_TOKEN`

Jira API token for authentication with the Jira REST API.

Generated at: `https://id.atlassian.com/manage/api-tokens`

### `JIRA_URL`

Base URL of the Jira instance.

### `JIRA_EMAIL`

Email address associated with the Jira account.

---

### `TAVILY_API_KEY`

API key for the Tavily search API.

Obtained from: `https://tavily.com`

---

### `GIT_NAME` / `GIT_EMAIL`

Personal git identity. Used by `sync_git_config.py` to generate `~/.gitconfig`.

| Var | Purpose |
|-----|---------|
| `GIT_NAME` | `[user] name` in `~/.gitconfig` |
| `GIT_EMAIL` | `[user] email` in `~/.gitconfig` |

```zsh
GIT_NAME="Your Name"
GIT_EMAIL="your@email.com"
```

### `COMPANY_GIT_NAME` / `COMPANY_GIT_EMAIL`

Work git identity. Used by `sync_git_config.py` to generate `~/.gitconfig-work`,
loaded via `includeIf` when inside `COMPANY_DIR`.

```zsh
COMPANY_GIT_NAME="Your Work Name"
COMPANY_GIT_EMAIL="your@work.com"
```

### `DOCS_DIR`

Documents directory path. Used by Neovim to locate custom plugins.

```zsh
DOCS_DIR="$HOME/Documents"
```

---

### `COMPANY_DIR`

Company project root directory. Used by:

- **`sync_git_config.py`** — generates `includeIf` in `~/.gitconfig`
- **Neovim** — detects company projects and activates Augment

Supports `~` expansion.

```zsh
COMPANY_DIR="~/Documents/MyCompany"
```
