# Technische Dokumentation

## Aufbau

```text
AK-Weather.exe                 Stabiler Windows-Starter (x64)
payload/
  app/
    WeatherShell.exe           Native WPF-Oberfläche
    MainWindow.xaml            Layout und Vektorillustration
    updater.py                 Python-Updater
    dwd_mosmix.py              DWD-MOSMIX-Provider
    dwd_warnings.py            DWD-CAP-Warnungsprovider
    dwd_current.py             DWD-10-Minuten-Messwertprovider
    healthcheck.py             Offline-Startprüfung
    version.json               Versionsinformationen
  runtime/                     Eingebettetes Python 3.13.15 inklusive Lizenz
update-manifest.json           SHA-256 und Größe jeder Datei in payload
docs/                          Öffentliche Dokumentation
.ak-weather/                   Nur lokal, von Git ausgeschlossen
  update.lock                  Prozessübergreifende Updatersperre
  current.txt                  ID des aktiven Updatepakets
  manifests/<id>.json          Zugehöriges geprüftes Manifest
  versions/<id>/              Vollständiger neuer Programmstand
```

`public` ist die Wurzel des GitHub-Repositories. Der danebenliegende Entwicklungsordner des Autors gehört nicht zur öffentlichen Auslieferung. Zum Betrieb erforderliche Python-Dateien und XAML werden als Teil von `payload` öffentlich mitgeliefert.

Die Windows-Oberfläche verwendet das vorhandene .NET Framework/WPF. Der Python-Updater nutzt ausschließlich die Standardbibliothek. Es gibt keine Paketinstallation, keinen lokalen HTTP-Server, keine Browser-Laufzeit und keine System-Python-Abhängigkeit.

## Vorbereiteter DWD-MOSMIX-Import

`payload/app/dwd_mosmix.py` kapselt den offiziellen DWD-MOSMIX_L-Einzelstationsabruf. Der Provider hat bewusst keine voreingestellte Station und führt weder Standortermittlung noch Stationszuordnung aus. Ein späterer Aufrufer muss immer eine geprüfte fünfstellige DWD-Stationskennung sowie die zugehörigen Breiten- und Längengrade in `StationRequest` übergeben; ohne diesen vollständigen Kontext ist kein Abruf möglich.

Die einzige Wetterdaten-URL hat das feste Schema `https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/<ID>/kml/MOSMIX_L_LATEST_<ID>.kmz`. KMZ und KML werden ausschließlich mit der Python-Standardbibliothek gelesen. Ausgegeben werden Stationsmetadaten, die DWD-Erstellzeit, Koordinate und chronologische Zeitpunkte für `TTT` (in °C umgerechnet), `FF` (m/s), `DD` (°) und `R101` (%). DWD-Fehlwerte bleiben `None`; sie werden nie zu null. Die Oberfläche verwendet den Provider in dieser Version noch nicht.

## Vorbereiteter DWD-10-Minuten-Messwertimport

`payload/app/dwd_current.py` stellt `fetch_current_conditions(station_id, *, transport=None)` bereit. Die Schnittstelle akzeptiert ausschließlich fünf ASCII-Ziffern als explizite CDC-Stations-ID. Sie führt keine Orts-, Koordinaten- oder Stationssuche aus und setzt CDC-Stationen nicht mit MOSMIX-Stationen gleich.

Pro Aufruf werden genau die beiden festen `now`-Archive für Lufttemperatur und Wind über `https://opendata.dwd.de` mit 20 Sekunden Timeout geladen. Umleitungen werden abgelehnt. Download und entpackte Produktdatei sind je Abruf auf 4 MiB beziehungsweise 16 MiB begrenzt. Erlaubt ist genau eine unverschlüsselte CSV-/TXT-Produktdatei ohne Pfadangabe im ZIP. Die Semikolon-CSV muss die jeweiligen DWD-Pflichtfelder enthalten; aus gültigen Zeilen der angefragten normalisierten Stations-ID wird der neueste UTC-Zeitstempel gewählt.

Das unveränderliche Ergebnis `DwdCurrentConditions` enthält Temperatur (`TT_10`), relative Luftfeuchte (`RF_10`), Windgeschwindigkeit (`FF_10`) und Windrichtung (`DD_10`). DWD-Fehlwerte `-999` werden feldweise zu `None`; die ganzzahligen `QN`-Qualitätscodes bleiben erhalten. Temperatur und Wind besitzen bewusst getrennte UTC-Zeitstempel, weil die offiziellen Produkte zeitversetzt aktualisiert werden können. Die `now`-Messwerte sind laut DWD noch nicht abschließend qualitätsgesichert und können korrigiert werden; sie sind weder Prognosen noch Wahrscheinlichkeiten.

Ungültige Stations-IDs werden vor einem Abruf abgewiesen. Netzwerk-, Timeout-, TLS-, HTTP-/404-, Größen-, ZIP-, Pflichtspalten-, Stations-, Zeitstempel- und Qualitätsfehler besitzen unterscheidbare Fehlerklassen. Es gibt keinen stillen Ersatzwert, keine Persistenz, keinen Hintergrundabruf und noch keine Verwendung durch die Oberfläche. Der optionale Transport dient ausschließlich isolierten Tests.

## Vorbereiteter DWD-CAP-Warnungsimport

`payload/app/dwd_warnings.py` stellt `get_warnings(warncell_id, *, transport=None)` bereit. Die Schnittstelle akzeptiert ausschließlich neunstellige DWD-WarnCellIDs ohne führende Null und verwirft ungültige Werte vor jedem Netzwerkzugriff mit `ValueError`. Sie lädt den vollständigen deutschen `COMMUNEUNION_DWD_STAT`-Statusfeed über eine feste HTTPS-Adresse. Die angefragte WarnCellID ist nur ein lokaler Filter und wird nicht an DWD übertragen.

Das ZIP und die einzelne CAP-XML-Datei werden ausschließlich im Speicher verarbeitet. Begrenzungen für komprimierte und entpackte Daten, eine feste Archivstruktur sowie die Ablehnung von XML-Entitätsdefinitionen schützen die Verarbeitung. Zeitangaben werden als zeitzonenbewusste UTC-`datetime`-Werte ausgegeben. `severity`, `urgency` und `certainty` bleiben unveränderte CAP-Werte; insbesondere wird daraus keine numerische Wetterwahrscheinlichkeit abgeleitet.

Das Ergebnis ist ein unveränderliches Tupel aus `DwdWarning`-Datensätzen in Quellreihenfolge. Eine gültige, nicht enthaltene WarnCellID und eine CAP-Aufhebungsnachricht ergeben `()`. Netzwerk-, Timeout-, HTTP-, Downloadgrößen-, ZIP- und CAP-Fehler besitzen dagegen eigene Providerfehler und werden nicht als warnungsfreier Zustand behandelt. Geometrien, Standortauflösung, automatische Aktualisierung und die Darstellung in der Oberfläche gehören noch nicht zu diesem Baustein.

## Start und Versionswechsel

1. `AK-Weather.exe` verhindert eine zweite Instanz derselben Installation.
2. Ohne Updatezeiger wird `payload` verwendet. Andernfalls wird die SHA-256-ID aus `.ak-weather/current.txt` gelesen und das zugehörige Versionsverzeichnis ausgewählt.
3. Die eingebettete Python-Laufzeit prüft Versionsdaten, Python-Bestandteile und das Laden der WPF-Oberfläche ohne Netzwerkzugriff.
4. Die Oberfläche öffnet sich und startet die Updateprüfung als separaten Prozess. Das Ergebnis wird über UTF-8-JSON-Zeilen an die Oberfläche übertragen.
5. Der neue Stand wird für den nächsten Start aktiviert. „Jetzt neu starten“ beendet die Oberfläche mit dem internen Exitcode 42; der Starter öffnet anschließend den aktiven Stand erneut.

Schlägt die Startprüfung eines Updates fehl, versucht der Starter das ursprüngliche `payload` und zeigt einen Wiederherstellungshinweis. Dieses Grundsystem bleibt während Updates unangetastet. Ist auch das ursprüngliche Paket beschädigt, muss es neu heruntergeladen werden.

Der kleine Starter `AK-Weather.exe` bildet die stabile Protokollbasis 1. Er gehört bewusst nicht zum austauschbaren `payload`. Oberfläche, Updater und Python-Laufzeit sind automatisch aktualisierbar. Eine zukünftige Änderung des Starterprotokolls erfordert ein neues Startpaket; dies muss bei einer solchen Version gesondert angekündigt werden.

## Dateibasierter Updater

Die Quelle ist fest auf `Contralto0/AK-Weather` und `live` eingestellt:

```text
GET https://api.github.com/repos/Contralto0/AK-Weather/commits/live
GET https://raw.githubusercontent.com/Contralto0/AK-Weather/<commit>/update-manifest.json
GET https://raw.githubusercontent.com/Contralto0/AK-Weather/<commit>/payload/<dateipfad>
```

Alle Dateiabrufe verwenden dieselbe Commit-SHA. Ein während des Downloads weitergeschobener Branch erzeugt daher keinen gemischten Programmstand. Neue GitHub Releases sind weder notwendig noch beteiligt.

Das Manifest hat das folgende Format (Prüfsumme hier verkürzt):

```json
{
  "schema": 1,
  "version": "0.1.0",
  "files": [
    {"path": "app/version.json", "size": 122, "sha256": "…64 Kleinbuchstaben/Hex-Zeichen…"}
  ]
}
```

Die tatsächliche Liste muss alle Laufzeitdateien enthalten, einschließlich der notwendigen Startdateien. Das Manifest selbst liegt außerhalb von `payload`, damit keine Selbstreferenz entsteht. Die ID eines Updatepakets ist die SHA-256 der unveränderten Manifestbytes.

Der Updater ermittelt die vorhandenen Dateien und berechnet deren tatsächliche Prüfsummen. Ein Dateidatum oder eine Versionszeichenfolge allein löst keinen Download aus. Nur neue oder abweichende Dateien werden über das Netzwerk geladen; unveränderte Dateien werden lokal kopiert. Im neuen Manifest entfernte Dateien erscheinen nicht mehr im neuen Stand. Reine Dokumentationsänderungen ohne verändertes `payload` führen zu keinen Programm-Downloads und zu keinem Versionswechsel.

Das Verfahren arbeitet **auf Dateiebene**, nicht mit Binärpatches innerhalb einer Datei. Eine veränderte DLL wird vollständig geladen. Das enthaltene `python313.zip` ist eine einzelne Datei der Python-Standardbibliothek und wird nur übertragen, wenn sich diese Datei tatsächlich ändert. Vollständige Repository-Archive oder Updatepaket-ZIPs werden vom Updater nie angefordert.

## Transaktion und Fehlerbehandlung

Ein exklusiver Betriebssystem-Lock schützt die Aktualisierung. Der neue Stand entsteht zunächst in einem zufälligen `.staging-*`-Unterordner. Jede geladene und lokal übernommene Datei wird gegen das Manifest geprüft. Danach folgt ein echter Offline-Starttest mit der neuen Python-Laufzeit und der neuen WPF-Oberfläche. Anschließend werden erneut alle Hashes kontrolliert.

Erst nach erfolgreicher Prüfung wird das Verzeichnis an seinen endgültigen Platz verschoben und `current.txt` atomar ersetzt. Der bisherige aktive Stand und `payload` bleiben erhalten. Abgebrochene Vorgänge aktivieren keine Teilinstallation. Unvollständige temporäre Ordner werden nach Möglichkeit entfernt; nach einem harten Prozessabbruch können unbenutzte Reste verbleiben. Frühere vollständige Versionen werden nicht automatisch gelöscht.

Der Updater verweigert unter anderem Pfadtraversierung, absolute Pfade, Windows-Gerätenamen, alternative Datenströme, mehrdeutige Groß-/Kleinschreibung sowie symbolische Links und Junctions in Updatepfaden. Grenzen: 2 MiB Manifest, 10.000 Dateien, 256 MiB pro Datei und 1 GiB Gesamtumfang. Netzwerkzugriffe haben einen Timeout von 20 Sekunden je blockierendem Socket-Vorgang. Langsam, aber kontinuierlich liefernde Verbindungen können entsprechend länger dauern.

Eine bereits vorhandene Version mit derselben Manifest-ID wird vor Wiederverwendung vollständig geprüft. Ist sie beschädigt, wird sie nicht überschrieben. Die sichere Rücksetzung ist im [Benutzerhandbuch](BENUTZERHANDBUCH.md) beschrieben.

Die SHA-256-Prüfung ist keine Herausgebersignatur. Das [Vertrauensmodell](../SECURITY.md) beruht derzeit auf GitHub, HTTPS und der Repositorykontrolle des Autors.

## Veröffentlichung durch den Autor

1. Änderungen im separaten Entwicklungsordner vornehmen, Versionsdaten und Änderungsprotokoll pflegen.
2. Mit dem vorhandenen Buildskript die Anwendung erstellen und prüfen. Es kopiert die vorhandene portable Laufzeit, kompiliert mit dem Windows-.NET-Compiler und erzeugt das Manifest.
3. Geänderte Laufzeitdateien, aktualisiertes Manifest und Dokumentation **gemeinsam in einem Commit** im Repository aus `public` auf den Branch **`live`** übertragen. Keine Releases erstellen. Entwicklungsdateien bleiben außerhalb von `public`.
4. Auf GitHub prüfen, dass `AK-Weather.exe`, `payload` und `update-manifest.json` im Branch vorhanden sind. Erst dann können bestehende Installationen die Änderung beziehen.

Die eigenen EXE-Dateien und die Laufzeit werden als normale Git-Dateien veröffentlicht. **Kein Git LFS verwenden**, da die Raw-URLs sonst LFS-Zeiger statt ausführbarer Dateien liefern können. Der initiale GitHub-ZIP-Download enthält bereits alle benötigten Dateien.

Die `.gitattributes` deaktiviert Zeilenenden-Umwandlungen für `payload/**`. Diese Regel muss erhalten bleiben, damit Git exakt die Bytes veröffentlicht, auf die sich die SHA-256-Werte beziehen – auch bei Python-, Lizenz- und Konfigurationsdateien.

## Referenzen

- [DWD: 10-Minuten-Stationsmessungen der Lufttemperatur](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/air_temperature/DESCRIPTION_obsgermany_climate_10min_air_temperature_en.pdf)
- [DWD: 10-Minuten-Stationsmessungen des Windes](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/DESCRIPTION_obsgermany_climate_10min_wind_en.pdf)
- [DWD Climate Data Center: Open Data](https://www.dwd.de/EN/ourservices/cdc/cdc.html?lsbId=646268)
- [GitHub: Commit-API](https://docs.github.com/en/rest/commits/commits#get-a-commit)
- [Python: eingebettete Windows-Distribution](https://docs.python.org/3.13/using/windows.html#the-embeddable-package)
- [Microsoft: Windows Presentation Foundation](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/)
