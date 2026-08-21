#!/usr/bin/env python3
"""Run WT-MetaD production diagnostics."""

import sys

sys.path.insert(0, "..")
from analyze_metad import main  # noqa: E402

if __name__ == "__main__":
    sys.argv.insert(1, "wt-metad")
    main()
