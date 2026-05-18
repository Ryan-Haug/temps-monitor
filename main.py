"""
hw_monitor/main.py
------------------
Lightweight Windows 11 hardware monitor.
Shows CPU temp, CPU usage, GPU temp, GPU usage, VRAM, and RAM.
Refreshes every second.
"""

import tkinter as tk
import psutil
import subprocess
import sys
import os

# Hide the console window when launching subprocesses (fixes flashing CMD)
STARTUPINFO = subprocess.STARTUPINFO()
STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
STARTUPINFO.wShowWindow = subprocess.SW_HIDE

# ---------------------------------------------------------------------------
# CPU Temperature via WMI
# ---------------------------------------------------------------------------

import wmi
_wmi = wmi.WMI(namespace="root/WMI")

def get_cpu_temp() -> str:
    try:
        temps = _wmi.MSAcpi_ThermalZoneTemperature()
        if not temps:
            return "N/A"
        # CurrentTemperature is in tenths of Kelvin — convert to Celsius
        kelvin_tenths = max(int(t.CurrentTemperature) for t in temps)
        celsius = (kelvin_tenths / 10.0) - 273.15
        return f"{celsius:.0f} °C"
    except Exception as e:
        return f"Err: {e}"


# ---------------------------------------------------------------------------
# GPU stats via nvidia-smi
# ---------------------------------------------------------------------------

def get_gpu_stats() -> dict:
    result = {"temp": "N/A", "usage": "N/A", "vram_used": "N/A", "vram_total": "N/A"}
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]
        out = subprocess.check_output(
            cmd, timeout=2, stderr=subprocess.DEVNULL,
            startupinfo=STARTUPINFO  # no flashing CMD window
        )
        parts = out.decode().strip().split(",")
        if len(parts) == 4:
            result["temp"]       = f"{parts[0].strip()} °C"
            result["usage"]      = f"{parts[1].strip()} %"
            vram_used            = int(parts[2].strip())
            vram_total           = int(parts[3].strip())
            result["vram_used"]  = f"{vram_used} MB"
            result["vram_total"] = f"{vram_total} MB"
    except FileNotFoundError:
        result["temp"] = "nvidia-smi not found"
    except Exception as e:
        result["temp"] = f"Err: {e}"
    return result


# ---------------------------------------------------------------------------
# CPU / RAM stats via psutil
# ---------------------------------------------------------------------------

def get_cpu_usage() -> str:
    return f"{psutil.cpu_percent(interval=None):.1f} %"


def get_ram_stats() -> dict:
    mem = psutil.virtual_memory()
    used_gb  = mem.used  / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    return {
        "used":    f"{used_gb:.1f} GB",
        "total":   f"{total_gb:.1f} GB",
        "percent": f"{mem.percent:.1f} %",
    }


# ---------------------------------------------------------------------------
# Tkinter UI
# ---------------------------------------------------------------------------

BG       = "#1a1a1a"
FG_LABEL = "#888888"
FG_VALUE = "#e8e8e8"
FG_TITLE = "#00ccff"
FONT_LBL = ("Consolas", 10)
FONT_VAL = ("Consolas", 13, "bold")
FONT_TTL = ("Consolas", 11, "bold")

def make_row(parent, label: str, row: int):
    lbl = tk.Label(parent, text=label, font=FONT_LBL, fg=FG_LABEL, bg=BG, anchor="w")
    lbl.grid(row=row, column=0, sticky="w", padx=(12, 6), pady=3)
    var = tk.StringVar(value="...")
    val = tk.Label(parent, textvariable=var, font=FONT_VAL, fg=FG_VALUE, bg=BG, anchor="e", width=18)
    val.grid(row=row, column=1, sticky="e", padx=(6, 12), pady=3)
    return var


def make_section_title(parent, text: str, row: int):
    lbl = tk.Label(parent, text=text, font=FONT_TTL, fg=FG_TITLE, bg=BG, anchor="w")
    lbl.grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 2))


def build_ui(root: tk.Tk):
    root.title("HW Monitor")
    root.configure(bg=BG)
    root.resizable(False, False)

    f = tk.Frame(root, bg=BG)
    f.pack(fill="both", expand=True)

    row = 0
    make_section_title(f, "── CPU ──────────────────", row); row += 1
    v_cpu_temp  = make_row(f, "Temperature",  row); row += 1
    v_cpu_usage = make_row(f, "Usage",        row); row += 1

    make_section_title(f, "── GPU (RTX 5070) ───────", row); row += 1
    v_gpu_temp  = make_row(f, "Temperature",  row); row += 1
    v_gpu_usage = make_row(f, "Usage",        row); row += 1
    v_vram_used = make_row(f, "VRAM Used",    row); row += 1
    v_vram_tot  = make_row(f, "VRAM Total",   row); row += 1

    make_section_title(f, "── RAM ──────────────────", row); row += 1
    v_ram_used  = make_row(f, "Used / Total", row); row += 1
    v_ram_pct   = make_row(f, "Usage",        row); row += 1

    tk.Label(f, text="Refreshing every 1 s", font=("Consolas", 8),
             fg="#555555", bg=BG).grid(row=row, column=0, columnspan=2, pady=(6, 8))

    return {
        "cpu_temp":  v_cpu_temp,
        "cpu_usage": v_cpu_usage,
        "gpu_temp":  v_gpu_temp,
        "gpu_usage": v_gpu_usage,
        "vram_used": v_vram_used,
        "vram_total":v_vram_tot,
        "ram_used":  v_ram_used,
        "ram_pct":   v_ram_pct,
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    psutil.cpu_percent(interval=None)
    root = tk.Tk()
    ui_vars = build_ui(root)
    root.after(100, refresh, root, ui_vars)
    root.mainloop()