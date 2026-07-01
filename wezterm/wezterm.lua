-- dev-os WezTerm entrypoint. Self-contained: launch explicitly with
--   wezterm --config-file /path/to/dev-os/wezterm/wezterm.lua
-- This does not touch or depend on your personal ~/.config/wezterm setup.
local wezterm = require("wezterm")
local config = wezterm.config_builder()

-- WezTerm only auto-adds the *default* config dir to package.path. Since this
-- config is launched via `--config-file` from an arbitrary location, sibling
-- requires would otherwise fail silently. Add this file's own directory.
-- (WezTerm's Lua sandbox has no `debug.getinfo`, so use wezterm.config_file.)
local this_dir = wezterm.config_file:match("(.*/)")
package.path = this_dir .. "?.lua;" .. package.path

local keybindings = require("keybindings")
local launch_menu = require("launch_menu")

config.leader = keybindings.leader
config.keys = keybindings.keys
config.launch_menu = launch_menu.entries

return config
