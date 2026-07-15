"""Compatibility import for older scripts; use ``konspekt.bbb_import`` instead."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from konspekt.bbb_import import *  # noqa: F403
