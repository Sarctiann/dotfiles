local DOCS_DIR = os.getenv("DOCS_DIR")
local plugin_dir = DOCS_DIR and (DOCS_DIR .. "/SARCTIANN/LuaCode/custom_plugins/mojo.nvim/") or nil

local plugin_spec = {
  --- @module "mojo"
  {
    "Sarctiann/mojo.nvim",
    main = "mojo",
    --- @type Mojo-lang.Config
    opts = {
      statusline = {
        -- Lazyvim already comes with Trouble
        show_diag = false,
      },
    },
  },
}

if plugin_dir and vim.fn.isdirectory(plugin_dir) == 1 then
  plugin_spec[1].dev = true
  plugin_spec[1].dir = plugin_dir
end

return plugin_spec
