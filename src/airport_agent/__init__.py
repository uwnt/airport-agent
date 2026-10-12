"""Airport Investment Intelligence Agent.

Command line (installed as `airport-agent`):
    airport-agent refresh [--as-of YYYY-MM] [--cache-dir data/cache] [--keep-raw] [--check-facts]
    airport-agent check-facts [--record] [--accept URL] [--open-issue]
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


def _report_fact_changes():
    """Report only: a network error here must not fail a refresh that already succeeded."""
    from airport_agent.data.fact_watch import check_facts

    try:
        check_facts()
    except Exception as error:  # noqa: BLE001 - the watch is advisory
        print(f"Fact check skipped: {error}", file=sys.stderr)


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
    refresh.add_argument(
        "--check-facts", action="store_true", help="afterwards, report changed fact sources"
    )
    check = commands.add_parser(
        "check-facts", help="re-download the source of every verified fact and report changes"
    )
    check.add_argument("--record", action="store_true", help="store fingerprints of new sources")
    check.add_argument(
        "--accept",
        action="append",
        default=[],
        metavar="URL",
        help="re-store a changed source after a person re-verified its facts (repeatable)",
    )
    check.add_argument("--open-issue", action="store_true", help="file one GitHub issue")
    args = parser.parse_args(argv)

    if args.command == "check-facts":
        from airport_agent.data.fact_watch import IssueError, check_facts

        try:
            check_facts(record_baseline=args.record, accept=args.accept, issue=args.open_issue)
        except IssueError as error:
            print(error, file=sys.stderr)
            return 1
        return 0

    from airport_agent.data.build import BuildError
    from airport_agent.data.refresh import refresh as run_refresh

    try:
        run_refresh(args.as_of, args.cache_dir, keep_raw=args.keep_raw)
    except (BuildError, ValueError) as error:
        print(f"Refresh stopped: {error}", file=sys.stderr)
        return 1
    if args.check_facts:
        _report_fact_changes()
    return 0
