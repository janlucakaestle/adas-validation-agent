"""Thin wrapper kept for compatibility; use `python -m avval.cli [--final] reference-boxes`.

    PYTHONPATH=. python scripts/ac01_clusters.py <campaign>
"""
import sys

from avval.clusters import write_clusters
from avval.policy import LearnedACC
from avval.store import Store

if __name__ == "__main__":
    print(write_clusters(Store(), LearnedACC.load(), *sys.argv[1:]))
