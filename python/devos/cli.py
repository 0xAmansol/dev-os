import argparse
from pathlib import Path

from devos import __version__
from devos.state import store
from devos.tickets import registry, worktree


def cmd_status(args: argparse.Namespace) -> None:
    tickets = registry.list_all()
    tunnels = store.load("tunnels", {"tunnels": {}})["tunnels"]

    ticket_part = (
        f"{len(tickets)} active ticket(s): {', '.join(tickets)}"
        if tickets
        else "no active tickets"
    )
    tunnel_part = (
        f"{len(tunnels)} open tunnel(s): {', '.join(tunnels)}"
        if tunnels
        else "no open tunnels"
    )
    print(f"{ticket_part}, {tunnel_part}.")


def cmd_ticket_start(args: argparse.Namespace) -> None:
    key = args.key
    if registry.get(key):
        print(f"Ticket {key} already has an active worktree.")
        raise SystemExit(1)

    try:
        source_repo = worktree.resolve_source_repo(Path.cwd())
        path = worktree.create_worktree(source_repo, key)
    except worktree.WorktreeError as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    registry.register(key, branch=key, worktree_path=path, source_repo=source_repo)
    print(f"Created worktree for {key} at {path}")


def cmd_ticket_close(args: argparse.Namespace) -> None:
    key = args.key
    entry = registry.get(key)
    if not entry:
        print(f"No active ticket found for {key}.")
        raise SystemExit(1)

    path = Path(entry["worktree_path"])
    source_repo = Path(entry["source_repo"])

    if path.exists() and worktree.has_uncommitted_changes(path) and not args.force:
        print(
            f"Ticket {key} has uncommitted changes in {path}. "
            "Commit or stash them, or re-run with --force to discard and close."
        )
        raise SystemExit(1)

    try:
        if path.exists():
            worktree.remove_worktree(source_repo, path, force=args.force)
    except worktree.WorktreeError as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    try:
        worktree.delete_branch(source_repo, entry["branch"], force=args.force)
    except worktree.WorktreeError as e:
        print(
            f"Worktree closed, but branch '{entry['branch']}' was kept "
            f"(not merged): {e}. Re-run with --force to delete it anyway."
        )

    registry.deregister(key)
    print(f"Closed ticket {key}.")


def cmd_ticket_list(args: argparse.Namespace) -> None:
    dropped = registry.reconcile()
    for key in dropped:
        print(f"Note: {key}'s worktree was gone on disk; removed from registry.")

    tickets = registry.list_all()
    if not tickets:
        print("No active tickets.")
        return
    for key, entry in sorted(tickets.items()):
        print(f"{key}\t{entry['branch']}\t{entry['worktree_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devos")
    parser.add_argument(
        "--version", action="version", version=f"devos {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    status_parser = subparsers.add_parser(
        "status", help="Show active tickets, agents, and open tunnels"
    )
    status_parser.set_defaults(func=cmd_status)

    ticket_parser = subparsers.add_parser("ticket", help="Manage ticket worktrees")
    ticket_subparsers = ticket_parser.add_subparsers(dest="ticket_command")

    start_parser = ticket_subparsers.add_parser("start", help="Create a worktree for a ticket")
    start_parser.add_argument("key", help="Jira ticket key, e.g. JIRA-1234")
    start_parser.set_defaults(func=cmd_ticket_start)

    close_parser = ticket_subparsers.add_parser("close", help="Remove a ticket's worktree")
    close_parser.add_argument("key", help="Jira ticket key, e.g. JIRA-1234")
    close_parser.add_argument(
        "--force", action="store_true",
        help="Discard uncommitted changes and force-delete the branch even if unmerged",
    )
    close_parser.set_defaults(func=cmd_ticket_close)

    list_parser = ticket_subparsers.add_parser("list", help="List active tickets")
    list_parser.set_defaults(func=cmd_ticket_list)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
