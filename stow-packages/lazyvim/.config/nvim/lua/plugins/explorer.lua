local function explorer_toggle(picker, item)
  if not item then
    return
  end
  local Tree = require("snacks.explorer.tree")
  local actions = require("snacks.explorer.actions")
  if item.dir then
    Tree:toggle(item.file)
    actions.update(picker, { refresh = true })
  else
    local dir = vim.fs.dirname(item.file)
    Tree:close(dir)
    actions.update(picker, { target = dir, refresh = true })
  end
end

local function explorer_del_perm(picker)
  local actions = require("snacks.explorer.actions")
  local Tree = require("snacks.explorer.tree")
  local paths = vim.tbl_map(Snacks.picker.util.path, picker:selected({ fallback = true }))
  if #paths == 0 then
    return
  end
  local what = #paths == 1 and vim.fn.fnamemodify(paths[1], ":p:~:.") or #paths .. " files"
  Snacks.picker.util.confirm("Permanently delete " .. what .. "?", function()
    for _, path in ipairs(paths) do
      local ok, err = pcall(vim.fn.delete, path, "rf")
      if not ok or err ~= 0 then
        Snacks.notify.error("Failed to delete `" .. path .. "`:\n" .. tostring(err))
      else
        Snacks.bufdelete({ file = path, force = true })
      end
      Tree:refresh(vim.fs.dirname(path))
    end
    picker.list:set_selected()
    actions.update(picker)
  end)
end

return {
  "folke/snacks.nvim",
  opts = {
    explorer = {
      replace_netrw = true,
    },
    picker = {
      sources = {
        explorer = {
          ignored = true,
          hidden = true,
          actions = {
            explorer_toggle = explorer_toggle,
            explorer_del_perm = explorer_del_perm,
          },
          win = {
            list = {
              keys = {
                ["s"] = "explorer_toggle", -- toggle expand/collapse node
                ["D"] = "explorer_del_perm", -- permanent delete (skip trash)
              },
            },
          },
        },
      },
    },
  },
}
