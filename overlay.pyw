#!/usr/bin/env pythonw
"""Silent launcher: starts the overlay with no console window.

Equivalent to `python -m gwolves_battery`, but usable as the target of a
Windows shortcut through pythonw.exe.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gwolves_battery.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
