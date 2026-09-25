# Versionsverlauf

## 0.1.7 - DWD-MOSMIX-Signifikantes Wetter vorbereitet - 25.09.2026

- Die UI-unabhängigen MOSMIX_L-Vorhersagepunkte enthalten zusätzlich den unveränderten amtlichen DWD-Code `ww` für signifikantes Wetter.
- DWD-Fehlwerte und eine fehlende `ww`-Reihe bleiben als `None` erkennbar; eine vorhandene fehlerhafte Reihe wird strikt abgewiesen.
- `ww` ist ein priorisierter kategorialer Wetterzustand, keine Niederschlags- oder Gewitterwahrscheinlichkeit, keine Beobachtung und keine amtliche Warnung.

## 0.1.6 - DWD-MOSMIX-Stationenkatalog vorbereitet - 25.09.2026

- UI-unabhängige, deterministische Zuordnung von WGS-84-Koordinaten zur geografisch nächsten DWD-MOSMIX-Station.
- Der unveränderliche Stationsdatensatz enthält Kennung, optionalen ICAO-Code, Namen, Koordinate und optionale Höhe; `----` bleibt kein ICAO-Code.
- Der laufend gepflegte offizielle Katalog wird ausschließlich auf ausdrücklichen Abruf per festem HTTPS-Endpunkt geladen, auf 1 MiB begrenzt, strikt geprüft und nicht zwischengespeichert.
- Bei Distanzgleichstand entscheidet die Stationskennung reproduzierbar; ungültige Eingaben oder Kataloge liefern keine geratene Ersatzstation.
- Keine Standortermittlung, Kartenansicht, Ortsoberfläche, Speicherung oder automatische DWD-Abfrage beim Start.

## 0.1.5 - DWD-POI-Wetterzustand vorbereitet - 25.09.2026

- UI-unabhängiger Import des neuesten amtlich beobachteten DWD-POI-Wetterzustands für eine explizite Stationskennung.
- Die unveränderliche Beobachtung enthält UTC-Zeit, originalen `present_weather`-Code sowie die vollständige offizielle deutsche DWD-Zuordnung für die Codes 1 bis 31.
- Fehlwert `---` bleibt ohne erfundene Bezeichnung; später unbekannte numerische Codes bleiben erhalten und werden bewusst nicht übersetzt.
- Feste HTTPS-Dateiadresse, 128-KiB-Grenze, Umleitungsablehnung und strikte Latin-1-/Semikolon-CSV-Prüfung ohne Cache oder Persistenz.
- Der Zustand ist eine Beobachtung, keine Prognose, keine Niederschlags- oder Gewitterwahrscheinlichkeit und wird von der Oberfläche noch nicht automatisch abgerufen.

## 0.1.4 - DWD-KONRAD3D-Gewitterzellen vorbereitet - 25.09.2026

- UI-unabhängiger Import des neuesten amtlichen DWD-KONRAD3D-Schnappschusses aus dem festen HTTPS-Verzeichnis.
- Erkannte konvektive Zellen enthalten DWD-Referenzzeit, WGS-84-Schwerpunkt, Hagel-, Starkregen- und Böenklasse sowie alle gelieferten Schwerpunktprognosen einschließlich verfügbarer Unsicherheitsellipsen.
- Der DWD-Ausfallwert `-1000000000` für eine nicht berechnete Böenklasse wird als `None` behandelt; gültige Nullklassen bleiben erhalten.
- Exakte Dateinamenauswahl, Größenlimits, strikte XML-/Werteprüfung und ein auf höchstens zwei ältere Verzeichniseinträge begrenzter Rückfall bei HTTP 404.
- KONRAD3D bleibt als radarobjektbasierte Kurzfristinformation gekennzeichnet und wird weder als Blitzortung noch als amtliche CAP-Warnung oder Wahrscheinlichkeit ausgegeben.
- Keine Kartenanzeige, Standortübermittlung, Speicherung, Hintergrundaktualisierung oder automatische Wetterabfrage beim Start.

## 0.1.3 – DWD-RADOLAN-RW-Regengitter vorbereitet – 25.09.2026

- UI-unabhängiger Import des aktuellen, angeeichten DWD-RADOLAN-RW-Niederschlagsrasters vom festen amtlichen HTTPS-Endpunkt.
- Strikte Prüfung von BZip2, ETX-Header, UTC-Zeit, `RW`, `INT 60`, `PR E-01`, offiziellen Rastergrößen und exakter Binärnutzlastlänge.
- Einzelpixel werden bedarfsgesteuert aus kompakten Little-Endian-16-Bit-Rohwerten gelesen; Interpolation, Fehlwert und Clutter bleiben erkennbar.
- Fehlende Pixel ergeben `None` statt `0.0`; RW bleibt als aktuelle 60-Minuten-Niederschlagsintensität klar von Prognosen und Wahrscheinlichkeiten getrennt.
- Keine Kartenanzeige, Koordinatenumrechnung, Standortermittlung, Speicherung oder Hintergrundaktualisierung.

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
