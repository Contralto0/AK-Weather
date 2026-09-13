"""Vorhandene Paketdateien ausschließlich lesend auf Größe und SHA-256 prüfen."""

import hashlib
import os
from pathlib import Path
import re
import stat


class PackageVerificationError(ValueError):
    """Die Datei stimmt nicht mit den vertrauenswürdigen Sollwerten überein."""


def verify_package_file(path: Path, *, size_bytes: int, sha256: str) -> None:
    """Erfolg liefert None; Abweichungen/ungültige Sollwerte lösen ValueError aus.

    OSError (einschließlich fehlender Dateien) bleibt sichtbar. Die Sollwerte müssen
    aus vertrauenswürdigen Metadaten stammen. Das Ergebnis gilt für die gelesenen
    Bytes; der Aufrufer muss spätere Änderungen vor der Verwendung verhindern.
    """
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("Die erwartete Dateigröße muss eine nichtnegative Ganzzahl sein.")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ValueError("Erwartet wird ein SHA-256-Wert mit 64 kleinen Hexadezimalzeichen.")

    with path.open("rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise PackageVerificationError("Das Paket muss eine reguläre Datei sein.")
        if metadata.st_size != size_bytes:
            raise PackageVerificationError("Die Paketgröße stimmt nicht mit dem Sollwert überein.")
        digest = hashlib.sha256()
        count = 0
        # Ein zusätzliches Byte erkennt Wachstum; nie unbegrenzt bis EOF lesen.
        while chunk := stream.read(min(1024 * 1024, size_bytes - count + 1)):
            count += len(chunk)
            if count > size_bytes:
                raise PackageVerificationError("Das Paket ist während der Prüfung größer geworden.")
            digest.update(chunk)
        if count != size_bytes:
            raise PackageVerificationError("Das Paket wurde während der Prüfung unvollständig.")
        if digest.hexdigest() != sha256:
            raise PackageVerificationError("Die SHA-256-Prüfsumme des Pakets stimmt nicht überein.")
