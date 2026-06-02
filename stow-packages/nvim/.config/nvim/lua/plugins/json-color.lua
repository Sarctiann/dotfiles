vim.api.nvim_create_autocmd("LspAttach", {
  group = vim.api.nvim_create_augroup("json-color-fix", { clear = true }),
  desc = "Disable LSP documentColor for jsonls (nvim-colorizer handles it)",
  callback = function(args)
    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if client and client.name == "jsonls" then
      vim.lsp.document_color.enable(false, { client_id = client.id })
    end
  end,
})

return {
  {
    "neovim/nvim-lspconfig",
    opts = function(_, opts)
      opts.servers = opts.servers or {}
      opts.servers.jsonls = vim.tbl_deep_extend("force", opts.servers.jsonls or {}, {
        capabilities = {
          textDocument = {
            colorProvider = false,
          },
        },
      })
      return opts
    end,
  },
}
