#!/usr/bin/env python3
"""Run Funnel-MetaD production diagnostics."""

import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "..")
from analyze_metad import main  # noqa: E402

if __name__ == "__main__":
    sys.argv.insert(1, "funnel-metad")
    main()
