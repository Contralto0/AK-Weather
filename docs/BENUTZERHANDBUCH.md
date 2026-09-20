# Benutzerhandbuch

## Starten

Lade das [Startpaket von `live`](https://github.com/Contralto0/AK-Weather/archive/refs/heads/live.zip) herunter und entpacke alle Dateien. Öffne anschließend `AK-Weather.exe`. Python wird mitgeliefert. Verwende einen normalen beschreibbaren Ordner; `Programme`, schreibgeschützte Datenträger und der geöffnete ZIP-Ordner eignen sich nicht für automatische Updates.

Voraussetzung: Windows 10/11 x64 und .NET Framework 4.8 als vorhandener Windows-Bestandteil. ARM64 wird derzeit nicht als native Zielplattform angeboten. Die Anwendung benötigt weder ein Benutzerkonto bei GitHub noch einen API-Schlüssel.

## Die erste Oberfläche

Die Übersicht zeigt **„Das Grundsystem steht.“** und den Hinweis **„Erste Entwicklung · Grundsystem“**. AK-Weather ist eine Wetter-App in Entwicklung. Es werden noch keine Temperaturen, Standortdaten oder Vorhersagen abgerufen. Die Hinweise „Vorhersage“ und „Meine Orte“ in der Seitenleiste markieren geplante Funktionen und sind noch keine Bedienelemente.

Die Schaltflächen lassen sich mit Tab und Eingabe bedienen. Bei kleineren Fenstern lässt sich der Inhalt rechts scrollen. Windows-Skalierung wird unterstützt.

## Updates

Die Prüfung startet automatisch, sobald das Fenster geöffnet ist. Sie lässt sich mit **„Nach Updates suchen“** wiederholen. Die laufende Oberfläche bleibt dabei bedienbar.

- **Aktuell:** Die Programmdateien entsprechen bereits dem Stand auf `live`.
- **Update wird geladen:** Nur neue und geänderte Dateien werden übertragen.
- **Update bereit:** Die neue Version wurde geprüft. **„Jetzt neu starten“** öffnet sie. Alternativ die App später normal neu öffnen.
- **Offline / nicht verfügbar:** Die vorhandene Version bleibt benutzbar. Die Prüfung kann später wiederholt werden.
- **Fehler:** Die neue Version wurde nicht aktiviert; die vorhandenen Dateien bleiben erhalten.

Schließt du während eines Downloads das Fenster, kann der eigenständige Updater seine laufende Transaktion noch abschließen. Bereits laufende Versionen werden nicht überschrieben. Einen begonnenen Download nicht durch das Löschen des Programmordners unterbrechen.

Für die Updates werden `api.github.com` und `raw.githubusercontent.com` über HTTPS angesprochen. GitHub begrenzt anonyme API-Anfragen. Bei Erreichen des Limits später erneut prüfen. Für Updates werden keine ZIP-Archive und keine Releases geladen.

## Häufige Probleme

**Es passiert nichts / Dateien fehlen:** Das gesamte Startpaket erneut in einen neuen Ordner entpacken. Die EXE allein genügt nicht. Der Ordner `payload` muss danebenliegen.

**Windows zeigt einen Herausgeberhinweis:** Die eigenen Programmdateien sind noch nicht digital signiert. Prüfe, dass der Download vom Repository `Contralto0/AK-Weather` stammt. Die enthaltenen Python-Binärdateien stammen aus der Python-Distribution.

**Updates können nicht gespeichert werden:** Prüfe Schreibrechte und freien Speicherplatz. Ein vorbereiteter Stand benötigt zusätzlich etwa die Größe der Anwendung auf dem Datenträger, obwohl nur geänderte Dateien aus dem Netz geladen werden. Frühere Versionen werden zur Absicherung erhalten und nicht automatisch gelöscht.

**Die vorherige Version startet:** Ein Update wird erst beim nächsten Start geöffnet. Eine zweite Instanz derselben Installation wird verhindert.

**Das Grundsystem wurde wiederhergestellt:** Wenn die Startprüfung des aktiven Updates fehlschlägt, öffnet der Starter das mitgelieferte `payload` und zeigt einen Hinweis. Für eine vollständige Rücksetzung die App schließen, einen eventuell laufenden Updatevorgang abwarten und den Ordner `.ak-weather` im entpackten Programmordner in `.ak-weather-backup` umbenennen. Beim nächsten Start wird wieder der mitgelieferte Stand verwendet und nach Updates gesucht. Alternativ das aktuelle Startpaket in einen neuen Ordner entpacken.

**GitHub meldet noch kein Updatepaket:** Solange der neue Inhalt noch nicht auf `live` veröffentlicht wurde, existiert dort noch kein Update-Manifest. Die lokale App funktioniert trotzdem.

## Daten und Entfernen

Der lokale Updatezustand liegt ausschließlich unter `.ak-weather` neben der Startdatei. Das Grundsystem sammelt keine Standortdaten und enthält keine Telemetrie. Es gibt noch keine persönlichen Wettereinstellungen.

Zum Entfernen die App schließen, laufende Updates abwarten und den entpackten Programmordner löschen. Es gibt keinen Installer und keine Autostart-Registrierung.

## Nutzung

Autor: **Andy Klemann**. Kostenlos verwendbar; Änderungen an eigenen Programmteilen sind nicht gestattet. Offizielle Updates und das Verwalten eigener lokaler Daten sind erlaubt. Einzelheiten in [LICENSE.md](../LICENSE.md).

<sub>Mit KI-Unterstützung programmiert.</sub>
