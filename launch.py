"""Startgrundlage; der Windows-Launcher verwendet explizit portables Python."""

from pathlib import Path
import sys

# Die isolierte Embeddable-Laufzeit nimmt den Skriptordner nicht selbst auf.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ak_weather.versioning import read_version


def main() -> int:
    try:
        version = read_version()
    except (OSError, ValueError):
        print("Fehler: Die Programmversion kann nicht gelesen werden."
              " Bitte die Programmdateien pruefen.", file=sys.stderr)
        return 1
    print(f"AK-Weather {version}")
    print("Die grafische Wetteroberflaeche folgt in einer spaeteren Version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
