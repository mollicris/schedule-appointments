"""Make the project root importable so `from src...` works.

Without this, `pytest` collects fine from the project root but a single-file run
(`pytest tests/test_slot_occupancy.py`) fails with ModuleNotFoundError: src.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
