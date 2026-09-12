# AK-Weather

Eine geplante portable Wetteranwendung von **Andy Klemann**, entwickelt mit KI-Unterstützung.

## Aktueller Stand

Version **0.1.0.0** enthält die getestete fachliche Versionslogik.
Eine grafische Wetteranwendung und automatische Updates sind noch nicht vorhanden.
Die Umsetzung erfolgt alle drei Stunden in genau einem sehr kleinen Teilschritt,
mit höchstens 30 Minuten und nur bei ausreichend Codex-Kontingent.

## Entwicklung

Python wird ohne neue Systeminstallation verwendet. Die Erstprüfung verwendet die
bereits vorhandene Codex-Laufzeit (Python 3.12.14). Eine eigene portable Laufzeit
unter dem freigegebenen Softwareordner ist noch nicht eingerichtet.
Die folgenden Befehle werden im Projektordner ausgeführt; auf anderen Rechnern
ist der Pfad durch einen bereits vorhandenen Python-Interpreter ab Version 3.12 zu ersetzen:

```powershell
$pythonExe = 'C:/Users/andyk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $pythonExe tests/test_versioning.py -v
& $pythonExe tools/bump_version.py
& $pythonExe tools/bump_version.py --dry-run improvement
```

Die Kategorien `major`, `feature`, `improvement`, `fix` entsprechen Hauptversion,
Funktion, Verbesserung und Fehlerbehebung. Ohne `--dry-run` wird VERSION geändert;
dies darf nur für einen abgeschlossenen, geprüften Teilschritt geschehen.
Bei erneutem Push derselben Änderung die Version **nicht** nochmals erhöhen.

Der vollständige Auftrag und nächste Schritt stehen in [DEVELOPMENT.md](DEVELOPMENT.md).
Veröffentlichungen erfolgen ausschließlich als Commits im Branch `live`.

## Rechte

Kostenlose private Nutzung gemäß [LICENSE.txt](LICENSE.txt).
Alle weiteren Rechte am eigenen Code bleiben Andy Klemann vorbehalten.
