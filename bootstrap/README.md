# Python-Datensatz und Archivprüfung

Seit 0.6.0.0 prüft `Test-PythonArchive.ps1` ein vorhandenes Archiv mit Windows
PowerShell 5.1, ohne Python oder Codex aufzurufen. Standardmäßig liest es
`windows-python.lock.json` neben dem Skript; `-MetadataPath` erlaubt einen anderen
vertrauenswürdigen Datensatz. Es validiert Formatversion, Größe und SHA-256.
Erfolg liefert Rückgabewert 0; Fehler werden auf stderr mit Rückgabewert 1 gemeldet.
Das Archiv bleibt unverändert. Windows sperrt Schreiben und Löschen während der
Prüfung; nach Ende muss der spätere Verwender Änderungen selbst verhindern.

Beispiel aus dem Projektordner für das bereits vorhandene Archiv:

```powershell
& "$env:SystemRoot/System32/WindowsPowerShell/v1.0/powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File .\bootstrap\Test-PythonArchive.ps1 -ArchivePath 'C:/Users/andyk/HiDrive/OpenAI Codex/Software/python-3.14.7-embeddable-amd64.zip'
```

`RemoteSigned` gilt hier nur für diesen Prozess, ohne dauerhafte Richtlinienänderung.
Gruppenrichtlinien bleiben maßgeblich; aus dem Internet geladene Skripte unterliegen
weiterhin der Signaturprüfung. Siehe [Microsoft-Dokumentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies).
Die Auslieferung muss diese Startbedingungen noch berücksichtigen. Das Skript lädt
nichts herunter und entpackt nichts; es ist noch kein vollständiger Bootstrapper.

Seit 0.7.0.0 lädt `Get-PythonArchive.ps1` ein fehlendes Archiv von der im Datensatz
festgelegten absoluten HTTPS-Adresse. Der Download landet unter einem zufälligen
`.partial`-Namen im Zielordner. Erst nach erfolgreicher Größen- und SHA-256-Prüfung
wird er unter dem endgültigen Namen bereitgestellt. Fehlerhafte oder unvollständige
Downloads werden entfernt. Ein vorhandenes gültiges Archiv wird wiederverwendet;
ein vorhandenes ungültiges Archiv bleibt zur Diagnose erhalten und wird nicht
überschrieben. Der Zielordner muss bereits bestehen.

Die produktive Downloadaktion verwendet `Invoke-WebRequest`. Der optionale Parameter
`DownloadAction` dient der isolierten Prüfung mit simulierten Antworten und darf in
der normalen Auslieferung nicht aus nicht vertrauenswürdigen Eingaben befüllt werden.
Die Tests starten ohne Python in PATH, verwenden keinen lokalen Server und führen
keinen echten Download aus. Der Baustein entpackt oder installiert noch nichts.

Seit 0.8.0.0 entpackt `Expand-PythonArchive.ps1` ein bereits geprüftes lokales ZIP
in einen neuen, separaten Zielordner. Es prüft vor dem ersten Schreibzugriff alle
Einträge und lehnt absolute Pfade, Laufwerks- und UNC-Pfade, `..`, Verknüpfungen,
Windows-Gerätenamen, mehrdeutige Ziele sowie außerhalb des Zielordners aufgelöste
Pfade ab. Bei einem Fehler wird nur der vom Skript neu angelegte Zielordner entfernt. Vorhandene
Ziele und fehlende Elternordner werden unverändert abgelehnt.

Das Skript prüft die ZIP-Prüfsumme nicht erneut. Der Aufrufer muss ausschließlich
ein zuvor erfolgreich geprüftes und bis zum Aufruf unverändertes Archiv übergeben.
Es aktiviert oder installiert die entpackte Laufzeit noch nicht. Die Tests verwenden
nur kleine lokale Beispieldateien, Windows PowerShell 5.1 und einen leeren PATH.

Seit 0.9.0.0 veröffentlicht `Publish-PythonRuntime.ps1` einen bereits sicher
entpackten Ordner atomar unter `runtime.directory_name`. Temporärer Ordner und Ziel
müssen direkte Kinder desselben vorhandenen Stammordners sein; damit bleibt der
abschließende Verzeichniswechsel auf demselben Datenträger. Vor der Verschiebung
entsteht im temporären Ordner `.ak-weather-runtime.json` mit Laufzeitversion,
Ordnername und Programmdatei aus dem Repository-Datensatz.

Ein vorhandener Zielordner wird nur mit passender Markierung und regulärer
Python-Programmdatei unverändert wiederverwendet. Fehlende oder abweichende
Markierungen, Verknüpfungen, ungültige Windows-Namen und fehlende Programmdateien
führen zu einem Fehler, ohne den vorhandenen Zielordner oder den temporären Ordner
zu verändern. Bei erfolgreicher Wiederverwendung bleibt der temporäre Ordner zur
späteren kontrollierten Bereinigung erhalten. Das Skript startet Python noch nicht.

Seit 0.10.0.0 verbindet `Initialize-PythonRuntime.ps1` die bestehenden Bausteine
in der festgelegten Reihenfolge: vorhandene Laufzeit erkennen, Archiv laden und
prüfen, in einen zufälligen direkten Unterordner sicher entpacken und atomar
veröffentlichen. Eine eindeutig passende markierte Laufzeit beendet den Ablauf vor
jedem Download. Konflikte, beschädigte Archive und unsichere ZIP-Einträge brechen ab;
temporäre Entpackordner dieses Ablaufs werden entfernt.

Der optionale Parameter `DownloadAction` dient ausschließlich Tests mit simulierten
Downloads. Die produktive Ausführung übergibt ihn nicht und verwendet den festgelegten
HTTPS-Download aus `Get-PythonArchive.ps1`. Die Ablaufprüfungen verwenden kleine lokale
ZIP-Dateien, leeren PATH und keinen Server. Python wird noch nicht gestartet, und der
Ablauf ist noch nicht mit der Doppelklick-Startdatei verbunden.

Seit 0.11.0.0 ruft `Start-AK-Weather.cmd` diesen Ablauf auf, wenn weder
`AK_WEATHER_PYTHON` gesetzt noch die versionsgebundene Standardlaufzeit vorhanden ist.
Die Startdatei verwendet Windows PowerShell über den absoluten Systempfad, legt nur
den globalen Software-Stammordner an und startet nach erfolgreicher Bereitstellung
direkt dessen `python.exe`. Bootstrap-Fehlercodes bleiben erhalten. Ein expliziter,
aber fehlender Interpreterpfad wird weiterhin ohne Ausweichen auf System-Python
abgelehnt. Die Tests simulieren den Bootstrapaufruf ohne Netzwerkzugriff.

`windows-python.lock.json` legt die portable CPython-Laufzeit **3.14.7**, Windows
11 x64, als Embeddable-ZIP ohne Free-Threading fest. Die Archivgröße beträgt
**12.673.909 Byte**. URL und SHA-256 stammen aus dem Eintrag
`pythonembed-3.14-64` der [offiziellen Python-Metadaten](https://www.python.org/ftp/python/3.14.7/windows-3.14.7.json).
Die Größe wurde am vorhandenen Archiv gemessen; dessen SHA-256 stimmt mit dem
offiziellen Wert und dem lokalen Bereitstellungsnachweis überein.

Diese JSON-Datei ist ein versionierter Datensatz und noch kein ausführbarer
Bootstrapper. Sie enthält keine Benutzerpfade und keine Programmversionsnummer.
`runtime.version` bezeichnet ausschließlich die Python-Version; die Version von
AK-Weather bleibt in `VERSION`. `bootstrap_requirements` beschreibt Anforderungen,
keine bereits bestandenen Starttests. Die Prüfmerkmale unterscheiden die bereits
erfolgte Archivprüfung von den offenen Bootstrapper- und Auslieferungsprüfungen.

Der künftige Bootstrapper liegt im Repository und muss selbst ohne Python oder
Codex starten. Er verwendet exakt diese URL, Größe und Prüfsumme, prüft ein Archiv
vor dem Entpacken und startet Python direkt über den ermittelten portablen Pfad.
Ein beschädigtes Archiv darf nicht verwendet werden. `directory_name` ist nur der
Produkt-/Versionsordner unter dem vom Bootstrapper ermittelten Softwareverzeichnis,
kein fest codierter Pfad zu Andys Rechner. Registry und systemweiter PATH bleiben
unverändert; passende globale Laufzeiten werden wiederverwendet.

Für diesen Vorbereitungsschritt wurde das bestehende Archiv ausschließlich gelesen
und mit `ak_weather.package_verification` geprüft. Keine Kopie, kein erneuter
Archivdownload, keine Entpackung und keine weitere Python-Bereitstellung. Die
einmalige lokale Bereitstellung bleibt abgeschlossen. Der vollständige Start auf
einem frischen Windows-Rechner ohne vorbereitetes Python ist weiterhin nachzuweisen.
