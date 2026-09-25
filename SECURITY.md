# Sicherheit und Datenschutz

## Updatequelle und Vertrauensmodell

AK-Weather lädt Updates ausschließlich aus `Contralto0/AK-Weather`, Branch `live`. Die Auflösung des Branches erfolgt über die GitHub-API; Manifest und Dateien werden anschließend von genau diesem Commit über HTTPS geladen. SHA-256 und Dateigrößen prüfen, ob die Dateien mit dem Manifest übereinstimmen.

Das Manifest ist derzeit **nicht separat kryptografisch signiert**. Die Vertrauensbasis sind die Kontrolle über das GitHub-Repository und HTTPS. Prüfsummen schützen vor defekten oder unvollständigen Downloads, nicht vor einem kompromittierten Repository. Der Updater lädt Programmcode, der nach erfolgreicher Prüfung beim nächsten Start ausgeführt wird. Auch der Starttest führt bereits den neuen Code im Updateordner aus.

## Schutz der vorhandenen Installation

Downloads werden in einem separaten Verzeichnis vorbereitet. Pfade, Dateigrößen und Prüfsummen werden geprüft. Pfade außerhalb des vorgesehenen Updateordners, Windows-Sonderpfade und verlinkte Updatepfade werden abgewiesen. Die Aktivierung erfolgt erst nach vollständigem Download und erfolgreicher Startprüfung durch atomaren Austausch einer kleinen Zeigerdatei. Ein Prozess-Lock verhindert konkurrierende Aktualisierungen.

Vorhandene Versionen bleiben erhalten. Eine beschädigte aktive Version führt beim nächsten Start zur Rückkehr zum mitgelieferten Grundsystem, sofern dieses noch intakt ist. Ein absichtliches lokales Verändern der Installation durch ein anderes Programm mit denselben Benutzerrechten wird dadurch nicht verhindert.

## Netzwerk und Daten

Automatische Verbindungen gehen nur zur Updateprüfung an GitHub. Dabei fallen bei GitHub technisch notwendige Verbindungsdaten wie IP-Adresse und Zeitpunkt an. Es werden keine Konten, API-Schlüssel, persönlichen Dateien oder Standortdaten übertragen. Das Grundsystem enthält keine Telemetrie und führt beim Start keine Wetterabfrage aus. Die Schaltflächen für Projekt und Dokumentation öffnen GitHub im Standardbrowser.

Der vorbereitete KONRAD3D-Provider greift nur dann auf `opendata.dwd.de` zu, wenn ihn ein künftiger Programmteil ausdrücklich aufruft. Dabei werden keine lokalen Koordinaten, Konten oder Schlüssel übertragen; beim DWD fallen lediglich technisch notwendige HTTPS-Verbindungsdaten wie IP-Adresse und Zeitpunkt an. Die Verzeichnisliste und die ausgewählte XML-Datei werden nicht dauerhaft gespeichert.

Der vorbereitete DWD-POI-Provider greift ebenfalls nur nach einem ausdrücklichen Aufruf auf `opendata.dwd.de` zu. Die angegebene Stationskennung wird dabei ausschließlich als Teil des festen Dateinamens übertragen; Standortdaten, Konten, Tokens und Koordinaten werden nicht gesendet. Beim DWD fallen technisch unvermeidbar IP-Adresse, Zeitpunkt und die angefragte POI-Datei an. Die Antwort wird weder zwischengespeichert noch dauerhaft gespeichert.

## Probleme melden

Allgemeine Fehler können über die [GitHub-Issues](https://github.com/Contralto0/AK-Weather/issues) gemeldet werden. Bitte keine Passwörter, Tokens, persönlichen Daten oder vertraulichen Exploitdetails öffentlich einstellen. Ein gesonderter vertraulicher Meldekanal ist für dieses Grundsystem noch nicht eingerichtet.
