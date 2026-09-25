# Versionsverlauf

## 0.1.2 – Aktuelle DWD-Messwerte vorbereitet – 25.09.2026

- UI-unabhängiger Import aktueller DWD-10-Minuten-Messwerte für eine explizite fünfstellige CDC-Stations-ID.
- Temperatur, relative Luftfeuchte, Windgeschwindigkeit und Windrichtung werden mit getrennten UTC-Zeitstempeln und DWD-Qualitätscodes ausgegeben.
- Fehlwerte `-999` bleiben als `None` erkennbar; vorläufig qualitätsgeprüfte `now`-Daten werden nicht als Vorhersage oder Wahrscheinlichkeit ausgegeben.
- Feste HTTPS-Ziele, Größenlimits und strikte ZIP-/CSV-Prüfungen; Netzwerk-, HTTP-, Archiv- und Datenfehler bleiben unterscheidbar.
- Keine Standort- oder Stationssuche, Oberfläche, Zwischenspeicherung oder Hintergrundaktualisierung.

## 0.1.1 – DWD-Datenprovider vorbereitet – 25.09.2026

- UI-unabhängiger Import für eine explizit ausgewählte DWD-MOSMIX_L-Station.
- UI-unabhängiger Import aktueller deutschsprachiger DWD-CAP-Warnungen für eine explizite WarnCellID.
- Der vollständige Gemeindestatus wird mit festen Größenlimits ausschließlich im Speicher verarbeitet; die WarnCellID wird nicht an DWD übertragen.
- Netzwerk-, HTTP-, Größen-, Archiv- und CAP-Fehler bleiben von einer gültigen Zelle ohne Warnungen unterscheidbar.
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
