"""
Pytest configuration for backend directory.
"""

import sys
from pathlib import Path

# Resolve project root: ceylix-ai
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

backend_dir = repo_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
