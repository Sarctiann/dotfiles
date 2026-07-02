return {
  "mini-nvim/mini.diff",
  config = function(_, opts)
    require("mini.diff").setup(opts)
    vim.api.nvim_set_hl(0, "MiniDiffSignAdd", { link = "Added" })
    vim.api.nvim_set_hl(0, "MiniDiffSignChange", { link = "NeoTreeGitModified" })
    vim.api.nvim_create_autocmd("ColorScheme", {
      group = vim.api.nvim_create_augroup("CustomMiniDiffHl", {}),
      callback = function()
        vim.api.nvim_set_hl(0, "MiniDiffSignAdd", { link = "Added" })
        vim.api.nvim_set_hl(0, "MiniDiffSignChange", { link = "NeoTreeGitModified" })
      end,
    })
  end,
}
