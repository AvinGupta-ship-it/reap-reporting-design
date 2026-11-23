"""Download every raw input and write data/MANIFEST.yaml.

Usage: python scripts/fetch_data.py [--small]

``--small`` fetches only the regulatory documents and small reference files.
"""

from __future__ import annotations

import argparse

from reapschema.data.fetch import fetch_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--small", action="store_true", help="skip large weather/load downloads")
    args = parser.parse_args()
    fetch_all(include_large=not args.small)


if __name__ == "__main__":
    main()
