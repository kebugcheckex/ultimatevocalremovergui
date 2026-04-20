"""PySide6 application entrypoint for the new UVR frontend."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from uvr_qt.bootstrap import run
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            raise SystemExit(
                "PySide6 is not installed. Install it before running `python -m uvr_qt.app`."
            ) from exc
        raise

    return run()


if __name__ == "__main__":
    sys.exit(main())
