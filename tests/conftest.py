"""Root conftest.py -- shared pytest configuration.

Prefers installed package (pip install -e .). Falls back to sys.path
manipulation for environments without an editable install.
"""

try:
    import quest_dashboard  # noqa: F401
except ImportError:
    import sys
    from pathlib import Path

    _scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
