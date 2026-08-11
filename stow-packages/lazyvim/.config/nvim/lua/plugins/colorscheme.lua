return {
  "folke/tokyonight.nvim",
  lazy = false,
  priority = 1000,
  opts = {
    style = "night",
    transparent = true,
    styles = {
      sidebars = "dark",
      -- floats = "transparent",
    },
    on_highlights = function(hl, c)
      hl.MiniDiffSignAdd = { link = "Added" }
      hl.MiniDiffSignChange = { fg = c.orange }
    end,
  },
}
