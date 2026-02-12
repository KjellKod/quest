"""Root conftest.py -- shared pytest configuration.

Adds scripts/ to sys.path so the quest_dashboard package is importable
from all test files without per-file sys.path manipulation.
"""

import sys
from pathlib import Path

# Add scripts/ to path once, so quest_dashboard package is importable
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
