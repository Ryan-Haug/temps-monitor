# HW Monitor

A lightweight Windows 11 hardware monitor built with Python. Displays real-time CPU temperature, CPU usage, GPU temperature, GPU usage, VRAM, and RAM stats in a clean dark UI. Refreshes every second.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Platform](https://img.shields.io/badge/platform-Windows%2011-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- CPU temperature via Windows WMI (no background services or drivers needed)
- CPU usage via psutil
- GPU temperature, usage, and VRAM via nvidia-smi
- RAM used / total / percentage via psutil
- 1-second refresh rate
- Single-file exe build — hand it to anyone with an NVIDIA GPU and it just works

---

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10 / 11 | WMI and nvidia-smi are Windows-only |
| Python 3.12 | Other versions may work but are untested |
| NVIDIA GPU + drivers | nvidia-smi ships with NVIDIA drivers |
| Administrator privileges | Required by WMI to read CPU thermal sensors |

---

## Installation

**1. Clone the repo**
```bash
git clone https://github.com/yourusername/hw-monitor.git
cd hw-monitor
```

**2. Install dependencies**
```bash
py -3.12 -m pip install psutil wmi pywin32
```

**3. Run**
```bash
py -3.12 main.py
```

> Run as Administrator for CPU temperature to work. Right-click your terminal → "Run as administrator".

---

## Build to EXE

**1. Install PyInstaller**
```bash
py -3.12 -m pip install pyinstaller
```

**2. Build**
```bash
py -3.12 -m PyInstaller --onefile --noconsole --name "HWMonitor" --hidden-import wmi --hidden-import pythoncom --hidden-import win32com.client --uac-admin main.py
```

**3. Find your exe**
```
dist/HWMonitor.exe
```

The `--uac-admin` flag embeds a UAC manifest so Windows automatically prompts for elevation on launch — this is required for WMI CPU temperature access.

**Optional: custom icon**

Place an `icon.ico` file in the project root, add `root.iconbitmap("icon.ico")` in `build_ui()`, then append `--icon="icon.ico"` to the PyInstaller command.

---

## How It Works

### CPU Temperature — WMI
Windows exposes ACPI thermal zone data through WMI under `root/WMI`. The class `MSAcpi_ThermalZoneTemperature` returns temperatures in tenths of Kelvin, which are converted to Celsius:

```python
celsius = (kelvin_tenths / 10.0) - 273.15
```

This requires Administrator privileges but needs no third-party drivers or background services.

### CPU Usage — psutil
`psutil.cpu_percent()` reads CPU utilisation directly from the Windows performance counters. It's called with `interval=None` so it returns a non-blocking snapshot based on the delta since the last call.

### GPU Stats — nvidia-smi
Rather than importing a GPU library, the app shells out to `nvidia-smi` which ships with every NVIDIA driver installation:

```
nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
```

The subprocess uses `STARTUPINFO` with `SW_HIDE` to suppress any console window flash.

### RAM — psutil
`psutil.virtual_memory()` returns used and total RAM in bytes, converted to GB for display.

### UI — tkinter
The UI is pure tkinter — no external UI framework. A `tk.Frame` with a grid layout holds label/value pairs for each stat. All values are `tk.StringVar` instances updated in a `refresh()` function that reschedules itself every 1000ms using `root.after()`, keeping the main thread free and the window responsive.

---

## Project Structure

```
hw-monitor/
├── main.py        # entire application
├── icon.ico       # optional — window and exe icon
└── README.md
```

---

## Tested On

- Ryzen 7 7800X3D
- NVIDIA RTX 5070
- Gigabyte B650 Gaming X AX
- Windows 11
- Python 3.12
