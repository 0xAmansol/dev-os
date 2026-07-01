-- Keybindings are the only place user input is captured and routed to
-- workspaces.lua. No git/devos-domain logic here — just wiring.
local wezterm = require("wezterm")
local act = wezterm.action
local workspaces = require("workspaces")

local M = {}

M.leader = { key = "a", mods = "CTRL", timeout_milliseconds = 1000 }

M.keys = {
	{
		key = "t",
		mods = "LEADER",
		action = act.PromptInputLine({
			description = "Start ticket (key):",
			action = wezterm.action_callback(function(_, _, line)
				if line and line ~= "" then
					workspaces.start_ticket(line)
				end
			end),
		}),
	},
	{
		key = "w",
		mods = "LEADER",
		action = act.PromptInputLine({
			description = "Close ticket (key):",
			action = wezterm.action_callback(function(_, _, line)
				if line and line ~= "" then
					workspaces.close_ticket(line)
				end
			end),
		}),
	},
	{
		key = "l",
		mods = "LEADER",
		action = act.SpawnCommandInNewTab({
			args = { "zsh", "-lc", "devos ticket list; exec zsh" },
		}),
	},
}

return M
