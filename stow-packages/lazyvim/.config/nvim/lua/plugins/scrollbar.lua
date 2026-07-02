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
      Error = { color = "#f52a65" },
      Warn = { color = "#ffc777" },
      Info = { color = "#007197" },
      Hint = { color = "#9854f1" },
      GitAdd = { text = "▎", color = "#9ece6a" },
      GitChange = { text = "▎", color = "#ff9e64" },
      GitDelete = { text = "▁", color = "#f7768e" },
    },
    -- NOTE: hola
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
  end,
}
