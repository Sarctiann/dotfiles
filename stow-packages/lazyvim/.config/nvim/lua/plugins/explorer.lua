return {
  "folke/snacks.nvim",
  opts = {
    explorer = {
      replace_netrw = true,
    },
    picker = {
      sources = {
        explorer = {
          hidden = true,
          win = {
            list = {
              keys = {
                ["s"] = "confirm", -- toggle expand/collapse node
              },
            },
          },
        },
      },
    },
  },
}
