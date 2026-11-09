"""Retired recipe-agent entry point.

Verified records the selected documented procedure's result. It does not
repair recipes or retry modified procedures. Historical implementations and
reports remain in Git history; assist_report.py can still render old reports.
"""
from __future__ import annotations

import sys

RETIRED_MESSAGE = (
    "Recipe repair is disabled. STRhub Verified does not change installation, "
    "dependencies, configuration, commands or datasets after a failed attempt. "
    "Record the failure; any correction must be documented upstream before "
    "a separate verification is requested."
)


def main() -> int:
    # Deliberately ignore legacy arguments and credentials. No model client,
    # repository read, trial dispatch, file write or PR creation is attempted.
    print(RETIRED_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
