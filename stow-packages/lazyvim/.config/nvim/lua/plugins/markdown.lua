return {
  {
    "stevearc/conform.nvim",
    optional = true,
    opts = function(_, opts)
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      opts.formatters_by_ft.markdown = { "prettier" }
      opts.formatters = opts.formatters or {}
      opts.formatters.prettier = { prepend_args = { "--prose-wrap", "always", "--print-width", "80" } }
      return opts
    end,
  },
}
