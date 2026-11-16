"""Runtime paths shared by isolated studio services."""
from __future__ import annotations
import os
import pathlib
import sys
_configured_root = None

def configure_root(value):
    """Explicit application profile; does not change Windows environment settings."""
    global _configured_root
    _configured_root = pathlib.Path(value).expanduser().resolve()

def public_root() -> pathlib.Path:
    return pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parents[1]))

def data_root() -> pathlib.Path:
    if _configured_root is not None:
        _configured_root.mkdir(parents=True, exist_ok=True)
        return _configured_root
    override = os.environ.get('FBR_STUDIO_DIR')
    path = pathlib.Path(override) if override else pathlib.Path(os.environ.get('LOCALAPPDATA', pathlib.Path.home() / '.local/share')) / 'FreeBibleReader' / 'studio'
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
