return {
  "petertriho/nvim-scrollbar",
  event = "BufReadPost",
  opts = {
    handle = {
      blend = 3,
    },
    marks = {
      Cursor = {
        color = "#7086b5",
      },
      -- NOTE: normalize colors
      Error = { highlight = "DiagnosticVirtualTextError" },
      Warn = { highlight = "DiagnosticVirtualTextWarn" },
      Info = { highlight = "DiagnosticVirtualTextInfo" },
      Hint = { highlight = "DiagnosticVirtualTextHint" },
      GitAdd = { text = "▎", highlight = "MiniDiffSignAdd" },
      GitChange = { text = "▎", highlight = "MiniDiffSignChange" },
      GitDelete = { text = "▁", highlight = "MiniDiffSignDelete" },
    },
    handlers = {
      gitsigns = false,
      search = false,
    },
    excluded_filetypes = {
      "terminal",
      "help",
      "snacks_dashboard",
      "snacks_picker",
      "snacks_notifier",
      "snacks_input",
      "snacks_terminal",
      "neo-tree",
      "neotree",
      "NvimTree",
      "TelescopePrompt",
      "cli-integration",
    },
  },
  config = function(_, opts)
    require("scrollbar").setup(opts)

    local ok, minidiff = pcall(require, "mini.diff")
    if not ok then
      return
    end

    local handlers = require("scrollbar.handlers")
    local config = require("scrollbar.config").get()

    handlers.register("gitsigns", function(bufnr)
      local data = minidiff.get_buf_data(bufnr)
      if not data or not data.hunks then
        return {}
      end

      local marks = {}

      for _, hunk in ipairs(data.hunks) do
        if hunk.type == "add" then
          for line = hunk.buf_start, hunk.buf_start + hunk.buf_count - 1 do
            table.insert(marks, {
              line = line - 1,
              text = config.marks.GitAdd.text,
              type = "GitAdd",
              level = 1,
            })
          end
        elseif hunk.type == "change" then
          for line = hunk.buf_start, hunk.buf_start + hunk.buf_count - 1 do
            table.insert(marks, {
              line = line - 1,
              text = config.marks.GitChange.text,
              type = "GitChange",
              level = 1,
            })
          end
        elseif hunk.type == "delete" then
          table.insert(marks, {
            line = hunk.buf_start - 1,
            text = config.marks.GitDelete.text,
            type = "GitDelete",
            level = 1,
          })
        end
      end

      return marks
    end)

    vim.api.nvim_create_autocmd("User", {
      pattern = "MiniDiffUpdated",
      group = vim.api.nvim_create_augroup("ScrollbarMiniDiff", {}),
      callback = function()
        handlers.show()
        require("scrollbar").throttled_render()
      end,
    })
  end,
}
