return {
  "petertriho/nvim-scrollbar",
  -- Remove this line after 2026-11-16, when v2 replaces v1 on main.
  branch = "refactor/v2",
  event = "BufReadPost",
  opts = {
    exclude = {
      filetypes = {
        help = true,
        snacks_dashboard = true,
        snacks_explorer = true,
        snacks_layout_box = true, -- explorer sidebar: normal window with this ft
        snacks_picker = true,
        snacks_picker_list = true,
        snacks_picker_preview = true,
        snacks_notifier = true,
        snacks_input = true,
        snacks_terminal = true,
        ["cli-integration"] = true,
        mason = true,
        lazy = true,
        lazyextras = true,
      },
    },
    providers = {
      gitsigns = false,
      mini_diff = true,
      search = false,
    },
    marks = {
      Cursor = { highlight = { fg = "#7086b5" } },
      Error = { highlight = "DiagnosticVirtualTextError" },
      Warn = { highlight = "DiagnosticVirtualTextWarn" },
      Info = { highlight = "DiagnosticVirtualTextInfo" },
      Hint = { highlight = "DiagnosticVirtualTextHint" },
      MiniDiffAdd = { text = "▎" },
      MiniDiffChange = { text = "▎" },
      MiniDiffDelete = { text = "▁" },
    },
    scrollbar = {
      unit = "screenline",
      thumb = {
        blend = 3,
      },
    },
  },
}
