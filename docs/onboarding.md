# Onboarding

## Fresh machine setup

1. Clone this repo.
2. Run the installer:
   ```
   ./bootstrap/install.sh
   ```
   This checks for required dependencies (`git`, `kubectl`, `psql`, `wezterm`,
   `python3.11+`), creates a `.venv`, and installs the `devos` CLI into it.
3. Activate the venv and verify:
   ```
   source .venv/bin/activate
   devos --version
   ```
4. Copy `config/local.yaml.example` to `config/local.yaml` and fill in your
   real namespace, jumpbox host, and Grafana values. `config/local.yaml` is
   gitignored — never commit real infra values.

## What's here at this stage

This is Milestone 0: bootstrap and repo skeleton only. `devos` is a stub that
only supports `--version`. Ticket lifecycle, ops tooling, and the query
library land in later milestones — see `docs/architecture.md` for the full
roadmap.
