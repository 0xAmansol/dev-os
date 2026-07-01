import argparse

from devos import __version__
from devos.state import store


def cmd_status(args: argparse.Namespace) -> None:
    tickets = store.load("tickets", {"tickets": {}})["tickets"]
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
