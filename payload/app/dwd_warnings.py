"""UI-independent import of current German DWD CAP warnings by WarnCellID.

``get_warnings`` accepts only a nine-digit DWD WarnCellID whose first digit is
not zero. Invalid identifiers raise ``ValueError`` before the transport is
called. The fixed German COMMUNEUNION status feed contains the complete current
state, so the WarnCellID is never sent to DWD.

The module uses only the Python standard library. Downloads and ZIP payloads
are bounded, kept in memory, and exposed failures are split into provider error
types so callers can distinguish an unavailable service from invalid data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import http.client
from io import BytesIO
import re
import ssl
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ElementTree
import zipfile
import zlib


CAP_URL = (
    "https://opendata.dwd.de/weather/alerts/cap/COMMUNEUNION_DWD_STAT/"
    "Z_CAP_C_EDZW_LATEST_PVW_STATUS_PREMIUMDWD_COMMUNEUNION_DE.zip"
)
SOURCE = "DWD_CAP"
TIMEOUT_SECONDS = 20.0
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024
MAX_XML_BYTES = 128 * 1024 * 1024
READ_CHUNK_BYTES = 128 * 1024
_WARNCELL_ID = re.compile(r"^[1-9][0-9]{8}$")
_UNSAFE_XML_DECLARATION = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


class DwdWarningProviderError(RuntimeError):
    """Base class for failures while obtaining or interpreting DWD warnings."""


class DwdWarningNetworkError(DwdWarningProviderError):
    """The DWD service could not be reached."""


class DwdWarningTimeoutError(DwdWarningNetworkError):
    """The DWD request timed out."""


class DwdWarningHttpError(DwdWarningNetworkError):
    """The DWD service returned an HTTP error."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"DWD-Warnfeed antwortete mit HTTP-Status {status}.")


class DwdWarningDownloadLimitError(DwdWarningProviderError):
    """The compressed response exceeded the configured safety limit."""


class DwdWarningArchiveError(DwdWarningProviderError):
    """The downloaded ZIP archive is invalid."""


class DwdWarningArchiveStructureError(DwdWarningArchiveError):
    """The ZIP archive does not contain exactly the expected CAP XML entry."""


class DwdWarningUncompressedLimitError(DwdWarningArchiveError):
    """The uncompressed CAP payload exceeded the configured safety limit."""


class DwdWarningDocumentError(DwdWarningProviderError):
    """The archive does not contain a readable DWD CAP document."""


@dataclass(frozen=True)
class DwdWarning:
    """One German CAP information block that applies to the requested cell."""

    identifier: str
    warncell_ids: tuple[str, ...]
    event: str
    headline: str | None
    description: str | None
    instruction: str | None
    severity: str
    urgency: str
    certainty: str
    sent_at: datetime
    effective_at: datetime | None
    onset_at: datetime | None
    expires_at: datetime | None
    source: str = field(default=SOURCE, init=False)


Transport = Callable[[str, float], bytes]


class _DwdRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        parts = urlsplit(new_url)
        try:
            valid_port = parts.port in (None, 443)
        except ValueError:
            valid_port = False
        if (
            parts.scheme != "https"
            or parts.hostname != "opendata.dwd.de"
            or not valid_port
            or parts.username is not None
            or parts.password is not None
        ):
            raise DwdWarningNetworkError("DWD-Warnfeed leitete auf ein unzulässiges Ziel um.")
        return super().redirect_request(request, fp, code, message, headers, new_url)


def _download(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "AK-Weather/0.1.1 DWD-CAP",
            "Accept": "application/zip, application/octet-stream",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(_DwdRedirectHandler()).open(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise DwdWarningDownloadLimitError(
                        "DWD-Warnfeed meldete eine ungültige Downloadgröße."
                    ) from error
                if declared_length < 0 or declared_length > MAX_DOWNLOAD_BYTES:
                    raise DwdWarningDownloadLimitError(
                        "DWD-Warnfeed überschreitet die erlaubte Downloadgröße."
                    )
            result = BytesIO()
            total = 0
            while chunk := response.read(min(READ_CHUNK_BYTES, MAX_DOWNLOAD_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise DwdWarningDownloadLimitError(
                        "DWD-Warnfeed überschreitet die erlaubte Downloadgröße."
                    )
                result.write(chunk)
            return result.getvalue()
    except DwdWarningProviderError:
        raise
    except HTTPError as error:
        raise DwdWarningHttpError(error.code) from error
    except (TimeoutError, DwdWarningTimeoutError) as error:
        raise DwdWarningTimeoutError("Zeitüberschreitung beim Abruf des DWD-Warnfeeds.") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdWarningTimeoutError("Zeitüberschreitung beim Abruf des DWD-Warnfeeds.") from error
        raise DwdWarningNetworkError("DWD-Warnfeed ist nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException, ssl.SSLError) as error:
        raise DwdWarningNetworkError("DWD-Warnfeed ist nicht erreichbar.") from error


def get_warnings(warncell_id: str, *, transport: Transport | None = None) -> tuple[DwdWarning, ...]:
    """Return current German DWD warnings for one validated WarnCellID.

    A valid cell which is absent from the current status feed returns ``()``.
    The optional transport is intended for deterministic offline tests and has
    the signature ``transport(url, timeout_seconds) -> bytes``.
    """

    if not isinstance(warncell_id, str) or not _WARNCELL_ID.fullmatch(warncell_id):
        raise ValueError("DWD-WarnCellID muss aus genau neun Ziffern bestehen und darf nicht mit null beginnen.")

    selected_transport = transport or _download
    try:
        downloaded = selected_transport(CAP_URL, TIMEOUT_SECONDS)
    except DwdWarningProviderError:
        raise
    except HTTPError as error:
        raise DwdWarningHttpError(error.code) from error
    except TimeoutError as error:
        raise DwdWarningTimeoutError("Zeitüberschreitung beim Abruf des DWD-Warnfeeds.") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdWarningTimeoutError("Zeitüberschreitung beim Abruf des DWD-Warnfeeds.") from error
        raise DwdWarningNetworkError("DWD-Warnfeed ist nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException, ssl.SSLError) as error:
        raise DwdWarningNetworkError("DWD-Warnfeed ist nicht erreichbar.") from error

    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise DwdWarningNetworkError("DWD-Transport lieferte keine Binärdaten.")
    archive_bytes = bytes(downloaded)
    if len(archive_bytes) > MAX_DOWNLOAD_BYTES:
        raise DwdWarningDownloadLimitError("DWD-Warnfeed überschreitet die erlaubte Downloadgröße.")
    return _read_archive(archive_bytes, warncell_id)


def _read_archive(data: bytes, warncell_id: str) -> tuple[DwdWarning, ...]:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                raise DwdWarningArchiveStructureError(
                    "DWD-Warnarchiv muss genau eine CAP-XML-Datei enthalten."
                )
            entry = entries[0]
            if (
                entry.is_dir()
                or "/" in entry.filename
                or "\\" in entry.filename
                or not entry.filename.lower().endswith(".xml")
                or entry.flag_bits & 0x1
            ):
                raise DwdWarningArchiveStructureError(
                    "DWD-Warnarchiv enthält einen unerwarteten Eintrag."
                )
            if entry.compress_size > MAX_DOWNLOAD_BYTES:
                raise DwdWarningDownloadLimitError("Komprimierte CAP-Daten überschreiten die erlaubte Größe.")
            if entry.file_size > MAX_XML_BYTES:
                raise DwdWarningUncompressedLimitError(
                    "Entpackte CAP-Daten überschreiten die erlaubte Größe."
                )
            xml_data = archive.read(entry)
            if len(xml_data) > MAX_XML_BYTES or len(xml_data) != entry.file_size:
                raise DwdWarningUncompressedLimitError(
                    "Entpackte CAP-Daten überschreiten die erlaubte Größe."
                )
    except DwdWarningProviderError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, NotImplementedError, zlib.error) as error:
        raise DwdWarningArchiveError("DWD-Warnarchiv ist beschädigt oder nicht lesbar.") from error
    return _parse_cap(xml_data, warncell_id)


def _parse_cap(data: bytes, warncell_id: str) -> tuple[DwdWarning, ...]:
    if _UNSAFE_XML_DECLARATION.search(data):
        raise DwdWarningDocumentError("CAP-Dokument enthält unzulässige Entitätsdefinitionen.")
    try:
        root = ElementTree.fromstring(data)
    except (ElementTree.ParseError, ValueError, RecursionError) as error:
        raise DwdWarningDocumentError("CAP-Dokument ist kein lesbares XML.") from error
    if _local_name(root.tag) != "alert":
        raise DwdWarningDocumentError("DWD-Warnarchiv enthält kein CAP-alert-Dokument.")

    identifier = _required_text(root, "identifier")
    sent_at = _required_time(root, "sent")
    message_type = _required_text(root, "msgType")
    if message_type.casefold() not in {"alert", "update"}:
        return ()

    warnings = []
    for info in _children(root, "info"):
        language = _optional_text(info, "language")
        if language is None or not language.casefold().startswith("de"):
            continue
        cell_ids = _warncell_ids(info)
        if warncell_id not in cell_ids:
            continue
        warnings.append(
            DwdWarning(
                identifier=identifier,
                warncell_ids=cell_ids,
                event=_required_text(info, "event"),
                headline=_optional_text(info, "headline"),
                description=_optional_text(info, "description"),
                instruction=_optional_text(info, "instruction"),
                severity=_required_text(info, "severity"),
                urgency=_required_text(info, "urgency"),
                certainty=_required_text(info, "certainty"),
                sent_at=sent_at,
                effective_at=_optional_time(info, "effective"),
                onset_at=_optional_time(info, "onset"),
                expires_at=_optional_time(info, "expires"),
            )
        )
    return tuple(warnings)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _children(parent: ElementTree.Element, name: str):
    return (child for child in parent if _local_name(child.tag) == name)


def _child(parent: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next(_children(parent, name), None)


def _optional_text(parent: ElementTree.Element, name: str) -> str | None:
    child = _child(parent, name)
    if child is None:
        return None
    value = "".join(child.itertext()).strip()
    return value or None


def _required_text(parent: ElementTree.Element, name: str) -> str:
    value = _optional_text(parent, name)
    if value is None:
        raise DwdWarningDocumentError(f"CAP-Pflichtfeld {name} fehlt.")
    return value


def _parse_time(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DwdWarningDocumentError(f"CAP-Zeitfeld {name} ist ungültig.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DwdWarningDocumentError(f"CAP-Zeitfeld {name} enthält keine Zeitzone.")
    return parsed.astimezone(timezone.utc)


def _required_time(parent: ElementTree.Element, name: str) -> datetime:
    return _parse_time(_required_text(parent, name), name)


def _optional_time(parent: ElementTree.Element, name: str) -> datetime | None:
    value = _optional_text(parent, name)
    return None if value is None else _parse_time(value, name)


def _warncell_ids(info: ElementTree.Element) -> tuple[str, ...]:
    result = []
    seen = set()
    for area in _children(info, "area"):
        for geocode in _children(area, "geocode"):
            if (_optional_text(geocode, "valueName") or "").casefold() != "warncellid":
                continue
            value = _optional_text(geocode, "value")
            if value is not None and value not in seen:
                result.append(value)
                seen.add(value)
    return tuple(result)
