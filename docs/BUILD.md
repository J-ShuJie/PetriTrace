# Building PetriTrace

## Windows manager and Setup

Use Windows x64, the .NET 8 SDK, PowerShell and Inno Setup 6. The build includes the .NET runtime, so users do not need a separate .NET installation.

From the repository root:

```powershell
./scripts/build_windows_setup.ps1 -Version 1.0.0
```

The build creates `artifacts/setup/PetriTrace-1.0.0-Setup.exe`. It first packages the Raspberry Pi files listed in `deploy/release-files.txt`, then publishes the Windows manager and compiles Setup. `release-info.json` and the payload manifest record the selected version and file hashes.

Setup installs for the current user under `%LOCALAPPDATA%/Programs/PetriTrace`. Manager configuration is stored separately under `%LOCALAPPDATA%/PiCameraControl` and is retained when upgrading or uninstalling. The manager supports English, German and Chinese. Setup's installation screens currently offer English and German.

The `licenses/` directory contains notices for the runtime and NuGet versions used by the packaged release. When changing the SDK or dependency versions, update these notices to match the resolved build.

## Raspberry Pi application

The supported deployment path is the Windows manager connecting to a Raspberry Pi running 64-bit Raspberry Pi OS Desktop over SSH. The Pi downloads system packages and the Python dependencies in `requirements.txt` and `requirements-mcount.txt`. See the assembly and user manual for system preparation and deployment.

The deployment payload can also be built separately:

```powershell
./scripts/build_release.ps1 -Version 1.0.0
```

## Tests

Use Python 3.11 or newer, Node.js and the .NET 8 SDK. Create a Python environment and install both requirements files, then run:

```powershell
python -m unittest discover -s tests
dotnet run --project desktop/PiCameraControl.Manager.Core.Tests/PiCameraControl.Manager.Core.Tests.csproj -c Release
node --test tests/test_entry_context.js tests/test_history_axis.js tests/test_history_range.js tests/test_issue_dismissal.js tests/test_ui_update.cjs
```

Some tests require Linux or hardware-specific tools and skip on Windows. The local tests do not replace a complete deployment on a newly imaged Raspberry Pi.

## Manual PDFs

The Markdown manuals and their images are in `docs/`. On Windows, install Pillow, ReportLab and pypdfium2 in your document-building Python environment, then run:

```powershell
python scripts/build_manual.py --skip-cad --language zh
python scripts/build_manual.py --skip-cad --language en
python scripts/build_manual.py --skip-cad --language de
```

The builder uses Microsoft YaHei fonts from Windows and produces PDFs in `output/pdf/`. It also renders pages for layout checking under `tmp/`. Each main chapter starts on a new page. Contents entries and bookmarks link to sections.

The included figures are sufficient for rebuilding PDFs. To regenerate CAD illustrations, install OpenSCAD, extract `hardware/PetriTrace_OpenSCAD.zip`, and supply its `OpenSCAD` directory with `--cad-dir` instead of `--skip-cad`. The default renderer path is `C:/Program Files/OpenSCAD/openscad.com`. Run `scripts/localize_manual_figures.py` afterwards to recreate English and German labels.
