"""Resolve WGS-84 coordinates to the nearest DWD MOSMIX catalog station.

The catalog is downloaded only when :func:`fetch_catalog` is called.  The
module neither obtains a device location nor sends caller coordinates to DWD.
It keeps no cache; the small official catalog is parsed in memory instead.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import http.client
from io import BytesIO
import json
from math import asin, cos, isfinite, radians, sin, sqrt
import re
import socket
import ssl
import sys
from typing import Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


CATALOG_URL = (
    "https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/"
    "mosmix_stationskatalog.cfg?view=nasPublication&nn=16102"
)
TIMEOUT_SECONDS = 20.0
MAX_DOWNLOAD_BYTES = 1024 * 1024
READ_CHUNK_BYTES = 16 * 1024

_STATION_ID = re.compile(r"[A-Z0-9]{5}\Z", re.ASCII)
_ICAO = re.compile(r"[A-Z0-9]{4}\Z", re.ASCII)
_HEADER = "ID".ljust(5) + " " + "ICAO" + " " + "NAME".ljust(20) + " " + "LAT".ljust(5) + "  " + "LON".ljust(7) + " " + "ELEV".ljust(5)
_RULER = "----- ---- -------------------- -----  ------- -----"
_FIELD_SLICES = ((0, 5), (6, 10), (11, 31), (32, 37), (39, 46), (47, 52))


class DwdStationsError(RuntimeError):
    """The official DWD station catalog could not safely be used."""


class DwdStationsDownloadError(DwdStationsError):
    """The fixed HTTPS catalog endpoint was unavailable or unsafe."""


class DwdStationsFormatError(DwdStationsError):
    """The downloaded catalog does not match the documented DWD CFG schema."""


@dataclass(frozen=True)
class Station:
    """One immutable DWD MOSMIX catalog record in WGS-84 coordinates."""

    station_id: str
    icao: str | None
    name: str
    latitude: float
    longitude: float
    elevation_m: float | None


class Transport(Protocol):
    """Offline-test seam for the one bounded catalog download."""

    def get_bytes(self, url: str, limit: int) -> bytes: ...


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise DwdStationsDownloadError("Der DWD-MOSMIX-Stationenkatalog wurde umgeleitet.")


class _HttpsDwdTransport:
    """Production transport limited to the one documented DWD HTTPS URL."""

    def get_bytes(self, url: str, limit: int) -> bytes:
        _validate_download_url(url)
        if limit != MAX_DOWNLOAD_BYTES:
            raise DwdStationsDownloadError("Das DWD-MOSMIX-Downloadlimit ist ungueltig.")
        request = Request(
            url,
            headers={
                "User-Agent": "AK-Weather/0.1.6 DWD-MOSMIX-Stationskatalog",
                "Accept": "text/plain, text/*",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with build_opener(_RejectRedirectHandler()).open(
                request, timeout=TIMEOUT_SECONDS
            ) as response:
                if response.geturl() != url:
                    raise DwdStationsDownloadError(
                        "Der DWD-MOSMIX-Stationenkatalog wurde umgeleitet."
                    )
                _check_content_length(response.headers.get("Content-Length"), limit)
                output = BytesIO()
                total = 0
                while chunk := response.read(min(READ_CHUNK_BYTES, limit - total + 1)):
                    total += len(chunk)
                    if total > limit:
                        raise DwdStationsDownloadError(
                            "Der DWD-MOSMIX-Stationenkatalog ist groesser als 1 MiB."
                        )
                    output.write(chunk)
                return output.getvalue()
        except DwdStationsDownloadError:
            raise
        except (HTTPError, URLError, TimeoutError, socket.timeout, ssl.SSLError,
                ConnectionError, OSError, http.client.HTTPException) as error:
            raise DwdStationsDownloadError(
                "Der DWD-MOSMIX-Stationenkatalog ist nicht erreichbar."
            ) from error


def fetch_catalog(*, transport: Transport | None = None) -> tuple[Station, ...]:
    """Download and strictly parse the current official MOSMIX station catalog.

    ``transport`` is an optional offline-test seam.  The production transport
    only admits :data:`CATALOG_URL`, HTTPS, a 20 second socket timeout, and a
    one MiB response limit.
    """

    selected_transport: Transport = transport if transport is not None else _HttpsDwdTransport()
    payload = _call_transport(selected_transport)
    return parse_catalog(payload)


def parse_catalog(payload: bytes) -> tuple[Station, ...]:
    """Parse documented fixed-width ``ID ICAO NAME LAT LON ELEV`` CFG bytes."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise DwdStationsFormatError("Der DWD-MOSMIX-Stationenkatalog muss Binaerdaten enthalten.")
    try:
        text = bytes(payload).decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DwdStationsFormatError(
            "Der DWD-MOSMIX-Stationenkatalog ist kein UTF-8-Text."
        ) from error

    lines = text.splitlines()
    if len(lines) < 2 or not _is_valid_header(lines[0]) or lines[1].rstrip() != _RULER:
        raise DwdStationsFormatError(
            "Der DWD-MOSMIX-Stationenkatalog besitzt keinen gueltigen Kopf."
        )

    stations: list[Station] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(lines[2:], start=3):
        if not line.strip():
            continue
        station = _parse_station_line(line, line_number)
        if station.station_id in seen_ids:
            raise DwdStationsFormatError(
                f"Der DWD-MOSMIX-Stationenkatalog enthaelt die Kennung {station.station_id} doppelt."
            )
        seen_ids.add(station.station_id)
        stations.append(station)
    if not stations:
        raise DwdStationsFormatError("Der DWD-MOSMIX-Stationenkatalog enthaelt keine Stationen.")
    return tuple(stations)


def nearest_station(
    stations: Sequence[Station], latitude: float, longitude: float
) -> Station:
    """Return the geographically nearest station, then the lowest station ID.

    The deterministic secondary sort key is used only for exactly equal
    Haversine distances.  Input coordinates are validated locally before any
    station is considered.
    """

    query_latitude = _validate_coordinate(latitude, "Breitengrad", -90.0, 90.0)
    query_longitude = _validate_coordinate(longitude, "Laengengrad", -180.0, 180.0)
    if not stations:
        raise DwdStationsFormatError("Es sind keine DWD-MOSMIX-Stationen zur Auswahl vorhanden.")
    try:
        return min(
            (_validate_station(station) for station in stations),
            key=lambda station: (_haversine_km(
                query_latitude, query_longitude, station.latitude, station.longitude
            ), station.station_id),
        )
    except TypeError as error:
        raise DwdStationsFormatError("Die DWD-MOSMIX-Stationen sind nicht gueltig.") from error


def _is_valid_header(line: str) -> bool:
    return len(line) >= len(_HEADER) and line[:len(_HEADER)] == _HEADER and not line[len(_HEADER):].strip()


def _parse_station_line(line: str, line_number: int) -> Station:
    if len(line) < 52 or line[52:].strip():
        raise DwdStationsFormatError(
            f"DWD-MOSMIX-Zeile {line_number} besitzt keine gueltige Feldbreite."
        )
    values = [line[start:end].strip() for start, end in _FIELD_SLICES]
    station_id, icao_value, name, latitude_value, longitude_value, elevation_value = values
    if not _STATION_ID.fullmatch(station_id):
        raise DwdStationsFormatError(f"DWD-MOSMIX-Zeile {line_number} besitzt eine ungueltige Kennung.")
    if not name or any(ord(character) < 32 for character in name):
        raise DwdStationsFormatError(f"DWD-MOSMIX-Zeile {line_number} besitzt keinen gueltigen Namen.")
    if icao_value == "----":
        icao = None
    elif _ICAO.fullmatch(icao_value):
        icao = icao_value
    else:
        raise DwdStationsFormatError(f"DWD-MOSMIX-Zeile {line_number} besitzt einen ungueltigen ICAO-Code.")
    latitude = _parse_number(latitude_value, "Breitengrad", line_number)
    longitude = _parse_number(longitude_value, "Laengengrad", line_number)
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise DwdStationsFormatError(
            f"DWD-MOSMIX-Zeile {line_number} besitzt Koordinaten ausserhalb von WGS-84."
        )
    elevation = None if _is_missing_elevation(elevation_value) else _parse_number(
        elevation_value, "Hoehe", line_number
    )
    return Station(station_id, icao, name, latitude, longitude, elevation)


def _parse_number(value: str, description: str, line_number: int) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise DwdStationsFormatError(
            f"DWD-MOSMIX-Zeile {line_number} besitzt einen ungueltigen {description}."
        ) from error
    if not isfinite(number):
        raise DwdStationsFormatError(
            f"DWD-MOSMIX-Zeile {line_number} besitzt einen ungueltigen {description}."
        )
    return number


def _is_missing_elevation(value: str) -> bool:
    return not value or bool(re.fullmatch(r"-+", value))


def _validate_coordinate(value: object, description: str, lower: float, upper: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{description} muss eine endliche Zahl sein.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{description} muss eine endliche Zahl sein.") from error
    if not isfinite(number) or not lower <= number <= upper:
        raise ValueError(f"{description} liegt ausserhalb des gueltigen WGS-84-Bereichs.")
    return number


def _validate_station(station: Station) -> Station:
    if not isinstance(station, Station):
        raise DwdStationsFormatError("Die DWD-MOSMIX-Stationen sind nicht gueltig.")
    _validate_coordinate(station.latitude, "Stationsbreitengrad", -90.0, 90.0)
    _validate_coordinate(station.longitude, "Stationslaengengrad", -180.0, 180.0)
    if not _STATION_ID.fullmatch(station.station_id):
        raise DwdStationsFormatError("Die DWD-MOSMIX-Stationen sind nicht gueltig.")
    return station


def _haversine_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    sin_latitude = sin(latitude_delta / 2.0)
    sin_longitude = sin(longitude_delta / 2.0)
    a = sin_latitude * sin_latitude + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin_longitude * sin_longitude
    return 6371.0088 * 2.0 * asin(sqrt(min(1.0, a)))


def _validate_download_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as error:
        raise DwdStationsDownloadError("Die DWD-MOSMIX-Adresse ist ungueltig.") from error
    expected = urlsplit(CATALOG_URL)
    if (
        url != CATALOG_URL
        or parts.scheme != "https"
        or parts.hostname != "www.dwd.de"
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or parts.path != expected.path
        or parts.query != expected.query
        or parts.fragment
    ):
        raise DwdStationsDownloadError(
            "Nur die feste HTTPS-Adresse des DWD-MOSMIX-Stationenkatalogs ist erlaubt."
        )


def _check_content_length(value: object, limit: int) -> None:
    if value is None:
        return
    try:
        length = int(value)
    except (TypeError, ValueError) as error:
        raise DwdStationsDownloadError(
            "Der DWD-MOSMIX-Stationenkatalog meldet eine ungueltige Groesse."
        ) from error
    if length < 0 or length > limit:
        raise DwdStationsDownloadError(
            "Der DWD-MOSMIX-Stationenkatalog ist groesser als 1 MiB."
        )


def _call_transport(transport: Transport) -> bytes:
    try:
        downloaded = transport.get_bytes(CATALOG_URL, MAX_DOWNLOAD_BYTES)
    except DwdStationsDownloadError:
        raise
    except (HTTPError, URLError, TimeoutError, socket.timeout, ssl.SSLError,
            ConnectionError, OSError, http.client.HTTPException, AttributeError) as error:
        raise DwdStationsDownloadError(
            "Der DWD-MOSMIX-Stationenkatalog ist nicht erreichbar."
        ) from error
    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise DwdStationsDownloadError("Der DWD-MOSMIX-Transport lieferte keine Binaerdaten.")
    result = bytes(downloaded)
    if len(result) > MAX_DOWNLOAD_BYTES:
        raise DwdStationsDownloadError("Der DWD-MOSMIX-Stationenkatalog ist groesser als 1 MiB.")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Write one UTF-8 JSON station record for explicit WGS-84 coordinates."""

    parser = argparse.ArgumentParser(description="Nächste DWD-MOSMIX-Station bestimmen.")
    parser.add_argument("--latitude", required=True)
    parser.add_argument("--longitude", required=True)
    arguments = parser.parse_args(argv)
    try:
        station = nearest_station(
            fetch_catalog(), arguments.latitude, arguments.longitude
        )
    except (DwdStationsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(
        (json.dumps(asdict(station), ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
