return {
  {
    "sphamba/smear-cursor.nvim",
    cond = function()
      return vim.env.WT_SESSION ~= nil
    end,
    opts = {
      stiffness = 1.0,
      trailing_stiffness = 0.7,
      damping = 0.95,
      distance_stop_animating = 1.0,
      time_interval = 5,
    },
  },
}
