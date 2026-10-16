"""
Backend App Package.
Ensures repository root and backend directory are always on sys.path.
"""

import sys
from pathlib import Path

_app_dir = Path(__file__).resolve().parent
_backend_dir = _app_dir.parent
_repo_root = _backend_dir.parent

for _p in (_repo_root, _backend_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
