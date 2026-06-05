-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Add any additional autocmds here

-- Redirect `:edit`|`:e` from non-file windows (terminal, help, etc.) into the
-- first normal file window. This ensures MCP file-open tools and any agent
-- that sends `:e <path>` always open in a proper editor window automatically,
-- regardless of whether the agent remembered to focus first.
do
  local function is_edit_cmd(cmdline)
    if cmdline == "e" or cmdline == "edit" or cmdline == "e!" or cmdline == "edit!" then
      return true
    end
    if cmdline:match("^e[!]?%s") or cmdline:match("^edit[!]?%s") then
      return true
    end
    return false
  end

  local group = vim.api.nvim_create_augroup("EditRedirect", { clear = true })
  vim.api.nvim_create_autocmd("CmdlineLeave", {
    group = group,
    pattern = ":",
    callback = function()
      local cmdline = vim.fn.getcmdline() or ""
      if not is_edit_cmd(cmdline) then
        return
      end
      local cur_win = vim.api.nvim_get_current_win()
      local cur_buf = vim.api.nvim_win_get_buf(cur_win)
      if vim.bo[cur_buf].buftype == "" then
        return
      end
      for _, w in ipairs(vim.api.nvim_list_wins()) do
        local b = vim.api.nvim_win_get_buf(w)
        if vim.bo[b].buftype == "" and vim.api.nvim_buf_get_name(b) ~= "" then
          vim.api.nvim_set_current_win(w)
          return
        end
      end
    end,
  })
end

if not vim.g.vscode then
  -- Single source of truth for cursor behavior in Neovim and on exit
  local nvim_cursor =
    "n:block,c:ver30-CmdTermCursor,ci:ver30-CmdTermCursor,cr:ver30-CmdTermCursor,sm:block,i:ver30-CursorL,t:ver30-CmdTermCursor,v-ve-o:hor30-VisualCursor,r:hor50-ReplaceCursor,a:blinkon100"
  local exit_cursor = "a:ver30-blinkon100-blinkoff400-blinkon250"

  -- Create a single cursor autocommand group
  local cursor_group = vim.api.nvim_create_augroup("Custom-Cursor", { clear = true })

  -- Apply cursor config immediately (autocmds.lua is loaded on VeryLazy,
  -- so VimEnter may already have happened).
  vim.opt.guicursor = nvim_cursor

  -- Restore terminal cursor on exit
  vim.api.nvim_create_autocmd("VimLeave", {
    group = cursor_group,
    callback = function()
      vim.opt.guicursor = exit_cursor
    end,
  })

  -- Change the color of unused code highlight
  vim.api.nvim_create_autocmd({ "DiagnosticChanged" }, {
    group = cursor_group,
    callback = function()
      vim.api.nvim_command("highlight! link DiagnosticUnnecessary UnusedCode")
    end,
  })
end
