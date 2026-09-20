# Drittanbieter-Komponenten

## Python 3.13.15 für Windows x64

AK-Weather enthält das offizielle eingebettete Python-Paket. Es wird portabel neben der Anwendung bereitgestellt und nicht systemweit installiert. Die isolierte Pfadkonfiguration `python313._pth` beschränkt die Python-Suche auf die enthaltene Standardbibliothek und das Laufzeitverzeichnis; externe Benutzerpakete werden nicht eingebunden.

- Herausgeber: Python Software Foundation und weitere in der Lizenz genannte Rechteinhaber.
- Produkt und Download: [Python 3.13.15](https://www.python.org/downloads/release/python-31315/).
- [Vollständige mitgelieferte Lizenzhinweise](payload/runtime/LICENSE.txt).
- [Python: History and License](https://docs.python.org/3.13/license.html).
- [Dokumentation zur eingebetteten Windows-Laufzeit](https://docs.python.org/3.13/using/windows.html#the-embeddable-package).

Die Python-Lizenzdatei enthält auch Hinweise zu enthaltenen Bestandteilen wie OpenSSL, SQLite und weiteren Bibliotheken. Die Dateien der Laufzeit werden mit ihren ursprünglichen Lizenzhinweisen weitergegeben. Für diese Bestandteile gelten deren eigene Lizenzen, einschließlich der dort erlaubten Änderungen. Die Änderungsbeschränkung für AK-Weather schränkt diese Rechte nicht ein.

## Windows und .NET Framework

Die grafische Oberfläche nutzt die Windows Presentation Foundation des vorhandenen .NET Frameworks. Windows und .NET Framework werden nicht als Teil dieses Pakets verteilt. Es gelten die Bedingungen ihrer jeweiligen Rechteinhaber.

## Gestaltung

Die Wetterillustration wird durch Vektorgeometrie in der Oberfläche gezeichnet. Es werden keine externen Bilddienste, Webfonts oder nachzuladenden UI-Bibliotheken verwendet.
