"""Airport Investment Intelligence Agent.

Command line (installed as `airport-agent`):
    airport-agent refresh [--as-of YYYY-MM] [--cache-dir data/cache] [--keep-raw]
"""

import argparse
import sys
from pathlib import Path


def _as_of(text):
    from airport_agent.data.asof import parse_as_of

    try:
        parse_as_of(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None
    return text


def main(argv=None):
    """Entry point of the `airport-agent` command; returns the exit code."""
    parser = argparse.ArgumentParser(prog="airport-agent")
    commands = parser.add_subparsers(dest="command", required=True)
    refresh = commands.add_parser(
        "refresh", help="build a dated data snapshot and publish it to DATA_STORE"
    )
    refresh.add_argument(
        "--as-of", type=_as_of, help="YYYY-MM: only data published by the end of that month"
    )
    refresh.add_argument("--cache-dir", type=Path, default=Path("data/cache"))
    refresh.add_argument("--keep-raw", action="store_true", help="keep the BTS ZIPs")
    args = parser.parse_args(argv)

    from airport_agent.data.build import BuildError
    from airport_agent.data.refresh import refresh as run_refresh

    try:
        run_refresh(args.as_of, args.cache_dir, keep_raw=args.keep_raw)
    except (BuildError, ValueError) as error:
        print(f"Refresh stopped: {error}", file=sys.stderr)
        return 1
    return 0
