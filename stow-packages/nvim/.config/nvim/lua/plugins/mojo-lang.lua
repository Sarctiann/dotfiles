local DOCS_DIR = os.getenv("DOCS_DIR")
local plugin_dir = DOCS_DIR and (DOCS_DIR .. "/SARCTIANN/LuaCode/custom_plugins/mojo.nvim/") or nil

return {
  --- @module 'mojo'
  {
    "Sarctiann/mojo.nvim",
    dev = true,
    dir = plugin_dir,
    main = "mojo",
    opts = {
      filetype = { enabled = true },
      treesitter = { enabled = true },
      lsp = { enabled = true },
      format = { enabled = true },
      terminal = { enabled = true, auto_activate = true },
    },
  },
}
