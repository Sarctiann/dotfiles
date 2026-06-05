return {
  {
    "neovim/nvim-lspconfig",
    -- NOTE: Intentionally empty. LazyVim's opts.servers pipeline
    -- strips on_new_config from unknown servers, so we register
    -- mojo directly via lspconfig.mojo.setup() in init.
    opts = {
      servers = {},
    },
    init = function()
      -- NOTE: vim.schedule defers this until after all plugins are loaded.
      -- Avoids a "Snacks global not found" error that occurs when
      -- require("lspconfig") runs during lazy.nvim's spec processing.
      vim.schedule(function()
        pcall(function()
          require("lspconfig").mojo.setup({
            on_new_config = function(config)
              -- NOTE: Override the default cmd with the full binary path.
              -- This gives mojo-lsp-server a correct argv[0] so it can
              -- resolve its std library relative to its own location
              -- (../lib/mojo/std.mojopkg).
              local cmd = require("utils.mojo-env").get_lsp_cmd()
              if cmd then
                config.cmd = cmd
              end
            end,
          })
        end)
      end)

      -- NOTE: BufReadPre fires before FileType. This gives us a chance
      -- to set PATH / MODULAR_HOME before lspconfig's FileType handler
      -- (which runs via vim.schedule) tries to start mojo-lsp-server.
      vim.api.nvim_create_autocmd({ "BufReadPre", "BufNewFile" }, {
        pattern = "*.mojo",
        callback = function()
          require("utils.mojo-env").find_and_activate()
        end,
      })

      -- NOTE: TermOpen fires when a terminal buffer is created.
      -- We detect the mojo env from the terminal's cwd and source
      -- the activation script automatically — exactly like VSCode
      -- does when it auto-activates the Python env in the integrated
      -- terminal. This makes `mojo`, `mojo-lsp-server`, etc. available
      -- without the user needing to run `pixi shell` manually.
      --
      -- Restricted to regular shell terminals only (not filepicker popups,
      -- AI integration panels, or other non-shell terminal buffers).
      vim.api.nvim_create_autocmd("TermOpen", {
        callback = function()
          local buf = vim.api.nvim_get_current_buf()

          vim.schedule(function()
            local win = vim.api.nvim_get_current_win()

            -- Skip floating windows (filepickers, popup terminals) and narrow
            -- side panels (< 40% of editor width) which are typically AI
            -- integration panels rather than user-invoked terminals.
            local win_config = vim.api.nvim_win_get_config(win)
            if win_config.relative ~= ''
              or vim.api.nvim_win_get_width(win) < vim.o.columns * 0.4
            then
              return
            end
            local channel = vim.bo[buf].channel
            if not channel or channel <= 0 then
              return
            end

            -- Only activate in regular shell terminals (not AI integration
            -- panels running opencode / gemini / auggie, etc.)
            local ok, info = pcall(vim.fn.job_info, channel)
            if ok and info and info.cmd and #info.cmd > 0 then
              local shell = vim.fn.fnamemodify(vim.o.shell, ":t")
              local cmd = vim.fn.fnamemodify(info.cmd[1], ":t")
              if cmd ~= shell then
                return
              end
            end

            -- NOTE: vim.fn.getcwd() respects :lcd window-local dirs,
            -- so the terminal opens in the same directory the user sees.
            local env = require("utils.mojo-env").activate_in_terminal(
              channel,
              vim.fn.getcwd()
            )
            if env then
              vim.notify(
                "Terminal activated [" .. env.type .. "]",
                vim.log.levels.INFO,
                { title = "MOJO", timeout = 2000 }
              )
            end
          end)
        end,
      })

      vim.api.nvim_create_autocmd("FileType", {
        pattern = "mojo",
        callback = function()
          vim.bo.expandtab = true
          vim.bo.tabstop = 4
          vim.bo.shiftwidth = 4
          vim.bo.softtabstop = 4

          local mojo_env = require("utils.mojo-env")
          if mojo_env.get_active() then
            vim.notify(
              "Mojo LSP ready [" .. mojo_env.get_active().type .. "]",
              vim.log.levels.INFO,
              { title = "MOJO", timeout = 2000 }
            )
          else
            -- NOTE: vim.schedule avoids the notification being swallowed
            -- when called during a buffer event callback.
            vim.schedule(function()
              vim.notify(
                "No env found. Run `pixi shell` / `source .venv/bin/activate` before neovim.",
                vim.log.levels.WARN,
                { title = "MOJO LSP NOT FOUND", timeout = 10000 }
              )
            end)
          end
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
        -- NOTE: Resolves the mojo binary path from the active env,
        -- same strategy as mojo-lsp-server. Falls back to "mojo"
        -- (PATH lookup) if no env is active.
        command = function()
          return require("utils.mojo-env").get_mojo_cmd() or "mojo"
        end,
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
  {
    "nvim-treesitter/nvim-treesitter",
    opts = function(_, opts)
      -- Register custom Mojo parser (not in nvim-treesitter's official registry).
      -- NOTE: nvim-treesitter was rewritten in Apr 2026 (Neovim 0.12+). The old
      -- get_parser_configs() API no longer exists. Instead we mutate the parsers
      -- table directly (which is cached by require).
      local parsers = require("nvim-treesitter.parsers")
      parsers.mojo = {
        install_info = {
          url = "https://github.com/oaustegard/tree-sitter-mojo",
          files = { "src/parser.c", "src/scanner.c" },
        },
        filetype = "mojo",
      }

      if type(opts.ensure_installed) == "table" then
        vim.list_extend(opts.ensure_installed, { "mojo" })
      end
    end,
  },
}
