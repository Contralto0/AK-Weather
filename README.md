# AK-Weather

Eine geplante portable Wetteranwendung von **Andy Klemann**, entwickelt mit KI-Unterstützung.

## Aktueller Stand

Version **0.4.0.0** enthält eine Windows-Startdatei für die portable Python-Laufzeit,
die fachliche Versionslogik, einen Changelog-Leser und die Speicherung des zuletzt
erfolgreich angezeigten Versionsstands.
Damit lassen sich alle noch ungelesenen Neuerungen ermitteln. Die Anzeige folgt separat.
Eine grafische Wetteranwendung und automatische Updates sind noch nicht vorhanden.
Die Umsetzung erfolgt alle drei Stunden in genau einem sehr kleinen Teilschritt,
mit höchstens 30 Minuten und nur bei ausreichend Codex-Kontingent.

## Start unter Windows

`Start-AK-Weather.cmd` per Doppelklick öffnen. Der Start zeigt derzeit die zentrale
Programmversion im Konsolenfenster; eine Taste schließt es wieder. Für automatisierte
Aufrufe unterdrückt `--no-pause` das Warten. Die grafische Oberfläche folgt separat.

Die Startdatei verwendet die vorhandene Laufzeit
`../../Software/python-3.14.7/python.exe`, ausgehend vom Programmordner. Das entspricht
hier dem globalen Softwareordner neben `Projekte`. Sie benötigt weder Python in PATH
noch Codex und ändert keine systemweiten Einstellungen. Bei einem anderen Speicherort
lässt sich für die aktuelle PowerShell-Sitzung ein vollständiger Pfad setzen:

```powershell
$env:AK_WEATHER_PYTHON = 'D:/Software/python-3.14.7/python.exe'
.\Start-AK-Weather.cmd
```

Die Laufzeit muss bereits vorhanden sein. Fehlende Laufzeit oder ungültige Versionsdatei
werden mit einer Fehlermeldung und Rückgabewert 1 gemeldet. Automatische Einrichtung,
Downloads und Updates sind noch nicht implementiert.

Für die fertige Windows-Auslieferung wird Python mitgeliefert oder durch einen
selbst ohne Python startfähigen Bootstrap automatisch portabel bereitgestellt.
Der Doppelklick muss auf einem frischen Windows-Rechner ohne Python, Codex oder
manuell eingerichtete Python-Pfade funktionieren. Version 0.4.0.0 erfüllt dieses
Auslieferungsziel noch nicht; ein entsprechender Test auf sauberem Windows ist vorgesehen.

## Entwicklung

Die festgelegten Pakete für das erste Qt-Fenster stehen in
[dependencies/windows-gui.lock.json](dependencies/windows-gui.lock.json).
[Prüfstand und Lizenzhinweise](dependencies/README.md) unterscheiden die geprüften
Paketmetadaten von den noch ausstehenden Download-, Import- und Auslieferungsprüfungen.

Die offizielle portable Python-Laufzeit 3.14.7 (Windows x64) ist auf Andys Rechner
direkt im globalen Softwareordner eingerichtet, ohne Projekt-Unterordner. Alle
Projekte können dieselbe Laufzeit verwenden. Ihr Start und die Tests wurden
mit leerem PATH geprüft: Ein installiertes Python oder die Codex-Laufzeit werden
dabei nicht verwendet. Der SHA-256-Wert des Originalarchivs wurde geprüft.

Die folgenden Befehle werden im Projektordner ausgeführt. Auf anderen Rechnern
muss der Pfad auf die dort bereitgestellte portable Laufzeit zeigen.

```powershell
$pythonExe = 'C:/Users/andyk/HiDrive/OpenAI Codex/Software/python-3.14.7/python.exe'
& $pythonExe -I -m unittest discover -s tests -v
& $pythonExe tools/bump_version.py
& $pythonExe tools/bump_version.py --dry-run improvement
```

Die Kategorien `major`, `feature`, `improvement`, `fix` entsprechen Hauptversion,
Funktion, Verbesserung und Fehlerbehebung. Ohne `--dry-run` wird VERSION geändert;
dies darf nur für einen abgeschlossenen, geprüften Teilschritt geschehen.
Bei erneutem Push derselben Änderung die Version **nicht** nochmals erhöhen.

`ak_weather.changelog.read_changelog()` liefert die Historie mit der neuesten Version
zuerst. `entries_since("0.1.0.0")` wählt alle neueren Einträge; `entries_since(None)`
liefert beim Erststart alle Einträge. Beide Funktionen lesen nur. Beschädigte Inhalte
melden `ChangelogError`; Dateizugriffsfehler bleiben `OSError`.

`ak_weather.read_state.load_last_seen()` liest den Lesestand, beim Erststart `None`.
`save_after_display(version, displayed=True)` speichert ihn nach erfolgreicher Anzeige
atomisch; `displayed=False` verändert nichts. Die Oberfläche muss diese Aufrufe
serialisieren. Ältere Versionen setzen den Lesestand nicht zurück.
Unter Windows liegt die Datei in `%LOCALAPPDATA%/AK-Weather/read-state.json`, unter
Linux in `$XDG_STATE_HOME/AK-Weather/read-state.json` (sonst `~/.local/state`).
Fehlt unter Windows LOCALAPPDATA, wird `~/AppData/Local` verwendet. Relative
Umgebungswerte werden ignoriert. Beschädigte Inhalte melden `ReadStateError` und
werden nicht überschrieben; Dateizugriffsfehler bleiben sichtbar.

Der vollständige Auftrag und nächste Schritt stehen in [DEVELOPMENT.md](DEVELOPMENT.md).
Veröffentlichungen erfolgen ausschließlich als Commits im Branch `live`.

## Rechte

Kostenlose private Nutzung gemäß [LICENSE.txt](LICENSE.txt).
Alle weiteren Rechte am eigenen Code bleiben Andy Klemann vorbehalten.
