import argparse

from devos import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devos")
    parser.add_argument(
        "--version", action="version", version=f"devos {__version__}"
    )
    return parser


def main() -> None:
    parser = build_parser()
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
