local M = {}

-- WARN:
-- configure your nvim-mcp-server to work with auggie by going to the directory
-- where you have your augment cache dir and running this command in your terminal (only needs to be done once):
--    auggie --augment-cache-dir=.augment_work_profile mcp add nvim -- nvim-mcp --connect auto
-- It should result in the following entry in your ~/.gemini/settings.json file:
--   {
--     ...
--     "mcpServers": {
--       "nvim": {
--         "type": "stdio",
--         "command": "npx",
--         "args": [
--           "-y",
--           "nvim-mcp-server"
--          ],
--         "env": {
--           "NVIM": "$NVIM"
--         }
--       }
--     }
--     ...
--   }

-- NOTE: Helper function to get the augment cache directory
-- Returns the cache directory path based on current working directory and COMPANY_DIR
function M.get_augment_cache_dir()
  local current_dir = vim.fn.getcwd()
  local company_dir_str = os.getenv("COMPANY_DIR") or ""

  if company_dir_str ~= "" then
    local company_dir = vim.fn.expand(company_dir_str):gsub("/+$", "")
    if (current_dir .. "/"):sub(1, #company_dir + 1) == company_dir .. "/" then
      return company_dir .. "/.augment_work_profile"
    end
  end

  -- Default to standard augment directory if no company dir is found
  -- Return the user's standard augment dir so callers always get a usable path.
  return vim.fn.expand("~/.augment")
end

-- NOTE: Returns user-facing name based on current cache dir
-- "Augment<work>" when using company work profile, "Augment" otherwise
function M.get_display_name()
  local cache_dir = M.get_augment_cache_dir()
  if cache_dir:match("[/\\]%.augment_work_profile$") then
    return "Augment<work>"
  end
  return "Augment"
end

-- NOTE: Show a floating notification at bottom-right, auto-dismisses after 2s
-- Captures editor dimensions before any potential terminal split.
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
    end, 3500)
  end)
end

-- NOTE: Resume last session (opens terminal with -c flag)
-- @param cache_dir (optional) The augment cache directory path
function M.resume_last_session(cache_dir)
  cache_dir = cache_dir or M.get_augment_cache_dir()
  local name = M.get_display_name()
  local d = cache_dir:gsub(vim.fn.expand("~"), "~")
  M.show_notification(" " .. name .. " (profile: <" .. d .. ">) ")
  vim.cmd("CLIIntegration open_root Augment -c")
end

-- NOTE: New Augment session (opens terminal)
-- @param cache_dir (optional) The augment cache directory path
function M.new_session(cache_dir)
  cache_dir = cache_dir or M.get_augment_cache_dir()
  local name = M.get_display_name()
  local d = cache_dir:gsub(vim.fn.expand("~"), "~")
  M.show_notification(" " .. name .. " (profile: <" .. d .. ">) ")
  vim.cmd("CLIIntegration open_root Augment")
end

-- NOTE: Augment ask inline
-- @param cache_dir (optional) The augment cache directory path
function M.ask_inline(cache_dir)
  cache_dir = cache_dir or M.get_augment_cache_dir()
  local name = M.get_display_name()
  local d = cache_dir:gsub(vim.fn.expand("~"), "~")
  M.show_notification(" " .. name .. " (profile: <" .. d .. ">) ")
  require("cli-integration").hooks.ask("Augment")
end

-- NOTE: Function to delete all Augment sessions with confirmation
-- @param cache_dir (optional) The augment cache directory path. If nil, uses default or auto-detected path
function M.delete_all_augment_sessions(cache_dir)
  cache_dir = cache_dir or M.get_augment_cache_dir()
  local name = M.get_display_name()

  vim.ui.select({ "Yes", "No" }, {
    prompt = "⚠️  Delete ALL " .. name .. " sessions? This action cannot be undone!",
  }, function(choice)
    if choice == "Yes" then
      local esc = vim.fn.shellescape(cache_dir)
      local cmd = cache_dir and string.format("! auggie --augment-cache-dir=%s session delete --all", esc)
        or "! auggie session delete --all"
      vim.cmd(cmd)
      vim.notify("✓ All " .. name .. " sessions have been deleted", vim.log.levels.INFO)
    else
      vim.notify("Deletion cancelled", vim.log.levels.INFO)
    end
  end)
end

function M.resume_session(session_id)
  local term = require("cli-integration.terminal")
  local term_data = term.terminals["Augment"]
  if term_data and term_data.term_buf and vim.api.nvim_buf_is_valid(term_data.term_buf) then
    term.close_terminal(term_data.term_buf)
  end
  if session_id == "" then
    vim.cmd("CLIIntegration open_root Augment")
  else
    vim.cmd("CLIIntegration open_root Augment session resume " .. session_id)
  end
end

-- NOTE: Function to manage Augment sessions (Uses plugin hooks with Lazy Load)
-- @param show_all (optional) Whether to show all sessions or just current workspace
-- @param cache_dir (optional) The augment cache directory path. If nil, uses default or auto-detected path
function M.manage_augment_sessions(show_all, cache_dir)
  cache_dir = cache_dir or M.get_augment_cache_dir()
  local name = M.get_display_name()

  local sessions_dir = cache_dir and (cache_dir .. "/sessions") or vim.fn.expand("~/.augment/sessions")

  local resume_cmd = "lua require('utils.augment_utils').resume_session([[%s]])"

  require("cli-integration.hooks").manage_sessions({
    name = name,
    resume_cmd = resume_cmd,
    show_all = show_all,
    get_sessions = function()
      local sessions = {}
      local files = vim.fn.glob(sessions_dir .. "/*.json", false, true)

      for _, file_path in ipairs(files) do
        local f = io.open(file_path, "r")
        if f then
          local content = f:read("*all")
          f:close()
          local ok, data = pcall(vim.json.decode, content)

          if ok and data then
            local modified = data.modified or data.created or "Unknown"
            local session_id = data.sessionId or vim.fn.fnamemodify(file_path, ":t:r")

            local session_workspace = "Unknown"
            if data.chatHistory and #data.chatHistory > 0 then
              local first_exchange = data.chatHistory[1].exchange
              if first_exchange and first_exchange.request_nodes then
                for _, node in ipairs(first_exchange.request_nodes) do
                  if node.ide_state_node and node.ide_state_node.workspace_folders then
                    local folders = node.ide_state_node.workspace_folders
                    if folders[1] and folders[1].repository_root then
                      session_workspace = folders[1].repository_root
                      break
                    end
                  end
                end
              end
            end

            local first_message = "No messages"
            if data.chatHistory and #data.chatHistory > 0 then
              local exchange = data.chatHistory[1].exchange
              if exchange then
                -- Try to use customTitle first, fallback to request_message
                if data.customTitle and data.customTitle ~= "" then
                  first_message = data.customTitle:gsub("\n", " "):sub(1, 60)
                  if #data.customTitle > 60 then
                    first_message = '" ' .. first_message .. '... "'
                  else
                    first_message = '" ' .. first_message .. ' "'
                  end
                elseif exchange.request_message then
                  first_message = exchange.request_message:gsub("\n", " "):sub(1, 60)
                  if #exchange.request_message > 60 then
                    first_message = first_message .. "..."
                  end
                end
              end
            end

            local date = modified:match("(%d%d%d%d%-%d%d%-%d%d)") or "Unknown"
            local time = modified:match("T(%d%d:%d%d)") or ""

            table.insert(sessions, {
              id = session_id,
              modified = modified,
              workspace = session_workspace,
              file_path = file_path,
              display = string.format("[%s %s] %s", date, time, first_message),
            })
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

-- NOTE: Deploy work-profile config (skills, scripts, commands) to ~/.augment/
-- so Auggie discovers them. Reads from the work profile's directories (the source
-- of truth, not tracked in dotfiles). Auggie discovers skills/commands from
-- ~/.augment/ (not from --augment-cache-dir), so we copy them on every session open.
--
-- Deployed directories:
--   skills/   — flat .md files (Auggie looks for skills/<name>.md, not skills/<name>/SKILL.md)
--   scripts/  — shell scripts and other executables used by skills/hooks
--   commands/ — custom slash commands as flat .md files (~/.augment/commands/<name>.md)
--
-- AGENTS.md is NOT deployed — it already lives in the cache_dir and is read directly by auggie.
-- @param cache_dir string Path to the augment cache directory (e.g. $COMPANY_DIR/.augment_work_profile)
function M.deploy_work_profile_config(cache_dir)
  -- Helper: copy all files matching a glob pattern from a source subdirectory to a target dir
  -- @param source_subdir string  Subdirectory name under cache_dir (e.g. "skills")
  -- @param target_base string    Target base directory (e.g. "~/.augment")
  -- @param glob_pattern string   Glob pattern to match (e.g. "*.md", "*")
  local function deploy_dir(source_subdir, target_base, glob_pattern)
    local source = cache_dir .. "/" .. source_subdir
    if vim.fn.isdirectory(source) == 0 then
      return
    end
    local target = vim.fn.expand(target_base .. "/" .. source_subdir)
    vim.fn.mkdir(target, "p")
    for _, file in ipairs(vim.fn.glob(source .. "/" .. glob_pattern, false, true)) do
      local name = vim.fn.fnamemodify(file, ":t")
      vim.fn.system({ "cp", file, target .. "/" .. name })
    end
  end

  deploy_dir("skills", "~/.augment", "*.md")
  deploy_dir("scripts", "~/.augment", "*")
  deploy_dir("commands", "~/.augment", "*.md")
end

-- NOTE: Function to inject env vars into augment's settings.json MCP server config
-- @param cache_dir string Path to the augment cache directory (contains settings.json)
-- @param env_vars table Table with structure { mcp_server_name = { VAR = value } }
--   Overwrites matching variables or adds them if they don't exist
function M.on_open_auggie(cache_dir, env_vars)
  local settings_path = cache_dir .. "/settings.json"
  local f = io.open(settings_path, "r")
  if not f then
    vim.notify("on_open_auggie: could not open " .. settings_path, vim.log.levels.WARN)
    return
  end

  local content = f:read("*all")
  f:close()

  local ok, data = pcall(vim.json.decode, content)
  if ok and data then
    data.mcpServers = data.mcpServers or {}
    for server_name, vars in pairs(env_vars) do
      if data.mcpServers[server_name] then
        data.mcpServers[server_name].env = data.mcpServers[server_name].env or {}
        for var_name, value in pairs(vars) do
          data.mcpServers[server_name].env[var_name] = value
        end
      end
    end

    local new_content = vim.json.encode(data)
    local wf = io.open(settings_path, "w")
    if wf then
      wf:write(new_content)
      wf:close()
    else
      vim.notify("on_open_auggie: could not write " .. settings_path, vim.log.levels.ERROR)
    end
  else
    vim.notify("on_open_auggie: failed to parse settings.json", vim.log.levels.ERROR)
  end

  M.deploy_work_profile_config(cache_dir)
end

return M
