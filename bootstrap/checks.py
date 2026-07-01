"""Verifies required dependencies exist before dev-os is installed.

Run directly: python3 bootstrap/checks.py
Exits 0 if every required dependency is present, 1 otherwise.
"""
import shutil
import sys
from dataclasses import dataclass

MIN_PYTHON = (3, 11)


@dataclass
class Dependency:
    name: str
    binary: str
    required: bool


DEPENDENCIES = [
    Dependency("Git", "git", required=True),
    Dependency("kubectl", "kubectl", required=True),
    Dependency("psql", "psql", required=True),
    Dependency("WezTerm", "wezterm", required=True),
]


def check_python() -> bool:
    ok = sys.version_info[:2] >= MIN_PYTHON
    status = "OK" if ok else "MISSING"
    print(f"[{status}] Python >= {'.'.join(map(str, MIN_PYTHON))} (found {sys.version.split()[0]})")
    return ok


def check_binary(dep: Dependency) -> bool:
    found = shutil.which(dep.binary) is not None
    status = "OK" if found else ("MISSING" if dep.required else "MISSING (optional)")
    print(f"[{status}] {dep.name} ({dep.binary})")
    return found or not dep.required


def main() -> int:
    results = [check_python()]
    results += [check_binary(dep) for dep in DEPENDENCIES]

    if all(results):
        print("\nAll required dependencies satisfied.")
        return 0

    print("\nMissing required dependencies. Install them and re-run this script.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
