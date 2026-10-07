"""Loading of configurable reference data.

Files live in <project root>/reference_data/. The path is resolved relative to
this file, so loading works regardless of the current working directory.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "reference_data"


@lru_cache
def load_reference(filename: str) -> dict[str, Any]:
    """Load and cache a reference JSON file by name (e.g. "name_variants.json")."""
    path = REFERENCE_DIR / filename
    with path.open(encoding="utf-8") as file:
        return json.load(file)