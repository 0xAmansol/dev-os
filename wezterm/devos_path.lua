-- Resolves the absolute path to the `devos` executable. WezTerm's child
-- processes don't inherit an interactively-activated venv PATH, so we can't
-- rely on `devos` being findable on $PATH.
local wezterm = require("wezterm")

local M = {}

function M.bin()
	local wezterm_dir = wezterm.config_file:match("(.*/)")
	return wezterm_dir .. "../.venv/bin/devos"
end

return M
