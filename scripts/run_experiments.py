"""Run the experiment pipeline and build the generated values and tables.

Usage: python scripts/run_experiments.py --config configs/paper.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reapschema import report
from reapschema.config import load_config
from reapschema.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/paper.yaml")
    args = parser.parse_args()
    out = run(load_config(args.config))
    generated = report.build(Path(args.config))
    print(f"results: {out}\ngenerated: {generated}")


if __name__ == "__main__":
    main()
