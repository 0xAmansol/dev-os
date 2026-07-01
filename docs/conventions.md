# Conventions

## WezTerm manual acceptance checklist (Milestone 3)

The UI layer isn't unit-testable in the traditional sense. `wezterm show-keys
--config-file wezterm/wezterm.lua` will catch Lua syntax errors and confirm
keybindings/launch menu entries resolve, but it does not exercise runtime
behavior (spawning windows/panes). Run this checklist by hand after changes
to anything under `wezterm/`:

1. From inside a git repo, run:
   ```
   wezterm start --config-file /path/to/dev-os/wezterm/wezterm.lua
   ```
2. Press `Ctrl+A` (leader) then `t`, type a test ticket key (e.g. `TEST-1`),
   press Enter.
   - Expect: a new workspace named `TEST-1` opens with 3 panes (editor,
     agent, shell), all `cd`'d into the new worktree.
   - Confirm on disk: `git worktree list` in the source repo shows `TEST-1`.
3. Press `Ctrl+A` then `w`, type the same key, press Enter.
   - Expect: the `TEST-1` workspace closes.
   - Confirm on disk: `git worktree list` no longer shows `TEST-1`.
4. Press `Ctrl+A` then `l`.
   - Expect: a new tab opens running `devos ticket list`.
5. Open the launcher (default WezTerm launcher keybinding) and confirm
   "devos: ticket list" and "devos: status" both appear and run correctly.
6. Spot-check every file under `wezterm/`: none should contain git commands,
   SQL, or kubectl/ssh invocations — only calls into the `devos` CLI and
   pane/workspace rendering.

## Milestone branch policy

Each milestone's acceptance criteria must pass before merging to `main`.
A milestone that fails its acceptance criteria stays on its own branch for
debugging rather than landing broken on `main`.
