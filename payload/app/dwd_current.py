"""Import current DWD 10-minute temperature and wind station observations.

The public ``fetch_current_conditions`` function accepts one explicit five-digit
CDC station identifier.  It downloads the two fixed ``now`` products, keeps
their observation times separate, and performs no station or location lookup.
Only the Python standard library is used.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import http.client
from io import BytesIO, StringIO
import math
import re
import ssl
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile
import zlib


TEMPERATURE_BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "climate/10_minutes/air_temperature/now"
)
WIND_BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "climate/10_minutes/wind/now"
)
SOURCE_LABEL = (
    "Deutscher Wetterdienst (DWD), Climate Data Center, "
    "10‑Minuten-Stationmessungen"
)
SOURCE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/"
    "climate/10_minutes/"
)
TIMEOUT_SECONDS = 20.0
MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
_STATION_ID = re.compile(r"^[0-9]{5}$", re.ASCII)
_PRODUCT_STATION_ID = re.compile(r"^[0-9]{1,5}$", re.ASCII)
_TIMESTAMP = re.compile(r"^[0-9]{12}$", re.ASCII)


class DwdCurrentProviderError(RuntimeError):
    """Base class for failures while obtaining or interpreting observations."""


class DwdCurrentNetworkError(DwdCurrentProviderError):
    """The DWD service could not be reached."""


class DwdCurrentTimeoutError(DwdCurrentNetworkError):
    """A DWD request timed out."""


class DwdCurrentTlsError(DwdCurrentNetworkError):
    """TLS negotiation or certificate validation failed."""


class DwdCurrentRedirectError(DwdCurrentNetworkError):
    """The DWD endpoint attempted to redirect the request."""


class DwdCurrentHttpError(DwdCurrentNetworkError):
    """The DWD service returned an HTTP error."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"DWD-Messdaten antworteten mit HTTP-Status {status}.")


class DwdCurrentNotFoundError(DwdCurrentHttpError):
    """At least one requested station product does not exist (HTTP 404)."""


class DwdCurrentDownloadLimitError(DwdCurrentProviderError):
    """A compressed response exceeded the configured safety limit."""


class DwdCurrentArchiveError(DwdCurrentProviderError):
    """A downloaded ZIP archive is invalid or unreadable."""


class DwdCurrentArchiveStructureError(DwdCurrentArchiveError):
    """A ZIP archive does not contain exactly one safe product file."""


class DwdCurrentUncompressedLimitError(DwdCurrentArchiveError):
    """An uncompressed product exceeded the configured safety limit."""


class DwdCurrentDocumentError(DwdCurrentProviderError):
    """A product CSV is not a readable DWD observation document."""


class DwdCurrentMissingColumnsError(DwdCurrentDocumentError):
    """A product CSV is missing required columns."""


class DwdCurrentEmptyDataError(DwdCurrentDocumentError):
    """A product CSV contains no observation data."""


class DwdCurrentStationMismatchError(DwdCurrentDocumentError):
    """A product CSV contains no row for the requested station."""


class DwdCurrentTimestampError(DwdCurrentDocumentError):
    """No matching row contains a parseable DWD UTC timestamp."""


class DwdCurrentQualityError(DwdCurrentDocumentError):
    """No matching row contains a parseable DWD quality code."""


@dataclass(frozen=True)
class DwdCurrentConditions:
    """Latest temperature and wind products for one explicit CDC station."""

    station_id: str
    temperature_at: datetime
    temperature_c: float | None
    relative_humidity_percent: float | None
    temperature_quality: int
    wind_at: datetime
    wind_speed_m_s: float | None
    wind_direction_degrees: float | None
    wind_quality: int
    source_label: str = field(default=SOURCE_LABEL, init=False)
    source_url: str = field(default=SOURCE_URL, init=False)


Transport = Callable[[str, float], bytes]


@dataclass(frozen=True)
class _ProductRecord:
    observed_at: datetime
    quality: int
    first_value: float | None
    second_value: float | None


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise DwdCurrentRedirectError("DWD-Messdaten dürfen nicht umgeleitet werden.")


def _download(url: str, timeout: float) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "AK-Weather/0.1.2 DWD-10-Minuten-Messwerte",
            "Accept": "application/zip, application/octet-stream",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(_RejectRedirectHandler()).open(request, timeout=timeout) as response:
            if response.geturl() != url:
                raise DwdCurrentRedirectError("DWD-Messdaten wurden von einer anderen Adresse geliefert.")
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as error:
                    raise DwdCurrentDownloadLimitError(
                        "DWD-Messdaten meldeten eine ungültige Downloadgröße."
                    ) from error
                if declared_length < 0 or declared_length > MAX_DOWNLOAD_BYTES:
                    raise DwdCurrentDownloadLimitError(
                        "DWD-Messdaten überschreiten die erlaubte Downloadgröße."
                    )
            result = BytesIO()
            total = 0
            while chunk := response.read(min(READ_CHUNK_BYTES, MAX_DOWNLOAD_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise DwdCurrentDownloadLimitError(
                        "DWD-Messdaten überschreiten die erlaubte Downloadgröße."
                    )
                result.write(chunk)
            return result.getvalue()
    except DwdCurrentProviderError:
        raise
    except HTTPError as error:
        if error.code == 404:
            raise DwdCurrentNotFoundError(error.code) from error
        raise DwdCurrentHttpError(error.code) from error
    except ssl.SSLError as error:
        raise DwdCurrentTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
    except TimeoutError as error:
        raise DwdCurrentTimeoutError("Zeitüberschreitung beim Abruf der DWD-Messdaten.") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdCurrentTimeoutError("Zeitüberschreitung beim Abruf der DWD-Messdaten.") from error
        if isinstance(error.reason, ssl.SSLError):
            raise DwdCurrentTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
        raise DwdCurrentNetworkError("DWD-Messdaten sind nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise DwdCurrentNetworkError("DWD-Messdaten sind nicht erreichbar.") from error


def fetch_current_conditions(
    station_id: str, *, transport: Transport | None = None
) -> DwdCurrentConditions:
    """Return the latest temperature and wind observations for ``station_id``.

    ``station_id`` must contain exactly five ASCII digits.  The optional
    transport is for deterministic offline tests and has the signature
    ``transport(url, timeout_seconds) -> bytes``.
    """

    if not isinstance(station_id, str) or not _STATION_ID.fullmatch(station_id):
        raise ValueError("DWD-CDC-Stations-ID muss aus genau fünf ASCII-Ziffern bestehen.")

    temperature_url = f"{TEMPERATURE_BASE_URL}/10minutenwerte_TU_{station_id}_now.zip"
    wind_url = f"{WIND_BASE_URL}/10minutenwerte_wind_{station_id}_now.zip"
    selected_transport = transport or _download
    temperature_data = _call_transport(selected_transport, temperature_url)
    wind_data = _call_transport(selected_transport, wind_url)
    temperature = _read_product(
        temperature_data,
        station_id,
        required_columns=("STATIONS_ID", "MESS_DATUM", "QN", "TT_10", "RF_10"),
        value_columns=("TT_10", "RF_10"),
        product_name="Temperaturprodukt",
    )
    wind = _read_product(
        wind_data,
        station_id,
        required_columns=("STATIONS_ID", "MESS_DATUM", "QN", "FF_10", "DD_10"),
        value_columns=("FF_10", "DD_10"),
        product_name="Windprodukt",
    )
    return DwdCurrentConditions(
        station_id=station_id,
        temperature_at=temperature.observed_at,
        temperature_c=temperature.first_value,
        relative_humidity_percent=temperature.second_value,
        temperature_quality=temperature.quality,
        wind_at=wind.observed_at,
        wind_speed_m_s=wind.first_value,
        wind_direction_degrees=wind.second_value,
        wind_quality=wind.quality,
    )


def _call_transport(transport: Transport, url: str) -> bytes:
    try:
        downloaded = transport(url, TIMEOUT_SECONDS)
    except DwdCurrentProviderError:
        raise
    except HTTPError as error:
        if error.code == 404:
            raise DwdCurrentNotFoundError(error.code) from error
        raise DwdCurrentHttpError(error.code) from error
    except ssl.SSLError as error:
        raise DwdCurrentTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
    except TimeoutError as error:
        raise DwdCurrentTimeoutError("Zeitüberschreitung beim Abruf der DWD-Messdaten.") from error
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise DwdCurrentTimeoutError("Zeitüberschreitung beim Abruf der DWD-Messdaten.") from error
        if isinstance(error.reason, ssl.SSLError):
            raise DwdCurrentTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
        raise DwdCurrentNetworkError("DWD-Messdaten sind nicht erreichbar.") from error
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise DwdCurrentNetworkError("DWD-Messdaten sind nicht erreichbar.") from error
    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise DwdCurrentNetworkError("DWD-Transport lieferte keine Binärdaten.")
    result = bytes(downloaded)
    if len(result) > MAX_DOWNLOAD_BYTES:
        raise DwdCurrentDownloadLimitError(
            "DWD-Messdaten überschreiten die erlaubte Downloadgröße."
        )
    return result


def _read_product(
    data: bytes,
    station_id: str,
    *,
    required_columns: tuple[str, ...],
    value_columns: tuple[str, str],
    product_name: str,
) -> _ProductRecord:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                raise DwdCurrentArchiveStructureError(
                    f"{product_name} muss genau eine Produktdatei enthalten."
                )
            entry = entries[0]
            filename = entry.filename
            if (
                entry.is_dir()
                or not filename
                or "/" in filename
                or "\\" in filename
                or ":" in filename
                or filename in {".", ".."}
                or not filename.lower().endswith((".txt", ".csv"))
                or entry.flag_bits & 0x1
            ):
                raise DwdCurrentArchiveStructureError(
                    f"{product_name} enthält einen unerwarteten oder unsicheren Eintrag."
                )
            if entry.compress_size > MAX_DOWNLOAD_BYTES:
                raise DwdCurrentDownloadLimitError(
                    f"Komprimiertes {product_name} überschreitet die erlaubte Größe."
                )
            if entry.file_size > MAX_UNCOMPRESSED_BYTES:
                raise DwdCurrentUncompressedLimitError(
                    f"Entpacktes {product_name} überschreitet die erlaubte Größe."
                )
            output = BytesIO()
            total = 0
            with archive.open(entry, "r") as source:
                while chunk := source.read(
                    min(READ_CHUNK_BYTES, MAX_UNCOMPRESSED_BYTES - total + 1)
                ):
                    total += len(chunk)
                    if total > MAX_UNCOMPRESSED_BYTES:
                        raise DwdCurrentUncompressedLimitError(
                            f"Entpacktes {product_name} überschreitet die erlaubte Größe."
                        )
                    output.write(chunk)
            if total != entry.file_size:
                raise DwdCurrentArchiveError(f"{product_name} besitzt widersprüchliche Größenangaben.")
            document = output.getvalue()
    except DwdCurrentProviderError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, NotImplementedError, zlib.error) as error:
        raise DwdCurrentArchiveError(f"{product_name} ist beschädigt oder nicht lesbar.") from error

    return _parse_product(
        document,
        station_id,
        required_columns=required_columns,
        value_columns=value_columns,
        product_name=product_name,
    )


def _parse_product(
    data: bytes,
    station_id: str,
    *,
    required_columns: tuple[str, ...],
    value_columns: tuple[str, str],
    product_name: str,
) -> _ProductRecord:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as error:
        raise DwdCurrentDocumentError(f"{product_name} ist kein gültiges UTF-8.") from error

    try:
        rows = csv.reader(StringIO(text, newline=""), delimiter=";")
        header = next(rows, None)
    except (csv.Error, ValueError) as error:
        raise DwdCurrentDocumentError(f"{product_name} ist keine lesbare Semikolon-CSV.") from error
    if header is None or not any(cell.strip() for cell in header):
        raise DwdCurrentEmptyDataError(f"{product_name} ist leer.")
    columns = [cell.strip().upper() for cell in header]
    if len(columns) != len(set(columns)):
        raise DwdCurrentMissingColumnsError(f"{product_name} enthält doppelte Spalten.")
    missing = [column for column in required_columns if column not in columns]
    if missing:
        raise DwdCurrentMissingColumnsError(
            f"{product_name} enthält nicht alle Pflichtspalten: {', '.join(missing)}."
        )
    indexes = {column: columns.index(column) for column in required_columns}

    newest: _ProductRecord | None = None
    saw_data = False
    saw_matching_station = False
    saw_bad_timestamp = False
    saw_bad_quality = False
    saw_other_invalid = False
    try:
        for row in rows:
            if not row or not any(cell.strip() for cell in row):
                continue
            saw_data = True
            if len(row) != len(columns):
                saw_other_invalid = True
                continue
            normalized_station = _normalize_product_station(row[indexes["STATIONS_ID"]])
            if normalized_station != station_id:
                continue
            saw_matching_station = True
            try:
                observed_at = _parse_timestamp(row[indexes["MESS_DATUM"]])
            except ValueError:
                saw_bad_timestamp = True
                continue
            try:
                quality = _parse_quality(row[indexes["QN"]])
            except ValueError:
                saw_bad_quality = True
                continue
            try:
                first_value = _parse_measurement(row[indexes[value_columns[0]]])
                second_value = _parse_measurement(row[indexes[value_columns[1]]])
            except ValueError:
                saw_other_invalid = True
                continue
            record = _ProductRecord(observed_at, quality, first_value, second_value)
            if newest is None or record.observed_at >= newest.observed_at:
                newest = record
    except (csv.Error, ValueError) as error:
        raise DwdCurrentDocumentError(f"{product_name} ist keine lesbare Semikolon-CSV.") from error

    if newest is not None:
        return newest
    if not saw_data:
        raise DwdCurrentEmptyDataError(f"{product_name} enthält keine Messzeilen.")
    if not saw_matching_station:
        raise DwdCurrentStationMismatchError(
            f"{product_name} enthält keine Messzeile für Station {station_id}."
        )
    if saw_bad_timestamp:
        raise DwdCurrentTimestampError(
            f"{product_name} enthält für Station {station_id} keinen parsbaren UTC-Zeitstempel."
        )
    if saw_bad_quality:
        raise DwdCurrentQualityError(
            f"{product_name} enthält für Station {station_id} keinen parsbaren Qualitätscode."
        )
    if saw_other_invalid:
        raise DwdCurrentDocumentError(
            f"{product_name} enthält für Station {station_id} keine syntaktisch gültige Messzeile."
        )
    raise DwdCurrentStationMismatchError(
        f"{product_name} enthält keine Messzeile für Station {station_id}."
    )


def _normalize_product_station(value: str) -> str | None:
    stripped = value.strip()
    if not _PRODUCT_STATION_ID.fullmatch(stripped):
        return None
    return stripped.zfill(5)


def _parse_timestamp(value: str) -> datetime:
    stripped = value.strip()
    if not _TIMESTAMP.fullmatch(stripped):
        raise ValueError("invalid timestamp")
    try:
        return datetime.strptime(stripped, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("invalid timestamp") from error


def _parse_quality(value: str) -> int:
    stripped = value.strip()
    if not re.fullmatch(r"-?[0-9]+", stripped, re.ASCII):
        raise ValueError("invalid quality")
    return int(stripped)


def _parse_measurement(value: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        raise ValueError("missing measurement")
    try:
        parsed = float(stripped)
    except ValueError as error:
        raise ValueError("invalid measurement") from error
    if not math.isfinite(parsed):
        raise ValueError("non-finite measurement")
    return None if parsed == -999.0 else parsed
