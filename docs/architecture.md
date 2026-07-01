# Developer Operating System — Architecture & Roadmap

**Role:** Lead Architect / Principal Engineer perspective
**Scope:** A production-grade internal engineering platform for backend development, production debugging, Kubernetes operations, PostgreSQL investigation, Grafana debugging, Git worktree management, and AI-assisted software engineering.
**Non-goal:** This is not a terminal theme, not a WezTerm config, not a dotfiles repo. WezTerm is the UI shell only.

---

## 1. Workflow & Pain Point Analysis

### 1.1 The two workflows, made explicit

**Workflow 1 — Development**
Jira Ticket → Git Worktree → Claude Code → Development → Testing → Commit

**Workflow 2 — Investigation**
Jira → Grafana → Kubernetes → Jumpbox → (sometimes) PostgreSQL → SQL Queries → CSV Export → `kubectl cp` → Root Cause → back to Development

These are structurally different in every way that matters:

| Dimension | Development | Investigation |
|---|---|---|
| State | Long-lived (a worktree persists for the life of a ticket) | Ephemeral (a session is disposable once root cause is found) |
| Isolation need | High — parallel Claude Code agents must not collide | Low — investigation tools are shared, read-mostly |
| Trigger | Explicit ("start ticket X") | Explicit but *never* implied by opening a ticket |
| Side effects | Local filesystem, git | Remote systems (cluster, DB, jumpbox) — costly to open unnecessarily |
| Failure mode if conflated | Two agents corrupt the same working tree | An idle terminal silently holds a jumpbox/DB tunnel open |

The single most important architectural rule falls out of this table: **opening a ticket must never imply opening infrastructure.** Every remote connection (Grafana, K8s context, jumpbox tunnel, Postgres session) is a *separate, explicit, user-triggered action*, decoupled from ticket lifecycle.

### 1.2 Inferred repetitive tasks (things you didn't say but almost certainly do)

- Creating a worktree by hand: `git worktree add`, branch naming, then `cd`-ing in, then re-opening the editor/agent context — a 4–6 step manual sequence per ticket, done multiple times a day.
- Re-typing the same `kubectl port-forward` / jumpbox SSH command with slightly different pod names each investigation.
- Re-writing near-identical SQL (find user by ID, find failed jobs in last N hours, check queue depth) from muscle memory or scrollback, with no shared library — meaning the same query gets reinvented and re-debugged repeatedly.
- Losing track of *which* Claude Code agent is working on *which* ticket when 2–3 are running concurrently in the same repo — a context-identity problem, not just a filesystem one.
- Manually exporting query results to CSV, then `kubectl cp`-ing them out of a pod — a fragile multi-step pipeline with no error handling and no record of what was pulled or why.
- No persistent record connecting "ticket X" → "root cause found" → "queries used" → "commit that fixed it." Institutional knowledge evaporates after each investigation.
- Re-deriving Grafana dashboard URLs/filters per incident instead of jumping straight from a ticket to the relevant pre-filtered view.
- Manually cleaning up stale worktrees and forgotten port-forwards/tunnels after a ticket closes — a garbage-collection problem nobody owns.

### 1.3 Pain points

- **Cognitive overhead of context switching** between "I am coding" mode and "I am investigating prod" mode, with no environment-level signal to reinforce which mode you're in.
- **No isolation boundary for concurrent AI agents** — the biggest correctness risk in your stated workflow. Two Claude Code sessions in one working tree is a data-loss incident waiting to happen.
- **Tribal knowledge trapped in scrollback.** SQL queries, kubectl incantations, and root-cause reasoning live in terminal history, not in a searchable, reusable artifact.
- **No feedback loop from investigation back into prevention.** Root causes are found but not systematically turned into runbooks or query-library entries.

### 1.4 Future scalability issues

- As more engineers (eventually) adopt this, hardcoded personal paths/namespaces become a portability bug farm — config must be externalized from day one, not retrofitted.
- SQL-as-scrollback doesn't scale past one person; it needs to become a versioned, reviewable **query library** early, or it never will.
- Multiple concurrent AI agents will eventually want **shared context** (e.g., "what did the other agent already try on this ticket") — worth designing the data model for this now even if you don't build it yet.
- Grafana/K8s/Jumpbox credentials and session state will eventually need centralized lifecycle management (auto-expiry, cleanup) or you'll accumulate zombie tunnels indefinitely.
- If this ever grows beyond one user, "business logic in Lua" becomes an onboarding and maintenance nightmare — which is precisely why it's excluded now, before the codebase exists.

---

## 2. Target Architecture

### 2.1 Design philosophy

WezTerm is a **rendering and input surface** — panes, tabs, workspaces, a status bar, and a launch menu. It should be *replaceable* without touching business logic. Everything that decides *what happens* — worktree creation, tunnel management, SQL templating, ticket-to-workspace mapping — lives in Python and shell, callable independently of WezTerm (from a CI job, a cron cleanup task, or eventually an MCP server).

**Layering:**

```
┌─────────────────────────────────────────┐
│  UI Layer (WezTerm/Lua)                  │  panes, keybindings, status bar, launch menu
├─────────────────────────────────────────┤
│  Orchestration Layer (Python CLI)        │  ticket lifecycle, workspace state, command dispatch
├─────────────────────────────────────────┤
│  Domain Logic (Python modules)           │  worktree mgmt, k8s/jumpbox/grafana clients, query engine
├─────────────────────────────────────────┤
│  Data / Templates (SQL, YAML, runbooks)  │  .sql files, config, markdown runbooks
└─────────────────────────────────────────┘
```

Each layer only talks to the layer directly below it. The UI layer never touches SQL. The domain layer never renders anything — it returns data structures; the orchestration layer decides how to present them.

### 2.2 Why not alternatives

- **Pure tmux + shell scripts, no Python.** Rejected: shell is fine for glue but bad for structured state (which ticket owns which worktree, what tunnels are open, query templating with parameters). You'd end up reimplementing a weak version of a CLI framework in bash.
- **A custom TUI application (e.g., Textual/Bubbletea) replacing WezTerm entirely.** Rejected for now: much higher build cost, and you already have a terminal workflow you like. Revisit only if the Python CLI's output becomes too rich for a terminal launch-menu to represent well.
- **Heavier orchestration framework (e.g., a local web dashboard).** Rejected: contradicts the "keyboard-first, terminal-native" goal, and adds a browser dependency to what should be a fast, local, always-available tool. A local web view could later be an *optional* add-on for the query library, not the primary interface.
- **Business logic in Lua (WezTerm's config language).** Rejected explicitly per your constraints, and rightly so: Lua has weak tooling for testing, no real package ecosystem for SQL/K8s/DB clients, and mixing UI config with domain logic is exactly the kind of coupling that makes a codebase unmaintainable as it grows.

### 2.3 Core architectural decisions

1. **Ticket workspaces and Operations workspaces are structurally separate WezTerm workspaces**, each with its own pane layout, launched independently. A ticket workspace never auto-launches an operations tool.
2. **Git worktrees are the unit of ticket isolation.** One worktree per ticket, named deterministically from the Jira key, so any tool (including future AI agents) can resolve "ticket → worktree path" without ambiguity.
3. **SQL lives as versioned `.sql` template files** with named parameters, rendered by Python (Jinja2-style), never string-concatenated in Lua or inline in shell.
4. **All remote connections (K8s context, jumpbox tunnel, Postgres session) are explicit, named, and independently teardown-able** — never implied by ticket state.
5. **State is file-based and human-readable** (YAML/JSON under `~/.dev-os/state/`), not a hidden database — so it's inspectable, git-friendly for config, and debuggable by hand if something breaks.
6. **Everything the Python CLI can do, it can do headless** (no WezTerm required) — this is what makes future AI-agent and MCP integration possible without rearchitecting.

---

## 3. Repository Structure

```
dev-os/
├── bootstrap/                  # one-shot installer, idempotent
│   ├── install.sh
│   └── checks.py               # verifies deps: git, kubectl, psql, wezterm, python
│
├── wezterm/                    # UI layer only — thin
│   ├── wezterm.lua             # entrypoint, wires up the below
│   ├── keybindings.lua
│   ├── launch_menu.lua         # calls into python/cli.py, never contains logic
│   ├── status_bar.lua          # reads state/*.json, renders only
│   └── workspaces.lua          # ticket vs ops workspace definitions
│
├── python/
│   ├── devos/
│   │   ├── cli.py              # single entrypoint: `devos <command>`
│   │   ├── tickets/
│   │   │   ├── worktree.py     # create/list/remove worktrees
│   │   │   └── registry.py     # ticket ↔ worktree ↔ agent state
│   │   ├── ops/
│   │   │   ├── kubernetes.py   # context switch, port-forward mgmt
│   │   │   ├── jumpbox.py      # SSH tunnel lifecycle
│   │   │   ├── grafana.py      # deep-link builder, dashboard lookup
│   │   │   └── postgres.py     # connection mgmt, query execution
│   │   ├── queries/
│   │   │   ├── engine.py       # loads + renders .sql templates
│   │   │   └── export.py       # result → CSV, kubectl cp wrapper
│   │   ├── claude/
│   │   │   └── agent_bridge.py # tracks which agent owns which worktree
│   │   ├── state/
│   │   │   └── store.py        # read/write ~/.dev-os/state/*.json
│   │   └── config/
│   │       └── loader.py       # env-specific config, no hardcoded paths
│   └── tests/
│
├── sql/
│   ├── investigation/
│   │   ├── find_user_by_id.sql
│   │   ├── failed_jobs_last_n_hours.sql
│   │   └── queue_depth.sql
│   └── schema/                 # reference schema notes, not migrations
│
├── runbooks/
│   ├── template.md
│   └── <incident-slug>.md      # generated/curated post-investigation
│
├── docs/
│   ├── architecture.md         # this document, kept in-repo
│   ├── onboarding.md
│   └── conventions.md
│
├── config/
│   ├── defaults.yaml
│   └── local.yaml.example      # user overrides, gitignored when real
│
└── tests/
    └── integration/
```

**Directory responsibilities, briefly:**
- `bootstrap/` — gets a new machine from zero to working system, checks all dependencies exist before touching anything.
- `wezterm/` — UI only; every file here should be short enough to read in one sitting, and none should contain SQL, kubectl invocations, or business rules.
- `python/devos/` — the actual product. Fully testable and runnable without WezTerm.
- `sql/` — the query library; grows over time, is the single source of truth for "how do we investigate X."
- `runbooks/` — the output of investigations, turned into reusable documents — this is the feedback loop from §1.4.
- `config/` — the only place environment-specific values (namespaces, jumpbox hosts) live.

---

## 4. Subsystem Designs

### 4.1 Ticket Workspace
- `devos ticket start JIRA-1234` → creates worktree at `~/worktrees/JIRA-1234/`, branch `JIRA-1234`, registers in `state/tickets.json`, opens a new WezTerm workspace with a fixed pane layout (editor pane, agent pane, shell pane).
- `devos ticket close JIRA-1234` → prompts for uncommitted changes, removes worktree, deregisters, closes the workspace.
- No implicit infra connections on start — enforced by construction, since `ticket start` only calls `worktree.py` and `workspaces.lua`.

### 4.2 Operations Workspace
- A separate, singleton WezTerm workspace (`devos ops open`) for investigation. Reused across tickets rather than recreated.
- Panes are opened on demand: `devos ops grafana`, `devos ops k8s <namespace>`, `devos ops jumpbox`, `devos ops postgres` — each an independent, named, teardown-able session.

### 4.3 Grafana Integration
- `grafana.py` builds deep-link URLs from ticket metadata (time range, service name if known) rather than opening a bare dashboard — first-class, not an afterthought.
- No credential storage; opens the browser and relies on existing SSO session.

### 4.4 Kubernetes
- Context switches are explicit and logged (`devos ops k8s <namespace>` records the switch in state, so the status bar can show "current k8s context" honestly).
- Port-forwards are tracked with PIDs in `state/tunnels.json` so `devos ops cleanup` can find and kill anything orphaned.

### 4.5 Jumpbox
- SSH tunnels wrapped the same way as port-forwards — named, tracked, independently closeable, visible in the status bar.

### 4.6 PostgreSQL + Query Library
- `postgres.py` opens a connection using tunnel info from `state/tunnels.json` (never hardcodes host/port).
- `engine.py` renders a chosen `.sql` file with parameters passed via CLI flags (`devos query run failed_jobs_last_n_hours --hours=4`).
- Results can be piped to `export.py` for CSV output, which in turn wraps `kubectl cp` when the destination is a pod filesystem, or writes directly to local disk otherwise.

### 4.7 Claude Code Integration
- `agent_bridge.py` maintains a mapping of `worktree → agent session id → ticket`, written when an agent is launched in a given worktree pane.
- Purpose today: visibility (status bar can show "2 agents active: JIRA-1234, JIRA-1230"). Purpose long-term: the foundation for cross-agent context sharing (§7).

### 4.8 Git Worktrees
- All creation/removal goes through `worktree.py`, never raw `git worktree` commands in muscle memory — this is what keeps naming and state registration consistent.

### 4.9 Python CLI
- Single entrypoint `devos`, subcommands via `argparse`/`click`. Every WezTerm launch-menu item is a thin wrapper calling `devos <command>` — meaning the entire system is testable and scriptable without ever opening WezTerm.

### 4.10 Shell Scripts
- Reserved for genuinely OS-level glue (e.g., checking if a binary is on `$PATH` during bootstrap) — anything with real logic belongs in Python instead.

### 4.11 WezTerm (keybindings, status bar, launch menu)
- `status_bar.lua` polls `state/*.json` on an interval and renders: active ticket, active agents, open tunnels, current k8s context. Read-only, no side effects.
- `launch_menu.lua` is a declarative list of `{label, command}` pairs mapping to `devos` CLI calls.

### 4.12 Documentation & Runbooks
- Every closed investigation produces a runbook (from `runbooks/template.md`), optionally auto-drafted from the queries run and the ticket description, then hand-edited before committing.

### 4.13 Environment / Configuration Management
- `config/defaults.yaml` (committed) + `config/local.yaml` (gitignored, per-machine overrides: namespaces, jumpbox host, DB aliases). `loader.py` merges them, defaults never contain real infra values.

### 4.14 Bootstrap
- `install.sh` checks for `git`, `kubectl`, `psql`, `wezterm`, `python3.11+`, sets up a venv, symlinks `wezterm.lua`, and does a dry-run health check — fails loudly and specifically rather than partially installing.

### 4.15 Testing
- `python/tests/` unit-tests worktree logic, query template rendering, and state store read/write with no external dependencies mocked-in.
- `tests/integration/` exercises real `git worktree` operations against a throwaway repo fixture; K8s/Postgres/Grafana clients are tested against mocks/interfaces, not live systems.

### 4.16 Future AI Integrations
- The `state/` files and `agent_bridge.py` mapping are the seam where an MCP server would attach later — exposing "list active tickets," "get query library," "get runbook for incident X" as MCP tools without any redesign, because domain logic is already decoupled from WezTerm.

---

## 5. Milestone Roadmap

> Each milestone yields a working, independently testable system. No milestone assumes code from a later one. Wait for explicit approval before starting the next.

### Milestone 0 — Bootstrap & Repo Skeleton
- **Goal:** A cloneable repo that installs cleanly on a fresh machine and does nothing else yet.
- **Features:** `bootstrap/install.sh`, `checks.py`, empty folder skeleton per §3, `config/defaults.yaml`.
- **Architecture:** No business logic yet — this is pure scaffolding + dependency verification.
- **Files:** `bootstrap/install.sh`, `bootstrap/checks.py`, `config/defaults.yaml`, `config/local.yaml.example`, `docs/onboarding.md`.
- **Testing:** Run `install.sh` on a clean shell profile; verify `checks.py` correctly fails when a dependency is missing.
- **Expected Result:** `devos --version` (stub) runs after install.
- **Estimated Time:** 0.5 day.
- **Dependencies:** None.
- **Acceptance Criteria:** Fresh clone → `install.sh` → no errors → stub CLI runs.
- **Git Commit:** `chore: bootstrap repo skeleton and installer`
- **Future Refactoring:** `checks.py` will grow to check WezTerm version compatibility once WezTerm config is added.

### Milestone 1 — Python CLI Core + State Store
- **Goal:** `devos` CLI exists with a real command dispatcher and a file-based state store.
- **Features:** `cli.py`, `state/store.py` (read/write JSON under `~/.dev-os/state/`), `config/loader.py`.
- **Architecture:** Establishes the orchestration layer; no domain logic yet beyond a `devos status` command that prints empty state.
- **Files:** `python/devos/cli.py`, `python/devos/state/store.py`, `python/devos/config/loader.py`, `python/tests/test_state_store.py`.
- **Testing:** Unit tests for state read/write, including corrupt-file recovery.
- **Expected Result:** `devos status` prints "no active tickets, no open tunnels."
- **Estimated Time:** 1 day.
- **Dependencies:** Milestone 0.
- **Acceptance Criteria:** `devos status` works from any directory; state file survives process restarts.
- **Git Commit:** `feat: cli core and file-based state store`
- **Future Refactoring:** Consider SQLite for state if concurrent-write conflicts appear (unlikely at single-user scale).

### Milestone 2 — Git Worktree Management (Ticket Lifecycle)
- **Goal:** Full ticket start/close lifecycle via worktrees, no WezTerm yet.
- **Features:** `devos ticket start <KEY>`, `devos ticket close <KEY>`, `devos ticket list`.
- **Architecture:** `tickets/worktree.py` + `tickets/registry.py`, writes to state store from Milestone 1.
- **Files:** `python/devos/tickets/worktree.py`, `python/devos/tickets/registry.py`, tests.
- **Testing:** Integration test against a throwaway git repo fixture: create, list, close, verify worktree removed and branch handled per policy (merged vs. abandoned).
- **Expected Result:** Can manage 3 concurrent ticket worktrees purely from the CLI.
- **Estimated Time:** 1.5 days.
- **Dependencies:** Milestone 1.
- **Acceptance Criteria:** No orphaned worktrees after close; registry always reflects filesystem reality (self-healing check on `devos ticket list`).
- **Git Commit:** `feat: git worktree lifecycle management`
- **Future Refactoring:** Add `devos ticket status <KEY>` once agent tracking (Milestone 6) exists.

### Milestone 3 — WezTerm UI Shell (Read-Only Integration)
- **Goal:** WezTerm becomes a thin frontend to the CLI — first real UI milestone.
- **Features:** `wezterm.lua`, `keybindings.lua`, `launch_menu.lua` wired to `devos ticket start/close/list`, `workspaces.lua` for ticket-workspace creation on `ticket start`.
- **Architecture:** Enforces §2.3 rule #1 — launch menu items are one-line calls into the CLI, nothing else.
- **Files:** all of `wezterm/*.lua`.
- **Testing:** Manual acceptance test (UI layer isn't unit-testable in the traditional sense) — checklist in `docs/conventions.md`.
- **Expected Result:** Starting a ticket from the WezTerm launch menu creates the worktree AND opens a dedicated workspace with editor/agent/shell panes.
- **Estimated Time:** 1.5 days.
- **Dependencies:** Milestone 2.
- **Acceptance Criteria:** Zero Lua files contain business logic (spot-check during review); ticket start/close fully usable via keyboard only.
- **Git Commit:** `feat: wezterm ui shell wired to cli`
- **Future Refactoring:** Status bar (Milestone 7) will read the same state files this milestone starts populating.

### Milestone 4 — Operations Workspace: Kubernetes + Jumpbox
- **Goal:** Explicit, trackable, teardown-able infra connections, fully decoupled from tickets.
- **Features:** `devos ops k8s <namespace>`, `devos ops jumpbox`, `devos ops cleanup`, tunnel/context tracking in `state/tunnels.json`.
- **Architecture:** `ops/kubernetes.py`, `ops/jumpbox.py`; singleton "ops" WezTerm workspace opened via `devos ops open`.
- **Files:** `python/devos/ops/kubernetes.py`, `python/devos/ops/jumpbox.py`, `wezterm/workspaces.lua` (extended), tests with mocked subprocess calls.
- **Testing:** Unit tests mock `kubectl`/`ssh` subprocess calls; verify tunnel PIDs are tracked and `cleanup` kills all tracked processes.
- **Expected Result:** Can open/close a K8s context and a jumpbox tunnel independently of any ticket; `devos ops cleanup` reliably kills orphans.
- **Estimated Time:** 2 days.
- **Dependencies:** Milestone 3.
- **Acceptance Criteria:** No tunnel/context is ever opened as a side effect of `ticket start`; `cleanup` leaves zero orphaned processes after a stress test of open/close cycles.
- **Git Commit:** `feat: kubernetes and jumpbox ops with tunnel tracking`
- **Future Refactoring:** Auto-expiry for tunnels idle beyond N minutes.

### Milestone 5 — PostgreSQL + Query Library
- **Goal:** Templated, versioned SQL replaces ad hoc scrollback queries.
- **Features:** `devos query run <name> [--param=value ...]`, `devos query list`, CSV export, `kubectl cp` wrapper for pod-resident output destinations.
- **Architecture:** `queries/engine.py` (Jinja2 template rendering over `.sql` files in `sql/investigation/`), `ops/postgres.py` (uses tunnel state from Milestone 4), `queries/export.py`.
- **Files:** `python/devos/queries/engine.py`, `python/devos/queries/export.py`, `python/devos/ops/postgres.py`, seed `sql/investigation/*.sql` (3–5 real queries from your current scrollback history).
- **Testing:** Unit tests for template rendering with parameter substitution and injection-safety (parameterized queries, not string interpolation into SQL); integration test against a local throwaway Postgres via Docker.
- **Expected Result:** `devos query run failed_jobs_last_n_hours --hours=4` returns results and can export to CSV.
- **Estimated Time:** 2 days.
- **Dependencies:** Milestone 4.
- **Acceptance Criteria:** All example queries parameterized (no raw string formatting into SQL); CSV export round-trips correctly for at least one large (>10k row) result set.
- **Git Commit:** `feat: postgres query library and csv export`
- **Future Refactoring:** Query recommendation/search once the library grows past ~20 entries.

### Milestone 6 — Claude Code Agent Bridge
- **Goal:** Visibility into which agent is working on which ticket.
- **Features:** `agent_bridge.py` records agent session start/stop per worktree pane; `devos ticket status <KEY>` shows active agent info.
- **Architecture:** Hooked into the `ticket start` pane-launch step from Milestone 3; purely additive, no change to existing commands' external behavior.
- **Files:** `python/devos/claude/agent_bridge.py`, tests.
- **Testing:** Unit test the state transitions (agent registered → active → deregistered on pane close).
- **Expected Result:** `devos status` lists all active tickets alongside their agent session state.
- **Estimated Time:** 1 day.
- **Dependencies:** Milestone 3.
- **Acceptance Criteria:** Running two agents in two ticket worktrees simultaneously shows both correctly and independently in `devos status`.
- **Git Commit:** `feat: claude code agent bridge and tracking`
- **Future Refactoring:** This is the seam for cross-agent shared context (§7) and later MCP exposure.

### Milestone 7 — Status Bar & Grafana Deep Links
- **Goal:** Passive, always-visible situational awareness; first-class Grafana integration.
- **Features:** `status_bar.lua` rendering active ticket / agents / tunnels / k8s context; `devos ops grafana` builds ticket-aware deep links.
- **Architecture:** Status bar is strictly read-only against `state/*.json`; `ops/grafana.py` builds URLs from ticket metadata + config-defined dashboard templates.
- **Files:** `wezterm/status_bar.lua`, `python/devos/ops/grafana.py`, `config/defaults.yaml` (dashboard URL templates).
- **Testing:** Unit test URL construction with various metadata combinations; manual check of status bar refresh behavior.
- **Expected Result:** Status bar always reflects true system state at a glance; `devos ops grafana` opens a pre-filtered dashboard relevant to the current ticket.
- **Estimated Time:** 1.5 days.
- **Dependencies:** Milestones 4, 6.
- **Acceptance Criteria:** Status bar never shows stale state after a tunnel/agent is torn down (verified via the cleanup stress test from Milestone 4).
- **Git Commit:** `feat: status bar and grafana deep linking`
- **Future Refactoring:** None anticipated; stable subsystem.

### Milestone 8 — Runbooks & Investigation Feedback Loop
- **Goal:** Close the loop from §1.4 — investigations produce reusable knowledge.
- **Features:** `devos runbook new <KEY>` scaffolds from `runbooks/template.md`, pre-filled with the queries run during that ticket's investigation (pulled from query-run history in state).
- **Architecture:** New `runbooks/` writer in `python/devos/`, reads query-run log (extend `state/store.py` to log query invocations per ticket).
- **Files:** `python/devos/runbooks/generator.py`, `runbooks/template.md`, tests.
- **Testing:** Unit test scaffold generation with a fixture query-history; verify template fills correctly with zero, one, and many queries.
- **Expected Result:** Closing an investigation-heavy ticket produces a draft runbook automatically, ready for hand-editing.
- **Estimated Time:** 1.5 days.
- **Dependencies:** Milestone 5.
- **Acceptance Criteria:** At least 3 real past investigations backfilled as runbooks to validate the template is genuinely useful, not just theoretically complete.
- **Git Commit:** `feat: runbook generation from investigation history`
- **Future Refactoring:** Auto-linking runbooks to the git commit that resolved the ticket.

### Milestone 9 — Hardening, Docs, and "Production Ready"
- **Goal:** The system is trustworthy enough to depend on daily without supervision.
- **Features:** Full `docs/onboarding.md` and `docs/conventions.md`, error handling audit across all CLI commands (no silent failures), `devos doctor` health-check command, complete test coverage report.
- **Architecture:** No new subsystems — a hardening pass across everything in Milestones 0–8.
- **Files:** Updates across `python/devos/**`, `docs/*.md`, new `python/devos/doctor.py`.
- **Testing:** Full regression pass of the integration test suite; manual chaos test (kill processes mid-operation, corrupt a state file, verify graceful recovery/clear error messages).
- **Expected Result:** System survives a full week of real daily use without manual state-file surgery.
- **Estimated Time:** 2 days.
- **Dependencies:** All prior milestones.
- **Acceptance Criteria:** `devos doctor` catches and clearly explains every failure mode exercised in the chaos test.
- **Git Commit:** `chore: hardening pass, docs, and doctor command — v1.0`
- **Future Refactoring:** This is the natural point to evaluate MCP server exposure (§4.16) as a v1.1 initiative.

**Total estimated time:** ~13.5 engineering days across 10 milestones, assuming no major surprises in K8s/Postgres client integration.

---

## 6. Self-Review & Critique

**Weakness 1 — Milestone 5 (Query Library) is doing too much in one step.**
Templated rendering, Postgres connection management, *and* CSV export with `kubectl cp` wrapping is three distinct pieces of complexity bundled into a single 2-day milestone. If any one part slips, the whole milestone slips.
*Revision:* Split into 5a (query engine + Postgres connection, no export) and 5b (export + kubectl cp wrapper). This also means you get value from parameterized queries a full milestone earlier, without waiting on export tooling.

**Weakness 2 — No milestone validates the core isolation claim under real concurrent load.**
The entire architecture's central promise (§1.2, §2.3) is that concurrent Claude Code agents in separate worktrees won't collide. Milestone 6 tracks agent state but never actually stress-tests two simultaneous agents making real changes.
*Revision:* Add an explicit concurrency acceptance test to Milestone 6: run two real Claude Code sessions in two worktrees against the same upstream repo simultaneously, confirm no cross-contamination. This is the single highest-risk assumption in the whole plan and deserves a named test, not an implicit one.

**Weakness 3 — Grafana deep-linking (Milestone 7) assumes dashboard URL templates that don't exist yet.**
The plan hand-waves "config-defined dashboard templates" without a milestone to actually inventory which dashboards you use and how their filter parameters work.
*Revision:* Add a short (0.5 day) discovery task at the start of Milestone 7 to catalog your 3–5 most-used Grafana dashboards and their URL parameter schemes before writing `grafana.py`.

**Weakness 4 — State store corruption recovery is tested in Milestone 1 but never revisited as the schema grows.**
By Milestone 8, `state/store.py` holds tickets, tunnels, agents, and query history — four schemas layered into what started as a simple JSON file. Corruption-recovery logic written against the Milestone 1 schema may not hold.
*Revision:* Fold a state-schema regression test into Milestone 9's hardening pass explicitly, rather than assuming Milestone 1's test still covers it.

**Weakness 5 — The roadmap has no rollback story.**
Every milestone says "git commit" but none say what happens if a milestone's acceptance criteria fail after the commit. For a system you'll depend on daily, silently having a broken milestone in `main` is worse than in normal product work.
*Revision:* Add a standing rule (documented in `docs/conventions.md`, not a separate milestone): each milestone branch is only merged to `main` after acceptance criteria pass; failed milestones stay on their branch for debugging rather than landing broken.

**Net assessment:** The architecture itself (thin UI / thick domain layer, explicit infra connections, worktree-based isolation) is sound and I wouldn't change the core design. The roadmap's weaknesses were all in *sequencing and validation rigor*, not structure — the revisions above are incorporated into the milestone list in §5.

---

## 7. Appendix

**Assumptions made:**
- Single-user system for v1; multi-engineer rollout is a stated future goal but not in scope for these milestones.
- Postgres access is always via jumpbox/K8s tunnel, never direct.
- Claude Code is invoked manually per pane; this plan tracks agents, it doesn't launch or configure them.

**Open questions for you:**
1. Do ticket branches get deleted on `ticket close`, or only the worktree (keeping history for reference)?
2. Should `devos ops cleanup` run automatically on a timer, or only ever on explicit invocation?
3. For the query library seed (Milestone 5), which 3–5 queries do you currently run most often? Worth listing them now so Milestone 5 starts with real, not placeholder, content.

**Glossary / conventions:**
- **Ticket workspace** — a WezTerm workspace scoped to one Jira ticket and its worktree.
- **Ops workspace** — the singleton, shared WezTerm workspace for investigation tooling.
- **Tunnel** — any long-lived remote connection (K8s port-forward, jumpbox SSH) tracked in `state/tunnels.json`.
