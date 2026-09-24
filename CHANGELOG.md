# Versionsverlauf

## 0.1.1 – MOSMIX-Provider vorbereitet – 24.09.2026

- UI-unabhängiger Import für eine explizit ausgewählte DWD-MOSMIX_L-Station.
- Keine Standortermittlung, Stationszuordnung oder automatische Wetterabfrage.
- Abrufe sind erst mit Stationskennung und Koordinaten durch einen künftigen Aufrufer möglich.

## 0.1.0 – Grundsystem – 20.09.2026

- Portable Windows-App mit Startdatei `AK-Weather.exe`.
- Grafische Übersicht mit Entwicklungsstand und klar gekennzeichneten, noch ausstehenden Wetterfunktionen.
- Eingebettete Python-3.13.15-Laufzeit für Windows x64.
- Automatische Updateprüfung nach dem Start, zusätzliche manuelle Prüfung.
- Dateibasierte Updates vom GitHub-Branch `live`, ohne Releases und ohne Archivdownloads.
- SHA-256-Prüfung, getrennte Updateordner, Startprüfung und atomare Aktivierung.
- README, Benutzerhandbuch, technische Dokumentation und Nutzungsbedingungen.

Diese Version ruft noch keine Wetterdaten ab.
