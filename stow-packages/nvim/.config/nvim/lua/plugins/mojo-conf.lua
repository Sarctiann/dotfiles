return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        mojo = {
          on_new_config = function(config)
            if vim.fn.executable("mojo-lsp-server") == 0 then
              vim.notify(
                "(Run `pixi shell` or `source .venv/bin/activate` depending on your setup before entering neovim)",
                vim.log.levels.WARN,
                { title = "MOJO LSP NOT STARTED", icon = "🚨", timeout = 10000 }
              )
              config.cmd = { "echo", "" }
              return
            end
          end,
        },
      },
    },
    init = function()
      vim.api.nvim_create_autocmd("FileType", {
        pattern = "mojo",
        callback = function()
          vim.bo.expandtab = true
          vim.bo.tabstop = 4
          vim.bo.shiftwidth = 4
          vim.bo.softtabstop = 4
        end,
      })
    end,
  },
  {
    "stevearc/conform.nvim",
    optional = true,
    opts = function(_, opts)
      opts.formatters = opts.formatters or {}
      opts.formatters.mojo_format = {
        command = "mojo",
        args = { "format", "$FILENAME" },
        stdin = false,
      }
      opts.formatters_by_ft = opts.formatters_by_ft or {}
      if not opts.formatters_by_ft.mojo then
        opts.formatters_by_ft.mojo = { "mojo_format" }
      elseif type(opts.formatters_by_ft.mojo) == "table" then
        local has_mojo = false
        for _, formatter in ipairs(opts.formatters_by_ft.mojo) do
          if formatter == "mojo_format" then
            has_mojo = true
            break
          end
        end
        if not has_mojo then
          table.insert(opts.formatters_by_ft.mojo, "mojo_format")
        end
      end
      return opts
    end,
  },
}
