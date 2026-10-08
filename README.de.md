# PetriTrace

[English](README.md) · [Deutsch](README.de.md) · [中文](README.zh-CN.md)

PetriTrace ist ein System auf Raspberry-Pi-Basis zur Beobachtung von Petrischalen. Es verbindet zeitgesteuerte Fotoaufnahmen, Temperatur- und Feuchtigkeitsaufzeichnung sowie Koloniezählung. Das Projekt umfasst die Steuerungssoftware, Gehäusemodelle und Fertigungszeichnungen sowie eine bebilderte Bau- und Bedienungsanleitung.

![PetriTrace mit Touchscreen und Gehäuse](docs/assets/manual/photos/front.jpg)

Über den Touchscreen am Gerät oder einen Browser auf Computer, Smartphone oder Tablet können Sie Aufnahmen steuern, Fotos und Messwerte ansehen und Daten zur weiteren Auswertung exportieren.

## Einstieg

| Software | Gehäusezeichnungen | Anleitung |
|---|---|---|
| [Download unter Releases](https://github.com/J-ShuJie/PetriTrace/releases) | [Zeichnungen herunterladen](https://github.com/J-ShuJie/PetriTrace/releases) · [Dateibeschreibung](#gehäusezeichnungen) | [Online lesen](docs/PetriTrace_Manual_de.md) · [PDF ansehen](docs/pdf/PetriTrace_Manual_de.pdf) |
| Windows-Setup mit Bereitstellungsmanager und Anwendungsdateien für den Raspberry Pi | DWG-Zuschnittplan und OpenSCAD-Quelldateien für 19 Platten | Material, Zusammenbau, Verkabelung, Installation und Bedienung |

Software, Zeichnungen und Anleitung können Sie unabhängig voneinander herunterladen. Wenn Raspberry Pi und Kamerahardware bereits vorhanden sind, können Sie die Software installieren und ein eigenes Gehäuse verwenden. Der Quellcode ist in diesem Repository enthalten.

## Softwarefunktionen

- **Aufnahme und Beleuchtung:** Einzelbilder oder zeitgesteuerte Bildserien aufnehmen; Helligkeit des LED-Streifens und Beleuchtungsdauer vor und nach jeder Aufnahme einstellen.
- **Umwelt- und Koloniedaten:** Temperatur und Luftfeuchtigkeit von zwei Sensoren sowie die Entwicklung der Koloniezahl verfolgen.
- **Fotos und Messwerte:** Zu jedem Foto die Koloniezahl und Umgebungswerte anzeigen und den zugehörigen Punkt im Verlaufsdiagramm finden.
- **Export und Verwaltung:** Fotos und Daten nach Zeitraum oder Auswahl exportieren und mehrere Einträge gemeinsam löschen.
- **Installation und Wartung:** Mit dem Bereitstellungsmanager den Raspberry Pi verbinden, die Software installieren, Verbindungen prüfen und Reparaturen ausführen.

![Browseroberfläche mit Aufnahmesteuerung und Verlaufsdiagrammen](docs/assets/manual/ui/15_capture_overview_updated.png)

Der Bereitstellungsmanager läuft unter Windows. Nach der Installation führt der Raspberry Pi Aufnahmen und Aufzeichnungen selbstständig aus. Für die tägliche Bedienung öffnen Sie die Browseroberfläche. Für den Zugriff über verschiedene Netzwerke nutzen Sie Ihr eigenes Tailscale-Konto; Raspberry Pi und zugreifendes Gerät müssen zum selben berechtigten Tailscale-Netzwerk gehören.

## Gehäusezeichnungen

Das Referenzgerät verwendet einen Raspberry Pi 5, ein Camera Module 3, ein 5-Zoll-Touch Display 2, einen Pico WH mit Erweiterungsplatine, zwei Temperatur- und Feuchtigkeitssensoren und einen LED-Streifen. Das Gehäuse besteht aus 19 Platten mit 3 mm Stärke und umfasst einen fünflagigen Bildschirmrahmen, eine Tür und einen Magnetverschluss.

![Explosionszeichnung des Gehäuses](docs/assets/manual/exploded.png)

| Datei | Verwendung |
|---|---|
| `PetriTrace_19parts_mm_DWG2007.dwg` | Zuschnittplan in Millimetern; im Maßstab 1:1 fertigen |
| `PetriTrace_OpenSCAD.zip` | Bearbeitbares OpenSCAD-Modell mit den benötigten Bibliotheken und einzelnen Dateien für alle 19 Platten |

Beide Dateien finden Sie unter `hardware/` und als separate Downloads unter Releases. Die Anleitung enthält Bauteilspezifikationen, Schrauben- und Mutternmengen sowie die Schritte zur Verkabelung und Montage.

## Gerät bauen und verwenden

1. **Material beschaffen:** Elektronik und Befestigungsteile nach der Materialliste auswählen und die Platten aus 3 mm starkem Material fertigen.
2. **Raspberry Pi vorbereiten:** Raspberry Pi OS Desktop in der 64-Bit-Version auf die microSD-Karte schreiben und Benutzerkonto, Netzwerk und SSH einrichten. Die Karte vor dem Einbau der Platine einsetzen.
3. **Montieren und verkabeln:** Zuerst die Elektronik an den zugehörigen Platten befestigen, dann das Gehäuse schrittweise zusammenbauen und die Kabel anschließen. Die Vorbereitung des Pico WH ist in der Anleitung beschrieben.
4. **Software installieren:** Setup auf einem Windows-Computer ausführen, den PetriTrace-Bereitstellungsmanager öffnen und den Schritten für Verbindung und Installation folgen. Der Computer muss den Raspberry Pi erreichen können. Der Pi benötigt Internetzugang, um Softwareabhängigkeiten herunterzuladen.
5. **Probeaufnahme machen:** Die Petrischale auf die Auflage des oberen Rahmens legen, Fotos, Sensorwerte und Export prüfen und anschließend die zeitgesteuerte Aufnahme starten.

Für die erste Hardwaremontage sind etwa 1,5 Stunden vorgesehen. Betriebssystemeinrichtung und Softwareinstallation kommen hinzu. Die vollständigen Schritte finden Sie in der [Bau- und Bedienungsanleitung](docs/PetriTrace_Manual_de.md). Zum Erstellen der Software aus dem Quellcode dient die [Build-Anleitung auf Englisch](docs/BUILD.md).

## Lizenz und Mitarbeit

Projektautor: [J-ShuJie](https://github.com/J-ShuJie).

Die projekteigene Software, Gehäusezeichnungen und Anleitungen stehen unter der [MIT-Lizenz](LICENSE). Lizenzen und Urheberhinweise zu Drittanbieterkomponenten sind in den [Third-party notices](THIRD_PARTY_NOTICES.md) aufgeführt.

Probleme und Vorschläge können Sie unter [Issues](https://github.com/J-ShuJie/PetriTrace/issues) melden. Verbesserungen per [Pull Request](https://github.com/J-ShuJie/PetriTrace/pulls) sind willkommen.
