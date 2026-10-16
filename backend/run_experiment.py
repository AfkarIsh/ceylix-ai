"""
Convenience CLI runner for running benchmark experiment from inside the backend directory.
"""

import sys
import argparse
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from research.evaluation.run_experiment import run_experiment

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Ceylix AI evaluation experiment.")
    parser.add_argument("--simulate", action="store_true", help="Force deterministic simulation")
    parser.add_argument("--max-cases", type=int, default=0, help="Limit cases evaluated")
    args = parser.parse_args()

    run_experiment(
        force_simulation=args.simulate,
        max_cases=args.max_cases
    )
