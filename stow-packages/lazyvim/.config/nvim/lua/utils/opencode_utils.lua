local M = {}

-- WARN (OpenCode V2 architecture):
-- 1. Local TUI — `opencode --standalone` runs a PRIVATE server in the same process as the
--    TUI. The Neovim overlay below is injected through OPENCODE_CONFIG (see get_env()), so
--    the per-instance NVIM socket is honored WITHOUT managing a port, a PID file, a log
--    file, or a server password. Closing the terminal tears the private server down.
-- 2. Internet — `<leader>ast` runs `opencode pair --remote --yes` against the SHARED
--    background service, mints a one-time link and renders the CLI's QR block in a
--    persistent float (M.pair / M.open_pair_float) with copy/open/regenerate shortcuts.
--    `<leader>asi` reads the service's real state (`/api/info` via service.json) and only
--    mints a fresh link when the tunnel is already on; it never enables remote access.
--    All servers share one database, so the phone sees the same sessions (without the
--    Neovim-only MCP tools, which is expected).
-- 3. The TUI's built-in `/pair` stays loopback-only: it queries the private standalone
--    server, which has no tunnel, and its pairing codes are not reusable by the service.
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
-- _state : last pairing result rendered by the pairing float
-- _job   : jobstart id of the running `opencode pair`, nil when idle
M._state = nil
M._job = nil

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

-- NOTE: One-time pairing links expire five minutes after they are printed.
local PAIR_TTL = 300

local function notify_pair(message, level)
  vim.notify(message, level or vim.log.levels.INFO, { title = "OpenCode pairing" })
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

-- NOTE: A QR line is block-art only: spaces plus the half/full block glyphs the CLI
-- renders modules with. Anything else (headings, links, prose) is not part of it.
local function is_qr_line(line)
  if not line or not line:find("[█▀▄]") then
    return false
  end
  return line:match("^[ %█▀▄]+$") ~= nil
end

-- NOTE: Parses the full `opencode pair` output (links, pairing code, QR block).
-- Links are de-duplicated in first-seen order. The QR block keeps its module columns:
-- only the common leading indent is removed, since the CLI indents the whole block.
function M._parse_pair_output(text)
  local links = {}
  local seen = {}
  local code = nil
  local qr = nil
  local qr_closed = false

  for line in (text or ""):gmatch("[^\n]+") do
    local url = extract_pair_url(line)
    if url then
      if not seen[url] then
        seen[url] = true
        table.insert(links, url)
      end
      code = code or url:match("/auth/connect/([%w%-_]+)$")
    elseif qr_closed then
      -- The block already ended; ignore everything after it.
      -- (no-op)
    elseif is_qr_line(line) then
      qr = qr or {}
      table.insert(qr, line)
    elseif qr then
      qr_closed = true
    end
  end

  if qr then
    local indent = nil
    for _, line in ipairs(qr) do
      local lead = #(line:match("^( *)") or "")
      indent = math.min(indent or lead, lead)
    end
    for i, line in ipairs(qr) do
      qr[i] = line:sub((indent or 0) + 1)
    end
  end

  return { links = links, code = code, qr = qr }
end

-- NOTE: Host part of a URL, without port or credentials.
local function host_of(url)
  return url and url:match("^https?://([^/:]+)")
end

-- NOTE: Splits pairing/service URLs into the three kinds the client can use:
-- loopback (same machine), LAN (same Wi-Fi) and remote (OpenTunnel). First match wins.
function M._classify_urls(urls)
  local out = {}
  for _, url in ipairs(urls or {}) do
    local host = host_of(url)
    if host then
      local is_loopback = host == "localhost"
        or host == "[::1]"
        or host == "0.0.0.0"
        or host:match("^127%.") ~= nil
      if is_loopback then
        out.loopback = out.loopback or url
      elseif is_private_host(host) then
        out.lan = out.lan or url
      else
        out.remote = out.remote or url
      end
    end
  end
  return out
end

-- NOTE: The service binds 0.0.0.0 so other devices can reach it; locally we must
-- address the loopback interface instead.
local function loopback_url(url)
  return url:gsub("//0%.0%.0%.0:", "//127.0.0.1:"):gsub("//%[::%]:", "//127.0.0.1:")
end

-- NOTE: Builds the live service state from the two JSON documents involved:
-- `service.json` (url + password) and the shared service `/api/info` response.
-- A reachable non-private URL in `/api/info` means the OpenTunnel is up.
function M._service_state(service_json, info_json)
  local state = { tunnel = false }

  local service_ok, service = pcall(vim.json.decode, service_json or "")
  if not service_ok or type(service) ~= "table" or type(service.url) ~= "string" then
    state.error = "no se pudo leer service.json"
    return state
  end

  state.service_url = loopback_url(service.url)

  local info_ok, info = pcall(vim.json.decode, info_json or "")
  if not info_ok or type(info) ~= "table" then
    state.error = "no se pudo consultar /api/info"
    return state
  end

  local classified = M._classify_urls(info.urls or {})
  state.remote_url = classified.remote
  state.lan_url = classified.lan
  state.tunnel = classified.remote ~= nil
  return state
end

-- NOTE: Async live state of the shared background service. Reads `service.json`
-- for the URL and password, then asks the service for its addresses. Always calls
-- `cb` exactly once, on the main loop, with the `_service_state` shape.
function M.get_service_state(cb)
  local called = false
  local function finish(state)
    if called then
      return
    end
    called = true
    vim.schedule(function()
      cb(state)
    end)
  end

  local path = vim.fn.expand("~/.local/state/opencode/service.json")
  if vim.fn.filereadable(path) == 0 then
    finish(M._service_state(nil, nil))
    return
  end

  local lines = vim.fn.readfile(path)
  local service_text = table.concat(lines, "\n")
  local service_ok, service = pcall(vim.json.decode, service_text)
  if not service_ok or type(service) ~= "table" or type(service.url) ~= "string" then
    finish(M._service_state(nil, nil))
    return
  end

  if vim.fn.executable("curl") == 0 then
    local state = M._service_state(service_text, nil)
    state.error = "curl no está instalado"
    finish(state)
    return
  end

  local base = loopback_url(service.url)
  vim.system({
    "curl",
    "-s",
    "--max-time",
    "3",
    "-u",
    "opencode:" .. (service.password or ""),
    base .. "/api/info",
  }, { text = true }, function(obj)
    local state = M._service_state(service_text, obj.stdout)
    if state.error and obj.code ~= 0 then
      state.error = string.format("curl falló (exit %d)", obj.code)
    end
    finish(state)
  end)
end

-- NOTE: Pairing float -------------------------------------------------------
-- One persistent floating window renders `M._state`: the loader while
-- `opencode pair` runs, the QR/link/code block when it finishes, the expired
-- notice after five minutes, and a plain status line for `asi`.

local function format_remaining(expires_at)
  local remaining = math.max(0, (expires_at or 0) - os.time())
  return string.format("%d:%02d", math.floor(remaining / 60), remaining % 60)
end

-- NOTE: Block-art QR lines are multi-byte UTF-8; sizes must be in display
-- cells, not bytes, or a 41-column QR is measured as 123 and discarded.
local function display_width(text)
  return vim.fn.strdisplaywidth(text)
end

local function truncate(text, max)
  if not text or #text <= max then
    return text
  end
  if max <= 1 then
    return "…"
  end
  return text:sub(1, max - 1) .. "…"
end

local function primary_link(state)
  return state and (state.remote_url or (state.links and state.links[1])) or nil
end

-- NOTE: Pure layout helper so the sizing rules are testable headlessly.
function M._layout(state, columns, rows)
  columns = columns or vim.o.columns
  rows = rows or vim.o.lines
  local kind = (state and state.kind) or "ready"
  local lines = {}
  local qr_shown = false

  if kind == "off" then
    lines = { " Remote off — <leader>ast para activar" }
  elseif kind == "loading" then
    lines = {
      " Generando link de pairing...",
      "",
      " El primer túnel puede tardar hasta un minuto.",
      "",
      " q cerrar",
    }
  elseif kind == "error" then
    lines = {
      " No se pudo generar el link.",
      "",
      " " .. (state.error or "error desconocido"),
      "",
      " r reintentar · q cerrar",
    }
  else
    local qr = (state and state.qr) or {}
    local qr_start, qr_end
    if #qr > 0 then
      local qr_width = 0
      for _, line in ipairs(qr) do
        qr_width = math.max(qr_width, display_width(line))
      end
      if qr_width + 2 > columns then
        table.insert(lines, " Aumenta el ancho de la terminal para ver el QR")
      else
        qr_shown = true
        qr_start = #lines + 1
        for _, line in ipairs(qr) do
          table.insert(lines, " " .. line)
        end
        qr_end = #lines
      end
      table.insert(lines, "")
    end

    local link_width = math.max(columns - 12, 1)
    local primary = primary_link(state)
    if primary then
      table.insert(lines, " Public  " .. truncate(primary, link_width))
    end
    if state and state.lan_url then
      table.insert(lines, " LAN     " .. truncate(state.lan_url, link_width))
    end
    if state and state.code then
      table.insert(lines, " Code    " .. state.code)
    end
    if kind == "expired" then
      table.insert(lines, " Expirado — pulsa r para generar otro")
    elseif state and state.expires_at then
      table.insert(lines, " Expira  " .. format_remaining(state.expires_at))
    end
    table.insert(lines, "")
    table.insert(lines, " y público · l LAN · c código · o abrir · r regenerar · q cerrar")

    -- NOTE: A QR taller than the terminal would be clipped into an unreadable
    -- fragment. Drop it (and its trailing blank line) and say why instead.
    if qr_shown and rows and #lines > math.max(rows - 4, 3) then
      for _ = qr_start, qr_end + 1 do
        table.remove(lines, qr_start)
      end
      table.insert(lines, qr_start, " Aumenta el tamaño de la terminal para ver el QR")
      qr_shown = false
    end
  end

  local width = 0
  for _, line in ipairs(lines) do
    width = math.max(width, display_width(line))
  end
  return { lines = lines, width = width, qr_shown = qr_shown }
end

local function float_geometry(layout)
  local width = math.min(layout.width + 2, math.max(vim.o.columns - 4, 10))
  local height = math.min(#layout.lines, math.max(vim.o.lines - 6, 3))
  return {
    relative = "editor",
    width = width,
    height = height,
    row = math.max(1, math.floor((vim.o.lines - height) / 2)),
    col = math.max(1, math.floor((vim.o.columns - width) / 2)),
    style = "minimal",
    border = "rounded",
    title = " OpenCode pairing ",
    title_pos = "center",
  }
end

local function render_pair_float()
  local float = M._float
  if not (float and vim.api.nvim_buf_is_valid(float.buf)) then
    return
  end
  local layout = M._layout(M._state, vim.o.columns, vim.o.lines)
  vim.api.nvim_set_option_value("modifiable", true, { buf = float.buf })
  vim.api.nvim_buf_set_lines(float.buf, 0, -1, false, layout.lines)
  vim.api.nvim_set_option_value("modifiable", false, { buf = float.buf })
  if vim.api.nvim_win_is_valid(float.win) then
    vim.api.nvim_win_set_config(float.win, float_geometry(layout))
  end
end

-- NOTE: Copies a link/code, refusing to hand out a one-time link that expired.
local function copy_value(value, label)
  if not value or value == "" then
    notify_pair("No hay " .. label .. " disponible", vim.log.levels.WARN)
    return
  end
  if M._state and M._state.kind == "expired" then
    notify_pair("Link expirado — pulsa r para generar otro", vim.log.levels.WARN)
    return
  end
  vim.fn.setreg("+", value)
  notify_pair(label .. " copiado")
end

function M.close_pair_float()
  local float = M._float
  M._float = nil
  if not float then
    return
  end
  if float.timer then
    pcall(function()
      float.timer:stop()
      float.timer:close()
    end)
  end
  if float.win and vim.api.nvim_win_is_valid(float.win) then
    pcall(vim.api.nvim_win_close, float.win, true)
  end
end

function M.open_pair_float(state)
  M.close_pair_float()
  M._state = state

  local layout = M._layout(state, vim.o.columns, vim.o.lines)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, layout.lines)
  vim.api.nvim_set_option_value("modifiable", false, { buf = buf })
  vim.api.nvim_set_option_value("bufhidden", "wipe", { buf = buf })

  local win = vim.api.nvim_open_win(buf, true, float_geometry(layout))
  vim.api.nvim_set_option_value("wrap", false, { win = win })
  vim.api.nvim_set_option_value("cursorline", false, { win = win })

  M._float = { win = win, buf = buf, timer = nil }

  local opts = { buffer = buf, nowait = true, silent = true }

  vim.keymap.set("n", "y", function()
    copy_value(primary_link(M._state), "Link público")
  end, opts)

  vim.keymap.set("n", "l", function()
    copy_value(M._state and M._state.lan_url, "Link LAN")
  end, opts)

  vim.keymap.set("n", "c", function()
    copy_value(M._state and M._state.code, "Código")
  end, opts)

  vim.keymap.set("n", "o", function()
    local link = primary_link(M._state)
    if not link or link == "" then
      notify_pair("No hay link disponible", vim.log.levels.WARN)
      return
    end
    if M._state and M._state.kind == "expired" then
      notify_pair("Link expirado — pulsa r para generar otro", vim.log.levels.WARN)
      return
    end
    vim.ui.open(link)
  end, opts)

  vim.keymap.set("n", "r", function()
    local current = M._state
    if not current then
      return
    end
    M.pair(current.remote == true)
  end, opts)

  vim.keymap.set("n", "q", function()
    M.close_pair_float()
  end, opts)
  vim.keymap.set("n", "<Esc>", function()
    M.close_pair_float()
  end, opts)

  local timer = vim.uv.new_timer()
  if timer then
    M._float.timer = timer
    timer:start(
      1000,
      1000,
      vim.schedule_wrap(function()
        local current = M._state
        if not current then
          return
        end
        if current.kind == "ready" and current.expires_at and os.time() >= current.expires_at then
          current.kind = "expired"
        end
        render_pair_float()
      end)
    )
  end

  -- NOTE: Closing the window by any other means (for example `:q`) must stop
  -- the countdown timer instead of leaving it rewriting a dead buffer.
  vim.api.nvim_create_autocmd("WinClosed", {
    pattern = tostring(win),
    once = true,
    callback = function()
      local current = M._float
      if current and current.win == win then
        if current.timer then
          pcall(function()
            current.timer:stop()
            current.timer:close()
          end)
        end
        M._float = nil
      end
    end,
  })
end

function M.update_pair_float(state)
  M._state = state
  if M._float and vim.api.nvim_win_is_valid(M._float.win) then
    render_pair_float()
  elseif state.kind == "ready" then
    -- NOTE: The user closed the float while the job ran; do not pop it back open.
    notify_pair("Link listo — <leader>asi para ver el QR")
  elseif state.kind == "error" then
    notify_pair(state.error or "No se pudo generar el link", vim.log.levels.WARN)
  end
end

-- NOTE: Pairs a browser or app with the shared background service using the native
-- `opencode pair` command and renders the CLI's QR block in the pairing float.
--   remote = false → local links only (loopback + LAN when the service hostname is 0.0.0.0)
--   remote = true  → `--remote --yes`, enabling OpenTunnel remote access on the shared
--                    service and printing a remote connect link.
-- WARN: links are one-time and expire after 5 minutes. The float stays open until
-- dismissed and offers copy/open/regenerate shortcuts.
function M.pair(remote)
  if M._job then
    notify_pair("Pairing ya en curso", vim.log.levels.INFO)
    return
  end

  local args = { "opencode", "pair" }
  if remote then
    table.insert(args, "--remote")
    table.insert(args, "--yes")
  end

  M._state = { kind = "loading", remote = remote, links = {} }
  M.open_pair_float(M._state)

  local stdout, stderr = {}, {}

  M._job = vim.fn.jobstart(args, {
    stdout_buffered = true,
    stderr_buffered = true,
    on_stdout = function(_, data)
      if data then
        stdout = data
      end
    end,
    on_stderr = function(_, data)
      if data then
        stderr = data
      end
    end,
    on_exit = function(_, code)
      M._job = nil
      vim.schedule(function()
        local text = table.concat(stdout, "\n") .. "\n" .. table.concat(stderr, "\n")
        local parsed = M._parse_pair_output(text)
        local state = M._state or { remote = remote }

        if code ~= 0 or #parsed.links == 0 then
          state.kind = "error"
          state.error = string.format("opencode pair falló (exit %d)", code)
          M.update_pair_float(state)
          return
        end

        local classified = M._classify_urls(parsed.links)
        local now = os.time()
        state.kind = "ready"
        state.remote = remote
        state.links = parsed.links
        state.code = parsed.code
        state.qr = parsed.qr
        state.remote_url = classified.remote
        state.lan_url = classified.lan
        state.created_at = now
        state.expires_at = now + PAIR_TTL
        M.update_pair_float(state)
      end)
    end,
  })

  if M._job <= 0 then
    M._job = nil
    M._state.kind = "error"
    M._state.error = "no se pudo ejecutar opencode pair"
    M.update_pair_float(M._state)
  end
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
      M._state = nil
      M.close_pair_float()
      vim.notify("Remote access disabled", vim.log.levels.INFO)
    else
      vim.notify("Failed to disable remote access: " .. out, vim.log.levels.ERROR)
    end
  end)
end

-- NOTE: `<leader>asi` — live pairing status. Reads the shared service's real state:
-- tunnel on → mint a fresh link and show the QR; tunnel off → say so and stop.
-- Never enables remote access; that is `<leader>ast`.
function M.show_info()
  M.get_service_state(function(state)
    if state.error then
      local error_state = { kind = "error", remote = false, links = {}, error = state.error }
      M._state = error_state
      M.open_pair_float(error_state)
      return
    end

    if state.tunnel then
      if M._job then
        notify_pair("Pairing ya en curso", vim.log.levels.INFO)
        return
      end
      M.pair(true)
      return
    end

    local off_state = { kind = "off", remote = false, links = {} }
    M._state = off_state
    M.open_pair_float(off_state)
  end)
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

-- NOTE: Query all sessions across projects directly from the OpenCode DB.
-- OpenCode V2 dropped the `opencode db` subcommand; `opencode session list` only lists
-- the current project, so direct DB access is required for the cross-project picker.
-- DB path comes from `opencode debug paths db` (~/.local/share/opencode/opencode.db).
local SESSION_COLUMNS = "id, title, directory, time_updated"

-- NOTE: OpenCode V2 migrated live sessions to `session_v2`; the legacy `session` table is
-- frozen at the migration date. Prefer `session_v2`, falling back to `session` on older DBs.
local SESSION_TABLE_QUERY = table.concat({
  "SELECT name FROM sqlite_master",
  "WHERE type = 'table' AND name IN ('session_v2', 'session')",
  "ORDER BY name = 'session_v2' DESC",
  "LIMIT 1;",
}, " ")

-- NOTE: Run a query and return its rows as JSON. Prefer the sqlite3 CLI and fall back to
-- Python's bundled sqlite3 module, since sqlite3 is not installed everywhere and
-- `vim.fn.system` raises E475 when the executable is missing.
local function query_db(db_path, sql)
  if vim.fn.executable("sqlite3") == 1 then
    local result = vim.fn.system({ "sqlite3", "-json", db_path, sql })
    return result, vim.v.shell_error
  end

  if vim.fn.executable("python3") == 1 then
    local script = table.concat({
      "import json, sqlite3, sys",
      "con = sqlite3.connect(sys.argv[1])",
      "cur = con.execute(sys.argv[2])",
      "cols = [d[0] for d in cur.description]",
      "print(json.dumps([dict(zip(cols, r)) for r in cur.fetchall()]))",
    }, "\n")
    local result = vim.fn.system({ "python3", "-c", script, db_path, sql })
    return result, vim.v.shell_error
  end

  return nil, 1
end

-- NOTE: Resolve the live session table, allowing only names read from sqlite_master.
local function session_table(db_path)
  local result, exit_code = query_db(db_path, SESSION_TABLE_QUERY)
  if exit_code ~= 0 or not result or result == "" then
    return "session"
  end
  local ok, data = pcall(vim.json.decode, result)
  if not ok or type(data) ~= "table" or type(data[1]) ~= "table" then
    return "session"
  end
  local name = data[1].name
  if name == "session_v2" or name == "session" then
    return name
  end
  return "session"
end

local function get_sessions()
  local sessions = {}
  local db_path = vim.fn.expand("~/.local/share/opencode/opencode.db")
  if vim.fn.filereadable(db_path) == 0 then
    vim.notify("OpenCode database not found: " .. db_path, vim.log.levels.WARN)
    return sessions
  end

  -- NOTE: Only top-level sessions, matching `opencode session list`.
  local sql = string.format(
    "SELECT %s FROM %s WHERE parent_id IS NULL ORDER BY time_updated DESC;",
    SESSION_COLUMNS,
    session_table(db_path)
  )
  local result, exit_code = query_db(db_path, sql)
  if not result or exit_code ~= 0 or result == "" then
    vim.notify("Cannot read OpenCode sessions: install `sqlite3` or `python3`", vim.log.levels.ERROR)
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
      M._state = nil
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
