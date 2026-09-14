# Windows-GUI-Abhängigkeiten

`windows-gui.lock.json` legt genau zwei Wheels fest: **PySide6-Essentials 6.11.2**
und **shiboken6 6.11.2**. Essentials enthält QtCore, QtGui und QtWidgets;
seine einzige deklarierte Python-Abhängigkeit ist die festgelegte shiboken6-Version.
Das vollständige PySide6-Metapaket und Addons werden für das erste Fenster nicht benötigt.
Quellen: [Essentials](https://pypi.org/project/PySide6-Essentials/6.11.2/),
[shiboken6](https://pypi.org/project/shiboken6/6.11.2/).

Die Windows-x64-Wheels tragen `cp310-abi3-win_amd64` und verlangen Python
`>=3.10,<3.15`. Das umfasst die vorhandene CPython-Laufzeit 3.14.7 mit GIL.
Dies ist die deklarierte Kompatibilität; ein Import- und Fenstertest mit der
portablen Laufzeit steht noch aus. Es wurden nur Metadaten gelesen, keine Wheels
heruntergeladen, entpackt oder installiert.

Seit 0.12.0.0 lädt `Get-GuiPackage.ps1` ausschließlich das zuerst benötigte
`shiboken6`-Wheel. Eine fehlende Datei wird unter einem zufälligen `.partial`-Namen
geladen und erst nach erfolgreichem Vergleich von Größe und SHA-256 übernommen.
Gültige vorhandene Dateien bleiben unverändert; fehlerhafte oder abgebrochene
Teilstände werden entfernt. Der Zielordner muss als direkter vorhandener Ordner
angegeben werden. Pfadbestandteile und Windows-Gerätenamen aus Metadaten werden
abgelehnt.

Der optionale Parameter `DownloadAction` ist nur für isolierte Tests mit simulierten
Antworten bestimmt. Die produktive Ausführung verwendet die festgelegte HTTPS-Adresse.
Dieser Schritt hat keine Wheels heruntergeladen, entpackt oder installiert und die
globale Python-Laufzeit nicht verändert. PySide6-Essentials folgt separat.

Die Datei enthält unveränderlich ausgewählte Dateinamen, HTTPS-Adressen, Größen
und die von PyPI veröffentlichten SHA-256-Werte. Diese erwarteten Werte wurden
gegen die versionsgebundene PyPI-API geprüft. Erst ein späterer Download erlaubt
den Vergleich mit dem selbst berechneten Archivhash. Keine automatische Auswahl
von `latest`, keine Abhängigkeitsauflösung auf andere Versionen.

Für die geplante LGPL-Nutzung sind die vollständigen LGPLv3- und GPLv3-Texte in
`licensing.required_license_texts` verlinkt. Die GPLv3 wird als Teil der LGPLv3
mitgeliefert; das ändert die Lizenz des eigenen Anwendungscodes nicht. Hinweise
auf verwendete Bibliotheken, deren Urheber und Rechte müssen in die Auslieferung.
Qt-Bibliotheken bleiben austauschbar; ihre Änderung und das Debuggen solcher
Änderungen dürfen durch die eigenen Bedingungen nicht eingeschränkt werden.
Quelle: [Qt-LGPL-Bedingungen](https://doc.qt.io/qt-6/lgpl.html).

Diese beiden Hauptlizenztexte ersetzen nicht die Lizenzhinweise eingebundener
Drittkomponenten. Vor Auslieferung müssen sämtliche tatsächlich mitgelieferten
DLLs, Plugins und Ressourcen samt zugehörigen Copyrights, Lizenztexten und
Quellenangeboten erfasst werden. Die Module enthalten weitere Komponenten;
Anhaltspunkte liefern die verlinkten offiziellen Qt-Modulseiten. Auch native
Windows-Abhängigkeiten und die tatsächliche Qt-Version sind noch zu prüfen.
`ready_for_distribution` ist deshalb ausdrücklich `false`.

Die globale Python-Laufzeit auf dem Entwicklungsrechner bleibt unverändert.
Die spätere Auslieferung stellt Python über einen Bootstrapper aus dem Repository
automatisch bereit. Dieser muss selbst ohne vorinstalliertes Python starten;
Laufzeitversion, Bezugsquelle und Prüfsumme werden im Repository gepflegt.
Dieses Metadatendokument allein erfüllt das Ziel nicht.
