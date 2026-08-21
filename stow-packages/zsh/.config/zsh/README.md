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

The OpenCode Quota plugin no longer reads credentials from environment
variables. The `OPENCODE_WORKSPACE_ID` / `OPENCODE_AUTH_COOKIE` /
`OPENCODE_GO_WORKSPACE_ID` / `OPENCODE_GO_AUTH_COOKIE` exports were removed to
avoid colliding with OpenCode's workspace feature (which reads the same
`OPENCODE_WORKSPACE_ID` variable and caused an "(unknown)" entry in the
session sidebar).

Credentials are now provided through the plugin's own configuration:

| Provider | Source | Contents |
|----------|--------|----------|
| OpenCode Zen | `~/.config/opencode/opencode-quota/opencode-zen.json` | `{ "workspaceId", "authCookie" }` |
| OpenCode Go | `~/.local/share/opencode/auth.json` (or `OPENCODE_API_KEY`) | API key |

The Zen workspace ID and auth cookie are obtained from the web dashboard
(`https://opencode.ai`).

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

### `FIGMA_API_KEY`

Figma Personal Access Token. Used by the OpenFigma MCP server (registered in
the World Conquest project's `opencode.json`) so the `z-design` agent can read
and sync the Figma design book bidirectionally.

Scopes required: **File content: Read** and **Dev resources: Read**.

Generated at: `https://www.figma.com/settings` → *Security → Personal access
tokens*.

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
