local wezterm = require("wezterm")
local config = {}

config.color_scheme = "TokyoNight Night"
config.font = wezterm.font("CodeNewRoman Nerd Font Propo")
config.font_size = 13.0
config.line_height = 1.1

config.window_decorations = "RESIZE"
config.window_background_opacity = 0.90
config.macos_window_background_blur = 10
config.initial_cols = 120
config.initial_rows = 35
config.maximize_initial = true

config.hide_tab_bar_if_only_one_tab = true
config.tab_bar_at_bottom = true
config.use_fancy_tab_bar = false

config.audible_bell = "Disabled"
config.default_cursor_style = "BlinkingBar"

config.leader = { key = "a", mods = "CTRL", timeout_milliseconds = 1000 }
config.keys = {
  { key = "|", mods = "LEADER", action = wezterm.action.SplitHorizontal({ domain = "CurrentPaneDomain" }) },
  { key = "-", mods = "LEADER", action = wezterm.action.SplitVertical({ domain = "CurrentPaneDomain" }) },
  { key = "h", mods = "LEADER", action = wezterm.action.ActivatePaneDirection("Left") },
  { key = "j", mods = "LEADER", action = wezterm.action.ActivatePaneDirection("Down") },
  { key = "k", mods = "LEADER", action = wezterm.action.ActivatePaneDirection("Up") },
  { key = "l", mods = "LEADER", action = wezterm.action.ActivatePaneDirection("Right") },
  { key = "z", mods = "LEADER", action = wezterm.action.TogglePaneZoomState },
}

config.default_prog = { "tmux", "new-session", "-A", "-D", "-s", "main" }

local local_config = wezterm.config_builder()
local success, err = pcall(dofile, wezterm.config_dir .. "/local.lua")
if success then
  err(local_config)
end

return wezterm.merge(config, local_config)
