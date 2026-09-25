"""Import the latest observed present-weather code from one DWD POI station.

The provider downloads exactly one DWD POI ``-BEOB.csv`` file for an explicit
station identifier.  It exposes an observation, not a forecast or a
probability, and deliberately processes no other columns from the feed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import http.client
from io import BytesIO, StringIO
import re
import socket
import ssl
from types import MappingProxyType
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE_URL = "https://opendata.dwd.de/weather/weather_reports/poi/"
SOURCE_NAME = "DWD POI"
TIMEOUT_SECONDS = 20.0
MAX_DOWNLOAD_BYTES = 128 * 1024
READ_CHUNK_BYTES = 16 * 1024

_STATION_ID = re.compile(r"[A-Z0-9]{1,5}\Z", re.ASCII)
_FILE_ID = re.compile(r"[A-Z0-9_]{5}\Z", re.ASCII)
_CODE = re.compile(r"[0-9]+\Z", re.ASCII)

# DWD's April 2021 POI ``present_weather`` assignment table.  The spelling,
# including transliterations such as ``bewoelkt`` and ``Boen``, is retained
# word-for-word from the source table.
PRESENT_WEATHER_CODES = MappingProxyType({
    1: ("wolkenlos", "wolkenlos"),
    2: ("heiter", "heiter"),
    3: ("bewoelkt", "bewoelkt"),
    4: ("bedeckt", "bedeckt"),
    5: ("Nebel", "Nebel"),
    6: ("Nebel", "gefrierender Nebel"),
    7: ("Regen", "leichter Regen"),
    8: ("Regen", "Regen"),
    9: ("Regen", "kraeftiger Regen"),
    10: ("Schneeregen", "gefrierender Regen"),
    11: ("Schneeregen", "kraeftiger gefrierender Regen"),
    12: ("Schneeregen", "Schneeregen"),
    13: ("Schneeregen", "kraeftiger Schneeregen"),
    14: ("Schneefall", "leichter Schneefall"),
    15: ("Schneefall", "Schneefall"),
    16: ("Schneefall", "kraeftiger Schneefall"),
    17: ("Schneefall", "Eiskoerner"),
    18: ("Regenschauer", "Regenschauer"),
    19: ("Regenschauer", "kraeftiger Regenschauer"),
    20: ("Schneeregenschau", "Schneeregenschauer"),
    21: ("Schneeschauer", "kraeftiger Schneeregenschauer"),
    22: ("Schneeschauer", "Schneeschauer"),
    23: ("Schneeschauer", "kraeftiger Schneeschauer"),
    24: ("Schneeschauer", "Graupelschauer"),
    25: ("Schneeschauer", "kraeftiger Graupelschauer"),
    26: ("Gewitter", "Gewitter ohne Niederschlag"),
    27: ("Gewitter", "Gewitter"),
    28: ("Gewitter", "kraeftiges Gewitter"),
    29: ("Gewitter", "Gewitter mit Hagel"),
    30: ("Gewitter", "kraeftiges Gewitter mit Hagel"),
    31: ("Sturm", "Boen"),
})


class DwdPoiUnavailable(RuntimeError):
    """The exact DWD POI file could not be obtained safely."""


class DwdPoiFormatError(RuntimeError):
    """The downloaded POI file is not a usable DWD observation document."""


@dataclass(frozen=True)
class PresentWeather:
    """The newest observed DWD POI present-weather value for one station."""

    station_id: str
    observed_at: datetime
    code: int | None
    short_label_de: str | None
    long_label_de: str | None
    source_url: str
    source_name: str = field(default=SOURCE_NAME, init=False)


class Transport(Protocol):
    """Offline-test seam for one bounded DWD byte download."""

    def get_bytes(self, url: str, limit: int) -> bytes: ...


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise DwdPoiUnavailable("DWD-POI-Dateien duerfen nicht umgeleitet werden.")


class _HttpsDwdTransport:
    """The production transport; it admits only the fixed DWD POI URL schema."""

    def get_bytes(self, url: str, limit: int) -> bytes:
        _validate_download_url(url)
        if limit != MAX_DOWNLOAD_BYTES:
            raise DwdPoiUnavailable("DWD-POI-Downloadlimit ist ungueltig.")
        request = Request(
            url,
            headers={
                "User-Agent": "AK-Weather/0.1.5 DWD-POI",
                "Accept": "text/csv, text/plain",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with build_opener(_RejectRedirectHandler()).open(
                request, timeout=TIMEOUT_SECONDS
            ) as response:
                if response.geturl() != url:
                    raise DwdPoiUnavailable("DWD-POI-Datei wurde umgeleitet.")
                _check_content_length(response.headers.get("Content-Length"), limit)
                output = BytesIO()
                total = 0
                while chunk := response.read(min(READ_CHUNK_BYTES, limit - total + 1)):
                    total += len(chunk)
                    if total > limit:
                        raise DwdPoiUnavailable(
                            "DWD-POI-Datei ueberschreitet die erlaubte Groesse."
                        )
                    output.write(chunk)
                return output.getvalue()
        except DwdPoiUnavailable:
            raise
        except (HTTPError, URLError, TimeoutError, socket.timeout, ssl.SSLError,
                ConnectionError, OSError, http.client.HTTPException) as error:
            raise DwdPoiUnavailable("DWD-POI-Datei ist nicht erreichbar.") from error


def fetch_latest_present_weather(
    station_id: str, *, transport: Transport | None = None
) -> PresentWeather:
    """Return the newest observed present-weather value for ``station_id``.

    ``station_id`` is one to five uppercase ASCII letters or digits.  IDs
    shorter than five characters are right-padded with underscores only for
    the documented DWD POI filename.  ``transport`` is an optional offline
    test seam exposing ``get_bytes(url, limit) -> bytes``.
    """

    normalized_id = _validate_station_id(station_id)
    source_url = _source_url(normalized_id)
    selected_transport: Transport = transport if transport is not None else _HttpsDwdTransport()
    payload = _call_transport(selected_transport, source_url)
    return _parse_poi(payload, normalized_id, source_url)


def _validate_station_id(value: str) -> str:
    if not isinstance(value, str) or not _STATION_ID.fullmatch(value):
        raise ValueError(
            "DWD-POI-Stationskennung muss aus ein bis fuenf Grossbuchstaben oder Ziffern bestehen."
        )
    return value


def _source_url(station_id: str) -> str:
    return BASE_URL + station_id.ljust(5, "_") + "-BEOB.csv"


def _validate_download_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise DwdPoiUnavailable("DWD-POI-Adresse ist ungueltig.") from error
    prefix = "/weather/weather_reports/poi/"
    filename = parts.path[len(prefix):] if parts.path.startswith(prefix) else ""
    if (
        parts.scheme != "https"
        or parts.netloc != "opendata.dwd.de"
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or parts.query
        or parts.fragment
        or not filename.endswith("-BEOB.csv")
        or not _FILE_ID.fullmatch(filename[:-9])
    ):
        raise DwdPoiUnavailable("Nur die feste HTTPS-Adresse des DWD-POI-Feeds ist erlaubt.")


def _check_content_length(value: object, limit: int) -> None:
    if value is None:
        return
    try:
        length = int(value)
    except (TypeError, ValueError) as error:
        raise DwdPoiUnavailable("DWD-POI-Datei meldet eine ungueltige Groesse.") from error
    if length < 0 or length > limit:
        raise DwdPoiUnavailable("DWD-POI-Datei ueberschreitet die erlaubte Groesse.")


def _call_transport(transport: Transport, source_url: str) -> bytes:
    try:
        downloaded = transport.get_bytes(source_url, MAX_DOWNLOAD_BYTES)
    except DwdPoiUnavailable:
        raise
    except (HTTPError, URLError, TimeoutError, socket.timeout, ssl.SSLError,
            ConnectionError, OSError, http.client.HTTPException, AttributeError) as error:
        raise DwdPoiUnavailable("DWD-POI-Datei ist nicht erreichbar.") from error
    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise DwdPoiUnavailable("DWD-POI-Transport lieferte keine Binaerdaten.")
    result = bytes(downloaded)
    if len(result) > MAX_DOWNLOAD_BYTES:
        raise DwdPoiUnavailable("DWD-POI-Datei ueberschreitet die erlaubte Groesse.")
    return result


def _parse_poi(payload: bytes, station_id: str, source_url: str) -> PresentWeather:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise DwdPoiFormatError("DWD-POI-Eingabe muss binaer sein.")
    try:
        text = bytes(payload).decode("latin-1")
        rows = csv.reader(StringIO(text, newline=""), delimiter=";", strict=True)
        headers = [next(rows) for _ in range(3)]
    except (UnicodeError, csv.Error, StopIteration, ValueError) as error:
        raise DwdPoiFormatError("DWD-POI-Datei besitzt keine drei lesbaren Kopfzeilen.") from error
    if any(not header or not any(cell.strip() for cell in header) for header in headers):
        raise DwdPoiFormatError("DWD-POI-Datei besitzt ungueltige Kopfzeilen.")

    header = _find_column_header(headers)
    columns = [cell.strip().casefold() for cell in header]
    if len(columns) != len(set(columns)) or "present_weather" not in columns:
        raise DwdPoiFormatError("DWD-POI-Datei besitzt keine eindeutige present_weather-Spalte.")
    if len(columns) < 3:
        raise DwdPoiFormatError("DWD-POI-Datei besitzt keine Datums- und Zeitspalten.")
    weather_index = columns.index("present_weather")

    newest: tuple[datetime, int | None, str | None, str | None] | None = None
    saw_data = False
    try:
        for row in rows:
            if not row or not any(cell.strip() for cell in row):
                continue
            saw_data = True
            if len(row) != len(columns):
                raise DwdPoiFormatError("DWD-POI-Datenzeile besitzt eine falsche Spaltenzahl.")
            observed_at = _parse_observed_at(row[0], row[1])
            code, short_label, long_label = _parse_present_weather(row[weather_index])
            record = (observed_at, code, short_label, long_label)
            if newest is None or observed_at > newest[0]:
                newest = record
    except DwdPoiFormatError:
        raise
    except (csv.Error, ValueError) as error:
        raise DwdPoiFormatError("DWD-POI-Datei ist keine lesbare Semikolon-CSV.") from error

    if not saw_data:
        raise DwdPoiFormatError("DWD-POI-Datei enthaelt keine Beobachtungszeilen.")
    if newest is None:
        raise DwdPoiFormatError("DWD-POI-Datei enthaelt keine gueltige Beobachtung.")
    return PresentWeather(
        station_id=station_id,
        observed_at=newest[0],
        code=newest[1],
        short_label_de=newest[2],
        long_label_de=newest[3],
        source_url=source_url,
    )


def _find_column_header(headers: list[list[str]]) -> list[str]:
    matching = [header for header in headers if "present_weather" in {cell.strip().casefold() for cell in header}]
    if len(matching) != 1:
        raise DwdPoiFormatError("DWD-POI-Kopfzeilen enthalten keine eindeutige Spaltenbezeichnung.")
    return matching[0]


def _parse_observed_at(date_value: str, time_value: str) -> datetime:
    try:
        return datetime.strptime(
            date_value.strip() + ";" + time_value.strip(), "%d.%m.%y;%H:%M"
        ).replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise DwdPoiFormatError("DWD-POI-Beobachtungszeit ist ungueltig.") from error


def _parse_present_weather(value: str) -> tuple[int | None, str | None, str | None]:
    stripped = value.strip()
    if stripped == "---":
        return None, None, None
    if not _CODE.fullmatch(stripped):
        raise DwdPoiFormatError("DWD-POI-present_weather ist ungueltig.")
    code = int(stripped)
    labels = PRESENT_WEATHER_CODES.get(code)
    if labels is None:
        return code, None, None
    return code, labels[0], labels[1]
