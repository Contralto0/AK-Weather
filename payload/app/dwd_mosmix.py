"""Small, UI-independent import for DWD MOSMIX_L single-station forecasts.

The provider deliberately has no default station and does not locate a station.
Callers must pass a station identifier *and* the coordinates that were used to
select it. This makes a later location-to-station mapping explicit and prevents
an unintentional weather request without location context.

Source and file format:
https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/
https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/kml_formatbeschreibung.pdf
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from math import isfinite
import re
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import xml.etree.ElementTree as ElementTree
import zipfile


BASE_URL = "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations"
_STATION_ID = re.compile(r"^[A-Z0-9]{5}$")
_MISSING_VALUES = {"", "-", "---", "----", "nan", "-999", "-9999"}


class MosmixProviderError(RuntimeError):
    """A download, archive, or DWD KML document cannot be used."""


@dataclass(frozen=True)
class StationRequest:
    """A station chosen by a future mapping step, with its location context."""

    station_id: str
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        normalized_id = self.station_id.upper()
        if not _STATION_ID.fullmatch(normalized_id):
            raise ValueError("DWD-Stationskennung muss genau fünf Großbuchstaben oder Ziffern enthalten.")
        try:
            coordinates_are_finite = all(isfinite(float(value)) for value in (self.latitude, self.longitude))
        except (TypeError, ValueError) as error:
            raise ValueError("Koordinaten müssen endliche Zahlen sein.") from error
        if not coordinates_are_finite:
            raise ValueError("Koordinaten müssen endliche Zahlen sein.")
        if not -90 <= self.latitude <= 90 or not -180 <= self.longitude <= 180:
            raise ValueError("Koordinaten liegen außerhalb des gültigen Bereichs.")
        object.__setattr__(self, "station_id", normalized_id)


@dataclass(frozen=True)
class GeoCoordinate:
    latitude: float
    longitude: float
    elevation_m: Optional[float]


@dataclass(frozen=True)
class WeatherValue:
    """One value with an invariant output unit; ``value=None`` means DWD missing."""

    value: Optional[float]
    unit: str


@dataclass(frozen=True)
class ForecastPoint:
    timestamp: datetime
    temperature: WeatherValue
    wind_speed: WeatherValue
    wind_direction: WeatherValue
    precipitation_probability: WeatherValue
    significant_weather_code: Optional[int] = None


@dataclass(frozen=True)
class MosmixForecast:
    station_id: str
    station_name: str
    coordinate: GeoCoordinate
    issued_at: datetime
    points: tuple[ForecastPoint, ...]


Download = Callable[[str, float], bytes]


class DwdMosmixProvider:
    """Download one current MOSMIX_L station KMZ from the official DWD endpoint."""

    def __init__(self, download: Optional[Download] = None, timeout_seconds: float = 20.0) -> None:
        self._download = download or _download
        self._timeout_seconds = timeout_seconds

    def fetch(self, request: StationRequest) -> MosmixForecast:
        """Fetch the requested station. A request always requires ID and coordinates."""
        if not isinstance(request, StationRequest):
            raise TypeError("Abrufe benötigen ein StationRequest mit Stationskennung und Koordinaten.")
        try:
            kmz_bytes = self._download(self.url_for(request.station_id), self._timeout_seconds)
        except MosmixProviderError:
            raise
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            raise MosmixProviderError("DWD-MOSMIX-Datei konnte nicht geladen werden.") from error
        forecast = parse_kmz(kmz_bytes)
        if forecast.station_id.upper() != request.station_id:
            raise MosmixProviderError("DWD-Datei enthält nicht die angeforderte Stationskennung.")
        return forecast

    @staticmethod
    def url_for(station_id: str) -> str:
        normalized_id = station_id.upper()
        if not _STATION_ID.fullmatch(normalized_id):
            raise ValueError("DWD-Stationskennung muss genau fünf Großbuchstaben oder Ziffern enthalten.")
        return f"{BASE_URL}/{normalized_id}/kml/MOSMIX_L_LATEST_{normalized_id}.kmz"


def _download(url: str, timeout_seconds: float) -> bytes:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            return response.read()
    except (HTTPError, URLError, OSError, TimeoutError) as error:
        raise MosmixProviderError("DWD-MOSMIX-Datei konnte nicht geladen werden.") from error


def parse_kmz(kmz_bytes: bytes) -> MosmixForecast:
    """Extract the single KML member of a KMZ archive and parse it."""
    try:
        with zipfile.ZipFile(BytesIO(kmz_bytes)) as archive:
            kml_names = [name for name in archive.namelist() if name.lower().endswith(".kml") and not name.endswith("/")]
            if len(kml_names) != 1:
                raise MosmixProviderError("DWD-KMZ enthält nicht genau eine KML-Datei.")
            return parse_kml(archive.read(kml_names[0]))
    except MosmixProviderError:
        raise
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        raise MosmixProviderError("DWD-Antwort ist kein gültiges KMZ-Archiv.") from error


def parse_kml(kml_bytes: bytes) -> MosmixForecast:
    """Parse DWD's KML schema without binding to a hard-coded namespace URI."""
    try:
        root = ElementTree.fromstring(kml_bytes)
    except ElementTree.ParseError as error:
        raise MosmixProviderError("DWD-KML ist nicht gültiges XML.") from error
    issue_time = _parse_timestamp(_required_text(root, ".//{*}ProductDefinition/{*}IssueTime", "DWD-Erstellzeitpunkt"))
    time_steps = [_parse_timestamp(element.text or "") for element in root.findall(".//{*}ForecastTimeSteps/{*}TimeStep")]
    if not time_steps:
        raise MosmixProviderError("DWD-KML enthält keine Vorhersagezeitpunkte.")
    placemarks = root.findall(".//{*}Placemark")
    if len(placemarks) != 1:
        raise MosmixProviderError("DWD-KML enthält nicht genau eine Station.")
    placemark = placemarks[0]
    station_id = _required_text(placemark, "./{*}name", "Stationskennung")
    station_name = _required_text(placemark, "./{*}description", "Stationsname")
    coordinate = _parse_coordinate(_required_text(placemark, ".//{*}coordinates", "Stationskoordinate"))
    forecasts: dict[str, list[Optional[float]]] = {}
    significant_weather_codes: Optional[list[Optional[int]]] = None
    for element in placemark.findall(".//{*}Forecast"):
        parameter = _attribute_by_local_name(element, "elementName")
        if parameter in {"TTT", "FF", "DD", "R101"}:
            values = [_parse_dwd_value(token) for token in "".join(element.itertext()).split()]
            if len(values) != len(time_steps):
                raise MosmixProviderError(f"DWD-Werte für {parameter} passen nicht zu den Zeitpunkten.")
            forecasts[parameter] = values
        elif parameter == "ww":
            values = [_parse_significant_weather_code(token) for token in "".join(element.itertext()).split()]
            if len(values) != len(time_steps):
                raise MosmixProviderError("Invalid ww value count.")
            significant_weather_codes = values
    empty = [None] * len(time_steps)
    temperatures = forecasts.get("TTT", empty)
    wind_speeds = forecasts.get("FF", empty)
    wind_directions = forecasts.get("DD", empty)
    precipitation_probabilities = forecasts.get("R101", empty)
    weather_codes = significant_weather_codes if significant_weather_codes is not None else empty
    points = [
        ForecastPoint(
            timestamp=timestamp,
            temperature=WeatherValue(_kelvin_to_celsius(temperatures[index]), "°C"),
            wind_speed=WeatherValue(wind_speeds[index], "m/s"),
            wind_direction=WeatherValue(wind_directions[index], "°"),
            precipitation_probability=WeatherValue(precipitation_probabilities[index], "%"),
            significant_weather_code=weather_codes[index],
        )
        for index, timestamp in enumerate(time_steps)
    ]
    return MosmixForecast(station_id, station_name, coordinate, issue_time, tuple(sorted(points, key=lambda point: point.timestamp)))


def _required_text(parent: ElementTree.Element, path: str, label: str) -> str:
    element = parent.find(path)
    if element is None or not (element.text or "").strip():
        raise MosmixProviderError(f"DWD-KML enthält keinen {label}.")
    return (element.text or "").strip()


def _attribute_by_local_name(element: ElementTree.Element, name: str) -> Optional[str]:
    for key, value in element.attrib.items():
        if key.rsplit("}", 1)[-1] == name:
            return value
    return None


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise MosmixProviderError("DWD-KML enthält einen ungültigen Zeitstempel.") from error
    if parsed.tzinfo is None:
        raise MosmixProviderError("DWD-KML-Zeitstempel enthält keine Zeitzone.")
    return parsed.astimezone(timezone.utc)


def _parse_coordinate(value: str) -> GeoCoordinate:
    fields = value.strip().split(",")
    if len(fields) not in {2, 3}:
        raise MosmixProviderError("DWD-KML enthält eine ungültige Stationskoordinate.")
    try:
        longitude, latitude = (float(fields[0]), float(fields[1]))
        elevation = float(fields[2]) if len(fields) == 3 and fields[2].strip() else None
    except ValueError as error:
        raise MosmixProviderError("DWD-KML enthält eine ungültige Stationskoordinate.") from error
    return GeoCoordinate(latitude, longitude, elevation)


def _parse_dwd_value(token: str) -> Optional[float]:
    if token.strip().lower() in _MISSING_VALUES:
        return None
    try:
        return float(token)
    except ValueError as error:
        raise MosmixProviderError("DWD-KML enthält einen ungültigen Wetterwert.") from error


def _parse_significant_weather_code(token: str) -> Optional[int]:
    """Parse DWD's categorical ``ww`` code without treating it as a probability."""
    if token.strip().lower() in _MISSING_VALUES:
        return None
    if not re.fullmatch(r"[0-9]{1,2}", token):
        raise MosmixProviderError("Invalid ww weather code.")
    return int(token)


def _kelvin_to_celsius(value: Optional[float]) -> Optional[float]:
    return None if value is None else value - 273.15
