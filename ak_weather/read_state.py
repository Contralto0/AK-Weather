"""Lesestand der Versionshinweise außerhalb des Programmverzeichnisses speichern."""

import json
import os
from pathlib import Path
import sys
import tempfile

from .versioning import Version


class ReadStateError(ValueError):
    """Ein vorhandener Lesestand ist beschädigt; nicht still überschreiben."""


def default_state_path() -> Path:
    if sys.platform == "win32":
        configured = os.environ.get("LOCALAPPDATA")
        fallback_parts = ("AppData", "Local")
    else:
        configured = os.environ.get("XDG_STATE_HOME")
        fallback_parts = (".local", "state")
    root = (
        Path(configured)
        if configured and Path(configured).is_absolute()
        else Path.home().joinpath(*fallback_parts)
    )
    return root / "AK-Weather" / "read-state.json"


def load_last_seen(path: Path | None = None) -> Version | None:
    """Fehlende Datei bedeutet Erststart; Lesen legt weder Datei noch Ordner an."""
    path = default_state_path() if path is None else path
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeError as error:
        raise ReadStateError("Der Lesestand enthält kein gültiges UTF-8.") from error
    try:
        record = json.loads(content)
        value = record["last_seen_version"]
        if not isinstance(value, str):
            raise ValueError("Die gespeicherte Version muss ein Text sein.")
        return Version.parse(value)
    except (ValueError, KeyError, TypeError) as error:
        raise ReadStateError("Der gespeicherte Lesestand ist ungültig.") from error


def save_after_display(
    version: Version | str,
    *,
    displayed: bool,
    path: Path | None = None,
) -> Version | None:
    """Nur nach erfolgreicher Anzeige mit displayed=True aufrufen.

    False verändert nichts. Ein älterer/gleicher Stand wird nicht erneut gespeichert.
    Aufrufe müssen von der Anwendung serialisiert werden. OSError bleibt sichtbar.
    """
    if not isinstance(displayed, bool):
        raise TypeError("displayed muss ein boolescher Wert sein.")
    if not displayed:
        return None
    version = Version.parse(version) if isinstance(version, str) else version
    if not isinstance(version, Version):
        raise TypeError("version muss eine Version oder ein Versionstext sein.")
    path = default_state_path() if path is None else path
    previous = load_last_seen(path)
    if previous is not None and previous >= version:
        return previous
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump({"last_seen_version": str(version)}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return version
