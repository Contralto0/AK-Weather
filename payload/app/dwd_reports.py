"""Import current German DWD VHDL01 regional text forecasts.

The provider deliberately keeps the DWD wording intact.  In particular, text
such as a qualitative thunderstorm tendency is not converted into a number.
Only the Python standard library is used and no downloaded report is cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import http.client
import json
import math
import re
import socket
import ssl
import urllib.error
import urllib.request


BASE_URL = "https://opendata.dwd.de/weather/text_forecasts/json"
PRODUCT_ID = "VHDL01"
TIMEOUT_SECONDS = 15.0
MAX_DOWNLOAD_BYTES = 256 * 1024
READ_CHUNK_BYTES = 64 * 1024
_REGION_SLUG = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*\Z")
_SCHEMA_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)*\Z")


class DwdReportError(RuntimeError):
    """Base class for a VHDL01 report failure."""


class DwdReportDownloadError(DwdReportError):
    """The current report could not be obtained safely."""


class DwdReportFormatError(DwdReportError):
    """The downloaded content is not a usable German VHDL01 report."""


@dataclass(frozen=True)
class DwdTextElement:
    """An unchanged DWD text element within one reporting area."""

    id: str
    element: str
    text: str
    source: str | None


@dataclass(frozen=True)
class DwdTextArea:
    """A regional area to which the section's elements apply."""

    name: str
    ags: str | None
    parent_area: str | None
    elements: tuple[DwdTextElement, ...]


@dataclass(frozen=True)
class DwdTextSection:
    """One VHDL01 section and its validity window."""

    id: str
    title: str
    valid_from: datetime
    valid_to: datetime
    areas: tuple[DwdTextArea, ...]


@dataclass(frozen=True)
class DwdTextReport:
    """The validated, current German DWD VHDL01 text report."""

    schema_version: str
    product_id: str
    issuer: str
    language: str
    region: str
    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    sections: tuple[DwdTextSection, ...]


def fetch_latest_vhdl01(region_slug: str, *, timeout_seconds: float = TIMEOUT_SECONDS) -> DwdTextReport:
    """Download and parse the current VHDL01 report for one safe region slug."""

    slug = _validate_region_slug(region_slug)
    timeout = _validate_timeout(timeout_seconds)
    url = f"{BASE_URL}/{PRODUCT_ID}_{slug}_latest.json"
    return parse_vhdl01(_download(url, timeout))


def parse_vhdl01(payload: bytes) -> DwdTextReport:
    """Parse a VHDL01 JSON payload, retaining all DWD texts without changes."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise DwdReportFormatError("Der DWD-Bericht liegt nicht als Binärdaten vor.")
    try:
        document = json.loads(bytes(payload).decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise DwdReportFormatError("Der DWD-Bericht ist kein gültiges UTF-8-JSON.") from error
    if not isinstance(document, dict):
        raise DwdReportFormatError("Der DWD-Bericht muss ein JSON-Objekt enthalten.")

    schema_version = _required_schema_version(document, "schemaVersion")
    product_id = _required_string(document, "productId")
    if product_id != PRODUCT_ID:
        raise DwdReportFormatError("Der DWD-Bericht ist kein VHDL01-Produkt.")
    issuer = _required_string(document, "issuer")
    language = _required_string(document, "language")
    if not _is_german(language):
        raise DwdReportFormatError("Der DWD-Bericht ist nicht deutschsprachig.")

    sections = _required_list(document, "sections")
    if not sections:
        raise DwdReportFormatError("Der DWD-Bericht enthält keine Abschnitte.")
    return DwdTextReport(
        schema_version=schema_version,
        product_id=product_id,
        issuer=issuer,
        language=language,
        region=_required_string(document, "region"),
        issued_at=_required_time(document, "issued"),
        valid_from=_required_time(document, "validFrom"),
        valid_to=_required_time(document, "validTo"),
        sections=tuple(_parse_section(section) for section in sections),
    )


def _download(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AK-Weather/0.1.0 DWD-VHDL01",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            _check_content_length(response.headers.get("Content-Length"))
            chunks = []
            total = 0
            while chunk := response.read(min(READ_CHUNK_BYTES, MAX_DOWNLOAD_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise DwdReportDownloadError("Der DWD-Bericht überschreitet die erlaubte Größe.")
                chunks.append(chunk)
            return b"".join(chunks)
    except DwdReportDownloadError:
        raise
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout,
            ConnectionError, OSError, http.client.HTTPException, ssl.SSLError) as error:
        raise DwdReportDownloadError("Der DWD-Bericht konnte nicht heruntergeladen werden.") from error


def _check_content_length(value: object) -> None:
    if value is None:
        return
    try:
        length = int(value)
    except (TypeError, ValueError) as error:
        raise DwdReportDownloadError("Der DWD-Bericht meldet eine ungültige Größe.") from error
    if length < 0 or length > MAX_DOWNLOAD_BYTES:
        raise DwdReportDownloadError("Der DWD-Bericht überschreitet die erlaubte Größe.")


def _validate_region_slug(value: str) -> str:
    if not isinstance(value, str) or not _REGION_SLUG.fullmatch(value):
        raise ValueError("Der DWD-Regionsname darf nur Buchstaben und Bindestriche enthalten.")
    return value


def _validate_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("timeout_seconds muss eine positive endliche Zahl sein.")
    return float(value)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("doppeltes JSON-Feld")
        result[key] = value
    return result


def _parse_section(value: object) -> DwdTextSection:
    section = _required_object(value, "Abschnitt")
    time_range = _required_object(section.get("timeRange"), "Abschnitt.timeRange")
    areas = _required_list(section, "area")
    if not areas:
        raise DwdReportFormatError("Ein DWD-Abschnitt enthält keine Gebiete.")
    return DwdTextSection(
        id=_required_string(section, "id"),
        title=_required_string(section, "title"),
        valid_from=_required_time(time_range, "from"),
        valid_to=_required_time(time_range, "to"),
        areas=tuple(_parse_area(area) for area in areas),
    )


def _parse_area(value: object) -> DwdTextArea:
    area = _required_object(value, "Gebiet")
    elements = _required_list(area, "elements")
    if not elements:
        raise DwdReportFormatError("Ein DWD-Gebiet enthält keine Elemente.")
    return DwdTextArea(
        name=_required_string(area, "name"),
        ags=_optional_string(area, "ags"),
        parent_area=_optional_string(area, "parentArea"),
        elements=tuple(_parse_element(element) for element in elements),
    )


def _parse_element(value: object) -> DwdTextElement:
    element = _required_object(value, "Element")
    source = _optional_string(element, "source")
    if source not in (None, "MAN", "AUTO"):
        raise DwdReportFormatError("Ein DWD-Element enthält eine unbekannte Herkunft.")
    return DwdTextElement(
        id=_required_string(element, "id"),
        element=_required_string(element, "element"),
        text=_required_string(element, "text"),
        source=source,
    )


def _required_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DwdReportFormatError(f"DWD-Pflichtstruktur {name} fehlt oder ist ungültig.")
    return value


def _required_list(parent: dict[str, object], name: str) -> list[object]:
    value = parent.get(name)
    if not isinstance(value, list):
        raise DwdReportFormatError(f"DWD-Pflichtfeld {name} fehlt oder ist ungültig.")
    return value


def _required_string(parent: dict[str, object], name: str) -> str:
    value = parent.get(name)
    if not isinstance(value, str) or not value:
        raise DwdReportFormatError(f"DWD-Pflichtfeld {name} fehlt oder ist ungültig.")
    return value


def _optional_string(parent: dict[str, object], name: str) -> str | None:
    value = parent.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise DwdReportFormatError(f"DWD-Feld {name} ist ungültig.")
    return value


def _required_schema_version(parent: dict[str, object], name: str) -> str:
    value = _required_string(parent, name)
    if not _SCHEMA_VERSION.fullmatch(value):
        raise DwdReportFormatError("Der DWD-Bericht enthält keine numerische Schema-Version.")
    return value


def _required_time(parent: dict[str, object], name: str) -> datetime:
    value = _required_string(parent, name)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DwdReportFormatError(f"DWD-Zeitfeld {name} ist ungültig.") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise DwdReportFormatError(f"DWD-Zeitfeld {name} enthält keine Zeitzone.")
    return result.astimezone(timezone.utc)


def _is_german(language: str) -> bool:
    normalized = language.casefold()
    return normalized == "de" or normalized.startswith("de-")
