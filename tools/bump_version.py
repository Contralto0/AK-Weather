"""Versionspflege für genau einen abgeschlossenen Entwicklungsschritt."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ak_weather.versioning import Change, advance_version_file, read_version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "changes", nargs="*", choices=("major", "feature", "improvement", "fix"),
        help="Höchstrangige Kategorie gewinnt; ohne Kategorie wird nur gelesen.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur Vorschau, nichts schreiben.")
    args = parser.parse_args()
    changes = [Change[name.upper()] for name in args.changes]
    result = read_version().advance(changes) if args.dry_run else advance_version_file(changes)
    print(result)


if __name__ == "__main__":
    main()
