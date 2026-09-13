# Python-Datensatz für den Windows-Bootstrapper

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
