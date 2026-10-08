# Third-party software notices

PetriTrace's own software, hardware designs and documentation use the MIT License in [LICENSE](LICENSE). Third-party components retain their own licenses and copyright notices.

## Included source and assets

| Component | Use | License text |
|---|---|---|
| MCount adapter | Colony-counting algorithm adapted in `tools/mcount_cli.py` | [MIT](tools/MCOUNT_LICENSE.txt) |
| Lucide Icons | Local interface icons | [ISC and included Feather MIT terms](static/icons/lucide/LICENSE.txt) |

## Windows application

The self-contained Windows application includes the following components. Their license texts accompany the installed application in `licenses/`.

| Component | Version | Notice directory |
|---|---|---|
| SSH.NET | 2026.0.0 | `licenses/SSH.NET` |
| BouncyCastle.Cryptography | 2.7.0 | `licenses/BouncyCastle` |
| Microsoft.Extensions.Logging.Abstractions | 8.0.3 | `licenses/Logging` |
| Microsoft.Extensions.DependencyInjection.Abstractions | 8.0.2 | `licenses/DependencyInjection` |
| .NET Core Runtime for Windows x64 | 8.0.31 | `licenses/NETCore` |
| .NET Windows Desktop Runtime for Windows x64 | 8.0.31 | `licenses/WindowsDesktop` |

The SSH.NET notice is assembled from the package's MIT license declaration and copyright metadata. Its package metadata and a provenance note are included in the same directory.

## Dependencies installed on the Raspberry Pi

The deployment process downloads system and Python packages to the Raspberry Pi. These packages are not bundled into the Setup executable or the application source archive.

| Component | Use |
|---|---|
| Flask | Web application |
| Pillow | Images and thumbnails |
| pySerial | USB communication with the Pico |
| NumPy, SciPy, OpenCV Python headless | MCount image processing and counting |
| OpenCFU | External colony-counting program |
| Picamera2 and libcamera | Camera access |
| Chromium, swayidle, wlopm, grim | Touchscreen display, screen sleep and diagnostic screenshots |

Python dependency ranges are listed in `requirements.txt` and `requirements-mcount.txt`. System packages are selected by `deploy/install_pi.sh`. Each package supplies its own license and copyright information on the device.

## Tailscale

Tailscale is an external program and service. When remote access is enabled in the deployment manager, the Raspberry Pi downloads Tailscale through its installation process. Users register their own accounts and authorize their own devices. Tailscale is not bundled in PetriTrace's Setup package.
