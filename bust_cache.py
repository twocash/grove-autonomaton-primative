#!/usr/bin/env python3
"""
bust_cache.py - Clear Python bytecode cache

Run from repo root: python bust_cache.py
"""

import shutil
from pathlib import Path


def bust():
    root = Path(__file__).parent
    removed = 0

    # Remove __pycache__ directories
    for cache_dir in root.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
        removed += 1
        print(f"  Removed: {cache_dir.relative_to(root)}")

    # Remove .pyc files (in case any are loose)
    for pyc in root.rglob("*.pyc"):
        pyc.unlink()
        removed += 1

    # Remove .pyo files
    for pyo in root.rglob("*.pyo"):
        pyo.unlink()
        removed += 1

    print(f"\nCache busted. {removed} item(s) removed.")


if __name__ == "__main__":
    bust()
