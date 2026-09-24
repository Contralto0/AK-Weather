from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload" / "app"))
from dwd_mosmix import DwdMosmixProvider, MosmixProviderError, StationRequest, parse_kml, parse_kmz

FIXTURE = Path(__file__).parent / "fixtures" / "mosmix_minimal.kml"


def fixture_kmz() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("forecast.kml", FIXTURE.read_bytes())
    return buffer.getvalue()


class MosmixParserTests(unittest.TestCase):
    def test_parses_metadata_units_missing_values_and_chronological_points(self) -> None:
        forecast = parse_kml(FIXTURE.read_bytes())
        self.assertEqual(forecast.station_id, "P0002")
        self.assertEqual(forecast.station_name, "Beispielstation")
        self.assertEqual(forecast.coordinate.latitude, 52.52)
        self.assertEqual(forecast.issued_at, datetime(2026, 9, 24, 10, tzinfo=timezone.utc))
        self.assertEqual([point.timestamp.hour for point in forecast.points], [11, 12])
        self.assertIsNone(forecast.points[0].temperature.value)
        self.assertEqual(forecast.points[1].temperature.value, 0.0)
        self.assertEqual(forecast.points[1].temperature.unit, "°C")
        self.assertEqual(forecast.points[0].wind_speed.unit, "m/s")
        self.assertEqual(forecast.points[0].wind_direction.unit, "°")
        self.assertIsNone(forecast.points[0].precipitation_probability.value)
        self.assertEqual(forecast.points[1].precipitation_probability.value, 25.0)
        self.assertEqual(forecast.points[1].precipitation_probability.unit, "%")

    def test_invalid_kmz_is_a_provider_error(self) -> None:
        with self.assertRaisesRegex(MosmixProviderError, "KMZ"):
            parse_kmz(b"not a zip archive")

    def test_download_error_is_a_provider_error_and_no_default_station_exists(self) -> None:
        provider = DwdMosmixProvider(download=lambda url, timeout: (_ for _ in ()).throw(OSError("offline")))
        with self.assertRaisesRegex(MosmixProviderError, "geladen"):
            provider.fetch(StationRequest("P0002", 52.52, 13.405))
        self.assertEqual(provider.url_for("P0002"), "https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/P0002/kml/MOSMIX_L_LATEST_P0002.kmz")

    def test_fetch_requires_complete_location_context(self) -> None:
        with self.assertRaises(ValueError):
            StationRequest("P0002", 52.52, None)  # type: ignore[arg-type]

    def test_fetch_parses_a_downloaded_station_file(self) -> None:
        forecast = DwdMosmixProvider(download=lambda url, timeout: fixture_kmz()).fetch(StationRequest("P0002", 52.52, 13.405))
        self.assertEqual(len(forecast.points), 2)


if __name__ == "__main__":
    unittest.main()
