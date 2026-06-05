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

### `OPENCODE_GO_WORKSPACE_ID`

Workspace ID for the opencode quota plugin.

### `OPENCODE_GO_AUTH_COOKIE`

Auth cookie for the opencode quota plugin.

Obtained from the opencode web dashboard (`https://opencode.ai`).

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

### `COMPANY_DIR`

Company project root directory. Used by:

- **`sync_git_config.py`** — generates `includeIf` in `~/.gitconfig`
- **Neovim** — detects company projects and activates Augment

Supports `~` expansion.

```zsh
COMPANY_DIR="~/Documents/MyCompany"
```
