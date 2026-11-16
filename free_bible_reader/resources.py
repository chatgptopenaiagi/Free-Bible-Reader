"""Resolve immutable public assets in source, frozen and wheel distributions."""
from __future__ import annotations
import os
from pathlib import Path
import sys


def asset_root() -> Path:
    """Return the root preserving data/, workbench/ and ui-core/ resource paths.

    FBR_ASSET_ROOT is an explicit deployment/test override, not a personal library.
    Normal wheels are extracted by pip; no database is extracted at import time.
    """
    override = os.environ.get("FBR_ASSET_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen).resolve()
    source = Path(__file__).resolve().parents[1]
    if (source / "pyproject.toml").is_file() and (source / "reader/service.py").is_file() and (source / "data/reader.sqlite").is_file():
        # Packaging stages a copy beneath this source tree. Development must
        # still see live source assets rather than that older staging snapshot.
        return source
    packaged = Path(__file__).resolve().parent / "assets"
    if (packaged / "data" / "reader.sqlite").is_file():
        return packaged
    return source


def asset_path(relative: str) -> Path:
    root = asset_root()
    value = (root / relative).resolve()
    if not value.is_relative_to(root):
        raise ValueError("ASSET_PATH_OUTSIDE_ROOT")
    return value

