#!/usr/bin/env python3
"""Warn about config keys that this template does not use (often typos).

The known keys are listed in helpers/config_keys.txt, generated from the
template's own config.toml with --generate. Unknown keys are reported as
warnings only; the build continues because TOML syntax and value checks are
done by the config readers.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

SECTION_LINE = re.compile(r"^\s*\[([A-Za-z0-9_.]+)\]\s*(#.*)?$")
# Optional keys shipped commented out, e.g. "# temperature_steps = 32".
COMMENTED_KEY_LINE = re.compile(r"^\s*#\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def flatten(values: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in values.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            keys |= flatten(value, f"{name}.")
        else:
            keys.add(name)
    return keys


def template_keys(path: Path) -> set[str]:
    with path.open("rb") as handle:
        keys = flatten(tomllib.load(handle))
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        header = SECTION_LINE.match(line)
        if header:
            section = header.group(1) + "."
            continue
        commented = COMMENTED_KEY_LINE.match(line)
        if commented:
            keys.add(section + commented.group(1))
    return keys


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Warn about config keys missing from this template's known-key list."
    )
    parser.add_argument("config", type=Path, help="config.toml to check, or the template config with --generate")
    parser.add_argument("known_keys", type=Path, nargs="?", help="helpers/config_keys.txt")
    parser.add_argument("--generate", action="store_true", help="Print the known-key list of CONFIG")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if tomllib is None:
        # The config readers report the missing TOML module with install guidance.
        return
    if args.generate:
        print("\n".join(sorted(template_keys(args.config))))
        return
    if args.known_keys is None:
        raise SystemExit("Error: known-key list is required unless --generate is used")
    try:
        with args.config.open("rb") as handle:
            used = flatten(tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError):
        # Leave missing files and syntax errors to the config readers.
        return
    known = set(args.known_keys.read_text(encoding="utf-8").split())
    # Engine passthrough tables take any engine keyword; apply_config checks
    # their stage names and refuses template-managed keywords.
    passthrough = ("amber.", "gromacs.", "plumed.")
    unknown = sorted(name for name in used - known if not name.startswith(passthrough))
    for name in unknown:
        section, _, key = name.rpartition(".")
        location = f"[{section}] {key}" if section else key
        print(
            f"Warning: unknown config key {location} in {args.config} is ignored; check its spelling against config.toml",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
