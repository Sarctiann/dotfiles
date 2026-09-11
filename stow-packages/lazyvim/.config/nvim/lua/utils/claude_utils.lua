local M = {}

-- WARN:
-- Claude Code stores its config/sessions in a *config dir*, controlled by the
-- CLAUDE_CONFIG_DIR env var. By default that is ~/.claude. When running inside
-- a company project, these utils use $COMPANY_DIR/.claude_work_profile so work
-- settings, MCP servers, and sessions stay separate from personal use.
--
-- Make nvim-mcp-server available inside a config dir by running once:
--     claude mcp add nvim -s user -e NVIM=\$NVIM -- "npx" -y nvim-mcp-server
-- (personal: default config dir; work profile: run with CLAUDE_CONFIG_DIR set).
-- It adds an entry to <config_dir>/settings.json:
--   {
--     "mcpServers": {
--       "nvim": {
--         "type": "stdio",
--         "command": "npx",
--         "args": ["-y", "nvim-mcp-server"],
--         "env": { "NVIM": "$NVIM" }
--       }
--     }
--   }

-- NOTE: True when the current working directory lives inside $COMPANY_DIR.
-- Mirrors the static check used by cli-integration.lua so tools can decide
-- between the work profile and the default ~/.claude config dir.
function M.is_company_project()
  local company_dir_str = os.getenv("COMPANY_DIR") or ""
  if company_dir_str == "" then
    return false
  end
  local company_dir = vim.fn.expand(company_dir_str):gsub("/+$", "")
  local current_dir = vim.fn.getcwd()
  return (current_dir .. "/"):sub(1, #company_dir + 1) == company_dir .. "/"
end

-- NOTE: Resolve the Claude Code config dir based on the current workspace.
-- Company projects use a dedicated work profile (like Augment), everything
-- else uses the standard ~/.claude directory.
function M.get_claude_config_dir()
  if M.is_company_project() then
    local company_dir = vim.fn.expand(os.getenv("COMPANY_DIR") or ""):gsub("/+$", "")
    return company_dir .. "/.claude_work_profile"
  end
  return vim.fn.expand("~/.claude")
end

-- NOTE: User-facing name based on the resolved config dir.
-- "Claude<work>" when using the company work profile, "Claude" otherwise.
function M.get_display_name()
  if M.is_company_project() then
    return "Claude<work>"
  end
  return "Claude"
end

-- NOTE: Shell command used by cli-integration to launch Claude Code.
-- Sets CLAUDE_CONFIG_DIR so the session reads/writes the right profile.
function M.get_cli_cmd()
  if M.is_company_project() then
    local cfg = M.get_claude_config_dir()
    return "env CLAUDE_CONFIG_DIR=" .. vim.fn.shellescape(cfg) .. " claude"
  end
  return "claude"
end

-- NOTE: Floating notification at bottom-right, auto-dismisses.
-- @param msg string The message to display
function M.show_notification(msg)
  local cols = vim.o.columns
  local lines = vim.o.lines
  local width = #msg
  vim.schedule(function()
    local buf = vim.api.nvim_create_buf(false, true)
    if buf == 0 or not buf then
      return
    end
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { msg })
    local win = vim.api.nvim_open_win(buf, false, {
      relative = "editor",
      width = width,
      height = 1,
      row = lines - 4,
      col = cols - width - 2,
      style = "minimal",
      border = "rounded",
      focusable = false,
    })
    if not win then
      pcall(vim.api.nvim_buf_delete, buf, { force = true })
      return
    end
    vim.defer_fn(function()
      pcall(vim.api.nvim_win_close, win, true)
      pcall(vim.api.nvim_buf_delete, buf, { force = true })
    end, 3000)
  end)
end

-- NOTE: Show which profile is active before running a session action.
local function announce()
  local cfg = M.get_claude_config_dir()
  local d = cfg:gsub(vim.fn.expand("~"), "~")
  M.show_notification(" " .. M.get_display_name() .. " (profile: <" .. d .. ">) ")
end

-- NOTE: New Claude session (opens terminal)
function M.new_session()
  announce()
  vim.cmd("CLIIntegration open_root Claude")
end

-- NOTE: Resume the most recent Claude conversation in the current directory
function M.resume_last_session()
  announce()
  vim.cmd("CLIIntegration open_root Claude --continue")
end

-- NOTE: Claude ask inline
function M.ask_inline()
  announce()
  require("cli-integration").hooks.ask("Claude")
end

-- NOTE: Convert a UTC ISO-8601 timestamp to local date and time strings.
-- os.time() treats a time table as *local* time, so feeding UTC values yields
-- an epoch shifted by the UTC offset. Adding the offset back gives the true UTC
-- epoch; os.date() then renders it in the system's local timezone.
local function parse_timestamp_local(utc_timestamp)
  local year, month, day, hour, min =
    utc_timestamp:match("(%d+)-(%d+)-(%d+)T(%d+):(%d+)")
  if not year then
    return "Unknown", ""
  end

  -- Compute current UTC offset in seconds (e.g. -10800 for UTC-3)
  local now = os.time()
  local utc_offset = (tonumber(os.date("%H", now)) - tonumber(os.date("!%H", now))) * 3600
    + (tonumber(os.date("%M", now)) - tonumber(os.date("!%M", now))) * 60
  if utc_offset > 43200 then
    utc_offset = utc_offset - 86400
  elseif utc_offset < -43200 then
    utc_offset = utc_offset + 86400
  end

  local pseudo_epoch = os.time({
    year = tonumber(year) or 0,
    month = tonumber(month) or 0,
    day = tonumber(day) or 0,
    hour = tonumber(hour) or 0,
    min = tonumber(min) or 0,
    sec = 0,
    isdst = false,
  })
  local true_utc_epoch = pseudo_epoch + utc_offset
  return os.date("%Y-%m-%d", true_utc_epoch), os.date("%H:%M", true_utc_epoch)
end

-- NOTE: Extract the first user prompt from a Claude transcript line.
-- v2.x transcripts log `message.content` either as a plain string or as an
-- array of content blocks ({ type = "text", text = ... }). Meta entries
-- (tool results, auto summaries) are skipped so we don't surface garbage.
-- @param data table Decoded JSONL entry
-- @param fallback string Current value (only replaced while it's a placeholder)
-- @return string First message preview
local function extract_first_message(data, fallback)
  if data.type == "custom-title" and data.customTitle then
    return '" ' .. string.upper(data.customTitle) .. ' "'
  end
  if
    (fallback == "No messages" or fallback == "<Message Content Too Complex>")
    and data.type == "user"
    and not data.isMeta
    and data.message
  then
    local content = data.message.content
    local text
    if type(content) == "string" then
      text = content
    elseif type(content) == "table" then
      local parts = {}
      for _, block in ipairs(content) do
        if type(block) == "string" then
          parts[#parts + 1] = block
        elseif type(block) == "table" and block.type == "text" and type(block.text) == "string" then
          parts[#parts + 1] = block.text
        end
      end
      if #parts > 0 then
        text = table.concat(parts, " ")
      end
    end
    if type(text) == "string" and text ~= "" then
      local preview = text:gsub("\n", " "):sub(1, 40)
      if #text > 40 then
        preview = preview .. "..."
      end
      return preview
    elseif text == nil then
      return "<Message Content Too Complex>"
    end
  end
  return fallback
end

-- NOTE: Function to delete Claude sessions (current project or all, config-dir
-- aware). Sessions are transcript JSONL files under <config_dir>/projects/.
-- @param config_dir (optional) Resolved from workspace when nil
function M.delete_all_claude_sessions(config_dir)
  config_dir = config_dir or M.get_claude_config_dir()
  local base_dir = config_dir .. "/projects"
  local current_path = require("cli-integration.hooks").get_current_workspace()
  local project_dir_name = current_path:gsub("[/._]", "-")
  local project_dir = base_dir .. "/" .. project_dir_name

  local options = { "Current Project Only", "ALL Projects", "Cancel" }
  vim.ui.select(options, { prompt = "⚠️ Delete Claude sessions?" }, function(choice)
    if not choice or choice == "Cancel" then
      return
    end
    local session_files = (choice == "Current Project Only") and vim.fn.glob(project_dir .. "/*.jsonl", false, true)
      or vim.fn.glob(base_dir .. "/*/*.jsonl", false, true)

    if #session_files == 0 then
      vim.notify("No Claude sessions found", vim.log.levels.INFO)
      return
    end

    vim.ui.select({ "Yes, Delete " .. #session_files .. " sessions", "No, Cancel" }, {
      prompt = "Confirm: Delete ALL " .. #session_files .. " sessions?",
    }, function(confirm)
      if confirm and confirm:match("^Yes") then
        for _, file in ipairs(session_files) do
          vim.fn.delete(file)
        end
        vim.notify("✓ Sessions deleted", vim.log.levels.INFO)
      end
    end)
  end)
end

-- NOTE: Claude session manager (Uses plugin hooks with Lazy Load)
-- @param show_all (optional) Whether to show all sessions or just current workspace
-- @param config_dir (optional) Resolved from workspace when nil
function M.manage_claude_sessions(show_all, config_dir)
  config_dir = config_dir or M.get_claude_config_dir()
  local base_dir = config_dir .. "/projects"
  local name = M.get_display_name()
  local hooks = require("cli-integration.hooks")

  hooks.manage_sessions({
    name = name,
    resume_cmd = "CLIIntegration open_root Claude --resume %s",
    show_all = show_all,
    get_sessions = function()
      local sessions = {}
      local current_ws = hooks.get_current_workspace()
      local current_ws_dir = current_ws:gsub("[/._]", "-")
      local project_dirs = vim.fn.glob(base_dir .. "/*", false, true)
      for _, dir in ipairs(project_dirs) do
        if vim.fn.isdirectory(dir) == 1 then
          local project_name = vim.fn.fnamemodify(dir, ":t")
          -- Claude encodes paths as dir names by replacing "/" with "-", which is ambiguous
          -- (can't distinguish path separators from actual dashes in dir names).
          -- Use the real workspace path only when we can confirm the match; otherwise keep raw dir name.
          local workspace_path = (project_name == current_ws_dir) and current_ws or project_name

          local files = vim.fn.glob(dir .. "/*.jsonl", false, true)
          for _, file_path in ipairs(files) do
            local f = io.open(file_path, "r")
            if f then
              local last_updated = "0000-00-00"
              local first_message = "No messages"
              local session_id = vim.fn.fnamemodify(file_path, ":t:r")

              for line in f:lines() do
                local ok, data = pcall(vim.json.decode, line)
                if ok and data then
                  if data.timestamp then
                    last_updated = data.timestamp
                  end
                  first_message = extract_first_message(data, first_message)
                end
              end
              f:close()

              local date, time = parse_timestamp_local(last_updated)
              local display_project = project_name:gsub("^%-", "")
              if #display_project > 30 then
                display_project = "..." .. display_project:sub(-27)
              end

              table.insert(sessions, {
                id = session_id,
                modified = last_updated,
                workspace = workspace_path,
                file_path = file_path,
                display = string.format("[%s %s] (%s) %s", date, time, display_project, first_message),
              })
            end
          end
        end
      end
      return sessions
    end,
    delete_cmd = function(session)
      vim.fn.delete(session.file_path)
      vim.notify("✓ Session deleted: " .. session.id, vim.log.levels.INFO)
    end,
  })
end

-- NOTE: Called from cli-integration's on_open hook for Claude sessions.
-- Ensures the work profile exists and that the nvim MCP server is configured
-- with the live Neovim socket (mirrors augment_utils.on_open_auggie). Also
-- creates <config_dir>/settings.json from scratch when it is missing.
-- @param config_dir (optional) Resolved from workspace when nil
function M.on_open_claude(config_dir)
  config_dir = config_dir or M.get_claude_config_dir()
  vim.fn.mkdir(config_dir, "p")

  local settings_path = config_dir .. "/settings.json"
  local data = {}
  local f = io.open(settings_path, "r")
  if f then
    local content = f:read("*all")
    f:close()
    local ok, decoded = pcall(vim.json.decode, content)
    if ok and type(decoded) == "table" then
      data = decoded
    end
  end

  local nvim_soc = os.getenv("NVIM") or vim.v.servername or ""
  data.mcpServers = data.mcpServers or {}
  data.mcpServers.nvim = {
    type = "stdio",
    command = "npx",
    args = { "-y", "nvim-mcp-server" },
    env = { NVIM = nvim_soc },
  }

  local wf = io.open(settings_path, "w")
  if wf then
    wf:write(vim.json.encode(data))
    wf:close()
  else
    vim.notify("claude_utils: could not write " .. settings_path, vim.log.levels.ERROR)
  end
end

return M