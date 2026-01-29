"""Back-compat entrypoint.

The packaged CLI entrypoint is `mspt` -> `mspt.cli:main`.
This file remains to support `python main.py ...` during development.
"""

from __future__ import annotations


def main() -> int:
    from mspt.cli import main as _main

    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
