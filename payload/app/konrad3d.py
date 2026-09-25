"""UI-independent import of the latest DWD KONRAD3D cell snapshot.

KONRAD3D detects, tracks and extrapolates convective radar cells.  It is not
lightning detection and its severity flags are neither CAP warnings nor
probabilities.  This module deliberately exposes the DWD values unchanged.
Only the Python standard library is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
from io import BytesIO
import math
import re
import ssl
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ElementTree


DIRECTORY_URL = "https://opendata.dwd.de/weather/radar/konrad3d/"
SOURCE_LABEL = "Deutscher Wetterdienst (DWD), KONRAD3D"
TIMEOUT_SECONDS = 20.0
MAX_DIRECTORY_BYTES = 2 * 1024 * 1024
MAX_XML_BYTES = 4 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
MAX_FILE_ATTEMPTS = 3

_FILENAME = re.compile(r"KONRAD3D_([0-9]{8}T[0-9]{6})\.xml\Z", re.ASCII)
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z", re.ASCII)
_GUST_MISSING = -1_000_000_000


class Konrad3dProviderError(RuntimeError):
    """Base class for controlled KONRAD3D provider failures."""


class Konrad3dNetworkError(Konrad3dProviderError):
    """The DWD service could not be reached."""


class Konrad3dTimeoutError(Konrad3dNetworkError):
    """A DWD request timed out."""


class Konrad3dTlsError(Konrad3dNetworkError):
    """TLS negotiation or certificate validation failed."""


class Konrad3dRedirectError(Konrad3dNetworkError):
    """A fixed DWD URL attempted to redirect the request."""


class Konrad3dHttpError(Konrad3dNetworkError):
    """The DWD service returned an HTTP error."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"DWD-KONRAD3D antwortete mit HTTP-Status {status}.")


class Konrad3dNotFoundError(Konrad3dHttpError):
    """A directory entry disappeared during DWD rotation (HTTP 404)."""


class Konrad3dDownloadLimitError(Konrad3dProviderError):
    """A directory or XML response exceeded its safety limit."""


class Konrad3dDirectoryError(Konrad3dProviderError):
    """The DWD directory is unreadable or has no valid snapshot names."""


class Konrad3dXmlError(Konrad3dProviderError):
    """The response is not a safe, well-formed KONRAD3D XML document."""


class Konrad3dSchemaError(Konrad3dXmlError):
    """Required KONRAD3D fields are absent, duplicated or invalid."""


class Konrad3dTimestampError(Konrad3dSchemaError):
    """A required ISO-8601 timestamp is invalid or lacks a time zone."""


class Konrad3dCoordinateError(Konrad3dSchemaError):
    """A required WGS-84 coordinate is invalid."""


class Konrad3dFlagError(Konrad3dSchemaError):
    """A DWD severity flag has an undocumented value."""


@dataclass(frozen=True)
class CentroidForecast:
    """One DWD-provided future centroid and its optional uncertainty ellipse."""

    forecast_at: datetime
    latitude: float
    longitude: float
    major_axis_km: float | None
    minor_axis_km: float | None
    orientation_degrees: float | None


@dataclass(frozen=True)
class ConvectiveCell:
    """One detected KONRAD3D cell; flags remain DWD severity classes."""

    identifier: str
    observed_at: datetime
    latitude: float
    longitude: float
    hail_flag: int
    heavy_rain_flag: int
    gust_flag: int | None
    maximum_estimated_wind_gust_km_h: float | None
    forecasts: tuple[CentroidForecast, ...]


@dataclass(frozen=True)
class KonradSnapshot:
    """One complete KONRAD3D run from a concrete DWD source file."""

    reference_time: datetime
    source_url: str
    cells: tuple[ConvectiveCell, ...]


Transport = Callable[[str, float], bytes]


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise Konrad3dRedirectError(
            "Die festen DWD-KONRAD3D-Adressen dürfen nicht umgeleitet werden."
        )


class _DirectoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.filenames: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "a":
            return
        for name, value in attrs:
            if name.casefold() == "href" and value is not None and _FILENAME.fullmatch(value):
                self.filenames.add(value)


def fetch_latest_snapshot(*, transport: Transport | None = None) -> KonradSnapshot:
    """Download the newest listed snapshot, with at most two older 404 fallbacks."""

    selected_transport = transport or _download
    directory = _call_transport(
        selected_transport, DIRECTORY_URL, MAX_DIRECTORY_BYTES
    )
    candidates = _directory_candidates(directory)
    last_not_found: Konrad3dNotFoundError | None = None
    for filename in candidates[:MAX_FILE_ATTEMPTS]:
        source_url = DIRECTORY_URL + filename
        try:
            xml_bytes = _call_transport(
                selected_transport, source_url, MAX_XML_BYTES
            )
        except Konrad3dHttpError as error:
            if error.status != 404:
                raise
            last_not_found = (
                error
                if isinstance(error, Konrad3dNotFoundError)
                else Konrad3dNotFoundError(error.status)
            )
            continue
        return parse_snapshot(xml_bytes, source_url)
    if last_not_found is not None:
        raise last_not_found
    raise Konrad3dDirectoryError("DWD-KONRAD3D-Verzeichnis enthält keine abrufbare Datei.")


def parse_snapshot(xml_bytes: bytes, source_url: str) -> KonradSnapshot:
    """Purely parse and validate one bounded KONRAD3D XML document."""

    if not isinstance(xml_bytes, (bytes, bytearray, memoryview)):
        raise Konrad3dXmlError("KONRAD3D-Eingabe muss binär sein.")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError("KONRAD3D-Quelladresse fehlt.")
    document = bytes(xml_bytes)
    if len(document) > MAX_XML_BYTES:
        raise Konrad3dDownloadLimitError("DWD-KONRAD3D-XML ist zu groß.")
    lowered = document.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise Konrad3dXmlError("KONRAD3D-XML darf keine DTD oder Entitäten deklarieren.")
    try:
        root = ElementTree.fromstring(document)
    except (ElementTree.ParseError, ValueError) as error:
        raise Konrad3dXmlError("DWD-KONRAD3D-XML ist ungültig.") from error
    if _local_name(root.tag) != "konrad3d":
        raise Konrad3dSchemaError("KONRAD3D-Wurzelelement fehlt.")

    head = _single_child(root, "head")
    head_metadata = _single_child(head, "metadata")
    reference_time = _parse_timestamp(
        _required_text(head_metadata, "reference_time"), "Snapshot-Referenzzeit"
    )

    cells_nodes = _children(root, "cells")
    if not cells_nodes:
        raise Konrad3dSchemaError("KONRAD3D-Element cells fehlt.")
    cells: list[ConvectiveCell] = []
    for cells_node in cells_nodes:
        cells_reference = cells_node.get("reference_time")
        if cells_reference is None:
            raise Konrad3dSchemaError("KONRAD3D-cells besitzt keine Referenzzeit.")
        _parse_timestamp(cells_reference, "cells-Referenzzeit")
        for feature in _children(cells_node, "feature"):
            cells.append(_parse_cell(feature))
    return KonradSnapshot(reference_time, source_url, tuple(cells))


def _download(url: str, timeout: float) -> bytes:
    limit = MAX_DIRECTORY_BYTES if url == DIRECTORY_URL else MAX_XML_BYTES
    accept = "text/html" if url == DIRECTORY_URL else "application/xml, text/xml"
    request = Request(
        url,
        headers={
            "User-Agent": "AK-Weather/0.1.4 DWD-KONRAD3D",
            "Accept": accept,
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(_RejectRedirectHandler()).open(request, timeout=timeout) as response:
            if response.geturl() != url:
                raise Konrad3dRedirectError(
                    "DWD-KONRAD3D wurde von einer anderen Adresse geliefert."
                )
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_length = int(declared)
                except ValueError as error:
                    raise Konrad3dDownloadLimitError(
                        "DWD-KONRAD3D meldete eine ungültige Downloadgröße."
                    ) from error
                if declared_length < 0 or declared_length > limit:
                    raise Konrad3dDownloadLimitError(
                        "DWD-KONRAD3D überschreitet die erlaubte Downloadgröße."
                    )
            result = BytesIO()
            total = 0
            while chunk := response.read(min(READ_CHUNK_BYTES, limit - total + 1)):
                total += len(chunk)
                if total > limit:
                    raise Konrad3dDownloadLimitError(
                        "DWD-KONRAD3D überschreitet die erlaubte Downloadgröße."
                    )
                result.write(chunk)
            return result.getvalue()
    except Konrad3dProviderError:
        raise
    except HTTPError as error:
        _raise_http(error)
    except ssl.SSLError as error:
        raise Konrad3dTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
    except TimeoutError as error:
        raise Konrad3dTimeoutError("Zeitüberschreitung beim Abruf von DWD-KONRAD3D.") from error
    except URLError as error:
        _raise_url_error(error)
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise Konrad3dNetworkError("DWD-KONRAD3D ist nicht erreichbar.") from error
    raise AssertionError("unreachable")


def _call_transport(transport: Transport, url: str, limit: int) -> bytes:
    try:
        downloaded = transport(url, TIMEOUT_SECONDS)
    except Konrad3dProviderError:
        raise
    except HTTPError as error:
        _raise_http(error)
    except ssl.SSLError as error:
        raise Konrad3dTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
    except TimeoutError as error:
        raise Konrad3dTimeoutError("Zeitüberschreitung beim Abruf von DWD-KONRAD3D.") from error
    except URLError as error:
        _raise_url_error(error)
    except (OSError, ConnectionError, http.client.HTTPException) as error:
        raise Konrad3dNetworkError("DWD-KONRAD3D ist nicht erreichbar.") from error
    if not isinstance(downloaded, (bytes, bytearray, memoryview)):
        raise Konrad3dNetworkError("DWD-KONRAD3D-Transport lieferte keine Binärdaten.")
    result = bytes(downloaded)
    if len(result) > limit:
        raise Konrad3dDownloadLimitError(
            "DWD-KONRAD3D überschreitet die erlaubte Downloadgröße."
        )
    return result


def _raise_http(error: HTTPError) -> None:
    if error.code == 404:
        raise Konrad3dNotFoundError(error.code) from error
    raise Konrad3dHttpError(error.code) from error


def _raise_url_error(error: URLError) -> None:
    if isinstance(error.reason, TimeoutError):
        raise Konrad3dTimeoutError("Zeitüberschreitung beim Abruf von DWD-KONRAD3D.") from error
    if isinstance(error.reason, ssl.SSLError):
        raise Konrad3dTlsError("TLS-Verbindung zu DWD konnte nicht geprüft werden.") from error
    raise Konrad3dNetworkError("DWD-KONRAD3D ist nicht erreichbar.") from error


def _directory_candidates(directory: bytes) -> list[str]:
    try:
        text = directory.decode("utf-8")
    except UnicodeError as error:
        raise Konrad3dDirectoryError("DWD-KONRAD3D-Verzeichnis ist kein UTF-8.") from error
    parser = _DirectoryParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as error:
        raise Konrad3dDirectoryError("DWD-KONRAD3D-Verzeichnis ist ungültig.") from error
    candidates: list[tuple[datetime, str]] = []
    for filename in parser.filenames:
        match = _FILENAME.fullmatch(filename)
        if match is None:
            continue
        try:
            timestamp = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
        except ValueError:
            continue
        candidates.append((timestamp, filename))
    if not candidates:
        raise Konrad3dDirectoryError(
            "DWD-KONRAD3D-Verzeichnis enthält keine gültige XML-Datei."
        )
    candidates.sort(reverse=True)
    return [filename for _, filename in candidates]


def _parse_cell(feature: ElementTree.Element) -> ConvectiveCell:
    metadata = _single_child(feature, "metadata")
    identifier = _required_text(metadata, "identifier")
    observed_at = _parse_timestamp(
        _required_text(metadata, "reference_time"), "Zell-Referenzzeit"
    )

    geometry = _single_child(feature, "geometry")
    centroid = _single_child(geometry, "centroid_3d")
    coordinate = _single_child(centroid, "geodetic_coordinate")
    latitude = _coordinate(coordinate, "latitude", -90.0, 90.0)
    longitude = _coordinate(coordinate, "longitude", -180.0, 180.0)

    intensity = _single_child(feature, "intensity")
    hail_flag = _flag(intensity, "hail_flag", {0, 1, 2, 3})
    heavy_rain_flag = _flag(intensity, "heavy_rain_flag", {0, 1, 2, 3})
    raw_gust_flag = _flag(intensity, "gust_flag", {0, 1, 2, 3, _GUST_MISSING})
    gust_flag = None if raw_gust_flag == _GUST_MISSING else raw_gust_flag
    maximum_gust = _optional_float(intensity, "maximum_estimated_wind_gust")
    if maximum_gust is not None:
        gust_element = _single_child(intensity, "maximum_estimated_wind_gust")
        if gust_element.get("unit") not in (None, "km/h") or maximum_gust < 0:
            raise Konrad3dSchemaError("Maximale KONRAD3D-Böe ist nicht in km/h angegeben.")

    forecasts: list[CentroidForecast] = []
    forecast_nodes = _children(feature, "forecast")
    if len(forecast_nodes) > 1:
        raise Konrad3dSchemaError("KONRAD3D-Zelle enthält forecast mehrfach.")
    if forecast_nodes:
        collections = _children(forecast_nodes[0], "centroid_forecasts")
        if len(collections) > 1:
            raise Konrad3dSchemaError("KONRAD3D-Zelle enthält centroid_forecasts mehrfach.")
        if collections:
            forecasts = [
                _parse_forecast(node)
                for node in _children(collections[0], "centroid_forecast")
            ]

    return ConvectiveCell(
        identifier=identifier,
        observed_at=observed_at,
        latitude=latitude,
        longitude=longitude,
        hail_flag=hail_flag,
        heavy_rain_flag=heavy_rain_flag,
        gust_flag=gust_flag,
        maximum_estimated_wind_gust_km_h=maximum_gust,
        forecasts=tuple(forecasts),
    )


def _parse_forecast(node: ElementTree.Element) -> CentroidForecast:
    forecast_text = node.get("forecast_time")
    if forecast_text is None:
        raise Konrad3dSchemaError("KONRAD3D-Schwerpunktprognose besitzt keine Prognosezeit.")
    forecast_at = _parse_timestamp(forecast_text, "Prognosezeit")
    coordinate = _single_child(node, "geodetic_coordinate")
    latitude = _coordinate(coordinate, "latitude", -90.0, 90.0)
    longitude = _coordinate(coordinate, "longitude", -180.0, 180.0)

    ellipses = _children(node, "uncertainty_ellipse")
    if len(ellipses) > 1:
        raise Konrad3dSchemaError("Schwerpunktprognose enthält mehrere Unsicherheitsellipsen.")
    if ellipses:
        ellipse = ellipses[0]
        major = _required_float(ellipse, "major_axis")
        minor = _required_float(ellipse, "minor_axis")
        orientation = _required_float(ellipse, "angle")
        if major < 0 or minor < 0 or major < minor:
            raise Konrad3dSchemaError("KONRAD3D-Unsicherheitsellipse besitzt ungültige Achsen.")
        if not 0.0 <= orientation <= 360.0:
            raise Konrad3dSchemaError("KONRAD3D-Ellipsenorientierung ist ungültig.")
        for field_name in ("major_axis", "minor_axis"):
            if _single_child(ellipse, field_name).get("unit") not in (None, "km"):
                raise Konrad3dSchemaError("KONRAD3D-Ellipsenachse ist nicht in km angegeben.")
        if _single_child(ellipse, "angle").get("unit") not in (None, "degrees"):
            raise Konrad3dSchemaError("KONRAD3D-Ellipsenwinkel ist nicht in Grad angegeben.")
    else:
        major = minor = orientation = None
    return CentroidForecast(
        forecast_at, latitude, longitude, major, minor, orientation
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in parent if _local_name(child.tag) == name]


def _single_child(parent: ElementTree.Element, name: str) -> ElementTree.Element:
    matches = _children(parent, name)
    if len(matches) != 1:
        raise Konrad3dSchemaError(
            f"KONRAD3D-Feld {name} muss genau einmal vorhanden sein."
        )
    return matches[0]


def _required_text(parent: ElementTree.Element, name: str) -> str:
    text = (_single_child(parent, name).text or "").strip()
    if not text:
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist leer.")
    return text


def _parse_timestamp(text: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("time zone missing")
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as error:
        raise Konrad3dTimestampError(
            f"KONRAD3D-{field_name} ist kein gültiger ISO-8601-Zeitpunkt."
        ) from error


def _required_float(parent: ElementTree.Element, name: str) -> float:
    text = _required_text(parent, name)
    try:
        value = float(text)
    except ValueError as error:
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist keine Zahl.") from error
    if not math.isfinite(value):
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist nicht endlich.")
    return value


def _optional_float(parent: ElementTree.Element, name: str) -> float | None:
    matches = _children(parent, name)
    if not matches:
        return None
    if len(matches) != 1:
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist mehrfach vorhanden.")
    text = (matches[0].text or "").strip()
    if not text:
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist leer.")
    try:
        value = float(text)
    except ValueError as error:
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist keine Zahl.") from error
    if not math.isfinite(value):
        raise Konrad3dSchemaError(f"KONRAD3D-Feld {name} ist nicht endlich.")
    return value


def _coordinate(
    parent: ElementTree.Element, name: str, minimum: float, maximum: float
) -> float:
    element = _single_child(parent, name)
    text = (element.text or "").strip()
    try:
        value = float(text)
    except ValueError as error:
        raise Konrad3dCoordinateError(f"KONRAD3D-{name} ist keine Zahl.") from error
    if element.get("unit") not in (None, "degrees") or not minimum <= value <= maximum:
        raise Konrad3dCoordinateError(f"KONRAD3D-{name} liegt außerhalb von WGS 84.")
    return value


def _flag(parent: ElementTree.Element, name: str, allowed: set[int]) -> int:
    text = _required_text(parent, name)
    if _INTEGER.fullmatch(text) is None:
        raise Konrad3dFlagError(f"KONRAD3D-{name} ist keine ganzzahlige Klasse.")
    value = int(text)
    if value not in allowed:
        raise Konrad3dFlagError(f"KONRAD3D-{name} besitzt einen unbekannten Wert.")
    return value
