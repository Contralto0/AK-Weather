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
- Dieser Softwareordner ist global für alle Projekte. Keine Projekt-Unterordner
  verwenden; Laufzeiten nach Produkt/Version ablegen und gemeinsam wiederverwenden.
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
- Die App muss auf Windows-Rechnern ohne installiertes Python funktionieren. Eine
  eigene portable Laufzeit direkt per Pfad verwenden; weder Python/py aus PATH noch
  eine Codex-Laufzeit auf Benutzerrechnern voraussetzen. Auf Andys Rechner liegt die
  portable Python-Laufzeit unter `C:/Users/andyk/HiDrive/OpenAI Codex/Software`.
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
- Windows-Start ohne installiertes Python und ohne Python-Einträge in PATH; die eigene portable Laufzeit verwenden.
- Beispieldaten und simulierte Netzantworten verwenden; keine lokalen Testserver.

## Fortschritt und nächster Schritt

- 2026-09-12: Ersteinrichtung des Auftrags. Erster und einziger Entwicklungsschritt:
  fachliche Versionslogik 0.1.0.0 mit atomischer Dateipflege und Vorschau.
- Acht fachliche Tests bestanden mit vorhandenem Python 3.12.14; CLI-Lesen und
  Änderungsvorschau ebenfalls geprüft. Keine GUI, Wetterdaten oder Updates implementiert.
- Frühere Erstprüfung: vorhandene Codex-Laufzeit Python 3.12.14. Aktueller Testinterpreter:
  `C:/Users/andyk/HiDrive/OpenAI Codex/Software/python-3.14.7/python.exe`.
- Eigene portable Python-Laufzeit ist eingerichtet; PySide6/Qt noch nicht.
  Die frühere automatische Ablehnung wurde nach der erneuten ausdrücklichen
  Nutzerfreigabe bei dieser Bereitstellung erfolgreich geklärt.
- Neue ausdrückliche Nutzerfreigabe vom 12.09.2026: „ignoriere für diese bereitstellung
  einmalig die vorgabe, dass keine software abgelegt werden darf.“ Dies gilt für die
  einmalige portable Python-Bereitstellung im zuvor genannten Softwareordner.
  Die vorherige Freigabeblockade ist mit dieser neuen Autorisierung erneut prüfbar.
  Keine erneute routinemäßige Bestätigung verlangen und die Ausnahme nicht auf andere
  Software ausweiten. Systemweite Installationen und lokale Server bleiben verboten.
- Status der einmaligen Python-Bereitstellung: **ABGESCHLOSSEN am 12.09.2026**.
  Die einmalige Ausnahme ist verbraucht. Die geprüfte Laufzeit wiederverwenden;
  die frühere Bereitstellung nicht erneut ausführen.
  - Version: Python 3.14.7, offizielles Windows-x64-Embeddable-Paket.
  - Globaler Ordner: `C:/Users/andyk/HiDrive/OpenAI Codex/Software/python-3.14.7`.
    Auf Nutzerwunsch direkt unter Software abgelegt, gemeinsam für alle Projekte nutzbar.
  - Quelle: https://www.python.org/ftp/python/3.14.7/python-3.14.7-embeddable-amd64.zip
  - Hashquelle: https://www.python.org/ftp/python/3.14.7/windows-3.14.7.json
  - SHA-256: `76c3c0384ab3f822486f32450f3a4d20f5d65ad0ec32ee34290971aa0eb817e6`.
  - Lokaler Nachweis: `C:/Users/andyk/HiDrive/OpenAI Codex/Software/python-3.14.7-provisioning.json`.
  - Starttest am 12.09.2026, nach Verlagerung um 18:55:55 UTC erneut bestanden:
    Kindprozess mit leerem PATH, ohne
    PYTHONHOME/PYTHONPATH, isoliert (`-I -S`), 64 Bit; Interpreter, Prefix und sämtliche
    Python-Suchpfade innerhalb des portablen Ordners. SSL, ctypes und SQLite geprüft.
  - Acht vorhandene Versionstests, Versionslesen und Änderungsvorschau ebenfalls mit
    dieser Laufzeit und leerem PATH bestanden. Kein System-Python verwendet.
  - Keine dauerhaften Registry-/PATH-Änderungen; kein Paketmanager oder weiteres Paket
    installiert. Dies ersetzt keinen künftigen Test des fertigen GUI-Launchers auf
    einer sauberen Windows-Testmaschine.
- PySide6 und cryptography sind in der neuen unveränderten Embeddable-Laufzeit nicht
  enthalten. Nur die frühere Codex-Laufzeit enthält cryptography. Signaturschlüssel
  fehlen noch und sind vor der ersten Update-Veröffentlichung einzurichten.
- Die Python-Bereitstellung war reine Werkzeugpflege ohne Programmänderung; dabei
  blieb die Programmversion 0.1.0.0 unverändert.
- 2026-09-12, weiterer Lauf: **Changelog-Leser 0.2.0.0 abgeschlossen**. Genau ein
  Teilschritt: `ak_weather/changelog.py` liest die bestehende Historie, validiert sie
  und wählt numerisch alle Einträge nach der zuletzt angezeigten Version aus.
  Erststart (None) liefert alle Einträge, neueste zuerst. Keine GUI, Speicherung oder
  neue Abhängigkeiten. Beschädigte Daten und doppelte Versionen melden einen Fehler.
  Zehn neue Changelog-Prüfungen und acht bestehende Versionstests bestanden mit der
  globalen portablen Python-Laufzeit und leerem PATH.
- 2026-09-12/13: **Lesestand-Speicherung 0.3.0.0 abgeschlossen**.
  Genau ein Teilschritt: `ak_weather/read_state.py` lädt und speichert den zuletzt
  erfolgreich angezeigten Versionsstand außerhalb des austauschbaren Programmcodes.
  Fehlende Datei bedeutet Erststart. Fehlgeschlagene Anzeigen verändern nichts;
  ältere Versionen setzen den Stand nicht zurück. Beschädigte Inhalte bleiben
  erhalten und werden gemeldet. Atomischer Dateiaustausch schützt den bisherigen
  Stand bei Schreibfehlern. Noch keine GUI oder neue Abhängigkeiten.
  Neun neue Lesestandsprüfungen und 18 bestehende Tests bestanden mit der globalen
  portablen Python-Laufzeit und leerem PATH (insgesamt 27). Dazu zählen Erststart,
  Anzeigeabbruch, beschädigte Daten, Schreibfehler, Plattformpfade und Zusammenspiel
  mit dem Changelog-Leser. Eine gültige Datenpfadvariable benötigt kein Home-Verzeichnis.
  Die Veröffentlichung wurde am 12.09. wegen 7 % Fünfstundenrest verschoben.
  Wiederaufnahme am 13.09.: ausschließlich Prüfung und Veröffentlichung desselben
  Stands 0.3.0.0, ohne erneute Versionserhöhung oder zusätzlichen Entwicklungsschritt.
  Alle 27 Tests mit der portablen Laufzeit und leerem PATH erneut bestanden.
  Veröffentlichung ausschließlich als Commit/Push nach origin/live; vor einem
  neuen Schritt die Übereinstimmung von lokalem und Remote-Commit sicherstellen.
- 2026-09-13: **Windows-Startgrundlage 0.4.0.0**. Genau ein Teilschritt:
  `Start-AK-Weather.cmd` startet die gemeinsame portable Laufzeit direkt mit `-I`;
  `launch.py` zeigt die zentrale Version. Der Standardpfad liegt relativ zum
  Programmordner unter `../../Software/python-3.14.7/python.exe`. Ein vorhandener
  abweichender Interpreter kann über `AK_WEATHER_PYTHON` gewählt werden.
  Kein System-Python, keine neue Laufzeitkopie, keine Downloads oder GUI.
  Fünf Windows-Integrationstests prüfen den Start mit leerem PATH, störenden
  PYTHONHOME/PYTHONPATH-Werten, anderem Arbeitsordner, Leerzeichen und Sonderzeichen,
  die vorhandene globale Laufzeit, fehlende Laufzeiten sowie beschädigte Versionen.
  Alle 32 Tests (fünf neue und 27 bestehende) mit der portablen Laufzeit und leerem
  PATH bestanden. Versionsdatei und Historie verwenden übereinstimmend 0.4.0.0.
  Der interaktive Start wartet auf eine Taste; `--no-pause` erlaubt automatisierte
  Aufrufe. Rückgabewerte bleiben erhalten. Ein vollständiger Test auf einer sauberen
  Windows-Maschine ohne Python/Codex bleibt zur Abnahme des fertigen Launchers nötig.
- Nächster sehr kleiner Schritt: Abhängigkeiten für ein minimales Qt-Widgets-Fenster
  festlegen. Mit Python 3.14.7 kompatible PySide6-/Qt-Pakete, Originalquellen,
  SHA-256-Werte und erforderliche Lizenztexte in einer Abhängigkeitsdatei dokumentieren.
  In diesem nächsten Schritt noch keine GUI oder Softwarebereitstellung; die
  abgeschlossene Python-Bereitstellung nicht wiederholen. Reine Metadatenpflege
  ohne Programmänderung erzeugt keine neue Programmversion.
- Die automatische Laufzeit-/Bibliotheksbereitstellung folgt separat. Der fertige
  Launcher muss auf Benutzerrechnern ohne installiertes Python oder Codex starten.
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
