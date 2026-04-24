"""PySide6 application entrypoint for the new UVR frontend."""

from __future__ import annotations

import sys


def main() -> int:
    import argparse

    try:
        from uvr_qt.bootstrap import default_config_path, run
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            raise SystemExit(
                "PySide6 is not installed. Install it before running `python -m uvr_qt.app`."
            ) from exc
        raise

    parser = argparse.ArgumentParser(description="Ultimate Vocal Remover PySide6 frontend")
    parser.add_argument(
        "--config",
        default=None,
        help=f"Settings YAML/pickle path. Defaults to {default_config_path()}.",
    )
    args, qt_args = parser.parse_known_args()
    sys.argv = [sys.argv[0], *qt_args]
    return run(config_path=args.config)


if __name__ == "__main__":
    sys.exit(main())
