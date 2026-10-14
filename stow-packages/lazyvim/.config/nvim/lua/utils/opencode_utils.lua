local M = {}

-- WARN (OpenCode V2 architecture):
-- 1. Local TUI — `opencode --standalone` runs a PRIVATE server in the same process as the
--    TUI. The Neovim overlay below is injected through OPENCODE_CONFIG (see get_env()), so
--    the per-instance NVIM socket is honored WITHOUT managing a port, a PID file, a log
--    file, or a server password. Closing the terminal tears the private server down.
-- 2. Internet — `opencode pair --remote` targets the SHARED background service and exposes
--    it through OpenTunnel (see M.pair). All servers share one database, so the phone sees
--    the same sessions (without the Neovim-only MCP tools, which is expected).
--
-- The Neovim MCP server plus the nvim-only skills/commands/agent permissions live in
-- `opencode-neovim/opencode_nvim_mcps.jsonc` and are injected through OPENCODE_CONFIG when
-- OpenCode is started from Neovim (see get_env()). The global
-- `~/.config/opencode/opencode.jsonc` declares the same MCP server with `disabled: true`,
-- so sessions outside Neovim never see it. The overlay merges ON TOP of the global config,
-- so its entries win when OpenCode is launched from Neovim.
--
-- V2 shape of the global entry (for reference):
--
--  // MCP servers configuration
--  "mcp": {
--    "servers": {
--      "neovim": {
--        "type": "local",
--        "command": ["npx", "-y", "mcp-neovim-server"],
--        "disabled": true,
--        "environment": {
--          // Enable shell commands execution through vim
--          "ALLOW_SHELL_COMMANDS": "true",
--          // Socket path for neovim connection (uses NVIM env var)
--          "NVIM_SOCKET_PATH": "{env:NVIM}",
--        },
--      },
--    },
--  }

-- NOTE: Resolve paths relative to this file's directory using Neovim's debug.getinfo
local _this_dir = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":h")
-- NOTE: Overlay config with the Neovim MCP server, skills, commands, and agent permissions.
-- Passed as OPENCODE_CONFIG (merged on top of the global config) so it only applies when
-- OpenCode is started from Neovim.
local OPENCODE_MCP_CONFIG_FILE = _this_dir .. "/opencode-neovim/opencode_nvim_mcps.jsonc"

-- NOTE: Runtime state for the current neovim instance (not persisted).
-- _pair_urls  : one-time connect links captured from the last `opencode pair` run
-- _remote_url : remote (OpenTunnel) connect link, when remote pairing was used
M._pair_urls = nil
M._remote_url = nil

-- NOTE: Environment for the OpenCode terminal job, passed as the `env` field of the
-- cli-integration OpenCode entry (merged on top of the inherited environment).
--   OPENCODE_CONFIG : injects the Neovim overlay (MCP + skills + commands + agent
--     permissions). It is the only injection mechanism in V2; OPENCODE_CONFIG_DIR would
--     REPLACE the global config dir, losing global agents/plugins/mcp.
--   NVIM : pinned to this Neovim's socket so the overlay's `{env:NVIM}` resolves even if
--     the variable was not exported to the terminal job.
function M.get_env()
  return {
    OPENCODE_CONFIG = OPENCODE_MCP_CONFIG_FILE,
    NVIM = os.getenv("NVIM") or vim.v.servername,
  }
end

-- NOTE: Helpers for the native `opencode pair` flow.

-- NOTE: Classifies a pairing-link host as loopback/private so the LAN link can be
-- told apart from the OpenTunnel remote link.
local function is_private_host(host)
  return host == "localhost"
    or host == "127.0.0.1"
    or host == "0.0.0.0"
    or host:match("^192%.168%.") ~= nil
    or host:match("^10%.") ~= nil
    or host:match("^172%.1[6-9]%.") ~= nil
    or host:match("^172%.2%d%.") ~= nil
    or host:match("^172%.3[01]%.") ~= nil
end

-- NOTE: Extracts http(s) connect links from arbitrary `opencode pair` output lines.
-- The CLI prints plain URLs alongside a QR block and box-drawing decoration, so we
-- match the stable "/auth/connect/<token>" path instead of parsing the whole line.
local function extract_pair_url(line)
  return line:match("https?://[%w%._%-:]+/auth/connect/[%w%-_]+")
end

-- NOTE: Pairs a browser or app with the shared background service using the native
-- `opencode pair` command.
--   remote = false → local links only (loopback + LAN when the service hostname is 0.0.0.0)
--   remote = true  → `--remote --yes`, enabling OpenTunnel remote access on the shared
--                    service and printing a remote connect link.
-- WARN: links are one-time and expire after 5 minutes. The best link (the remote one
-- when present, otherwise the first) is copied to the clipboard as soon as it appears.
function M.pair(remote)
  local args = { "opencode", "pair" }
  if remote then
    table.insert(args, "--remote")
    table.insert(args, "--yes")
  end

  local urls = {}

  local function collect(data)
    if not data then
      return
    end
    for _, line in ipairs(data) do
      local url = extract_pair_url(line)
      if url then
        table.insert(urls, url)
      end
    end
  end

  vim.notify(
    remote and "Enabling remote access and pairing (this can take a minute)..."
      or "Generating pairing links...",
    vim.log.levels.INFO
  )

  vim.fn.jobstart(args, {
    stdout_buffered = true,
    stderr_buffered = true,
    on_stdout = function(_, data)
      collect(data)
    end,
    on_stderr = function(_, data)
      collect(data)
    end,
    on_exit = function(_, code)
      vim.schedule(function()
        if #urls == 0 then
          vim.notify(
            string.format("opencode pair produced no links (exit %d)", code),
            vim.log.levels.WARN
          )
          return
        end

        -- De-duplicate while preserving order.
        local seen = {}
        local unique = {}
        for _, url in ipairs(urls) do
          if not seen[url] then
            seen[url] = true
            table.insert(unique, url)
          end
        end
        M._pair_urls = unique

        -- Prefer the remote (non-private) link; fall back to the first link.
        local remote_url = nil
        for _, url in ipairs(unique) do
          local host = url:match("^https?://([^/:]+)")
          if host and not is_private_host(host) then
            remote_url = url
            break
          end
        end

        local copy_url = remote_url or unique[1]
        M._remote_url = remote_url
        vim.fn.setreg("+", copy_url)
        vim.notify(
          string.format("Pair link copied (%d link(s), expire in 5 min):\n%s", #unique, table.concat(unique, "\n")),
          vim.log.levels.INFO
        )
      end)
    end,
  })
end

-- NOTE: Disables OpenTunnel remote access on the shared background service.
-- WARN: `opencode service set` restarts the background service, which disrupts any
-- client attached to it (and any session it serves). The private TUI servers are
-- unaffected because they are separate processes.
function M.disable_remote()
  vim.ui.select({ "Yes, disable remote access", "No, cancel" }, {
    prompt = "Disable OpenTunnel remote access? This restarts the background service.",
  }, function(choice)
    if not choice or not choice:match("^Yes") then
      return
    end
    local out = vim.fn.system({ "opencode", "service", "set", "remote", "false" })
    if vim.v.shell_error == 0 then
      M._remote_url = nil
      M._pair_urls = nil
      vim.notify("Remote access disabled", vim.log.levels.INFO)
    else
      vim.notify("Failed to disable remote access: " .. out, vim.log.levels.ERROR)
    end
  end)
end

-- NOTE: Entry point for the <leader>ast mapping. Offers local pairing, remote
-- pairing (OpenTunnel), and turning remote access back off.
function M.pair_menu()
  local options = { "Pair local (links)", "Pair remote (OpenTunnel)", "Disable remote access" }
  vim.ui.select(options, { prompt = "OpenCode pairing" }, function(choice)
    if choice == "Pair local (links)" then
      M.pair(false)
    elseif choice == "Pair remote (OpenTunnel)" then
      M.pair(true)
    elseif choice == "Disable remote access" then
      M.disable_remote()
    end
  end)
end

-- NOTE: Shows a floating window in the top-right corner with the pairing status.
-- Keymaps: u copies the primary connect link, t copies the remote link. <CR>/<Esc> close.
-- NOTE: With the V2 architecture there is no per-instance server URL to show; internet
-- access is handled by `opencode pair --remote` (see M.pair).
function M.show_info()
  local link = (M._pair_urls and M._pair_urls[1]) or "Not paired (run <leader>ast)"
  local remote = M._remote_url or "off"

  local lines = {
    " Link:   " .. link,
    " Remote: " .. remote,
  }

  local width = 0
  for _, line in ipairs(lines) do
    if #line > width then
      width = #line
    end
  end
  width = width + 2

  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.api.nvim_set_option_value("modifiable", false, { buf = buf })
  vim.api.nvim_set_option_value("bufhidden", "wipe", { buf = buf })

  local win = vim.api.nvim_open_win(buf, true, {
    relative = "editor",
    row = 1,
    col = vim.o.columns - width - 2,
    width = math.max(width, 48),
    height = #lines,
    style = "minimal",
    border = "rounded",
    -- NOTE: Using Nerd Font CircleInfo glyph directly as requested
    title = "    u: Copy link │ t: Copy remote ",
    title_pos = "center",
  })

  local opts = { nowait = true, noremap = true, silent = true, buffer = buf }

  vim.keymap.set("n", "u", function()
    if M._pair_urls and M._pair_urls[1] then
      vim.fn.setreg("+", M._pair_urls[1])
      vim.notify("Pair link copied: " .. M._pair_urls[1], vim.log.levels.INFO)
    else
      vim.notify("No pairing link captured", vim.log.levels.WARN)
    end
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
  end, opts)

  vim.keymap.set("n", "t", function()
    if M._remote_url then
      vim.fn.setreg("+", M._remote_url)
      vim.notify("Remote pair link copied: " .. M._remote_url, vim.log.levels.INFO)
    else
      vim.notify("No remote link captured", vim.log.levels.WARN)
    end
    if vim.api.nvim_win_is_valid(win) then
      vim.api.nvim_win_close(win, true)
    end
  end, opts)

  local timer = nil
  local function close()
    if timer then
      pcall(function()
        timer:stop()
        timer:close()
      end)
      timer = nil
    end
    if vim.api.nvim_win_is_valid(win) then
      pcall(vim.api.nvim_win_close, win, true)
    end
  end

  vim.keymap.set("n", "<CR>", close, opts)
  vim.keymap.set("n", "<Esc>", close, opts)

  -- Auto-close after 5 seconds to avoid lingering UI
  timer = vim.loop.new_timer()
  if timer then
    timer:start(
      5000,
      0,
      vim.schedule_wrap(function()
        close()
      end)
    )
  end
end

-- NOTE: Convert a Unix millisecond timestamp to a sortable ISO-like string
-- and a formatted display pair (date, time).
local function parse_timestamp(ts_ms)
  local n = tonumber(ts_ms)
  if not n or n == 0 then
    return "0000-00-00T00:00:00", "Unknown", ""
  end
  local epoch = n / 1000
  local iso = os.date("!%Y-%m-%dT%H:%M:%S", epoch)
  local date = os.date("!%Y-%m-%d", epoch)
  local time = os.date("!%H:%M", epoch)
  return iso, date, time
end

-- NOTE: Query all sessions across projects via the sqlite3 CLI.
-- OpenCode V2 dropped the `opencode db` subcommand; `opencode session list` only lists
-- the current project, so direct DB access is required for the cross-project picker.
-- DB path comes from `opencode debug paths db` (~/.local/share/opencode/opencode.db).
local function get_sessions()
  local sessions = {}
  local db_path = vim.fn.expand("~/.local/share/opencode/opencode.db")
  local result = vim.fn.system({
    "sqlite3",
    "-json",
    db_path,
    "SELECT id, title, directory, time_updated FROM session ORDER BY time_updated DESC;",
  })
  if vim.v.shell_error ~= 0 or result == "" then
    return sessions
  end

  local ok, data = pcall(vim.json.decode, result)
  if not ok or type(data) ~= "table" then
    return sessions
  end

  for _, row in ipairs(data) do
    if row.id and row.title and row.directory and row.time_updated then
      local iso, date, time = parse_timestamp(row.time_updated)
      local project_name = vim.fn.fnamemodify(row.directory, ":t")
      if #project_name > 30 then
        project_name = "..." .. project_name:sub(-27)
      end
      local display_title = row.title:gsub("\n", " "):sub(1, 50)
      if #row.title > 50 then
        display_title = display_title .. "..."
      end

      table.insert(sessions, {
        id = row.id,
        modified = iso,
        workspace = row.directory,
        display = string.format("[%s %s] (%s) %s", date, time, project_name, display_title),
      })
    end
  end
  return sessions
end

-- NOTE: OpenCode session manager (uses cli-integration hooks engine)
function M.manage_opencode_sessions(show_all)
  local hooks = require("cli-integration.hooks")
  hooks.manage_sessions({
    name = "OpenCode",
    resume_cmd = "CLIIntegration open_root OpenCode -s %s",
    show_all = show_all,
    get_sessions = get_sessions,
    delete_cmd = function(session)
      vim.fn.system({ "opencode", "session", "delete", session.id })
      vim.notify("✓ Session deleted: " .. session.id, vim.log.levels.INFO)
    end,
  })
end

-- NOTE: Delete OpenCode sessions (current project or all)
function M.delete_all_opencode_sessions()
  local all_sessions = get_sessions()

  local options = { "Current Project Only", "ALL Projects", "Cancel" }
  vim.ui.select(options, { prompt = "⚠️ Delete OpenCode sessions?" }, function(choice)
    if not choice or choice == "Cancel" then
      return
    end

    local hooks = require("cli-integration.hooks")
    local current_ws = hooks.get_current_workspace()

    local session_ids = {}
    local scope_desc = ""

    if choice == "Current Project Only" then
      for _, sess in ipairs(all_sessions) do
        if sess.workspace == current_ws then
          table.insert(session_ids, sess.id)
        end
      end
      scope_desc = "current project"
    else
      for _, sess in ipairs(all_sessions) do
        table.insert(session_ids, sess.id)
      end
      scope_desc = "ALL projects"
    end

    if #session_ids == 0 then
      vim.notify("No OpenCode sessions found for " .. scope_desc, vim.log.levels.INFO)
      return
    end

    vim.ui.select({ "Yes, Delete " .. #session_ids .. " sessions", "No, Cancel" }, {
      prompt = "Confirm: Delete " .. #session_ids .. " sessions for " .. scope_desc .. "?",
    }, function(confirm)
      if confirm and confirm:match("^Yes") then
        local deleted = 0
        for _, id in ipairs(session_ids) do
          vim.fn.system({ "opencode", "session", "delete", id })
          if vim.v.shell_error == 0 then
            deleted = deleted + 1
          end
        end
        vim.notify("✓ " .. deleted .. " session(s) deleted", vim.log.levels.INFO)
      else
        vim.notify("Deletion cancelled", vim.log.levels.INFO)
      end
    end)
  end)
end

-- NOTE: Helper — returns the cwd of a process (macOS + Linux).
-- Uses lsof on macOS, /proc on Linux. Returns "" on failure.
-- `is_darwin` must be passed by the caller to avoid repeated uname calls.
local function get_proc_cwd(pid, is_darwin)
  if is_darwin then
    local lines = vim.fn.systemlist(string.format("lsof -a -d cwd -p %s -F n 2>/dev/null", pid))
    for _, l in ipairs(lines) do
      local path = l:match("^n(.+)$")
      if path then
        return path
      end
    end
  else
    local link = vim.fn.resolve(string.format("/proc/%s/cwd", pid))
    if link ~= "" then
      return link
    end
  end
  return ""
end

-- NOTE: Interactive inspector for ALL opencode-related processes on the machine.
-- Lists: opencode serve --service (shared background service), opencode --standalone
-- (local TUI private server), opencode serve / opencode --server (manual server/client).
-- Shows type, PID, directory, and allows killing one-by-one or all at once.
function M.inspect_opencode_processes()
  local entries = {}
  local is_darwin = vim.fn.system("uname -s"):gsub("%s+", "") == "Darwin"

  -- Collect all opencode processes via ps. The order of the checks matters:
  -- `opencode serve --service` also matches the "opencode serve" prefix.
  local oc_lines =
    vim.fn.systemlist("ps -eo pid,args | grep -E 'opencode (serve|--server|--standalone)' | grep -v grep 2>/dev/null")
  for _, line in ipairs(oc_lines) do
    local pid, cmd = line:match("^%s*(%d+)%s+(.*)$")
    if pid and cmd then
      local kind
      if cmd:find("opencode serve --service", 1, true) then
        kind = "service"
      elseif cmd:find("opencode --standalone", 1, true) then
        kind = "tui"
      elseif cmd:find("opencode serve", 1, true) then
        kind = "server"
      elseif cmd:find("opencode --server", 1, true) then
        kind = "client"
      end
      if kind then
        local cwd = get_proc_cwd(pid, is_darwin)
        local dir = cwd ~= "" and vim.fn.fnamemodify(cwd, ":~") or "?"
        table.insert(entries, { kind = kind, pid = pid, dir = dir, cmd = cmd })
      end
    end
  end

  if #entries == 0 then
    vim.notify("No opencode processes found", vim.log.levels.INFO)
    return
  end

  -- NOTE: Helper to reset this instance's runtime state if the killed pid matches.
  local function maybe_clear_state(e)
    if e.kind == "service" then
      -- Killing the shared service drops any captured pairing links.
      M._remote_url = nil
      M._pair_urls = nil
    end
  end

  local function kill_entry(e)
    vim.fn.system(string.format("kill %s 2>/dev/null || true", e.pid))
    maybe_clear_state(e)
  end

  -- Build display strings: [type] pid  dir
  local options = { "Kill All", "Cancel" }
  for _, e in ipairs(entries) do
    local label = string.format("[%-7s] pid %-6s  %s", e.kind, e.pid, e.dir)
    table.insert(options, label)
  end

  vim.ui.select(
    options,
    { prompt = "Inspect OpenCode processes (Kill All / select to kill one):" },
    function(choice, idx)
      if not choice or choice == "Cancel" then
        return
      end

      if choice == "Kill All" then
        vim.ui.select(
          { "Yes, kill all", "No, cancel" },
          { prompt = string.format("Confirm: kill ALL %d processes?", #entries) },
          function(confirm)
            if not confirm or not confirm:match("^Yes") then
              vim.notify("Cancelled", vim.log.levels.INFO)
              return
            end
            for _, e in ipairs(entries) do
              kill_entry(e)
            end
            vim.notify(string.format("Killed %d process(es)", #entries), vim.log.levels.INFO)
          end
        )
        return
      end

      -- Single selection: idx 1 = "Kill All", 2 = "Cancel", 3+ = entries
      local entry = entries[idx - 2]
      if not entry then
        vim.notify("Selection error", vim.log.levels.ERROR)
        return
      end

      vim.ui.select(
        { "Yes, kill", "No, cancel" },
        { prompt = string.format("Kill [%s] pid %s  %s ?", entry.kind, entry.pid, entry.dir) },
        function(confirm)
          if not confirm or not confirm:match("^Yes") then
            vim.notify("Cancelled", vim.log.levels.INFO)
            return
          end
          kill_entry(entry)
          vim.notify(string.format("Killed [%s] pid %s", entry.kind, entry.pid), vim.log.levels.INFO)
        end
      )
    end
  )
end

return M
