-- Ticket vs ops workspace definitions (§2.3 rule 1). This is the only place
-- that shells out to the `devos` CLI to drive ticket lifecycle, then renders
-- the resulting worktree as a dedicated workspace with a fixed pane layout.
-- It never touches git, state files, or SQL directly — that all lives in
-- devos itself.
local wezterm = require("wezterm")
local mux = wezterm.mux

local M = {}

local function run_devos(args)
	local ok, stdout, stderr = wezterm.run_child_process(args)
	return ok, stdout or "", stderr or ""
end

function M.start_ticket(key)
	local ok, stdout, stderr = run_devos({ "devos", "ticket", "start", key })
	if not ok then
		wezterm.log_error("devos ticket start failed: " .. stderr .. stdout)
		return
	end

	local worktree_path = stdout:match("at%s+(%S.-)%s*$")
	if not worktree_path then
		wezterm.log_error("devos: could not parse worktree path from: " .. stdout)
		return
	end

	local _, editor_pane, window = mux.spawn_window({
		workspace = key,
		cwd = worktree_path,
	})
	local agent_pane = editor_pane:split({ direction = "Right", size = 0.5, cwd = worktree_path })
	agent_pane:split({ direction = "Bottom", size = 0.3, cwd = worktree_path })

	mux.set_active_workspace(key)
end

function M.close_ticket(key)
	local ok, stdout, stderr = run_devos({ "devos", "ticket", "close", key })
	if not ok then
		wezterm.log_error("devos ticket close failed: " .. stderr .. stdout)
		return
	end

	for _, window in ipairs(mux.all_windows()) do
		if window:get_workspace() == key then
			window:close()
		end
	end
end

return M
