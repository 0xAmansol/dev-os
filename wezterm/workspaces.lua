-- Ticket vs ops workspace definitions (§2.3 rule 1). This is the only place
-- that shells out to the `devos` CLI to drive ticket lifecycle, then renders
-- the resulting worktree as a dedicated workspace with a fixed pane layout.
-- It never touches git, state files, or SQL directly — that all lives in
-- devos itself.
local wezterm = require("wezterm")
local mux = wezterm.mux
local devos_path = require("devos_path")

local M = {}

-- WezTerm's run_child_process doesn't run in the calling pane's cwd, so we
-- explicitly `cd` into it via a shell wrapper before invoking devos.
local function run_devos(args, cwd)
	local shell_cmd = "cd " .. wezterm.shell_quote_arg(cwd) .. " && " .. wezterm.shell_quote_arg(devos_path.bin())
	for _, a in ipairs(args) do
		shell_cmd = shell_cmd .. " " .. wezterm.shell_quote_arg(a)
	end
	local ok, stdout, stderr = wezterm.run_child_process({ "zsh", "-lc", shell_cmd })
	return ok, stdout or "", stderr or ""
end

local function pane_cwd(pane)
	local cwd_url = pane:get_current_working_dir()
	return cwd_url and cwd_url.file_path or nil
end

function M.start_ticket(window, pane, key)
	local cwd = pane_cwd(pane)
	if not cwd then
		window:toast_notification("devos", "Could not determine the current pane's working directory.", nil, 4000)
		return
	end

	local ok, stdout, stderr = run_devos({ "ticket", "start", key }, cwd)
	if not ok then
		window:toast_notification("devos", "ticket start failed: " .. stderr .. stdout, nil, 5000)
		return
	end

	local worktree_path = stdout:match("at%s+(%S.-)%s*$")
	if not worktree_path then
		window:toast_notification("devos", "Could not parse worktree path from: " .. stdout, nil, 5000)
		return
	end

	local _, editor_pane = mux.spawn_window({
		workspace = key,
		cwd = worktree_path,
	})
	local agent_pane = editor_pane:split({ direction = "Right", size = 0.5, cwd = worktree_path })
	agent_pane:split({ direction = "Bottom", size = 0.3, cwd = worktree_path })

	mux.set_active_workspace(key)
end

function M.close_ticket(window, pane, key)
	local cwd = pane_cwd(pane) or wezterm.home_dir

	local ok, stdout, stderr = run_devos({ "ticket", "close", key }, cwd)
	if not ok then
		window:toast_notification("devos", "ticket close failed: " .. stderr .. stdout, nil, 5000)
		return
	end

	for _, w in ipairs(mux.all_windows()) do
		if w:get_workspace() == key then
			w:close()
		end
	end
	window:toast_notification("devos", "Closed ticket " .. key, nil, 3000)
end

return M
