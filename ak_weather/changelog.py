"""Versionshistorie lesen und noch nicht angezeigte Neuerungen auswählen."""

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

from .versioning import Change, Version


CHANGELOG_FILE = Path(__file__).resolve().parent.parent / "changelog.json"


class ChangelogError(ValueError):
    """Die Historie ist ungültig und darf nicht als bereits gelesen gelten."""


@dataclass(frozen=True)
class ChangelogEntry:
    version: Version
    date: date
    category: Change
    title: str
    changes: tuple[str, ...]


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Ein nichtleerer Text wird erwartet.")
    return value


def _parse_entry(record: object) -> ChangelogEntry:
    if not isinstance(record, dict):
        raise ValueError("Ein Historieneintrag muss ein Objekt sein.")
    changes = record["changes"]
    if not isinstance(changes, list) or not changes:
        raise ValueError("Die Änderungsliste darf nicht leer sein.")
    return ChangelogEntry(
        version=Version.parse(_text(record["version"])),
        date=date.fromisoformat(_text(record["date"])),
        category=Change[_text(record["category"]).upper()],
        title=_text(record["title"]),
        changes=tuple(_text(change) for change in changes),
    )


def read_changelog(path: Path = CHANGELOG_FILE) -> tuple[ChangelogEntry, ...]:
    """Liefert die vollständige Historie, neueste Version zuerst.

    Dateizugriffsfehler bleiben OSError; ungültige Inhalte werden ChangelogError.
    Zusätzliche Metadaten werden toleriert. Die Quelldatei wird nicht verändert.
    """
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ChangelogError("Die Versionshistorie enthält kein gültiges UTF-8-JSON.") from error
    if not isinstance(records, list):
        raise ChangelogError("Die Versionshistorie muss eine Liste sein.")
    entries = []
    seen = set()
    for position, record in enumerate(records, start=1):
        try:
            entry = _parse_entry(record)
        except (KeyError, ValueError, TypeError) as error:
            raise ChangelogError(f"Ungültiger Historieneintrag an Position {position}.") from error
        if entry.version in seen:
            raise ChangelogError(f"Version {entry.version} kommt mehrfach in der Historie vor.")
        seen.add(entry.version)
        entries.append(entry)
    return tuple(sorted(entries, key=lambda entry: entry.version, reverse=True))


def entries_since(
    last_seen: Version | str | None,
    path: Path = CHANGELOG_FILE,
) -> tuple[ChangelogEntry, ...]:
    """Wählt ausschließlich neuere Versionen; None bedeutet Erststart.

    Der Aufruf speichert keinen Lesestand. Erst eine spätere erfolgreiche Anzeige
    darf ihn verändern. Versionsnummern werden numerisch, nicht als Text verglichen.
    """
    if isinstance(last_seen, str):
        last_seen = Version.parse(last_seen)
    if last_seen is not None and not isinstance(last_seen, Version):
        raise TypeError("last_seen muss eine Version, ein Versionstext oder None sein.")
    entries = read_changelog(path)
    if last_seen is None:
        return entries
    return tuple(entry for entry in entries if entry.version > last_seen)
