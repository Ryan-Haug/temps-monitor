# HW Monitor

A lightweight Windows 11 hardware monitor built with Python. Displays real-time CPU temperature, CPU usage, GPU temperature, GPU usage, VRAM, and RAM stats in a clean dark UI. Refreshes every second.

![Python](https://img.shields.io/badge/python-3.12-blue) ![Platform](https://img.shields.io/badge/platform-Windows%2011-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- CPU temperature via LibreHardwareMonitor — accurate Tctl/Tdie readings for Ryzen
- CPU usage via psutil
- GPU temperature, usage, and VRAM via nvidia-smi
- RAM used / total / percentage via psutil
- 1-second refresh rate
- No background monitoring service required

---

## Requirements

| Requirement | Notes |
|---|---|
| Windows 10 / 11 | WMI and nvidia-smi are Windows-only |
| Python 3.12 (64-bit) | 32-bit Python will not work |
| .NET Framework 4.7.2+ | Ships with Windows 10/11 — no install needed |
| NVIDIA GPU + drivers | nvidia-smi ships with NVIDIA drivers |
| Administrator privileges | Required by LibreHardwareMonitor to read CPU sensors |

---

## Project Structure

```
hw-monitor/
├── main.py
├── run.bat
├── icon.ico                          (optional)
├── README.md
└── lib/
    └── LibreHardwareMonitor/
        ├── LibreHardwareMonitorLib.dll
        ├── HidSharp.dll
        └── ...                       (all DLLs from the release zip)
```

---

## Installation

**1. Install Python dependencies**
```bash
py -3.12 -m pip install psutil pythonnet
```

**2. Download LibreHardwareMonitor DLLs**

- Go to https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases
- Download the `net472` release zip
- Extract all DLLs into `lib/LibreHardwareMonitor/`

**3. Run**

Double-click `run.bat`. It will automatically prompt for Administrator elevation via UAC — required for LibreHardwareMonitor to access CPU hardware sensors.

---

## run.bat

The batch script handles elevation automatically so you never need to manually run a terminal as Administrator.

```bat
@echo off
setlocal

set "PROJECT_DIR=C:\Users\Ryan\Documents\Projects\hw-monior"

REM Check if already admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'pyw' -ArgumentList '-3.12','main.py' -WorkingDirectory '%PROJECT_DIR%' -Verb RunAs"
    exit /b
)

cd /d "%PROJECT_DIR%"
start "" pyw -3.12 main.py
exit /b
```

How it works:
- `net session` checks whether the script is already running as Administrator
- If not elevated, PowerShell re-launches the script using `Start-Process` with `-Verb RunAs`, which triggers the Windows UAC prompt
- `pyw` instead of `python` or `py` suppresses the console window so only the monitor UI appears
- If already elevated (e.g. launched from an admin terminal), it runs directly

> To use on a different machine, update `PROJECT_DIR` to match the install path.


---

## How It Works

### CPU Temperature — LibreHardwareMonitor
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) is an open-source hardware monitoring library. The app loads `LibreHardwareMonitorLib.dll` at runtime using **pythonnet** with the `.NET Framework (netfx)` runtime.

The init sequence:
1. The `lib/LibreHardwareMonitor/` folder is added to `sys.path`, the Windows `PATH`, and registered via `os.add_dll_directory()` so all dependency DLLs are found automatically
2. An `AssemblyResolve` event handler is registered on the .NET `AppDomain` to catch any remaining dependency lookups at runtime
3. The `Computer` object is created with only `IsCpuEnabled` and `IsMotherboardEnabled` set to `True` — everything else is disabled to keep it lightweight
4. On each refresh, `hardware.Update()` is called recursively through all hardware and sub-hardware nodes before reading sensor values
5. Sensors are prioritised by name: `tctl/tdie` → `tctl` → `tdie` → `cpu package` → `package` → `ccd` → any CPU-named temp

Requires Administrator privileges — LibreHardwareMonitor needs elevated access to read hardware registers.

### CPU Usage — psutil
`psutil.cpu_percent(interval=None)` reads CPU utilisation from Windows performance counters. Called with `interval=None` for a non-blocking snapshot based on the delta since the previous call.

### GPU Stats — nvidia-smi
The app shells out to `nvidia-smi` which ships with every NVIDIA driver installation:
```
nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
```
`subprocess.STARTUPINFO` with `SW_HIDE` suppresses any console window flash.

### RAM — psutil
`psutil.virtual_memory()` returns used and total RAM in bytes, converted to GB for display.

### UI — tkinter
Pure tkinter — no external UI framework. A `tk.Frame` with a grid layout holds label/value pairs for each stat. All values are `tk.StringVar` instances updated in a `refresh()` function that reschedules itself every 1000ms via `root.after()`, keeping the main thread free and the window responsive.

---

## Tested On

- Ryzen 7 7800X3D
- NVIDIA RTX 5070
- Gigabyte B650 Gaming X AX
- Windows 11
- Python 3.12 (64-bit)