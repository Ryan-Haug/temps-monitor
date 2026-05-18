import os
import sys
import subprocess
import traceback
import tkinter as tk

import psutil


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LHM_DIR = os.path.join(BASE_DIR, "lib", "LibreHardwareMonitor")
LHM_DLL = os.path.join(LHM_DIR, "LibreHardwareMonitorLib.dll")


# ---------------------------------------------------------------------------
# Hide subprocess console flash
# ---------------------------------------------------------------------------

STARTUPINFO = None

if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE


# ---------------------------------------------------------------------------
# LibreHardwareMonitor CPU temp
# ---------------------------------------------------------------------------

_lhm_ready = False
_lhm_error = ""
_computer = None

_assembly_resolve_handler = None
_dll_directory_cookie = None

_printed_sensor_list_once = False


def init_lhm() -> None:
    global _lhm_ready
    global _lhm_error
    global _computer
    global _assembly_resolve_handler
    global _dll_directory_cookie

    try:
        if sys.maxsize <= 2**32:
            raise RuntimeError(
                "You are using 32-bit Python. Install 64-bit Python 3.12."
            )

        if not os.path.isdir(LHM_DIR):
            raise FileNotFoundError(f"Missing folder: {LHM_DIR}")

        if not os.path.isfile(LHM_DLL):
            raise FileNotFoundError(
                f"Missing LibreHardwareMonitorLib.dll at: {LHM_DLL}"
            )

        # Prevent old failed coreclr settings from breaking this net472 setup.
        os.environ.pop("PYTHONNET_RUNTIME", None)
        os.environ.pop("PYTHONNET_CORECLR_RUNTIME_CONFIG", None)

        # Let Python, Windows, and .NET find LibreHardwareMonitor dependencies.
        if LHM_DIR not in sys.path:
            sys.path.insert(0, LHM_DIR)

        os.environ["PATH"] = LHM_DIR + os.pathsep + os.environ.get("PATH", "")

        if hasattr(os, "add_dll_directory"):
            _dll_directory_cookie = os.add_dll_directory(LHM_DIR)

        # Use .NET Framework for LibreHardwareMonitor net472.
        from pythonnet import load

        load("netfx")

        from System import AppDomain, Activator
        from System.Reflection import Assembly

        def resolve_assembly(sender, args):
            assembly_name = args.Name.split(",")[0]

            dll_path = os.path.join(LHM_DIR, assembly_name + ".dll")
            if os.path.isfile(dll_path):
                return Assembly.LoadFrom(dll_path)

            exe_path = os.path.join(LHM_DIR, assembly_name + ".exe")
            if os.path.isfile(exe_path):
                return Assembly.LoadFrom(exe_path)

            return None

        _assembly_resolve_handler = resolve_assembly
        AppDomain.CurrentDomain.AssemblyResolve += _assembly_resolve_handler

        # Load the LibreHardwareMonitor DLL directly.
        assembly = Assembly.LoadFrom(LHM_DLL)

        computer_type = assembly.GetType("LibreHardwareMonitor.Hardware.Computer")

        if computer_type is None:
            raise RuntimeError(
                "Could not find LibreHardwareMonitor.Hardware.Computer "
                "inside LibreHardwareMonitorLib.dll"
            )

        computer = Activator.CreateInstance(computer_type)

        computer.IsCpuEnabled = True
        computer.IsMotherboardEnabled = True
        computer.IsGpuEnabled = False
        computer.IsMemoryEnabled = False
        computer.IsStorageEnabled = False
        computer.IsNetworkEnabled = False
        computer.IsControllerEnabled = False

        computer.Open()

        _computer = computer
        _lhm_ready = True
        _lhm_error = ""

        print("LibreHardwareMonitor loaded successfully.")

    except Exception:
        _lhm_ready = False
        _computer = None
        _lhm_error = traceback.format_exc()

        print()
        print("LibreHardwareMonitor failed to load:")
        print(_lhm_error)


def update_hardware(hardware) -> None:
    try:
        hardware.Update()
    except Exception:
        pass

    try:
        for subhardware in hardware.SubHardware:
            update_hardware(subhardware)
    except Exception:
        pass


def collect_sensors(hardware):
    sensors = []

    try:
        for sensor in hardware.Sensors:
            sensors.append(sensor)
    except Exception:
        pass

    try:
        for subhardware in hardware.SubHardware:
            sensors.extend(collect_sensors(subhardware))
    except Exception:
        pass

    return sensors


def get_cpu_temp() -> str:
    global _printed_sensor_list_once

    if not _lhm_ready or _computer is None:
        return "LHM load error"

    try:
        all_temp_sensors = []
        cpu_named_temps = []

        for hardware in _computer.Hardware:
            update_hardware(hardware)

            hardware_name = str(hardware.Name)
            hardware_type = str(hardware.HardwareType)

            for sensor in collect_sensors(hardware):
                sensor_type = str(sensor.SensorType)

                if sensor_type.lower() != "temperature":
                    continue

                if sensor.Value is None:
                    continue

                sensor_name = str(sensor.Name)
                value = float(sensor.Value)

                if value <= 0:
                    continue

                full_name = f"{hardware_name} / {sensor_name}"
                all_temp_sensors.append((full_name, value))

                name_lower = full_name.lower()

                cpu_keywords = [
                    "ryzen",
                    "cpu",
                    "tctl",
                    "tdie",
                    "ccd",
                    "package",
                    "core",
                ]

                if any(keyword in name_lower for keyword in cpu_keywords):
                    cpu_named_temps.append((full_name, value))

        if not _printed_sensor_list_once:
            print()
            print("All temperature sensors found:")
            if not all_temp_sensors:
                print("  No temperature sensors found.")
            else:
                for name, value in all_temp_sensors:
                    print(f"  {name}: {value:.1f} °C")
            _printed_sensor_list_once = True

        if not all_temp_sensors:
            return "N/A"

        preferred_keywords = [
            "tctl/tdie",
            "tctl",
            "tdie",
            "cpu package",
            "package",
            "ccd",
            "ryzen",
        ]

        for keyword in preferred_keywords:
            matches = [
                value
                for name, value in cpu_named_temps
                if keyword in name.lower()
            ]

            if matches:
                return f"{max(matches):.0f} °C"

        if cpu_named_temps:
            return f"{max(value for _, value in cpu_named_temps):.0f} °C"

        return "N/A"

    except Exception:
        print()
        print("CPU temp read failed:")
        print(traceback.format_exc())
        return "CPU temp error"


# ---------------------------------------------------------------------------
# GPU stats through nvidia-smi
# ---------------------------------------------------------------------------

def get_gpu_stats() -> dict:
    result = {
        "temp": "N/A",
        "usage": "N/A",
        "vram_used": "N/A",
        "vram_total": "N/A",
    }

    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]

        out = subprocess.check_output(
            cmd,
            timeout=2,
            stderr=subprocess.DEVNULL,
            startupinfo=STARTUPINFO,
        )

        parts = out.decode(errors="ignore").strip().split(",")

        if len(parts) == 4:
            gpu_temp = parts[0].strip()
            gpu_usage = parts[1].strip()
            vram_used = int(parts[2].strip())
            vram_total = int(parts[3].strip())

            result["temp"] = f"{gpu_temp} °C"
            result["usage"] = f"{gpu_usage} %"
            result["vram_used"] = f"{vram_used} MB"
            result["vram_total"] = f"{vram_total} MB"

    except FileNotFoundError:
        result["temp"] = "nvidia-smi missing"
    except Exception as e:
        result["temp"] = f"GPU error"

        print()
        print("GPU read failed:")
        print(str(e))

    return result


# ---------------------------------------------------------------------------
# CPU usage / RAM
# ---------------------------------------------------------------------------

def get_cpu_usage() -> str:
    return f"{psutil.cpu_percent(interval=None):.1f} %"


def get_ram_stats() -> dict:
    mem = psutil.virtual_memory()

    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)

    return {
        "used": f"{used_gb:.1f} GB",
        "total": f"{total_gb:.1f} GB",
        "percent": f"{mem.percent:.1f} %",
    }


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

BG = "#1a1a1a"
FG_LABEL = "#888888"
FG_VALUE = "#e8e8e8"
FG_TITLE = "#00ccff"

FONT_LBL = ("Consolas", 10)
FONT_VAL = ("Consolas", 13, "bold")
FONT_TTL = ("Consolas", 11, "bold")


def make_row(parent, label: str, row: int):
    lbl = tk.Label(
        parent,
        text=label,
        font=FONT_LBL,
        fg=FG_LABEL,
        bg=BG,
        anchor="w",
    )
    lbl.grid(row=row, column=0, sticky="w", padx=(12, 6), pady=3)

    var = tk.StringVar(value="...")

    val = tk.Label(
        parent,
        textvariable=var,
        font=FONT_VAL,
        fg=FG_VALUE,
        bg=BG,
        anchor="e",
        width=18,
    )
    val.grid(row=row, column=1, sticky="e", padx=(6, 12), pady=3)

    return var


def make_section_title(parent, text: str, row: int):
    lbl = tk.Label(
        parent,
        text=text,
        font=FONT_TTL,
        fg=FG_TITLE,
        bg=BG,
        anchor="w",
    )
    lbl.grid(
        row=row,
        column=0,
        columnspan=2,
        sticky="w",
        padx=12,
        pady=(10, 2),
    )


def build_ui(root: tk.Tk):
    root.title("HW Monitor")
    root.configure(bg=BG)
    root.resizable(False, False)

    frame = tk.Frame(root, bg=BG)
    frame.pack(fill="both", expand=True)

    row = 0

    make_section_title(frame, "── CPU ──────────────────", row)
    row += 1

    v_cpu_temp = make_row(frame, "Temperature", row)
    row += 1

    v_cpu_usage = make_row(frame, "Usage", row)
    row += 1

    make_section_title(frame, "── GPU ──────────────────", row)
    row += 1

    v_gpu_temp = make_row(frame, "Temperature", row)
    row += 1

    v_gpu_usage = make_row(frame, "Usage", row)
    row += 1

    v_vram_used = make_row(frame, "VRAM Used", row)
    row += 1

    v_vram_total = make_row(frame, "VRAM Total", row)
    row += 1

    make_section_title(frame, "── RAM ──────────────────", row)
    row += 1

    v_ram_used = make_row(frame, "Used / Total", row)
    row += 1

    v_ram_pct = make_row(frame, "Usage", row)
    row += 1

    tk.Label(
        frame,
        text="Refreshing every 1 s",
        font=("Consolas", 8),
        fg="#555555",
        bg=BG,
    ).grid(row=row, column=0, columnspan=2, pady=(6, 8))

    return {
        "cpu_temp": v_cpu_temp,
        "cpu_usage": v_cpu_usage,
        "gpu_temp": v_gpu_temp,
        "gpu_usage": v_gpu_usage,
        "vram_used": v_vram_used,
        "vram_total": v_vram_total,
        "ram_used": v_ram_used,
        "ram_pct": v_ram_pct,
    }


def refresh(root: tk.Tk, vars: dict):
    vars["cpu_temp"].set(get_cpu_temp())
    vars["cpu_usage"].set(get_cpu_usage())

    gpu = get_gpu_stats()
    vars["gpu_temp"].set(gpu["temp"])
    vars["gpu_usage"].set(gpu["usage"])
    vars["vram_used"].set(gpu["vram_used"])
    vars["vram_total"].set(gpu["vram_total"])

    ram = get_ram_stats()
    vars["ram_used"].set(f"{ram['used']} / {ram['total']}")
    vars["ram_pct"].set(ram["percent"])

    root.after(1000, refresh, root, vars)


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    psutil.cpu_percent(interval=None)

    init_lhm()

    root = tk.Tk()
    ui_vars = build_ui(root)

    root.after(100, refresh, root, ui_vars)
    root.mainloop()