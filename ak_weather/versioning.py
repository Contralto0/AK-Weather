"""Fachliche Versionen: Hauptversion.Funktion.Verbesserung.Fehlerbehebung."""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
import os
import re
import tempfile
from typing import Iterable


VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


class Change(IntEnum):
    MAJOR = 0
    FEATURE = 1
    IMPROVEMENT = 2
    FIX = 3


@dataclass(frozen=True, order=True)
class Version:
    major: int
    feature: int
    improvement: int
    fix: int

    def __post_init__(self) -> None:
        if any(type(value) is not int or value < 0 for value in self.parts):
            raise ValueError("Versionsstellen müssen nichtnegative ganze Zahlen sein.")

    @property
    def parts(self) -> tuple[int, int, int, int]:
        return self.major, self.feature, self.improvement, self.fix

    @classmethod
    def parse(cls, value: str) -> "Version":
        if re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){3}", value) is None:
            raise ValueError("Erwartet: Hauptversion.Funktion.Verbesserung.Fehlerbehebung.")
        return cls(*(int(part) for part in value.split(".")))

    def __str__(self) -> str:
        return ".".join(str(part) for part in self.parts)

    def advance(self, changes: Iterable[Change]) -> "Version":
        categories = tuple(changes)
        if not categories:
            return self
        if any(not isinstance(change, Change) for change in categories):
            raise ValueError("Änderungsarten müssen Werte aus Change sein.")
        position = min(categories).value
        parts = list(self.parts)
        parts[position] += 1
        parts[position + 1:] = [0] * (3 - position)
        return Version(*parts)


def read_version(path: Path = VERSION_FILE) -> Version:
    return Version.parse(path.read_text(encoding="utf-8").strip())


def advance_version_file(changes: Iterable[Change], path: Path = VERSION_FILE) -> Version:
    """Nur für einen geprüften Teilschritt aufrufen, niemals pro Zeitplan-Aufwachen.

    Ein fehlgeschlagener Push verwendet die bereits gespeicherte Version erneut.
    Der Aufrufer muss gleichzeitige Veröffentlichungsvorgänge ausschließen.
    """
    current = read_version(path)
    updated = current.advance(changes)
    if updated == current:
        return current
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(f"{updated}\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return updated
