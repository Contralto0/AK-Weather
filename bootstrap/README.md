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
