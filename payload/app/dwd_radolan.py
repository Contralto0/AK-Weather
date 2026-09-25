"""UI-independent import of the latest DWD RADOLAN RW precipitation grid.

The public ``fetch_latest_rw`` function downloads exactly one fixed DWD Open
Data product.  ``parse_rw`` validates and decompresses the classic RADOLAN
binary format.  Grid values remain in their compact two-byte representation
and are decoded only when ``DwdRadarFrame.pixel_at`` is called.
"""

from __future__ import annotations

import bz2
from dataclasses import dataclass, field
from datetime import datetime, timezone
import http.client
from io import BytesIO
import re
import ssl
import struct
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


RW_URL = (
    "https://opendata.dwd.de/weather/radar/radolan/rw/"
    "raa01-rw_10000-latest-dwd---bin.bz2"
)
SOURCE_LABEL = (
    "Deutscher Wetterdienst (DWD), RADOLAN RW, "
    "aktuelle Niederschlagsintensität"
)
SOURCE_URL = RW_URL
TIMEOUT_SECONDS = 20.0
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 3 * 1024 * 1024
MAX_HEADER_BYTES = 16 * 1024
READ_CHUNK_BYTES = 64 * 1024

_VALUE_MASK = 0x0FFF
_INTERPOLATED_MASK = 0x1000
_MISSING_MASK = 0x2000
_CLUTTER_MASK = 0x8000
_SUPPORTED_GRIDS = frozenset({(900, 900), (1100, 900)})  # rows, columns


class DwdRadolanProviderError(RuntimeError):
    """Base class for controlled RADOLAN provider failures."""


class DwdRadolanNetworkError(DwdRadolanProviderError):
    """The DWD service could not be reached."""


class DwdRadolanTimeoutError(DwdRadolanNetworkError):
    """The DWD request timed out."""


class DwdRadolanTlsError(DwdRadolanNetworkError):
    """TLS negotiation or certificate validation failed."""


class DwdRadolanRedirectError(DwdRadolanNetworkError):
    """The fixed DWD endpoint attempted to redirect the request."""


class DwdRadolanHttpError(DwdRadolanNetworkError):
    """The DWD service returned an HTTP error."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"DWD-RADOLAN antwortete mit HTTP-Status {status}.")


class DwdRadolanDownloadLimitError(DwdRadolanProviderError):
    """The compressed response exceeded its fixed safety limit."""


class DwdRadolanDecompressionError(DwdRadolanProviderError):
    """The response is not exactly one complete BZip2 stream."""


class DwdRadolanUncompressedLimitError(DwdRadolanDecompressionError):
    """The decompressed RADOLAN product exceeded its safety limit."""


class DwdRadolanHeaderError(DwdRadolanProviderError):
    """The RADOLAN ASCII header is absent or malformed."""


class DwdRadolanTimestampError(DwdRadolanHeaderError):
    """The RADOLAN UTC observation time is invalid."""


class DwdRadolanSchemaError(DwdRadolanHeaderError):
    """Required RW metadata is missing, duplicated, or unsupported."""


class DwdRadolanProductError(DwdRadolanSchemaError):
    """The product is not RADOLAN RW."""


class DwdRadolanGridError(DwdRadolanSchemaError):
    """The grid dimensions are not supported for the classic RW feed."""


class DwdRadolanPayloadLengthError(DwdRadolanProviderError):
    """The binary block length does not match the declared grid."""


@dataclass(frozen=True)
class DwdRadarPixel:
    """One decoded RW grid cell and its quality flags."""

    precipitation_mm_per_hour: float | None
    is_interpolated: bool
    is_missing: bool
    is_clutter: bool


@dataclass(frozen=True)
class DwdRadarFrame:
    """One complete RW observation whose first cell is at the lower left."""

    observed_at: datetime
    interval_minutes: int
    width: int
    height: int
    precision_exponent: int
    _raw_values: bytes = field(repr=False)
    source_label: str = field(default=SOURCE_LABEL, init=False)
    source_url: str = field(default=SOURCE_URL, init=False)

    def pixel_at(self, column: int, row_from_south: int) -> DwdRadarPixel:
        """Decode the zero-based cell at ``column, row_from_south``."""

        if isinstance(column, bool) or not isinstance(column, int):
            raise TypeError("Spaltenindex muss eine ganze Zahl sein.")
        if isinstance(row_from_south, bool) or not isinstance(row_from_south, int):
            raise TypeError("Zeilenindex muss eine ganze Zahl sein.")
        if not 0 <= column < self.width or not 0 <= row_from_south < self.height:
            raise IndexError("RADOLAN-Rasterkoordinate liegt außerhalb des Rasters.")

        offset = (row_from_south * self.width + column) * 2
        raw_value = struct.unpack_from("<H", self._raw_values, offset)[0]
        is_missing = bool(raw_value & _MISSING_MASK)
        value = raw_value & _VALUE_MASK
        # RW is accepted only with PR E-01. Division gives the same float
        # representation as ordinary decimal literals such as 1.2.
        precipitation = None if is_missing else value / 10.0
        return DwdRadarPixel(
            precipitation_mm_per_hour=precipitation,
            is_interpolated=bool(raw_value & _INTERPOLATED_MASK),
            is_missing=is_missing,
            is_clutter=bool(raw_value & _CLUTTER_MASK),
        )


Transport = Callable[[str, float], bytes]


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise DwdRadolanRedirectError(
            "Der feste DWD-RADOLAN-Endpunkt darf nicht umgeleitet werden."
        )


def _download(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "AK-Weather/0.1.3 DWD-RADOLAN-RW",
            "Accept": "application/x-bzip2, application/octet-stream",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(_RejectRedirectHandler()).open(request, timeout=timeout) as response:
            if response.geturl() != url:
                raise DwdRadolanRedirectError(
                    "DWD-RADOLAN wurde von einer anderen Adresse geliefert."
                )
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise DwdRadolanDownloadLimitError(
                        "DWD-RADOLAN meldete eine ungültige Downloadgröße."
                    ) from error
                if declared_length < 0 or declared_length > MAX_DOWNLOAD_BYTES:
                    raise DwdRadolanDownloadLimitError(
                        "DWD-RADOLAN überschreitet die erlaubte Downloadgröße."
                    )
            result = BytesIO()
            total = 0
            while chunk := response.read(min(READ_CHUNK_BYTES, MAX_DOWNLOAD_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise DwdRadolanDownloadLimitError(
                        "DWD-RADOLAN überschreitet die erlaubte Downloadgröße."
                    )
                result.write(chunk)
            return result.getvalue()
    except DwdRadolanProviderError:
        raise
    except HTTPError as error:
        raise DwdRadolanHttpError(error.code) from error
    except ssl.SSLError as error:
        raise DwdRadolanTlsError(
            "TLS-Verbindung zu DWD konnte nicht geprüft werden."
        ) from error
    except TimeoutError as error:
        raise DwdRadolanTimeoutError(
            "Zeitüberschreitung beim Abruf von DWD-RADOLAN."
        ) from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdRadolanTimeoutError(
                "Zeitüberschreitung beim Abruf von DWD-RADOLAN."
            ) from error
        if isinstance(error.reason, ssl.SSLError):
            raise DwdRadolanTlsError(
                "TLS-Verbindung zu DWD konnte nicht geprüft werden."
            ) from error
        raise DwdRadolanNetworkError("DWD-RADOLAN ist nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise DwdRadolanNetworkError("DWD-RADOLAN ist nicht erreichbar.") from error


def fetch_latest_rw(*, transport: Transport | None = None) -> DwdRadarFrame:
    """Download and parse the latest classic DWD RADOLAN RW grid."""

    selected_transport = transport or _download
    compressed = _call_transport(selected_transport)
    return parse_rw(compressed)


def _call_transport(transport: Transport) -> bytes:
    try:
        downloaded = transport(RW_URL, TIMEOUT_SECONDS)
    except DwdRadolanProviderError:
        raise
    except HTTPError as error:
        raise DwdRadolanHttpError(error.code) from error
    except ssl.SSLError as error:
        raise DwdRadolanTlsError(
            "TLS-Verbindung zu DWD konnte nicht geprüft werden."
        ) from error
    except TimeoutError as error:
        raise DwdRadolanTimeoutError(
            "Zeitüberschreitung beim Abruf von DWD-RADOLAN."
        ) from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdRadolanTimeoutError(
                "Zeitüberschreitung beim Abruf von DWD-RADOLAN."
            ) from error
        if isinstance(error.reason, ssl.SSLError):
            raise DwdRadolanTlsError(
                "TLS-Verbindung zu DWD konnte nicht geprüft werden."
            ) from error
        raise DwdRadolanNetworkError("DWD-RADOLAN ist nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise DwdRadolanNetworkError("DWD-RADOLAN ist nicht erreichbar.") from error

    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise DwdRadolanNetworkError("DWD-RADOLAN-Transport lieferte keine Binärdaten.")
    result = bytes(downloaded)
    if len(result) > MAX_DOWNLOAD_BYTES:
        raise DwdRadolanDownloadLimitError(
            "DWD-RADOLAN überschreitet die erlaubte Downloadgröße."
        )
    return result


def parse_rw(compressed: bytes) -> DwdRadarFrame:
    """Parse one bounded BZip2-compressed classic RADOLAN RW product."""

    if not isinstance(compressed, (bytes, bytearray, memoryview)):
        raise DwdRadolanDecompressionError("RADOLAN-Eingabe muss binär sein.")
    source = bytes(compressed)
    if len(source) > MAX_DOWNLOAD_BYTES:
        raise DwdRadolanDownloadLimitError(
            "Komprimiertes DWD-RADOLAN-Produkt ist zu groß."
        )
    document = _decompress_bounded(source)
    return _parse_document(document)


def _decompress_bounded(source: bytes) -> bytes:
    decompressor = bz2.BZ2Decompressor()
    output = bytearray()
    pending = source
    try:
        while True:
            remaining = MAX_UNCOMPRESSED_BYTES - len(output) + 1
            chunk = decompressor.decompress(pending, max_length=remaining)
            output.extend(chunk)
            if len(output) > MAX_UNCOMPRESSED_BYTES:
                raise DwdRadolanUncompressedLimitError(
                    "Entpacktes DWD-RADOLAN-Produkt ist zu groß."
                )
            if decompressor.eof:
                if decompressor.unused_data:
                    raise DwdRadolanDecompressionError(
                        "DWD-RADOLAN enthält Daten hinter dem BZip2-Stream."
                    )
                return bytes(output)
            if decompressor.needs_input:
                raise DwdRadolanDecompressionError(
                    "DWD-RADOLAN-BZip2-Stream ist unvollständig."
                )
            if not chunk:
                raise DwdRadolanDecompressionError(
                    "DWD-RADOLAN-BZip2-Stream kann nicht weiter entpackt werden."
                )
            pending = b""
    except DwdRadolanProviderError:
        raise
    except (OSError, EOFError, ValueError) as error:
        raise DwdRadolanDecompressionError(
            "DWD-RADOLAN-BZip2-Stream ist beschädigt."
        ) from error


def _parse_document(document: bytes) -> DwdRadarFrame:
    separator = document.find(b"\x03", 0, MAX_HEADER_BYTES + 1)
    if separator < 0:
        raise DwdRadolanHeaderError(
            "RADOLAN-Header fehlt, ist zu lang oder besitzt kein ETX."
        )
    try:
        header = document[:separator].decode("ascii")
    except UnicodeError as error:
        raise DwdRadolanHeaderError("RADOLAN-Header ist kein ASCII.") from error
    if len(header) < 17:
        raise DwdRadolanHeaderError("RADOLAN-Header ist unvollständig.")
    if header[:2] != "RW":
        raise DwdRadolanProductError("RADOLAN-Produkt ist nicht RW.")

    fixed = header[2:17]
    if not re.fullmatch(r"[0-9]{15}", fixed, re.ASCII):
        raise DwdRadolanHeaderError("RADOLAN-Kopf enthält keine gültige Zeitgruppe.")
    day, hour, minute = int(fixed[0:2]), int(fixed[2:4]), int(fixed[4:6])
    station = fixed[6:11]
    month, year = int(fixed[11:13]), 2000 + int(fixed[13:15])
    if station != "10000":
        raise DwdRadolanSchemaError("RADOLAN-RW stammt nicht vom Komposit 10000.")
    try:
        observed_at = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError as error:
        raise DwdRadolanTimestampError("RADOLAN-Zeitstempel ist ungültig.") from error

    metadata = header[17:]
    precision_text = _single_header_value(
        metadata, r"PR\s*(E[+-][0-9]{2})", "PR"
    )
    if precision_text != "E-01":
        raise DwdRadolanSchemaError("RADOLAN-RW muss PR E-01 verwenden.")
    interval_text = _single_header_value(metadata, r"INT\s*([0-9]{1,4})", "INT")
    interval = int(interval_text)
    if interval != 60:
        raise DwdRadolanSchemaError("RADOLAN-RW muss INT 60 verwenden.")
    grid_text = _single_header_value(
        metadata, r"GP\s*([0-9]{3,4})x\s*([0-9]{3,4})", "GP"
    )
    rows, columns = (int(value) for value in grid_text)
    if (rows, columns) not in _SUPPORTED_GRIDS:
        raise DwdRadolanGridError(
            "RADOLAN-RW besitzt keine unterstützte offizielle Rastergröße."
        )

    payload = document[separator + 1:]
    expected_length = rows * columns * 2
    if len(payload) != expected_length:
        raise DwdRadolanPayloadLengthError(
            "RADOLAN-Binärblock passt nicht zur deklarierten Rastergröße."
        )
    return DwdRadarFrame(
        observed_at=observed_at,
        interval_minutes=interval,
        width=columns,
        height=rows,
        precision_exponent=-1,
        _raw_values=payload,
    )


def _single_header_value(metadata: str, pattern: str, field_name: str):
    matches = re.findall(pattern, metadata, re.ASCII)
    if len(matches) != 1:
        raise DwdRadolanSchemaError(
            f"RADOLAN-Header muss genau ein gültiges {field_name}-Feld enthalten."
        )
    return matches[0]
