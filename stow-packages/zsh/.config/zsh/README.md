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

### `COMPANY_DIRS`

Colon-separated list of company project root directories used by Neovim to
detect company projects and activate Augment (instead of OpenCode).

```zsh
COMPANY_DIRS="/home/projects/company-a:/work/src/company-b"
```
