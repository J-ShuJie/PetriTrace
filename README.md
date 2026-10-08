# PetriTrace

[English](README.md) · [Deutsch](README.de.md) · [中文](README.zh-CN.md)

PetriTrace is a Raspberry Pi system for observing Petri dishes. It combines scheduled photography, temperature and humidity recording, and colony counting with enclosure designs, cutting drawings and an illustrated assembly and user manual.

![PetriTrace with its touchscreen and enclosure](docs/assets/manual/photos/front.jpg)

Use the device touchscreen or a browser on a computer, phone or tablet to take photographs, inspect records and export data for analysis.

## Get started

| Software | Hardware drawings | Manual |
|---|---|---|
| [Download from Releases](https://github.com/J-ShuJie/PetriTrace/releases) | [Download drawings](https://github.com/J-ShuJie/PetriTrace/releases) · [File guide](#hardware-drawings) | [Read online](docs/PetriTrace_Manual_en.md) · [View PDF](docs/pdf/PetriTrace_Manual_en.pdf) |
| Windows Setup, including the deployment manager and Raspberry Pi application files | DWG cutting layout and OpenSCAD source for 19 panels | Materials, assembly, wiring, deployment and daily use |

Download the software, drawings and manual separately as needed. If you already have a Raspberry Pi and camera hardware, you can install the software and use your own enclosure. Application source is included in this repository.

## Software

- **Capture and lighting:** take individual photographs or run scheduled captures; set light brightness and illumination times before and after each capture.
- **Environmental and colony records:** inspect readings from two temperature and humidity sensors and changes in colony counts over time.
- **Photos and measurements:** view each photo with its count and environmental readings, and locate its corresponding point in the history chart.
- **Export and organize:** export photos and data by date range or selection, and delete records in batches.
- **Deploy and maintain:** connect to the Raspberry Pi, install the application, diagnose connectivity and run repairs from the deployment manager.

![Browser interface with capture controls and history charts](docs/assets/manual/ui/15_capture_overview_updated.png)

The deployment manager runs on Windows. After deployment, the Raspberry Pi runs capture and logging independently. For daily use, open its browser interface. Remote access uses your own Tailscale account, with the Raspberry Pi and client device on the same authorized network.

## Hardware drawings

The reference device uses a Raspberry Pi 5, Camera Module 3, 5-inch Touch Display 2, Pico WH and expansion shield, two temperature and humidity sensors, and an LED strip. The enclosure consists of 19 panels of 3 mm sheet material, including a five-layer screen frame, door and magnetic latch.

![Exploded view of the enclosure](docs/assets/manual/exploded.png)

| File | Purpose |
|---|---|
| `PetriTrace_19parts_mm_DWG2007.dwg` | Cutting layout in millimetres; manufacture at 1:1 scale |
| `PetriTrace_OpenSCAD.zip` | Editable OpenSCAD model, including its dependencies and individual files for all 19 panels |

Both files are available in `hardware/` and as separate release downloads. The manual lists component specifications, screw and nut quantities, wiring and assembly steps.

## Build and use the device

1. **Gather materials:** obtain the electronic parts and fasteners listed in the manual, and cut the 3 mm panels.
2. **Prepare the Raspberry Pi:** write 64-bit Raspberry Pi OS Desktop to the microSD card; configure an account, networking and SSH. Insert the card before mounting the board.
3. **Assemble and wire:** mount electronics on their panels, then assemble the enclosure and connect cables. The manual explains how to prepare the Pico WH.
4. **Deploy:** run Setup on a Windows computer, open the PetriTrace deployment manager and follow the connection and installation steps. The computer must be able to reach the Raspberry Pi, and the Pi needs Internet access to download dependencies.
5. **Take a test photograph:** place the Petri dish on the upper frame, check photos, sensor readings and export, then start scheduled recording.

Allow approximately 1.5 hours for initial hardware assembly, plus system preparation and software deployment. See the manual for full instructions and the [build guide](docs/BUILD.md) to build the software from source.

## License and contributions

Project author: [J-ShuJie](https://github.com/J-ShuJie).

The project's own software, hardware drawings and manuals use the [MIT License](LICENSE). Third-party licenses and credits are listed in [Third-party notices](THIRD_PARTY_NOTICES.md).

Report problems and suggestions in [Issues](https://github.com/J-ShuJie/PetriTrace/issues). Contributions through [pull requests](https://github.com/J-ShuJie/PetriTrace/pulls) are welcome.
