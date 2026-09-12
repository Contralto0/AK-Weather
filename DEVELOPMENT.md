# AK-Weather – freigegebener Dauerauftrag

Autor: Andy Klemann. Umsetzung mit KI-Unterstützung.
Repository: https://github.com/Contralto0/AK-Weather – Veröffentlichungsbranch `live`.
Dieser Auftrag wurde am 12.09.2026 ausdrücklich zur Umsetzung freigegeben.

## Verbindliche Grenzen

- Alle drei Stunden genau EIN sehr kleiner, abgeschlossener Entwicklungsschritt.
- Höchstens 30 Minuten einschließlich Analyse, Implementierung, Tests, Commit und Push.
- Zu Beginn frische Codex-Kontingentwerte abfragen. Fünfstunden- und Wochenrest müssen
  jeweils mindestens 10 % betragen; weitere anwendbare Modelllimits ebenfalls beachten.
  `rateLimitsByLimitId` bevorzugen. Rest = max(0, min(100, 100 - usedPercent)).
  Fehlende Werte, Toolfehler, gesperrte gewöhnliche Nutzung oder unzureichender Rest:
  ohne Entwicklung und ohne Versionsänderung überspringen. Keine Reset-Guthaben nutzen.
- Vor Implementierung und Veröffentlichung erneut abfragen. Unter 10 % Arbeitsstand
  sichern und verschieben. Die kurze anfängliche Prüfung darf selbst Kontingent nutzen.
- Startzeit/Deadline festhalten; ab Minute 25 nur abschließen oder sichern.
  Kein zweiter Entwicklungsschritt im selben Lauf. Laufenden Besitzer eines exklusiven
  lokalen Locks respektieren. Unterbrochene Arbeit und ausstehenden Push zuerst fortsetzen.
- Eigenständig entscheiden, keine erneuten routinemäßigen Entwicklungsrückfragen.
  Keine fremden Änderungen überschreiben und keine erzwungenen Pushes.
- Keine lokalen Server, keine systemweiten Softwareinstallationen. Der Nutzer erlaubt
  fehlende Werkzeuge ausschließlich portabel unter
  `C:/Users/andyk/HiDrive/OpenAI Codex/Software`, aus Originalquellen mit Hashprüfung.
- Nur kostenlose, nichtkommerziell zulässige Datenquellen. Fehlende Rechte nicht umgehen.
- Benachrichtigungen nur zu veröffentlichtem Fortschritt, neuen Fehlern oder neuen
  Blockaden. Bei unverändertem oder übersprungenem Zustand still bleiben.
- Lokale Ausführung benötigt eingeschalteten Rechner und laufende Desktop-App.

## Versionierung und Veröffentlichung

`VERSION` ist die einzige Quelle der aktuellen Programmversion. Schema:
**Hauptversion.Funktion.Verbesserung.Fehlerbehebung**. Keine Lauf- oder Buildnummer.

| Kategorie | Bedeutung | Beispiel aus 1.2.3.4 |
| --- | --- | --- |
| major | Grundlegender Umbau / inkompatible Änderung | 2.0.0.0 |
| feature | Neue Funktion | 1.3.0.0 |
| improvement | Verbesserung bestehender Funktion | 1.2.4.0 |
| fix | Fehlerkorrektur | 1.2.3.5 |

Die höchste passende Kategorie gewinnt; alle folgenden Stellen werden 0. Die erste
Programmversion ist 0.1.0.0. Reine Planung/Protokollierung, fehlgeschlagene oder
übersprungene Läufe erhalten keine neue Programmversion.

Vorhandene Version nicht noch einmal erhöhen, wenn Tests oder Veröffentlichung eines
bereits begonnenen Schritts fortgesetzt werden. `tools/bump_version.py` ohne Kategorie
liest nur; `--dry-run` zeigt die nächste Version; ein Aufruf mit Kategorie schreibt.
Nach geprüftem Schritt `changelog.json` und Fortschritt pflegen, committen und nach
`origin/live` pushen. Remote-Commit anschließend prüfen. Keine GitHub Releases.

## Architektur und Updates

- Python und PySide6/Qt Widgets, zunächst Windows 11 x64; Plattformadapter für Linux.
- Deutsche Oberfläche, metrische Einheiten, Deutschland als erster Kartenausschnitt.
- Kleine Module für Oberfläche, Karte, Standort, Wetter, Prognose, Updates und Historie.
- Netzwerkzugriffe außerhalb des Oberflächenthreads; keine lokalen Server.
- Doppelklick-Bootstrap für portable Laufzeit und geprüfte Abhängigkeiten. Keine
  Registry-/PATH-Änderungen oder Admininstallation. Bibliotheken wiederverwenden.
- Ed25519-signiertes Update-Manifest mit Version, Laufzeitanforderungen und Dateien
  (Pfad, Größe, SHA-256). Etablierte Kryptobibliothek verwenden.
- Öffentlicher Prüfschlüssel im Launcher; privater Schlüssel geschützt außerhalb des
  Repositorys. Vor der ersten Update-Veröffentlichung Schlüssel einrichten und prüfen.
- `live` auf konkreten Commit auflösen; alle Dateien aus genau diesem Stand beziehen.
  Nur neue/geänderte Dateien herunterladen, unveränderte lokal übernehmen. Entfernte
  Dateien im neuen vollständigen Versionsverzeichnis nicht übernehmen.
- Downloads separat prüfen, keine Mischversion aktivieren. Pfadtraversal, beschädigte
  Dateien, ungültige Signaturen und unvollständige Downloads ablehnen.
- Beim Start und alle drei Stunden prüfen. Während der Nutzung geladene Updates beim
  nächsten Start aktivieren. Vorversion behalten und bei Startfehler automatisch nutzen.
- Einstellungen/Nutzerdaten getrennt vom Programmcode. Laufzeitdownloads nur bei
  Ersteinrichtung oder geänderten Abhängigkeiten. Keine Laufzeitarchive im Git-Repository.

## Oberfläche und Rechte

- Über-Menü: Andy Klemann, zentrale Versionsnummer, klein „Mit KI-Unterstützung entwickelt“.
- Kostenlose Privatnutzung der offiziellen App; weitere Rechte am eigenen Code vorbehalten.
- Vollständige Bibliotheks- und Datenlizenzen anzeigen und mitliefern. Fremdlizenzen nicht
  durch eigene Bedingungen einschränken. Qt-Bibliotheken austauschbar halten; nur passende
  Module einsetzen und notwendige Lizenztexte/Quellenhinweise beilegen.
- Versionshistorie aus `changelog.json`. Beim Öffnen alle seit der letzten Anzeige
  veröffentlichten Neuerungen direkt zeigen, auch bei übersprungenen Versionen.

## Reihenfolge der Arbeitspakete

Jeder Punkt wird in einzelne sehr kleine Schritte zerlegt, niemals in einem Lauf umgesetzt.

1. Startfähige Oberfläche und Updates: Versionsgrundlage, Launcher, Fenster,
   Versionsanzeige, Über-Menü, Historie; anschließend Dateivergleich, Download,
   Signaturprüfung, Aktivierung und Rückkehr zur Vorversion. Abnahme erst nach einem
   nachgewiesenen Update zwischen zwei veröffentlichten Versionen.
2. Deutschlandkarte: OpenStreetMap, verschieben/zoomen, nur benötigte sichtbare Kacheln,
   HTTP-Caching, identifizierbarer User-Agent und ständig sichtbare Attribution.
3. Standort: Windows-Standortdienst mit Berechtigung und Genauigkeitsanzeige. Ohne
   Zugriff manuelle Auswahl; Gerätestandort und Wetterauswahl unterschiedlich markieren.
4. Live-Blitze: austauschbare Quelle und Ebene. Nur nachweislich zulässige kostenlose
   Daten. Blitzortung-Rohdaten nicht als frei zugänglich voraussetzen. Ohne erlaubten
   Zugang als ausstehend markieren und mit dem nächsten unabhängigen Ziel fortfahren.
5. Aktuelles Wetter über Open-Meteo: Temperatur, gefühlte Temperatur, Wetterzustand,
   Niederschlag, Wind, Luftfeuchte, Datenzeitpunkt. Modellwerte als solche kennzeichnen.
6. Wetter per Kartenklick aktualisieren. Überholte Antworten verwerfen. Rückkehr zum
   Gerätestandort anbieten.
7. 48-Stunden-Prognose: kostenlose dokumentierte Open-Meteo-Modelle mit geeigneter
   Orts-/Zeitabdeckung selbst zusammenführen. Quellen, Alter und fehlende Modelle zeigen.
   Modellfamilien zunächst gleich gewichten, Mitglieder innerhalb einer Familie gleich
   gewichten und überlappende Varianten nicht mehrfach zählen. Temperatur/Wind als
   gewichteten Median mit 10.–90.-Perzentil zeigen. Regenwahrscheinlichkeit ab 0,1 mm/h
   aus Ensemblemitgliedern; Wetterzustände aus Modellstimmen und deren Anteil als
   Modellübereinstimmung. Wahrscheinlichkeiten als unkalibrierte Modellschätzungen zeigen.
8. Dauerhaft weiterentwickeln: Fehler/Zuverlässigkeit, Datenqualität, Geschwindigkeit,
   Bedienbarkeit, Gestaltung. Später Messdatenvalidierung und Kalibrierung. Linux als
   eigener späterer Meilenstein. „Alle Modelle“ meint kostenlos geeignete Modelle der
   angebundenen Quellen, nicht jeden weltweit existierenden Wetterdienst.

## Prüfungen

- Ein Teilschritt / höchstens 30 Minuten / Wiederaufnahme / Parallelität.
- Kontingent unter 10 %, genau 10 %, unbekannte Werte und Toolfehler.
- Fachliche Versionswahl, Zurücksetzen folgender Stellen, keine Erhöhung ohne Änderung.
- Delta-Downloads, Signaturen, Pfade, Teilabbrüche, Offlinebetrieb und Rückkehr zur Vorversion.
- Veröffentlichung derselben Version nach Fehler wiederholen, Remote-Stand prüfen.
- Historie bei Erststart, übersprungenen Versionen und erneutem Öffnen.
- Standort verweigert, schnelle Kartenklicks, Netzwerkausfall, veraltete Daten.
- Fehlende Modelle, Zeitauflösungen, Sommerzeitwechsel, Gewichtung und Wahrscheinlichkeiten.
- Windows-Start, Skalierung, Tastaturbedienung, Lizenzen.
- Beispieldaten und simulierte Netzantworten verwenden; keine lokalen Testserver.

## Fortschritt und nächster Schritt

- 2026-09-12: Ersteinrichtung des Auftrags. Erster und einziger Entwicklungsschritt:
  fachliche Versionslogik 0.1.0.0 mit atomischer Dateipflege und Vorschau.
- Acht fachliche Tests bestanden mit vorhandenem Python 3.12.14; CLI-Lesen und
  Änderungsvorschau ebenfalls geprüft. Keine GUI, Wetterdaten oder Updates implementiert.
- Testinterpreter: `C:/Users/andyk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
- Eigene portable Python-/Qt-Laufzeit noch nicht eingerichtet. Automatische Freigabe
  lehnte Download/Entpacken/Start von Python trotz portabler Nutzerfreigabe unter Berufung
  auf das ältere Installationsverbot ab. Nicht durch Umwege umgehen. Für Tests die
  vorhandene Laufzeit nutzen; neue Installation erst nach geklärter Freigabe.
- PySide6 fehlt in dieser vorhandenen Laufzeit; cryptography ist vorhanden. Signaturschlüssel
  fehlen noch und sind vor der ersten Update-Veröffentlichung einzurichten.
- Nächster sehr kleiner Schritt: sofern PySide6 ohne neue Installation bereits zulässig
  verfügbar ist, ein minimales Fenster mit zentraler Versionsanzeige erstellen.
  Andernfalls als unabhängigen Bestandteil zuerst den Changelog-Leser mit Auswahl der
  Einträge neuer als die zuletzt angezeigte Version implementieren (noch keine GUI).
- Veröffentlichung vor neuem Schritt anhand von `git status`, lokalem HEAD und
  `origin/live` prüfen; ausstehenden Push derselben Version zuerst abschließen.

## Quellen

- https://learn.chatgpt.com/docs/automations?surface=app
- https://doc.qt.io/qt-6/lgpl.html
- https://operations.osmfoundation.org/policies/tiles/
- https://www.blitzortung.org/en/contact.php?lang=en
- https://open-meteo.com/en/docs
- https://open-meteo.com/en/docs/ensemble-api
- https://www.python.org/ftp/python/3.14.7/windows-3.14.7.json
