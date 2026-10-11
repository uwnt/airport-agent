"""Entry point: `python -m airport_agent.data` builds the data cache."""

import sys

from airport_agent.data.build import main

sys.exit(main())
