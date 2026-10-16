"""
Convenience CLI runner for generating dataset from inside the backend directory.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from research.generator.dataset_generator import save_dataset

if __name__ == "__main__":
    save_dataset()
