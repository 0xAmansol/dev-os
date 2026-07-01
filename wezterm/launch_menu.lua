-- Declarative launch menu entries. Each one maps directly to a `devos` CLI
-- invocation and nothing else — no logic belongs in this file (§2.3 rule 1).
local devos_path = require("devos_path")

local M = {}

M.entries = {
	{ label = "devos: ticket list", args = { "zsh", "-lc", devos_path.bin() .. " ticket list; exec zsh" } },
	{ label = "devos: status", args = { "zsh", "-lc", devos_path.bin() .. " status; exec zsh" } },
}

return M
