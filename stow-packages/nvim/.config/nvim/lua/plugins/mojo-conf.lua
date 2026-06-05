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
          -- NOTE: Capture the terminal's window handle at TermOpen time.
          -- vim.schedule runs later when the user may have switched windows,
          -- making nvim_get_current_win() unreliable for window checks.
          local term_win = vim.api.nvim_get_current_win()

          -- Parse the terminal buffer name to identify the running command.
          -- Format: term://cwd//pid:command
          -- Only activate for known interactive shells (zsh, bash, etc.),
          -- not for AI integration panels, custom command runners, etc.
          local buf_name = vim.api.nvim_buf_get_name(buf)
          local cmd_in_name = buf_name:match(":([^:]+)$")
          if cmd_in_name then
            local cmd_base = vim.fn.fnamemodify(cmd_in_name, ":t")
            local known_shells = { "zsh", "bash", "fish", "sh", "dash", "ksh" }
            local is_shell = false
            for _, s in ipairs(known_shells) do
              if cmd_base == s then
                is_shell = true
                break
              end
            end
            if not is_shell then
              return
            end
          end

          vim.schedule(function()
            -- Skip floating windows (filepickers, popup terminals)
            local win_config = vim.api.nvim_win_get_config(term_win)
            if win_config.relative ~= "" then
              return
            end

            local channel = vim.bo[buf].channel
            if not channel or channel <= 0 then
              return
            end

            -- NOTE: vim.fn.getcwd() respects :lcd window-local dirs,
            -- so the terminal opens in the same directory the user sees.
            local env = require("utils.mojo-env").activate_in_terminal(channel, vim.fn.getcwd())
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
