"""`python -m airport_agent.data [--as-of YYYY-MM]` is the same as `airport-agent refresh`."""

import sys

from airport_agent import main

sys.exit(main(["refresh", *sys.argv[1:]]))
