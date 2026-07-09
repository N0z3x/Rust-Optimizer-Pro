#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rust FPS Optimizer для Windows 11/10.

Это НЕ чит, НЕ инжектор и НЕ обход EAC. Утилита делает только обычные
системные настройки Windows, бэкапы cfg/log-файлов и помогает подобрать
Steam launch options для Rust.

Сборка в exe:
    py -3 -m pip install pyinstaller
    py -3 -m PyInstaller --onefile --windowed --uac-admin --name RustFPSOptimizer RustFPSOptimizer.py
"""

from __future__ import annotations

import ctypes
import datetime as _dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except Exception:  # pragma: no cover
    tk = None  # type: ignore
    ttk = None  # type: ignore
    messagebox = None  # type: ignore
    scrolledtext = None  # type: ignore
    filedialog = None  # type: ignore

try:
    import winreg  # type: ignore
except Exception:  # not Windows
    winreg = None  # type: ignore

APP_NAME = "Rust FPS Optimizer"
APP_VERSION = "1.0.0"
RUST_APP_ID = "252490"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Known Windows power plans
HIGH_PERFORMANCE_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULTIMATE_PERFORMANCE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"


# ---------------------------------------------------------------------------
# Paths / state
# ---------------------------------------------------------------------------

def is_windows() -> bool:
    return os.name == "nt" and winreg is not None


def app_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / "RustFPSOptimizer"
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_root() -> Path:
    p = app_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path() -> Path:
    return app_dir() / "state.json"


def log_path() -> Path:
    return app_dir() / "optimizer.log"


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def sanitize_filename(text: str) -> str:
    text = re.sub(r"^[A-Za-z]:", lambda m: m.group(0).replace(":", ""), text)
    text = re.sub(r"[^A-Za-z0-9а-яА-ЯёЁ._-]+", "_", text)
    return text.strip("._-")[:160] or "path"


def load_state() -> Dict[str, Any]:
    p = state_path()
    if not p.exists():
        return {"version": APP_VERSION, "profiles": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if "profiles" not in data or not isinstance(data["profiles"], list):
            data["profiles"] = []
        return data
    except Exception:
        return {"version": APP_VERSION, "profiles": []}


def save_state(state: Dict[str, Any]) -> None:
    state["version"] = APP_VERSION
    p = state_path()
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_admin() -> None:
    if not is_windows():
        return
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
            params = ""
        else:
            exe = sys.executable
            params = '"{}"'.format(str(Path(__file__).resolve()))
        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    except Exception as exc:
        if messagebox:
            messagebox.showerror(APP_NAME, f"Не получилось перезапустить от администратора:\n{exc}")


def run_cmd(args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    try:
        cp = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            encoding="utf-8",
            errors="replace",
        )
        return cp.returncode, cp.stdout.strip(), cp.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    except Exception as exc:
        return 1, "", str(exc)


def run_powershell(script: str, timeout: int = 90) -> Tuple[int, str, str]:
    return run_cmd(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        timeout=timeout,
    )


def get_total_ram_gb() -> Optional[float]:
    if is_windows():
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

REG_KIND_TO_NAME: Dict[int, str] = {}
REG_NAME_TO_KIND: Dict[str, int] = {}
ROOTS: Dict[str, Any] = {}

if winreg is not None:
    REG_KIND_TO_NAME = {
        winreg.REG_DWORD: "REG_DWORD",
        winreg.REG_SZ: "REG_SZ",
        winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
        winreg.REG_QWORD: "REG_QWORD",
        winreg.REG_BINARY: "REG_BINARY",
    }
    REG_NAME_TO_KIND = {v: k for k, v in REG_KIND_TO_NAME.items()}
    ROOTS = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }


def _reg_access(root_name: str, access: int) -> int:
    if not is_windows():
        return access
    # For HKLM prefer native 64-bit view on 64-bit Windows.
    if root_name == "HKLM" and hasattr(winreg, "KEY_WOW64_64KEY"):
        return access | winreg.KEY_WOW64_64KEY
    return access


def _jsonable_reg_value(value: Any, kind: int) -> Any:
    if kind == getattr(winreg, "REG_BINARY", -1) and isinstance(value, (bytes, bytearray)):
        return {"__binary__": list(value)}
    return value


def _unjson_reg_value(value: Any, kind_name: str) -> Any:
    if kind_name == "REG_BINARY" and isinstance(value, dict) and "__binary__" in value:
        return bytes(value["__binary__"])
    return value


def query_reg_value(root_name: str, path: str, name: str) -> Dict[str, Any]:
    if not is_windows():
        return {"exists": False}
    root = ROOTS[root_name]
    try:
        with winreg.OpenKey(root, path, 0, _reg_access(root_name, winreg.KEY_READ)) as key:
            value, kind = winreg.QueryValueEx(key, name)
        return {
            "exists": True,
            "value": _jsonable_reg_value(value, kind),
            "kind": REG_KIND_TO_NAME.get(kind, str(kind)),
        }
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        return {"exists": False}


def set_reg_value(
    root_name: str,
    path: str,
    name: str,
    value: Any,
    kind_name: str,
    changes: List[Dict[str, Any]],
    log,
) -> None:
    if not is_windows():
        log(f"[skip] Registry недоступен: {root_name}\\{path} / {name}")
        return
    root = ROOTS[root_name]
    kind = REG_NAME_TO_KIND[kind_name]
    old = query_reg_value(root_name, path, name)
    try:
        write_access = winreg.KEY_SET_VALUE | getattr(winreg, "KEY_CREATE_SUB_KEY", 0)
        with winreg.CreateKeyEx(root, path, 0, _reg_access(root_name, write_access)) as key:
            winreg.SetValueEx(key, name, 0, kind, value)
        changes.append(
            {
                "type": "registry",
                "root": root_name,
                "path": path,
                "name": name,
                "old": old,
            }
        )
        log(f"[ok] Registry: {root_name}\\{path} -> {name} = {value}")
    except PermissionError:
        log(f"[skip] Нет прав: {root_name}\\{path} -> {name}. Запусти от администратора.")
    except Exception as exc:
        log(f"[err] Registry {root_name}\\{path} -> {name}: {exc}")


def restore_reg_value(change: Dict[str, Any], log) -> None:
    if not is_windows():
        return
    root_name = change["root"]
    path = change["path"]
    name = change["name"]
    old = change.get("old", {"exists": False})
    root = ROOTS[root_name]
    try:
        write_access = winreg.KEY_SET_VALUE | getattr(winreg, "KEY_CREATE_SUB_KEY", 0)
        with winreg.CreateKeyEx(root, path, 0, _reg_access(root_name, write_access)) as key:
            if old.get("exists"):
                kind_name = old.get("kind", "REG_SZ")
                kind = REG_NAME_TO_KIND.get(kind_name, winreg.REG_SZ)
                value = _unjson_reg_value(old.get("value"), kind_name)
                winreg.SetValueEx(key, name, 0, kind, value)
                log(f"[undo] Registry restored: {root_name}\\{path} -> {name}")
            else:
                try:
                    winreg.DeleteValue(key, name)
                    log(f"[undo] Registry deleted: {root_name}\\{path} -> {name}")
                except FileNotFoundError:
                    log(f"[undo] Registry already absent: {root_name}\\{path} -> {name}")
    except Exception as exc:
        log(f"[err] Undo registry {root_name}\\{path} -> {name}: {exc}")


# ---------------------------------------------------------------------------
# Steam / Rust detection
# ---------------------------------------------------------------------------

def reg_read_string(root_name: str, path: str, name: str) -> Optional[str]:
    if not is_windows():
        return None
    try:
        root = ROOTS[root_name]
        with winreg.OpenKey(root, path, 0, _reg_access(root_name, winreg.KEY_READ)) as key:
            value, _kind = winreg.QueryValueEx(key, name)
        if isinstance(value, str) and value.strip():
            return value
    except Exception:
        return None
    return None


def normalize_win_path(p: str) -> str:
    p = p.replace("/", "\\")
    p = p.replace("\\\\", "\\")
    return os.path.normpath(os.path.expandvars(p))


def discover_steam_roots() -> List[Path]:
    candidates: List[str] = []
    if is_windows():
        candidates += [
            reg_read_string("HKCU", r"Software\Valve\Steam", "SteamPath") or "",
            reg_read_string("HKCU", r"Software\Valve\Steam", "SteamExe") or "",
            reg_read_string("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath") or "",
            reg_read_string("HKLM", r"SOFTWARE\Valve\Steam", "InstallPath") or "",
        ]
    pf86 = os.environ.get("ProgramFiles(x86)")
    pf = os.environ.get("ProgramFiles")
    if pf86:
        candidates.append(str(Path(pf86) / "Steam"))
    if pf:
        candidates.append(str(Path(pf) / "Steam"))

    roots: List[Path] = []
    for c in candidates:
        if not c:
            continue
        if c.lower().endswith("steam.exe"):
            c = str(Path(c).parent)
        p = Path(normalize_win_path(c))
        if p.exists() and p not in roots:
            roots.append(p)
    return roots


def parse_libraryfolders(vdf_path: Path) -> List[Path]:
    libs: List[Path] = []
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return libs

    # New Steam format: "path"    "D:\\SteamLibrary"
    for m in re.finditer(r'"path"\s+"([^"]+)"', text, flags=re.IGNORECASE):
        raw = m.group(1).replace("\\\\", "\\")
        p = Path(normalize_win_path(raw))
        if p.exists() and p not in libs:
            libs.append(p)

    # Old Steam format: "1"    "D:\\SteamLibrary"
    for m in re.finditer(r'"\d+"\s+"([A-Za-z]:[^\"]+)"', text):
        raw = m.group(1).replace("\\\\", "\\")
        p = Path(normalize_win_path(raw))
        if p.exists() and p not in libs:
            libs.append(p)
    return libs


def discover_steam_libraries() -> List[Path]:
    libs: List[Path] = []
    for root in discover_steam_roots():
        if root not in libs:
            libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        for lib in parse_libraryfolders(vdf):
            if lib not in libs:
                libs.append(lib)
    return libs


def discover_rust_exes() -> List[Path]:
    exes: List[Path] = []
    for lib in discover_steam_libraries():
        p = lib / "steamapps" / "common" / "Rust" / "RustClient.exe"
        if p.exists() and p not in exes:
            exes.append(p)
    return exes


def local_low_rust_dir() -> Optional[Path]:
    local = os.environ.get("LOCALAPPDATA")
    user = os.environ.get("USERPROFILE")
    candidates: List[Path] = []
    if local:
        candidates.append(Path(local).parent / "LocalLow" / "Facepunch Studios LTD" / "Rust")
    if user:
        candidates.append(Path(user) / "AppData" / "LocalLow" / "Facepunch Studios LTD" / "Rust")
    for p in candidates:
        if p.exists():
            return p
    return candidates[0] if candidates else None


def discover_cfg_dirs() -> List[Path]:
    dirs: List[Path] = []
    ll = local_low_rust_dir()
    if ll:
        d = ll / "cfg"
        if d.exists() and d not in dirs:
            dirs.append(d)
    for exe in discover_rust_exes():
        install = exe.parent
        for d in [install / "cfg", install / "client" / "cfg"]:
            if d.exists() and d not in dirs:
                dirs.append(d)
    return dirs


def discover_shader_cache_dirs() -> List[Path]:
    dirs: List[Path] = []
    for lib in discover_steam_libraries():
        p = lib / "steamapps" / "shadercache" / RUST_APP_ID
        if p.exists() and p not in dirs:
            dirs.append(p)
    return dirs


def discover_log_files() -> List[Path]:
    files: List[Path] = []
    ll = local_low_rust_dir()
    if ll:
        for name in ["Player.log", "Player-prev.log", "output_log.txt", "Crashes"]:
            p = ll / name
            if p.exists() and p not in files:
                files.append(p)
    for exe in discover_rust_exes():
        for p in exe.parent.glob("*.log"):
            if p.exists() and p not in files:
                files.append(p)
    return files


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def make_profile_backup_dir(profile: str) -> Path:
    p = backup_root() / f"{now_stamp()}_{profile}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def copy_file_to_backup(src: Path, backup_dir: Path, category: str) -> Optional[Path]:
    try:
        rel_label = sanitize_filename(str(src))
        dst_dir = backup_dir / category
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / rel_label
        if src.is_file():
            shutil.copy2(src, dst)
            return dst
    except Exception:
        return None
    return None


def backup_configs(backup_dir: Path, log) -> int:
    cfg_dirs = discover_cfg_dirs()
    count = 0
    if not cfg_dirs:
        log("[info] cfg-папки Rust не найдены. Это нормально, если Rust ещё не запускался.")
        return 0
    for d in cfg_dirs:
        for src in d.rglob("*"):
            if src.is_file() and src.suffix.lower() in {".cfg", ".json", ".txt", ".xml"}:
                try:
                    rel = src.relative_to(d)
                except Exception:
                    rel = Path(sanitize_filename(str(src)))
                dst = backup_dir / "cfg" / sanitize_filename(str(d)) / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                count += 1
    log(f"[ok] Backup cfg: {count} файл(ов) -> {backup_dir / 'cfg'}")
    return count


def clear_logs(backup_dir: Path, log) -> int:
    removed = 0
    for p in discover_log_files():
        try:
            if p.is_file():
                copy_file_to_backup(p, backup_dir, "logs")
                p.unlink(missing_ok=True)
                log(f"[ok] Удалён log: {p}")
                removed += 1
            elif p.is_dir() and p.name.lower() == "crashes":
                # Backing up full crash dumps can be huge; remove only tiny text logs inside.
                for f in p.rglob("*.log"):
                    copy_file_to_backup(f, backup_dir, "logs")
                    f.unlink(missing_ok=True)
                    removed += 1
        except Exception as exc:
            log(f"[warn] Не смог удалить log {p}: {exc}")
    if removed == 0:
        log("[info] Логи для очистки не найдены.")
    return removed


def clear_shader_cache(log) -> int:
    removed = 0
    for d in discover_shader_cache_dirs():
        try:
            shutil.rmtree(d)
            log(f"[ok] Удалён shader cache Rust: {d}")
            removed += 1
        except Exception as exc:
            log(f"[warn] Не смог удалить shader cache {d}: {exc}")
    if removed == 0:
        log("[info] Shader cache Rust не найден.")
    return removed


# ---------------------------------------------------------------------------
# Power plan
# ---------------------------------------------------------------------------

def get_active_power_scheme() -> Optional[str]:
    if not is_windows():
        return None
    code, out, err = run_cmd(["powercfg", "/getactivescheme"])
    text = out + "\n" + err
    m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", text)
    return m.group(1) if m else None


def set_power_scheme(target: str, changes: List[Dict[str, Any]], log, label: str) -> None:
    if not is_windows():
        return
    old = get_active_power_scheme()
    code, out, err = run_cmd(["powercfg", "/setactive", target])
    if code == 0:
        if old:
            changes.append({"type": "power_scheme", "old_active": old})
        log(f"[ok] Power plan: {label}")
    else:
        log(f"[warn] Power plan не применился ({label}): {err or out}")


def ensure_ultimate_performance(log) -> str:
    # If GUID already works, powercfg /setactive can use it. If not, duplicate it.
    code, out, err = run_cmd(["powercfg", "/duplicatescheme", ULTIMATE_PERFORMANCE_GUID])
    text = out + "\n" + err
    m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", text)
    if code == 0 and m:
        guid = m.group(1)
        log(f"[ok] Ultimate Performance plan создан/найден: {guid}")
        return guid
    log("[info] Использую стандартный GUID Ultimate Performance.")
    return ULTIMATE_PERFORMANCE_GUID


def restore_power_scheme(change: Dict[str, Any], log) -> None:
    old = change.get("old_active")
    if not old:
        return
    code, out, err = run_cmd(["powercfg", "/setactive", old])
    if code == 0:
        log(f"[undo] Power plan восстановлен: {old}")
    else:
        log(f"[warn] Не смог восстановить power plan {old}: {err or out}")


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def apply_safe_tweaks(changes: List[Dict[str, Any]], log) -> None:
    # Enable Game Mode.
    set_reg_value("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, "REG_DWORD", changes, log)

    # Disable background game capture / DVR. This can reduce stutters and is reversible.
    set_reg_value("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "HistoricalCaptureEnabled", 0, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, "REG_DWORD", changes, log)

    # Prefer discrete/high-performance GPU for Rust in Windows Graphics settings.
    for exe in discover_rust_exes():
        set_reg_value(
            "HKCU",
            r"Software\Microsoft\DirectX\UserGpuPreferences",
            str(exe),
            "GpuPreference=2;",
            "REG_SZ",
            changes,
            log,
        )


def apply_balanced_tweaks(changes: List[Dict[str, Any]], log) -> None:
    apply_safe_tweaks(changes, log)

    # High performance power profile.
    set_power_scheme(HIGH_PERFORMANCE_GUID, changes, log, "High Performance")

    # Disable fullscreen optimizations for RustClient.exe only.
    for exe in discover_rust_exes():
        set_reg_value(
            "HKCU",
            r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
            str(exe),
            "~ DISABLEDXMAXIMIZEDWINDOWEDMODE",
            "REG_SZ",
            changes,
            log,
        )


def apply_aggressive_tweaks(changes: List[Dict[str, Any]], log) -> None:
    apply_balanced_tweaks(changes, log)

    # Ultimate Performance power plan.
    target = ensure_ultimate_performance(log)
    set_power_scheme(target, changes, log, "Ultimate Performance")

    # Extra GameDVR / FSE related flags. Reversible.
    set_reg_value("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", 2, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", 1, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", 1, "REG_DWORD", changes, log)
    set_reg_value("HKCU", r"System\GameConfigStore", "GameDVR_EFSEFeatureFlags", 0, "REG_DWORD", changes, log)

    # Tiny desktop overhead reduction.
    set_reg_value(
        "HKCU",
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        "EnableTransparency",
        0,
        "REG_DWORD",
        changes,
        log,
    )

    # Hardware-accelerated GPU scheduling. Needs admin + reboot, not always present.
    if is_admin():
        set_reg_value(
            "HKLM",
            r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
            "HwSchMode",
            2,
            "REG_DWORD",
            changes,
            log,
        )
        log("[info] HAGS может потребовать перезагрузку Windows.")
    else:
        log("[skip] HAGS не трогаю: нужны права администратора.")


PROFILE_DESCRIPTIONS = {
    "safe": "Safe: Game Mode, отключение Xbox DVR/записи, GPU preference, backup cfg, очистка логов.",
    "balanced": "Balanced: всё из Safe + High Performance power plan + disable fullscreen optimizations для Rust.",
    "aggressive": "Aggressive: всё из Balanced + Ultimate Performance, доп. GameDVR/FSE флаги, HAGS, transparency off.",
}


def suggested_gc_buffer(profile: str, ram_gb: Optional[float]) -> int:
    # Conservative values to reduce GC micro-stutters without wasting too much RAM.
    if ram_gb is None:
        ram_gb = 16
    if profile == "safe":
        return 1024 if ram_gb < 16 else 2048
    if profile == "balanced":
        return 2048 if ram_gb < 32 else 4096
    return 2048 if ram_gb < 32 else 4096


def launch_options(profile: str, ram_gb: Optional[float], exclusive: bool = False) -> str:
    gc = suggested_gc_buffer(profile, ram_gb)
    opts = ["-nolog", "-gc.buffer", str(gc)]
    if exclusive:
        opts += ["-window-mode", "exclusive"]
    return " ".join(opts)


# ---------------------------------------------------------------------------
# Process priority / Steam launch
# ---------------------------------------------------------------------------

def set_rust_priority_high(log, quiet_not_running: bool = False) -> bool:
    if not is_windows():
        log("[skip] Высокий приоритет работает только на Windows.")
        return False
    script = r"""
$p = Get-Process RustClient -ErrorAction SilentlyContinue
if ($null -eq $p) { Write-Output 'NOT_RUNNING'; exit 2 }
$p | ForEach-Object { $_.PriorityClass = 'High' }
Write-Output ('OK ' + $p.Count)
"""
    code, out, err = run_powershell(script)
    if "OK" in out:
        log(f"[ok] RustClient.exe -> PriorityClass High ({out})")
        return True
    if "NOT_RUNNING" in out:
        if not quiet_not_running:
            log("[info] RustClient.exe сейчас не запущен.")
        return False
    log(f"[warn] Не смог выставить High priority: {err or out}")
    return False


def launch_rust_via_steam(log) -> None:
    if not is_windows():
        log("[skip] steam:// запуск работает в Windows-приложении.")
        return
    try:
        os.startfile(f"steam://rungameid/{RUST_APP_ID}")  # type: ignore[attr-defined]
        log("[ok] Отправил Steam команду запуска Rust.")
    except Exception as exc:
        log(f"[warn] Не смог запустить Rust через Steam: {exc}")


def monitor_priority(log, seconds: int = 240) -> None:
    log(f"[info] Мониторю RustClient.exe {seconds} сек. Как появится — выставлю High priority.")
    deadline = time.time() + seconds
    already = False
    while time.time() < deadline:
        ok = set_rust_priority_high(log, quiet_not_running=True)
        if ok:
            already = True
            # Keep watching for a bit because EAC/Rust may restart the process during launch.
            time.sleep(10)
        else:
            time.sleep(3)
    if already:
        log("[ok] Мониторинг приоритета завершён.")
    else:
        log("[info] RustClient.exe так и не появился за время мониторинга.")

# ---------------------------------------------------------------------------
# Game Session helpers
# ---------------------------------------------------------------------------

BACKGROUND_PROCESS_GROUPS: Dict[str, List[str]] = {
    "browsers": ["chrome", "msedge", "firefox", "brave", "opera", "opera_gx", "vivaldi", "browser"],
    "recording": ["obs64", "obs32", "Streamlabs Desktop", "XSplit.Core", "XSplit Broadcaster", "Action", "Bandicam"],
    "launchers": ["EpicGamesLauncher", "Battle.net", "RiotClientServices", "UbisoftConnect", "GalaxyClient", "EADesktop"],
    "chat": ["Discord", "Telegram", "Skype"],
}


def _ps_string_array(values: List[str]) -> str:
    safe: List[str] = []
    for value in values:
        name = re.sub(r"[^A-Za-z0-9_. \-]", "", str(value)).strip()
        if name:
            safe.append("'" + name.replace("'", "''") + "'")
    return "@(" + ",".join(safe) + ")"


def is_process_running(process_name: str) -> bool:
    if not is_windows():
        return False
    name = re.sub(r"[^A-Za-z0-9_. \-]", "", process_name).strip()
    if not name:
        return False
    script = f"$p = Get-Process -Name '{name.replace("'", "''")}' -ErrorAction SilentlyContinue; if ($p) {{ 'RUNNING' }} else {{ 'NOT_RUNNING' }}"
    code, out, _err = run_powershell(script, timeout=12)
    return code == 0 and "RUNNING" in out


def rust_process_running() -> bool:
    return is_process_running("RustClient")


def close_processes_by_names(names: List[str], log, force: bool = False) -> int:
    """Politely close selected background apps. Optional force is explicit."""
    if not is_windows():
        log("[skip] Закрытие фоновых приложений доступно только на Windows.")
        return 0
    unique = []
    for n in names:
        clean = re.sub(r"[^A-Za-z0-9_. \-]", "", str(n)).strip()
        if clean and clean not in unique:
            unique.append(clean)
    if not unique:
        return 0
    arr = _ps_string_array(unique)
    force_text = "$true" if force else "$false"
    script = f'''
$names = {arr}
$force = {force_text}
$procs = @()
foreach ($n in $names) {{ $procs += Get-Process -Name $n -ErrorAction SilentlyContinue }}
$procs = @($procs | Sort-Object Id -Unique)
if ($procs.Count -eq 0) {{ Write-Output 'NONE'; exit 0 }}
foreach ($p in $procs) {{
  try {{
    if ($p.MainWindowHandle -ne 0) {{
      $ok = $p.CloseMainWindow()
      Write-Output ("CLOSE " + $p.ProcessName + " PID=" + $p.Id + " OK=" + $ok)
    }} else {{
      Write-Output ("SKIP_NO_WINDOW " + $p.ProcessName + " PID=" + $p.Id)
    }}
  }} catch {{ Write-Output ("ERR_CLOSE " + $p.ProcessName + " PID=" + $p.Id + " " + $_.Exception.Message) }}
}}
Start-Sleep -Milliseconds 1200
if ($force) {{
  foreach ($p in $procs) {{
    try {{
      $alive = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
      if ($alive) {{ Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; Write-Output ("FORCE_STOP " + $p.ProcessName + " PID=" + $p.Id) }}
    }} catch {{ Write-Output ("ERR_FORCE " + $p.ProcessName + " PID=" + $p.Id + " " + $_.Exception.Message) }}
  }}
}}
'''
    code, out, err = run_powershell(script, timeout=30)
    if code != 0:
        log(f"[warn] Не смог закрыть фоновые приложения: {err or out}")
        return 0
    count = 0
    for line in (out or "").splitlines():
        line = line.strip()
        if not line or line == "NONE":
            continue
        if line.startswith(("CLOSE", "FORCE_STOP")):
            count += 1
            log(f"[bg] {line}")
        else:
            log(f"[bg] {line}")
    if count == 0:
        log("[bg] Выбранные фоновые приложения не найдены или не имели окон для закрытия.")
    return count

# ---------------------------------------------------------------------------
# Cleaner / Repair helpers
# ---------------------------------------------------------------------------


def path_size_and_count(path: Path) -> Tuple[int, int]:
    """Return total bytes and file count for a file/dir. Best-effort."""
    try:
        if path.is_file():
            return path.stat().st_size, 1
        if not path.exists():
            return 0, 0
        total = 0
        count = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
                    count += 1
            except Exception:
                continue
        return total, count
    except Exception:
        return 0, 0


def _known_local_appdata_paths(*parts: str) -> Optional[Path]:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return Path(base).joinpath(*parts)


def discover_dx_shader_cache_dirs() -> List[Path]:
    """Common per-user DirectX/GPU shader cache dirs. Optional cleanup."""
    candidates: List[Optional[Path]] = [
        _known_local_appdata_paths("D3DSCache"),
        _known_local_appdata_paths("NVIDIA", "DXCache"),
        _known_local_appdata_paths("NVIDIA", "GLCache"),
        _known_local_appdata_paths("AMD", "DxCache"),
        _known_local_appdata_paths("AMD", "VkCache"),
    ]
    out: List[Path] = []
    for p in candidates:
        if p and p.exists() and p not in out:
            out.append(p)
    return out


def discover_rust_crash_dirs() -> List[Path]:
    dirs: List[Path] = []
    ll = local_low_rust_dir()
    if ll:
        for name in ["Crashes", "crashes"]:
            p = ll / name
            if p.exists() and p not in dirs:
                dirs.append(p)
    return dirs


def optimizer_monitor_report_dir() -> Path:
    p = app_dir() / "monitor_reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def old_optimizer_backup_dirs(days: int = 30) -> List[Path]:
    root = backup_root()
    cutoff = time.time() - days * 86400
    dirs: List[Path] = []
    try:
        for p in root.iterdir():
            try:
                if p.is_dir() and p.stat().st_mtime < cutoff:
                    dirs.append(p)
            except Exception:
                continue
    except Exception:
        pass
    return dirs


def _target_summary(target_id: str, title: str, description: str, paths: List[Path], risk: str = "safe") -> Dict[str, Any]:
    total = 0
    count = 0
    existing: List[Path] = []
    for p in paths:
        if not p or not p.exists():
            continue
        size, files = path_size_and_count(p)
        total += size
        count += files
        existing.append(p)
    return {
        "id": target_id,
        "title": title,
        "description": description,
        "risk": risk,
        "paths": [str(p) for p in existing],
        "size_bytes": total,
        "file_count": count,
        "exists": bool(existing),
    }


def scan_cleaner_targets() -> List[Dict[str, Any]]:
    log_files = [p for p in discover_log_files() if p.exists()]
    shader_dirs = discover_shader_cache_dirs()
    crash_dirs = discover_rust_crash_dirs()
    dx_dirs = discover_dx_shader_cache_dirs()
    report_dir = optimizer_monitor_report_dir()
    old_backups = old_optimizer_backup_dirs(days=30)

    targets = [
        _target_summary(
            "rust_logs",
            "Rust logs",
            "Player.log/output logs. Обычно можно чистить безопасно; перед удалением текстовые логи бэкапятся.",
            log_files,
            "safe",
        ),
        _target_summary(
            "rust_shader_cache",
            "Steam shader cache Rust",
            "Кэш шейдеров Steam только для Rust appid 252490. Первый запуск после очистки может временно фризить сильнее.",
            shader_dirs,
            "medium",
        ),
        _target_summary(
            "rust_crash_dumps",
            "Rust crash dumps",
            "Папка Crashes из LocalLow Facepunch. Может занимать много места, для FPS обычно не нужна.",
            crash_dirs,
            "safe",
        ),
        _target_summary(
            "dx_shader_cache",
            "DirectX/GPU shader cache",
            "Пользовательские D3DS/NVIDIA/AMD shader caches. Может помочь при битом кэше, но первая прогрузка игр может быть дольше.",
            dx_dirs,
            "medium",
        ),
        _target_summary(
            "monitor_reports",
            "Old Stutter Monitor reports",
            "Текстовые отчёты/CSV мониторинга, которые создал оптимизатор.",
            [report_dir],
            "safe",
        ),
        _target_summary(
            "old_backups",
            "Optimizer backups older than 30 days",
            "Старые бэкапы cfg/log/state, созданные этим оптимизатором больше 30 дней назад.",
            old_backups,
            "medium",
        ),
    ]
    return targets


def _is_safe_delete_root(path: Path) -> bool:
    try:
        rp = path.resolve()
        allowed: List[Path] = []
        for base in [os.environ.get("LOCALAPPDATA"), os.environ.get("TEMP"), os.environ.get("TMP")]:
            if base:
                allowed.append(Path(base).resolve())
        allowed.append(app_dir().resolve())
        ll = local_low_rust_dir()
        if ll:
            allowed.append(ll.resolve())
        for base in allowed:
            try:
                if rp == base or base in rp.parents:
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def delete_path_contents(path: Path, log, remove_root: bool = False) -> Tuple[int, int]:
    """Delete a known cache/report folder safely. Returns (files, bytes)."""
    if not path.exists():
        return 0, 0
    if not _is_safe_delete_root(path):
        log(f"[cleaner][skip] Небезопасный путь, не удаляю: {path}")
        return 0, 0
    size, files = path_size_and_count(path)
    try:
        if path.is_file():
            path.unlink(missing_ok=True)
            return 1, size
        if remove_root:
            shutil.rmtree(path, ignore_errors=True)
            return files, size
        for child in path.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except Exception as exc:
                log(f"[cleaner][warn] Не смог удалить {child}: {exc}")
        return files, size
    except Exception as exc:
        log(f"[cleaner][warn] Не смог очистить {path}: {exc}")
        return 0, 0


def clean_selected_targets(target_ids: List[str], log) -> Dict[str, Any]:
    """Clean selected targets. Only deletes known cache/log/report paths."""
    result = {"files": 0, "bytes": 0, "targets": []}
    if not target_ids:
        return result
    backup_dir = make_profile_backup_dir("cleaner")
    ids = set(target_ids)

    if "rust_logs" in ids:
        before = sum(path_size_and_count(p)[0] for p in discover_log_files() if p.exists())
        files = clear_logs(backup_dir, log)
        result["files"] += files
        result["bytes"] += before
        result["targets"].append("rust_logs")

    if "rust_shader_cache" in ids:
        dirs = discover_shader_cache_dirs()
        before_files = 0
        before_size = 0
        for d in dirs:
            s, c = path_size_and_count(d)
            before_size += s
            before_files += c
        clear_shader_cache(log)
        result["files"] += before_files
        result["bytes"] += before_size
        result["targets"].append("rust_shader_cache")

    if "rust_crash_dumps" in ids:
        for d in discover_rust_crash_dirs():
            files, size = delete_path_contents(d, log, remove_root=True)
            log(f"[cleaner] Rust crash dumps removed: {d} ({files} files, {fmt_bytes(size)})")
            result["files"] += files
            result["bytes"] += size
        result["targets"].append("rust_crash_dumps")

    if "dx_shader_cache" in ids:
        for d in discover_dx_shader_cache_dirs():
            files, size = delete_path_contents(d, log, remove_root=False)
            log(f"[cleaner] Shader cache cleaned: {d} ({files} files, {fmt_bytes(size)})")
            result["files"] += files
            result["bytes"] += size
        result["targets"].append("dx_shader_cache")

    if "monitor_reports" in ids:
        d = optimizer_monitor_report_dir()
        files, size = delete_path_contents(d, log, remove_root=False)
        log(f"[cleaner] Monitor reports cleaned: {d} ({files} files, {fmt_bytes(size)})")
        result["files"] += files
        result["bytes"] += size
        result["targets"].append("monitor_reports")

    if "old_backups" in ids:
        for d in old_optimizer_backup_dirs(days=30):
            files, size = delete_path_contents(d, log, remove_root=True)
            log(f"[cleaner] Old backup removed: {d} ({files} files, {fmt_bytes(size)})")
            result["files"] += files
            result["bytes"] += size
        result["targets"].append("old_backups")

    return result


def open_steam_validate_rust(log) -> None:
    if not is_windows():
        log("[repair][skip] steam://validate работает в Windows.")
        return
    try:
        os.startfile(f"steam://validate/{RUST_APP_ID}")  # type: ignore[attr-defined]
        log("[repair] Открыл Steam Validate Files для Rust.")
    except Exception as exc:
        log(f"[repair][warn] Не смог открыть Steam validate: {exc}")

# ---------------------------------------------------------------------------
# Rust Config Manager helpers
# ---------------------------------------------------------------------------


def config_backups_root() -> Path:
    p = app_dir() / "config_backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def discover_config_files() -> List[Path]:
    files: List[Path] = []
    for d in discover_cfg_dirs():
        try:
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in {".cfg", ".json", ".txt", ".xml"}:
                    if p not in files:
                        files.append(p)
        except Exception:
            continue
    return files


def config_file_summary() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in discover_config_files():
        try:
            stat = p.stat()
            out.append({
                "path": str(p),
                "name": p.name,
                "size_bytes": stat.st_size,
                "modified": _dt.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            })
        except Exception:
            out.append({"path": str(p), "name": p.name, "size_bytes": 0, "modified": "—"})
    return out


def create_config_snapshot(log) -> Optional[Path]:
    cfg_dirs = discover_cfg_dirs()
    if not cfg_dirs:
        log("[cfg] cfg-папки Rust не найдены. Запусти Rust хотя бы один раз или выбери RustClient.exe вручную.")
        return None
    snap = config_backups_root() / f"cfg_snapshot_{now_stamp()}"
    snap.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "version": APP_VERSION,
        "cfg_dirs": [],
        "files": [],
    }
    count = 0
    for idx, cfg_dir in enumerate(cfg_dirs, 1):
        sub = f"cfgdir_{idx}_{sanitize_filename(str(cfg_dir))}"
        manifest["cfg_dirs"].append({"original": str(cfg_dir), "backup_subdir": sub})
        for src in cfg_dir.rglob("*"):
            if not src.is_file() or src.suffix.lower() not in {".cfg", ".json", ".txt", ".xml"}:
                continue
            try:
                rel = src.relative_to(cfg_dir)
            except Exception:
                rel = Path(sanitize_filename(str(src)))
            dst = snap / sub / rel
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                manifest["files"].append({
                    "original": str(src),
                    "backup": str(Path(sub) / rel),
                    "size_bytes": src.stat().st_size,
                })
                count += 1
            except Exception as exc:
                log(f"[cfg][warn] Не смог backup {src}: {exc}")
    (snap / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[cfg] Snapshot создан: {snap} ({count} files)")
    return snap


def list_config_snapshots() -> List[Dict[str, Any]]:
    root = config_backups_root()
    items: List[Dict[str, Any]] = []
    try:
        for p in root.iterdir():
            if not p.is_dir():
                continue
            manifest_path = p / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
            size, files = path_size_and_count(p)
            items.append({
                "path": str(p),
                "name": p.name,
                "timestamp": manifest.get("timestamp") or _dt.datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
                "file_count": len(manifest.get("files", [])) or files,
                "size_bytes": size,
            })
    except Exception:
        pass
    items.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
    return items


def restore_config_snapshot(snapshot_dir: Path, log) -> int:
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        log(f"[cfg][err] manifest.json не найден: {snapshot_dir}")
        return 0
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"[cfg][err] Не смог прочитать manifest: {exc}")
        return 0
    restored = 0
    for item in manifest.get("files", []):
        try:
            src = snapshot_dir / item.get("backup", "")
            dst = Path(item.get("original", ""))
            if not src.exists() or not str(dst):
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored += 1
        except Exception as exc:
            log(f"[cfg][warn] Не смог восстановить {item}: {exc}")
    log(f"[cfg] Snapshot восстановлен: {snapshot_dir} ({restored} files)")
    return restored


def export_config_snapshot_zip(snapshot_dir: Path, out_zip: Path, log) -> Optional[Path]:
    if not snapshot_dir.exists():
        log(f"[cfg][err] Snapshot не найден: {snapshot_dir}")
        return None
    try:
        if out_zip.suffix.lower() != ".zip":
            out_zip = out_zip.with_suffix(".zip")
        base = str(out_zip.with_suffix(""))
        made = shutil.make_archive(base, "zip", root_dir=str(snapshot_dir))
        log(f"[cfg] Snapshot exported: {made}")
        return Path(made)
    except Exception as exc:
        log(f"[cfg][err] Не смог export zip: {exc}")
        return None


def write_recommended_settings_note(text: str, log) -> List[Path]:
    """Write a safe human-readable recommendation file. Does not alter game cfg commands."""
    outputs: List[Path] = []
    targets: List[Path] = []
    cfg_dirs = discover_cfg_dirs()
    if cfg_dirs:
        targets.append(cfg_dirs[0])
    targets.append(app_dir())
    for d in targets:
        try:
            d.mkdir(parents=True, exist_ok=True)
            out = d / "RustOptimizer_recommended_settings.txt"
            out.write_text(text, encoding="utf-8")
            outputs.append(out)
            log(f"[cfg] Recommended settings note written: {out}")
        except Exception as exc:
            log(f"[cfg][warn] Не смог записать note в {d}: {exc}")
    return outputs
# ---------------------------------------------------------------------------
# Health Check helpers
# ---------------------------------------------------------------------------


def _health_item(category: str, title: str, status: str, detail: str, fix: str = "") -> Dict[str, str]:
    status = status if status in {"ok", "warn", "bad", "info"} else "info"
    return {"category": category, "title": title, "status": status, "detail": detail, "fix": fix}


def _reg_dword_value(root: str, path: str, name: str) -> Optional[int]:
    try:
        q = query_reg_value(root, path, name)
        if not q.get("exists"):
            return None
        return int(q.get("value"))
    except Exception:
        return None


def storage_info_for_drive(drive_letter: str) -> Dict[str, Any]:
    """Best-effort physical disk info for a Windows drive letter."""
    if not is_windows() or not drive_letter:
        return {}
    letter = re.sub(r"[^A-Za-z]", "", drive_letter[:1]).upper()
    if not letter:
        return {}
    script = f'''
$ErrorActionPreference = 'SilentlyContinue'
$part = Get-Partition -DriveLetter '{letter}'
$disk = $part | Get-Disk
[ordered]@{{
  DriveLetter = '{letter}'
  FriendlyName = $disk.FriendlyName
  MediaType = [string]$disk.MediaType
  BusType = [string]$disk.BusType
  HealthStatus = [string]$disk.HealthStatus
  OperationalStatus = [string]($disk.OperationalStatus -join ',')
}} | ConvertTo-Json -Compress
'''
    data, _err = ps_json(script, timeout=20) if "ps_json" in globals() else (None, "")
    return data if isinstance(data, dict) else {}


def current_power_scheme_text() -> str:
    if not is_windows():
        return "—"
    code, out, err = run_cmd(["powercfg", "/getactivescheme"], timeout=15)
    return (out or err or "—").strip()


def running_background_processes() -> Dict[str, List[str]]:
    if not is_windows():
        return {}
    names: List[str] = []
    for group in BACKGROUND_PROCESS_GROUPS.values():
        names.extend(group)
    arr = _ps_string_array(names)
    script = f'''
$names = {arr}
$found = @()
foreach ($n in $names) {{
  $p = Get-Process -Name $n -ErrorAction SilentlyContinue
  foreach ($x in $p) {{ $found += [ordered]@{{Name=$x.ProcessName; Id=$x.Id}} }}
}}
$found | Sort-Object Name,Id -Unique | ConvertTo-Json -Depth 3 -Compress
'''
    data, _err = ps_json(script, timeout=20) if "ps_json" in globals() else (None, "")
    grouped: Dict[str, List[str]] = {k: [] for k in BACKGROUND_PROCESS_GROUPS}
    if not data:
        return grouped
    for item in as_list(data) if "as_list" in globals() else ([data] if isinstance(data, dict) else []):
        if not isinstance(item, dict):
            continue
        proc_name = clean_value(item.get("Name")) if "clean_value" in globals() else str(item.get("Name"))
        low = proc_name.lower()
        for group, group_names in BACKGROUND_PROCESS_GROUPS.items():
            if any(low == n.lower() or low.startswith(n.lower()) for n in group_names):
                if proc_name not in grouped[group]:
                    grouped[group].append(proc_name)
    return grouped


def health_check_scan() -> Dict[str, Any]:
    items: List[Dict[str, str]] = []

    # Basic environment.
    if is_windows():
        items.append(_health_item("System", "Windows", "ok", f"{platform.system()} {platform.release()}"))
    else:
        items.append(_health_item("System", "Windows", "bad", "Программа рассчитана на Windows 10/11."))

    items.append(
        _health_item(
            "System",
            "Admin rights",
            "ok" if is_admin() else "warn",
            "Запущено от администратора." if is_admin() else "Часть твиков не применится без прав администратора.",
            "Нажми Restart as admin / Run_Pro_Source_As_Admin.bat.",
        )
    )

    ram = get_total_ram_gb()
    if ram is None:
        items.append(_health_item("Hardware", "RAM", "info", "Не смог определить объём RAM."))
    elif ram < 15:
        items.append(_health_item("Hardware", "RAM", "bad", f"{ram} GB — для Rust мало, вероятны статтеры.", "Лучший апгрейд для Rust: 32 GB RAM."))
    elif ram < 24:
        items.append(_health_item("Hardware", "RAM", "warn", f"{ram} GB — играть можно, но большие серверы могут фризить.", "Закрывай браузер/стрим/запись; 32 GB заметно лучше."))
    else:
        items.append(_health_item("Hardware", "RAM", "ok", f"{ram} GB — нормально для Rust."))

    # Rust install / disk.
    exes = discover_rust_exes() if is_windows() else []
    if exes:
        exe = exes[0]
        items.append(_health_item("Rust", "Rust detected", "ok", str(exe)))
        try:
            usage = shutil.disk_usage(str(exe.anchor or exe.drive + "\\"))
            free = usage.free
            if free < 25 * 1024 ** 3:
                items.append(_health_item("Storage", "Rust drive free space", "bad", f"Свободно {fmt_bytes(free)} на диске с Rust.", "Освободи хотя бы 30-50 GB."))
            elif free < 50 * 1024 ** 3:
                items.append(_health_item("Storage", "Rust drive free space", "warn", f"Свободно {fmt_bytes(free)} на диске с Rust.", "Лучше держать 50+ GB свободно."))
            else:
                items.append(_health_item("Storage", "Rust drive free space", "ok", f"Свободно {fmt_bytes(free)} на диске с Rust."))
        except Exception:
            items.append(_health_item("Storage", "Rust drive free space", "info", "Не смог определить свободное место."))

        drive = exe.drive.rstrip(":") if exe.drive else ""
        disk_info = storage_info_for_drive(drive)
        media = clean_value(disk_info.get("MediaType")) if disk_info else "—"
        bus = clean_value(disk_info.get("BusType")) if disk_info else "—"
        friendly = clean_value(disk_info.get("FriendlyName")) if disk_info else "—"
        low = f"{media} {bus} {friendly}".lower()
        if any(x in low for x in ["ssd", "nvme"]):
            items.append(_health_item("Storage", "Rust storage type", "ok", f"{friendly} | {media} | {bus}"))
        elif "hdd" in low or "hard" in low:
            items.append(_health_item("Storage", "Rust storage type", "bad", f"Похоже Rust на HDD: {friendly} | {media} | {bus}", "Перенеси Rust на SSD/NVMe."))
        else:
            items.append(_health_item("Storage", "Rust storage type", "info", f"Не уверен: {friendly} | {media} | {bus}"))
    else:
        items.append(_health_item("Rust", "Rust detected", "warn", "RustClient.exe не найден автоматически.", "Выбери RustClient.exe вручную во вкладке Оптимизация."))

    # Power / Windows gaming settings.
    active_guid = get_active_power_scheme()
    scheme_text = current_power_scheme_text()
    if active_guid and active_guid.lower() in {HIGH_PERFORMANCE_GUID, ULTIMATE_PERFORMANCE_GUID}:
        items.append(_health_item("Windows", "Power plan", "ok", scheme_text))
    else:
        items.append(_health_item("Windows", "Power plan", "warn", scheme_text, "Профиль BALANCED/Game Session включит High Performance временно или постоянно."))

    gm1 = _reg_dword_value("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode")
    gm2 = _reg_dword_value("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled")
    if gm1 == 1 or gm2 == 1:
        items.append(_health_item("Windows", "Game Mode", "ok", "Game Mode включён/разрешён."))
    else:
        items.append(_health_item("Windows", "Game Mode", "warn", "Game Mode не включён или не найден.", "Safe Fix включит Game Mode."))

    dvr_values = [
        _reg_dword_value("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"),
        _reg_dword_value("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "HistoricalCaptureEnabled"),
        _reg_dword_value("HKCU", r"System\GameConfigStore", "GameDVR_Enabled"),
    ]
    if all(v in (0, None) for v in dvr_values):
        items.append(_health_item("Windows", "Xbox DVR/background capture", "ok", "DVR/background capture выключен или не задан."))
    else:
        items.append(_health_item("Windows", "Xbox DVR/background capture", "warn", f"Найдены включённые DVR значения: {dvr_values}", "Safe Fix выключит Xbox DVR/background capture."))

    hags = _reg_dword_value("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")
    if hags == 2:
        items.append(_health_item("Windows", "HAGS", "ok", "Hardware-accelerated GPU scheduling включён."))
    elif hags in (1, 0):
        items.append(_health_item("Windows", "HAGS", "info", f"HwSchMode={hags}. Это не всегда проблема."))
    else:
        items.append(_health_item("Windows", "HAGS", "info", "HAGS значение не найдено/не задано."))

    # Optimizer ecosystem.
    snaps = list_config_snapshots()
    if snaps:
        items.append(_health_item("Safety", "Config snapshot", "ok", f"Snapshots: {len(snaps)}. Последний: {snaps[0].get('timestamp', '—')}"))
    else:
        items.append(_health_item("Safety", "Config snapshot", "warn", "Нет cfg snapshot.", "Открой Config Manager → Create snapshot."))

    latest = latest_monitor_report()
    if latest:
        items.append(_health_item("Diagnostics", "Stutter Monitor report", "ok", f"Последний отчёт: {latest.name}"))
    else:
        items.append(_health_item("Diagnostics", "Stutter Monitor report", "info", "Отчётов Stutter Monitor пока нет."))

    cleaner = scan_cleaner_targets()
    junk = sum(int(x.get("size_bytes", 0) or 0) for x in cleaner)
    if junk > 5 * 1024 ** 3:
        items.append(_health_item("Cleanup", "Cache/log junk", "bad", f"Найдено примерно {fmt_bytes(junk)}.", "Cleaner / Repair → Clean selected."))
    elif junk > 1024 ** 3:
        items.append(_health_item("Cleanup", "Cache/log junk", "warn", f"Найдено примерно {fmt_bytes(junk)}.", "Cleaner / Repair → Clean selected."))
    else:
        items.append(_health_item("Cleanup", "Cache/log junk", "ok", f"Найдено примерно {fmt_bytes(junk)}."))

    state = load_state()
    if state.get("active_session"):
        items.append(_health_item("Safety", "Active Game Session", "bad", "Есть незавершённый active_session.", "Game Session → Restore / End Session."))
    else:
        items.append(_health_item("Safety", "Active Game Session", "ok", "Незавершённых session-изменений нет."))

    bg = running_background_processes()
    bg_count = sum(len(v) for v in bg.values())
    if bg_count >= 6:
        detail = "; ".join(f"{k}: {', '.join(v[:5])}" for k, v in bg.items() if v)
        items.append(_health_item("Background", "Background apps", "warn", detail, "Game Session может мягко закрыть выбранные группы."))
    elif bg_count:
        detail = "; ".join(f"{k}: {', '.join(v[:5])}" for k, v in bg.items() if v)
        items.append(_health_item("Background", "Background apps", "info", detail))
    else:
        items.append(_health_item("Background", "Background apps", "ok", "Тяжёлые фоновые приложения из списка не найдены."))

    try:
        import importlib.util
        psutil_ok = importlib.util.find_spec("psutil") is not None
    except Exception:
        psutil_ok = False
    items.append(_health_item("Diagnostics", "psutil", "ok" if psutil_ok else "warn", "psutil найден." if psutil_ok else "psutil не найден, Stutter Monitor не заработает.", "Run_Pro_Source_As_Admin.bat установит psutil."))

    score = 100
    for it in items:
        if it["status"] == "bad":
            score -= 18
        elif it["status"] == "warn":
            score -= 8
    score = max(0, min(100, score))
    if score >= 85:
        label = "Excellent"
    elif score >= 70:
        label = "Good"
    elif score >= 50:
        label = "Needs attention"
    else:
        label = "Bad"

    return {"score": score, "label": label, "items": items, "generated": _dt.datetime.now().isoformat(timespec="seconds")}


def render_health_report(scan: Dict[str, Any]) -> str:
    lines = [f"{APP_NAME} v{APP_VERSION} — Health Check", f"Generated: {scan.get('generated', '')}", ""]
    lines.append(f"Score: {scan.get('score', 0)}/100 — {scan.get('label', '—')}")
    lines.append("")
    for status in ["bad", "warn", "info", "ok"]:
        group = [x for x in scan.get("items", []) if x.get("status") == status]
        if not group:
            continue
        lines.append(f"[{status.upper()}]")
        for it in group:
            lines.append(f"• {it.get('category')} / {it.get('title')}: {it.get('detail')}")
            if it.get("fix"):
                lines.append(f"  Fix: {it.get('fix')}")
        lines.append("")
    return "\n".join(lines)


def apply_health_safe_fixes(log) -> Dict[str, Any]:
    """Apply only safe/reversible health fixes: snapshot + safe tweaks."""
    changes: List[Dict[str, Any]] = []
    backup_dir = make_profile_backup_dir("health_safe_fix")
    log("[health] Creating cfg snapshot/backup before safe fixes...")
    try:
        create_config_snapshot(log)
    except Exception as exc:
        log(f"[health][warn] Config snapshot failed: {exc}")
    try:
        backup_configs(backup_dir, log)
    except Exception as exc:
        log(f"[health][warn] Backup cfg failed: {exc}")
    apply_safe_tweaks(changes, log)
    record = {
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "profile": "health_safe_fix",
        "backup_dir": str(backup_dir),
        "changes": changes,
        "ui": "health",
    }
    state = load_state()
    state.setdefault("profiles", []).append(record)
    save_state(state)
    log(f"[health] Safe fixes applied. Changes: {len(changes)}")
    return {"changes": changes, "backup_dir": str(backup_dir)}


# ---------------------------------------------------------------------------
# Report Center / Support Bundle helpers
# ---------------------------------------------------------------------------


def reports_root() -> Path:
    p = app_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def latest_monitor_report() -> Optional[Path]:
    p = optimizer_monitor_report_dir()
    try:
        reports = [x for x in p.glob("stutter_report_*.txt") if x.is_file()]
        if not reports:
            return None
        reports.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return reports[0]
    except Exception:
        return None


def _html_escape(value: Any) -> str:
    # Do not call clean_value here: <pre> sections must preserve newlines.
    text = "—" if value is None else str(value)
    if not text:
        text = "—"
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_pre(text: str) -> str:
    return "<pre>" + _html_escape(text) + "</pre>"


def _html_kv(rows: List[Tuple[str, Any]]) -> str:
    out = ["<table>"]
    for k, v in rows:
        out.append(f"<tr><th>{_html_escape(k)}</th><td>{_html_escape(v)}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def support_bundle_html(
    info: Dict[str, Any],
    tuning: Dict[str, Any],
    cleaner: List[Dict[str, Any]],
    cfg_files: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    monitor_text: str,
    pc_text: str,
    tuning_text: str,
    health_text: str,
) -> str:
    cpu_name = tuning.get("cpu_name", "—")
    gpu_name = tuning.get("gpu_name", "—")
    ram_gb = tuning.get("ram_gb", "—")
    cleaner_total = sum(int(x.get("size_bytes", 0) or 0) for x in cleaner)
    cleaner_found = sum(1 for x in cleaner if x.get("exists"))
    rust_paths = [str(p) for p in discover_rust_exes()] if is_windows() else []
    cfg_dirs = [str(p) for p in discover_cfg_dirs()] if is_windows() else []
    generated = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cleaner_rows = []
    for item in cleaner:
        cleaner_rows.append(
            f"<tr><td>{_html_escape(item.get('title'))}</td><td>{_html_escape(item.get('risk'))}</td><td>{_html_escape(fmt_bytes(item.get('size_bytes')))}</td><td>{_html_escape(item.get('file_count'))}</td></tr>"
        )
    cfg_rows = []
    for item in cfg_files[:80]:
        cfg_rows.append(
            f"<tr><td>{_html_escape(item.get('name'))}</td><td>{_html_escape(fmt_bytes(item.get('size_bytes')))}</td><td>{_html_escape(item.get('modified'))}</td><td>{_html_escape(item.get('path'))}</td></tr>"
        )
    snap_rows = []
    for item in snapshots[:50]:
        snap_rows.append(
            f"<tr><td>{_html_escape(item.get('name'))}</td><td>{_html_escape(item.get('timestamp'))}</td><td>{_html_escape(item.get('file_count'))}</td><td>{_html_escape(fmt_bytes(item.get('size_bytes')))}</td></tr>"
        )

    summary_cards = [
        ("CPU", cpu_name),
        ("GPU", gpu_name),
        ("RAM", f"{ram_gb} GB"),
        ("Bottleneck", tuning.get("bottleneck", "—")),
        ("Recommended profile", tuning.get("recommended_profile", "—")),
        ("Cleaner found", f"{cleaner_found} targets / {fmt_bytes(cleaner_total)}"),
    ]
    cards = "\n".join(f"<div class='card'><div class='muted'>{_html_escape(k)}</div><div class='big'>{_html_escape(v)}</div></div>" for k, v in summary_cards)

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Rust FPS Optimizer Support Report</title>
<style>
:root {{ --bg:#070b14; --panel:#101827; --card:#162238; --text:#e5e7eb; --muted:#94a3b8; --blue:#38bdf8; --green:#22c55e; --yellow:#f59e0b; --border:#26334a; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:28px; background:var(--bg); color:var(--text); font-family:Segoe UI, Arial, sans-serif; }}
h1 {{ margin:0 0 6px; font-size:30px; }}
h2 {{ margin-top:28px; border-left:4px solid var(--blue); padding-left:10px; }}
.sub {{ color:var(--muted); margin-bottom:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:14px; }}
.big {{ font-size:18px; font-weight:700; margin-top:4px; }}
.muted {{ color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }}
.panel {{ background:var(--panel); border:1px solid var(--border); border-radius:18px; padding:16px; margin:14px 0; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ text-align:left; border-bottom:1px solid var(--border); padding:8px; vertical-align:top; }}
th {{ color:var(--blue); width:220px; }}
pre {{ white-space:pre-wrap; word-break:break-word; background:#050a14; border:1px solid var(--border); border-radius:14px; padding:14px; color:#dbeafe; max-height:520px; overflow:auto; }}
.badge {{ display:inline-block; background:#0f2a3a; color:var(--blue); border:1px solid #164e63; border-radius:999px; padding:4px 9px; margin:2px; font-size:12px; }}
.warn {{ color:var(--yellow); }}
</style>
</head>
<body>
<h1>Rust FPS Optimizer Pro Support Report</h1>
<div class="sub">Generated: {_html_escape(generated)} • Version: {_html_escape(APP_VERSION)}</div>
<div class="grid">{cards}</div>

<div class="panel">
<h2>Quick summary</h2>
{_html_kv([
    ("Launch options", tuning.get("launch_options", "—")),
    ("Rust paths", "\n".join(rust_paths) or "—"),
    ("cfg dirs", "\n".join(cfg_dirs) or "—"),
    ("Config files", len(cfg_files)),
    ("Snapshots", len(snapshots)),
])}
</div>

<div class="panel">
<h2>Health Check</h2>
{_html_pre(health_text)}
</div>

<div class="panel">
<h2>Rust Settings recommendation</h2>
{_html_pre(tuning_text)}
</div>

<div class="panel">
<h2>Latest Stutter Monitor report</h2>
{_html_pre(monitor_text or 'No monitor report found.')}
</div>

<div class="panel">
<h2>Cleaner scan</h2>
<table><tr><th>Target</th><th>Risk</th><th>Size</th><th>Files</th></tr>{''.join(cleaner_rows) or '<tr><td colspan="4">No cleaner data</td></tr>'}</table>
</div>

<div class="panel">
<h2>Config files</h2>
<table><tr><th>Name</th><th>Size</th><th>Modified</th><th>Path</th></tr>{''.join(cfg_rows) or '<tr><td colspan="4">No cfg files found</td></tr>'}</table>
</div>

<div class="panel">
<h2>Config snapshots</h2>
<table><tr><th>Name</th><th>Timestamp</th><th>Files</th><th>Size</th></tr>{''.join(snap_rows) or '<tr><td colspan="4">No snapshots found</td></tr>'}</table>
</div>

<div class="panel">
<h2>Full PC report</h2>
{_html_pre(pc_text)}
</div>

</body>
</html>"""


def create_support_bundle(log, target: str = "balanced") -> Dict[str, Any]:
    """Create HTML + TXT/JSON support bundle and ZIP it."""
    out_dir = reports_root() / f"support_bundle_{now_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log(f"[report] Creating support bundle: {out_dir}")

    info = collect_pc_info()
    tuning = generate_rust_tuning(info, target)
    pc_text = render_pc_report(info)
    tuning_text = render_rust_tuning(tuning)
    health_scan = health_check_scan()
    health_text = render_health_report(health_scan)
    cleaner = scan_cleaner_targets()
    cfg_files = config_file_summary()
    snapshots = list_config_snapshots()
    latest = latest_monitor_report()
    monitor_text = latest.read_text(encoding="utf-8", errors="replace") if latest and latest.exists() else "No Stutter Monitor report found."

    (out_dir / "pc_report.txt").write_text(pc_text, encoding="utf-8")
    (out_dir / "health_check.txt").write_text(health_text, encoding="utf-8")
    (out_dir / "rust_settings.txt").write_text(tuning_text, encoding="utf-8")
    (out_dir / "latest_stutter_report.txt").write_text(monitor_text, encoding="utf-8")
    (out_dir / "cleaner_scan.json").write_text(json.dumps(cleaner, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "config_files.json").write_text(json.dumps(cfg_files, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "config_snapshots.json").write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")
    state = load_state()
    state_summary = {
        "version": state.get("version"),
        "profiles_count": len(state.get("profiles", [])) if isinstance(state.get("profiles"), list) else 0,
        "active_session": bool(state.get("active_session")),
        "generated": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "state_summary.json").write_text(json.dumps(state_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    html = support_bundle_html(info, tuning, cleaner, cfg_files, snapshots, monitor_text, pc_text, tuning_text, health_text)
    html_path = out_dir / "support_report.html"
    html_path.write_text(html, encoding="utf-8")
    zip_path = Path(shutil.make_archive(str(out_dir), "zip", root_dir=str(out_dir)))
    log(f"[report] Support bundle ready: {zip_path}")
    return {
        "dir": str(out_dir),
        "zip": str(zip_path),
        "html": str(html_path),
        "summary": {
            "cpu": tuning.get("cpu_name"),
            "gpu": tuning.get("gpu_name"),
            "ram_gb": tuning.get("ram_gb"),
            "bottleneck": tuning.get("bottleneck"),
            "profile": tuning.get("recommended_profile"),
            "launch_options": tuning.get("launch_options"),
            "health_score": health_scan.get("score"),
            "health_label": health_scan.get("label"),
            "cleaner_bytes": sum(int(x.get("size_bytes", 0) or 0) for x in cleaner),
            "cfg_files": len(cfg_files),
            "snapshots": len(snapshots),
        },
    }


# ---------------------------------------------------------------------------
# PC specs / report helpers
# ---------------------------------------------------------------------------

DARK_BG = "#0B1020"
PANEL_BG = "#111827"
CARD_BG = "#162033"
CARD_BG_2 = "#0F172A"
TEXT_FG = "#E5E7EB"
MUTED_FG = "#94A3B8"
ACCENT = "#38BDF8"
ACCENT_2 = "#22C55E"
WARN = "#F59E0B"
DANGER = "#EF4444"
BORDER = "#243044"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def clean_value(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    return re.sub(r"\s+", " ", text)


def to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def fmt_bytes(value: Any) -> str:
    num = to_int(value)
    if num is None or num <= 0:
        return "—"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    n = float(num)
    unit = units[0]
    for unit in units:
        if n < 1024 or unit == units[-1]:
            break
        n /= 1024.0
    if unit in {"GB", "TB", "PB"}:
        return f"{n:.1f} {unit}"
    return f"{n:.0f} {unit}"


def fmt_mhz(value: Any) -> str:
    num = to_int(value)
    if num is None or num <= 0:
        return "—"
    if num >= 1000:
        return f"{num / 1000:.2f} GHz"
    return f"{num} MHz"


def ps_json(script: str, timeout: int = 45) -> Tuple[Optional[Any], str]:
    code, out, err = run_powershell(script, timeout=timeout)
    if code != 0:
        return None, err or out or f"PowerShell exit code {code}"
    text = (out or "").strip()
    if not text:
        return None, "PowerShell returned empty output"
    # Sometimes warnings/noise appear around JSON. Extract JSON body.
    start_obj = text.find("{")
    start_arr = text.find("[")
    starts = [x for x in [start_obj, start_arr] if x >= 0]
    if not starts:
        return None, text
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        return None, text
    try:
        return json.loads(text[start : end + 1]), ""
    except Exception as exc:
        return None, f"JSON parse error: {exc}\n{text[:1000]}"


def collect_pc_info() -> Dict[str, Any]:
    """Collect Windows PC build info without extra Python dependencies."""
    basic = {
        "Python": platform.python_version(),
        "Platform": platform.platform(),
        "Machine": platform.machine(),
        "RAM_GB": get_total_ram_gb(),
    }
    if not is_windows():
        return {"_basic": basic, "_error": "Полный сбор железа доступен в Windows."}

    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
$info = [ordered]@{
  Computer = (Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemType,NumberOfProcessors,NumberOfLogicalProcessors,@{Name='TotalPhysicalMemoryBytes';Expression={[int64]$_.TotalPhysicalMemory}})
  OS = (Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,InstallDate,LastBootUpTime,@{Name='TotalVisibleMemoryBytes';Expression={[int64]$_.TotalVisibleMemorySize * 1KB}},@{Name='FreePhysicalMemoryBytes';Expression={[int64]$_.FreePhysicalMemory * 1KB}})
  CPU = @(Get-CimInstance Win32_Processor | Select-Object Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize,SocketDesignation)
  GPU = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,DriverDate,VideoModeDescription,CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate,PNPDeviceID)
  Memory = @(Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel,DeviceLocator,Manufacturer,PartNumber,SerialNumber,@{Name='CapacityBytes';Expression={[int64]$_.Capacity}},Speed,ConfiguredClockSpeed,MemoryType,SMBIOSMemoryType)
  DiskDrives = @(Get-CimInstance Win32_DiskDrive | Select-Object Model,MediaType,InterfaceType,Partitions,SerialNumber,@{Name='SizeBytes';Expression={[int64]$_.Size}})
  PhysicalDisks = @(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,HealthStatus,OperationalStatus,@{Name='SizeBytes';Expression={[int64]$_.Size}})
  Volumes = @(Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter,FileSystemLabel,FileSystem,HealthStatus,@{Name='SizeBytes';Expression={[int64]$_.Size}},@{Name='SizeRemainingBytes';Expression={[int64]$_.SizeRemaining}})
  BaseBoard = (Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version,SerialNumber)
  BIOS = (Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate,SerialNumber)
}
$info | ConvertTo-Json -Depth 7 -Compress
'''
    data, error = ps_json(script, timeout=60)
    if not isinstance(data, dict):
        return {"_basic": basic, "_error": error or "Не удалось получить данные PowerShell."}
    data["_basic"] = basic
    return data


def total_ram_bytes_from_info(info: Dict[str, Any]) -> Optional[int]:
    comp = info.get("Computer") or {}
    total = to_int(comp.get("TotalPhysicalMemoryBytes")) if isinstance(comp, dict) else None
    if total:
        return total
    os_info = info.get("OS") or {}
    total = to_int(os_info.get("TotalVisibleMemoryBytes")) if isinstance(os_info, dict) else None
    if total:
        return total
    mem_total = 0
    for mem in as_list(info.get("Memory")):
        if isinstance(mem, dict):
            mem_total += to_int(mem.get("CapacityBytes")) or 0
    return mem_total or None


def make_pc_recommendations(info: Dict[str, Any]) -> str:
    lines: List[str] = []
    total_ram = total_ram_bytes_from_info(info)
    if total_ram:
        ram_gb = total_ram / (1024 ** 3)
        if ram_gb < 15:
            lines.append("• RAM меньше 16 GB — для Rust это главный источник фризов. Лучше 32 GB.")
        elif ram_gb < 31:
            lines.append("• RAM около 16 GB — играть можно, но для жирных серверов Rust 32 GB заметно стабильнее.")
        else:
            lines.append("• RAM 32+ GB — хорошо для Rust, можно пробовать -gc.buffer 4096.")
    else:
        lines.append("• Не смог определить общий объём RAM.")

    cpus = as_list(info.get("CPU"))
    if cpus and isinstance(cpus[0], dict):
        cpu = cpus[0]
        logical = to_int(cpu.get("NumberOfLogicalProcessors")) or 0
        cores = to_int(cpu.get("NumberOfCores")) or 0
        name = clean_value(cpu.get("Name"))
        if logical and logical <= 8:
            lines.append(f"• CPU: {name}. Rust сильно упирается в процессор; закрой браузер/запись/стримы.")
        elif cores:
            lines.append(f"• CPU: {name} ({cores}C/{logical}T) — норм, фокус на настройках графики и фоновых процессах.")

    gpus = [g for g in as_list(info.get("GPU")) if isinstance(g, dict)]
    gpu_names = [clean_value(g.get("Name")) for g in gpus]
    if gpu_names:
        only_integrated = all(any(x in n.lower() for x in ["intel uhd", "intel(r) uhd", "iris", "vega graphics", "radeon graphics"]) for n in gpu_names)
        if only_integrated:
            lines.append("• Похоже, активна только встроенная графика. Для Rust нужна дискретная GPU или очень низкие настройки.")
        else:
            lines.append("• Проверь, что Rust запускается на дискретной видеокарте. Оптимизатор ставит High performance GPU preference.")

    rust_exes = discover_rust_exes() if is_windows() else []
    if rust_exes:
        lines.append(f"• Rust найден: {rust_exes[0]}")
        lines.append("• Если игра стоит на HDD — перенеси на SSD/NVMe, это сильно влияет на прогрузки и статтеры.")
    else:
        lines.append("• Rust не найден автоматически. Если Steam Library нестандартная — можно выбрать RustClient.exe вручную.")

    lines.append("• После очистки shader cache первая загрузка может фризить сильнее, пока кэш пересобирается — это нормально.")
    return "\n".join(lines)


def pc_spec_sections(info: Dict[str, Any]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    sections: List[Tuple[str, List[Tuple[str, str]]]] = []

    if info.get("_error"):
        sections.append(("Ошибка/ограничение", [("Сообщение", clean_value(info.get("_error")))]))

    comp = info.get("Computer") if isinstance(info.get("Computer"), dict) else {}
    os_info = info.get("OS") if isinstance(info.get("OS"), dict) else {}
    basic = info.get("_basic") if isinstance(info.get("_basic"), dict) else {}
    sections.append((
        "Система",
        [
            ("ПК", f"{clean_value(comp.get('Manufacturer'))} {clean_value(comp.get('Model'))}".strip()),
            ("Тип", clean_value(comp.get("SystemType") or basic.get("Machine"))),
            ("Windows", f"{clean_value(os_info.get('Caption'))} {clean_value(os_info.get('Version'))} build {clean_value(os_info.get('BuildNumber'))}".strip()),
            ("Архитектура", clean_value(os_info.get("OSArchitecture") or basic.get("Platform"))),
            ("Последняя загрузка", clean_value(os_info.get("LastBootUpTime"))),
        ],
    ))

    cpus = [c for c in as_list(info.get("CPU")) if isinstance(c, dict)]
    cpu_rows: List[Tuple[str, str]] = []
    for idx, cpu in enumerate(cpus or [{}], 1):
        prefix = "CPU" if len(cpus) <= 1 else f"CPU {idx}"
        cpu_rows += [
            (f"{prefix} модель", clean_value(cpu.get("Name"))),
            (f"{prefix} ядра/потоки", f"{clean_value(cpu.get('NumberOfCores'))} / {clean_value(cpu.get('NumberOfLogicalProcessors'))}"),
            (f"{prefix} max clock", fmt_mhz(cpu.get("MaxClockSpeed"))),
            (f"{prefix} сокет", clean_value(cpu.get("SocketDesignation"))),
            (f"{prefix} L3 cache", f"{clean_value(cpu.get('L3CacheSize'))} KB" if cpu.get("L3CacheSize") else "—"),
        ]
    sections.append(("Процессор", cpu_rows))

    gpus = [g for g in as_list(info.get("GPU")) if isinstance(g, dict)]
    gpu_rows: List[Tuple[str, str]] = []
    for idx, gpu in enumerate(gpus or [{}], 1):
        prefix = "GPU" if len(gpus) <= 1 else f"GPU {idx}"
        res = "—"
        if gpu.get("CurrentHorizontalResolution") and gpu.get("CurrentVerticalResolution"):
            hz = clean_value(gpu.get("CurrentRefreshRate"))
            res = f"{gpu.get('CurrentHorizontalResolution')}x{gpu.get('CurrentVerticalResolution')} @ {hz} Hz"
        gpu_rows += [
            (f"{prefix} модель", clean_value(gpu.get("Name"))),
            (f"{prefix} VRAM", fmt_bytes(gpu.get("AdapterRAM"))),
            (f"{prefix} драйвер", clean_value(gpu.get("DriverVersion"))),
            (f"{prefix} режим", clean_value(gpu.get("VideoModeDescription") or res)),
        ]
    sections.append(("Видеокарта", gpu_rows))

    mems = [m for m in as_list(info.get("Memory")) if isinstance(m, dict)]
    total_ram = total_ram_bytes_from_info(info)
    mem_rows: List[Tuple[str, str]] = [("Всего RAM", fmt_bytes(total_ram))]
    if os_info:
        mem_rows.append(("Свободно сейчас", fmt_bytes(os_info.get("FreePhysicalMemoryBytes"))))
    for idx, mem in enumerate(mems, 1):
        slot = clean_value(mem.get("DeviceLocator") or mem.get("BankLabel") or f"Slot {idx}")
        speed = mem.get("ConfiguredClockSpeed") or mem.get("Speed")
        part = clean_value(mem.get("PartNumber"))
        manufacturer = clean_value(mem.get("Manufacturer"))
        mem_rows.append((slot, f"{fmt_bytes(mem.get('CapacityBytes'))} | {clean_value(speed)} MHz | {manufacturer} {part}".strip()))
    sections.append(("Оперативная память", mem_rows))

    physical = [d for d in as_list(info.get("PhysicalDisks")) if isinstance(d, dict)]
    drives = [d for d in as_list(info.get("DiskDrives")) if isinstance(d, dict)]
    disk_rows: List[Tuple[str, str]] = []
    if physical:
        for idx, disk in enumerate(physical, 1):
            disk_rows.append((
                f"Disk {idx}",
                f"{clean_value(disk.get('FriendlyName'))} | {fmt_bytes(disk.get('SizeBytes'))} | {clean_value(disk.get('MediaType'))} | {clean_value(disk.get('BusType'))} | {clean_value(disk.get('HealthStatus'))}",
            ))
    else:
        for idx, disk in enumerate(drives, 1):
            disk_rows.append((
                f"Disk {idx}",
                f"{clean_value(disk.get('Model'))} | {fmt_bytes(disk.get('SizeBytes'))} | {clean_value(disk.get('MediaType'))} | {clean_value(disk.get('InterfaceType'))}",
            ))
    sections.append(("Диски", disk_rows or [("Диски", "—")]))

    volumes = [v for v in as_list(info.get("Volumes")) if isinstance(v, dict)]
    volume_rows: List[Tuple[str, str]] = []
    for vol in volumes:
        letter = clean_value(vol.get("DriveLetter"))
        size = to_int(vol.get("SizeBytes")) or 0
        free = to_int(vol.get("SizeRemainingBytes")) or 0
        used_pct = 0 if not size else round((1 - free / size) * 100)
        volume_rows.append((
            f"{letter}:\\",
            f"{clean_value(vol.get('FileSystemLabel'))} | {clean_value(vol.get('FileSystem'))} | {fmt_bytes(free)} free / {fmt_bytes(size)} | used {used_pct}%",
        ))
    sections.append(("Разделы", volume_rows or [("Volumes", "—")]))

    board = info.get("BaseBoard") if isinstance(info.get("BaseBoard"), dict) else {}
    bios = info.get("BIOS") if isinstance(info.get("BIOS"), dict) else {}
    sections.append((
        "Материнская плата / BIOS",
        [
            ("Материнка", f"{clean_value(board.get('Manufacturer'))} {clean_value(board.get('Product'))} {clean_value(board.get('Version'))}".strip()),
            ("BIOS", f"{clean_value(bios.get('Manufacturer'))} {clean_value(bios.get('SMBIOSBIOSVersion'))}".strip()),
            ("BIOS release", clean_value(bios.get("ReleaseDate"))),
        ],
    ))

    rust_rows: List[Tuple[str, str]] = []
    rust_exes = discover_rust_exes() if is_windows() else []
    for idx, exe in enumerate(rust_exes, 1):
        rust_rows.append((f"RustClient.exe {idx}", str(exe)))
    rust_rows.append(("cfg dirs", "; ".join(str(p) for p in discover_cfg_dirs()) or "—"))
    rust_rows.append(("shader cache", "; ".join(str(p) for p in discover_shader_cache_dirs()) or "—"))
    sections.append(("Rust / Steam", rust_rows))

    return sections


def render_pc_report(info: Dict[str, Any]) -> str:
    lines = [f"{APP_NAME} v{APP_VERSION} — PC report", f"Generated: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for section, rows in pc_spec_sections(info):
        lines.append(f"[{section}]")
        for key, value in rows:
            lines.append(f"{key}: {value}")
        lines.append("")
    lines.append("[Рекомендации]")
    lines.append(make_pc_recommendations(info))
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rust auto settings generator
# ---------------------------------------------------------------------------

RUST_TUNING_TARGETS: Dict[str, str] = {
    "max_fps": "Max FPS",
    "balanced": "Balanced",
    "quality": "Quality",
    "streamer": "Streamer / Recording",
}


def _first_dict(items: Any) -> Dict[str, Any]:
    for item in as_list(items):
        if isinstance(item, dict):
            return item
    return {}


def _score_to_label(score: int) -> str:
    if score <= 1:
        return "очень слабый"
    if score == 2:
        return "слабый"
    if score == 3:
        return "средний"
    if score == 4:
        return "хороший"
    return "сильный"


def _cpu_score(info: Dict[str, Any]) -> Tuple[int, str, Dict[str, Any]]:
    cpu = _first_dict(info.get("CPU"))
    name = clean_value(cpu.get("Name"))
    low = name.lower()
    cores = to_int(cpu.get("NumberOfCores")) or 0
    threads = to_int(cpu.get("NumberOfLogicalProcessors")) or 0
    mhz = to_int(cpu.get("MaxClockSpeed")) or 0

    score = 3
    if any(x in low for x in ["7800x3d", "7950x3d", "7900x3d", "5800x3d", "5700x3d", "5600x3d"]):
        score = 5
    elif any(x in low for x in ["14900", "14700", "14600", "13900", "13700", "13600", "12900", "12700", "12600"]):
        score = 5 if any(x in low for x in ["900", "700", "600"]) else 4
    elif any(x in low for x in [" ryzen 9 ", " ryzen 7 7", " ryzen 7 9", " ryzen 5 7", "7500f", "7600", "7700", "7900", "7950"]):
        score = 5
    elif any(x in low for x in ["12400", "12500", "11600", "11700", "5600", "5600x", "5500", "3600", "3700x", "3800x", "10600", "10700", "11400"]):
        score = 4
    elif any(x in low for x in ["i3", "ryzen 3", "athlon", "pentium", "celeron", "fx-"]):
        score = 2

    if cores <= 4 and threads <= 8:
        score = min(score, 3)
    if cores <= 2:
        score = min(score, 1)
    if cores >= 8 and threads >= 12:
        score = max(score, 4)
    if mhz and mhz < 3000:
        score = min(score, 3)

    score = max(1, min(5, score))
    return score, name, {"cores": cores, "threads": threads, "mhz": mhz}


def _gpu_score_one(gpu: Dict[str, Any]) -> Tuple[int, str, float]:
    name = clean_value(gpu.get("Name"))
    low = name.lower()
    vram_bytes = to_int(gpu.get("AdapterRAM")) or 0
    # Some drivers report weird AdapterRAM values. Clamp to a sane range.
    if vram_bytes < 0 or vram_bytes > 64 * 1024 ** 3:
        vram_bytes = 0
    vram_gb = round(vram_bytes / (1024 ** 3), 1) if vram_bytes else 0.0

    score = 3
    integrated_terms = ["intel uhd", "intel(r) uhd", "iris", "vega graphics", "radeon graphics", "microsoft basic"]
    if any(t in low for t in integrated_terms):
        score = 1

    # NVIDIA RTX/GTX rough tiers.
    m = re.search(r"rtx\s*(\d{4})", low)
    if m:
        model = int(m.group(1))
        gen = model // 1000
        xx = (model % 1000) // 10
        if gen >= 4:
            score = 5 if xx >= 70 else 4 if xx >= 60 else 3
        elif gen == 3:
            score = 5 if xx >= 70 else 4 if xx >= 60 else 3
        elif gen == 2:
            score = 4 if xx >= 70 else 3
    m = re.search(r"gtx\s*(\d{3,4})", low)
    if m:
        model = int(m.group(1))
        if model >= 1660:
            score = 3
        elif model >= 1060:
            score = 2 if vram_gb and vram_gb < 6 else 3
        else:
            score = 2

    # AMD RX rough tiers.
    m = re.search(r"rx\s*(\d{3,4})", low)
    if m:
        model = int(m.group(1))
        if model >= 7800 or model in {6900, 6800}:
            score = 5
        elif model >= 6700 or model in {7600, 7700, 6750, 6650}:
            score = 4
        elif model >= 5600 or model in {6600, 5700}:
            score = 3
        else:
            score = 2

    if vram_gb:
        if vram_gb < 4:
            score = min(score, 2)
        elif vram_gb >= 8:
            score = max(score, 4 if score >= 3 else score)
        elif 4 <= vram_gb < 6:
            score = min(score, 3)

    score = max(1, min(5, score))
    return score, name, vram_gb


def _gpu_score(info: Dict[str, Any]) -> Tuple[int, str, float]:
    best = (1, "—", 0.0)
    for gpu in as_list(info.get("GPU")):
        if not isinstance(gpu, dict):
            continue
        score, name, vram = _gpu_score_one(gpu)
        if score > best[0]:
            best = (score, name, vram)
    return best


def _ram_score(info: Dict[str, Any]) -> Tuple[int, float]:
    total = total_ram_bytes_from_info(info)
    if not total:
        basic = info.get("_basic") if isinstance(info.get("_basic"), dict) else {}
        gb = float(basic.get("RAM_GB") or 0)
    else:
        gb = total / (1024 ** 3)
    if gb < 12:
        score = 1
    elif gb < 16:
        score = 2
    elif gb < 24:
        score = 3
    elif gb < 32:
        score = 4
    else:
        score = 5
    return score, round(gb, 1)


def _volume_free_for_rust(info: Dict[str, Any]) -> Optional[Tuple[str, int, int]]:
    exes = discover_rust_exes() if is_windows() else []
    if not exes:
        return None
    drive = str(exes[0].drive).rstrip(":").upper()
    if not drive:
        return None
    for vol in as_list(info.get("Volumes")):
        if not isinstance(vol, dict):
            continue
        letter = clean_value(vol.get("DriveLetter")).upper()
        if letter == drive:
            return drive, to_int(vol.get("SizeRemainingBytes")) or 0, to_int(vol.get("SizeBytes")) or 0
    return None


def _setting(section: str, name: str, value: str, reason: str = "") -> Dict[str, str]:
    return {"section": section, "name": name, "value": str(value), "reason": reason}


def _settings_for_target(target: str, power_tier: int, ram_gb: float, gpu_score: int) -> List[Dict[str, str]]:
    # power_tier: 1-5, lower means more aggressive in-game reductions.
    settings: List[Dict[str, str]] = []

    if target == "max_fps":
        if power_tier <= 2:
            gq, draw, obj = "1", "1000-1300", "75-100"
            aa = "Off / SMAA если мыло"
        elif power_tier == 3:
            gq, draw, obj = "2", "1400-1700", "100-150"
            aa = "SMAA"
        elif power_tier == 4:
            gq, draw, obj = "3", "1700-2000", "150"
            aa = "SMAA / TSSAA если FPS хватает"
        else:
            gq, draw, obj = "4", "2000-2300", "150-200"
            aa = "TSSAA/SMAA"
        shadows, water, grass, particles = "0", "0", "0-0.2", "0"
        fps_limit = "монитор Hz + 10-20 или uncapped для теста"
    elif target == "quality":
        if power_tier <= 2:
            gq, draw, obj = "2", "1300-1600", "100"
        elif power_tier == 3:
            gq, draw, obj = "3-4", "1800-2200", "150-200"
        elif power_tier == 4:
            gq, draw, obj = "4-5", "2200-2500", "200"
        else:
            gq, draw, obj = "5-6", "2500+", "200-250"
        shadows = "1-2" if power_tier >= 4 else "0-1"
        water = "1-2" if power_tier >= 4 else "0-1"
        grass = "0.5-0.8" if power_tier >= 4 else "0.2-0.4"
        particles = "1" if gpu_score >= 4 else "0"
        aa = "TSSAA"
        fps_limit = "под герцовку монитора или чуть ниже для стабильности"
    elif target == "streamer":
        if power_tier <= 2:
            gq, draw, obj = "1-2", "1000-1400", "75-100"
        elif power_tier == 3:
            gq, draw, obj = "2-3", "1500-1800", "100-150"
        else:
            gq, draw, obj = "3-4", "1800-2200", "150-200"
        shadows, water, grass, particles = "0", "0-1", "0-0.3", "0"
        aa = "SMAA/TSSAA"
        fps_limit = "60/90/120 — стабильный cap под запись/стрим"
    else:  # balanced
        if power_tier <= 2:
            gq, draw, obj = "1", "1100-1400", "75-100"
        elif power_tier == 3:
            gq, draw, obj = "2-3", "1500-1900", "100-150"
        elif power_tier == 4:
            gq, draw, obj = "3-4", "1900-2300", "150-200"
        else:
            gq, draw, obj = "4-5", "2200-2600", "200"
        shadows = "0-1"
        water = "0-1"
        grass = "0.2-0.4" if power_tier >= 4 else "0-0.2"
        particles = "0-1" if gpu_score >= 4 else "0"
        aa = "SMAA / TSSAA если FPS хватает"
        fps_limit = "на 5-10 FPS ниже среднего для меньших статтеров"

    settings += [
        _setting("Graphics", "Graphics Quality", gq, "Главный общий пресет графики."),
        _setting("Graphics", "Draw Distance", draw, "Сильно влияет на CPU/GPU и видимость на больших серверах."),
        _setting("Graphics", "Object Quality", obj, "Высокие значения грузят CPU/GPU в застроенных местах."),
        _setting("Graphics", "Shadow Quality", shadows, "Тени часто дают просадки FPS."),
        _setting("Graphics", "Shadow Cascades", "0-1", "Чем ниже — тем меньше нагрузка и микрофризы."),
        _setting("Graphics", "Max Shadow Lights", "0", "Лучше выключить ради стабильности."),
        _setting("Graphics", "Water Quality", water, "Вода грузит GPU, особенно на слабых картах."),
        _setting("Graphics", "Water Reflections", "0", "Обычно мало пользы, но есть нагрузка."),
        _setting("Graphics", "World Reflections", "0", "Выключить для стабильного FPS."),
        _setting("Graphics", "Shader Level", "300-500" if power_tier >= 4 and target == "quality" else "300", "Не задирай на слабой GPU."),
        _setting("Graphics", "Particle Quality", particles, "В замесах и рейдах снижает просадки."),
        _setting("Graphics", "Max Gibs", "0", "Меньше мусора/физики во время рейдов."),
        _setting("Mesh", "Tree Quality", "50-100" if target != "quality" else "100-150", "Деревья влияют на видимость и FPS."),
        _setting("Mesh", "Max Tree Meshes", "20-50" if target != "quality" else "50-100", "Ниже — меньше нагрузка."),
        _setting("Mesh", "Terrain Quality", "20-50" if power_tier <= 3 else "50-100", "Компромисс FPS/картинка."),
        _setting("Mesh", "Grass Quality", grass, "Трава часто мешает видимости и ест FPS."),
        _setting("Image Effects", "Anti-Aliasing", aa, "TSSAA красивее, SMAA легче."),
        _setting("Image Effects", "Depth of Field", "Off", "Лишний эффект, может мешать."),
        _setting("Image Effects", "Motion Blur", "Off", "Выключить для читаемости."),
        _setting("Image Effects", "Ambient Occlusion", "Off" if target != "quality" else "Low/Off", "AO красиво, но снижает FPS."),
        _setting("Performance", "FPS Limit", fps_limit, "Стабильный лимит часто уменьшает статтеры."),
    ]

    if ram_gb and ram_gb < 16:
        settings.append(_setting("Performance", "Texture Quality", "Low/Medium", "Мало RAM/VRAM — текстуры могут усиливать статтеры."))
    elif gpu_score <= 2:
        settings.append(_setting("Performance", "Texture Quality", "Medium", "Слабая/старая GPU или мало VRAM."))
    else:
        settings.append(_setting("Performance", "Texture Quality", "Medium/High", "Если VRAM 8+ GB — можно High."))
    return settings


def generate_rust_tuning(info: Dict[str, Any], target: str = "balanced") -> Dict[str, Any]:
    target = target if target in RUST_TUNING_TARGETS else "balanced"
    cpu_score, cpu_name, cpu_meta = _cpu_score(info)
    gpu_score, gpu_name, vram_gb = _gpu_score(info)
    ram_score, ram_gb = _ram_score(info)

    # Rust loves CPU and RAM. Penalize low RAM a bit stronger for stutters.
    power_tier = min(cpu_score, gpu_score)
    if ram_score <= 2:
        power_tier = min(power_tier, 2)
    elif ram_score == 3:
        power_tier = min(power_tier, 3)
    power_tier = max(1, min(5, power_tier))

    bottlenecks: List[str] = []
    if cpu_score <= gpu_score and cpu_score <= ram_score:
        bottlenecks.append("CPU")
    if gpu_score <= cpu_score and gpu_score <= ram_score:
        bottlenecks.append("GPU")
    if ram_score <= cpu_score and ram_score <= gpu_score:
        bottlenecks.append("RAM")
    bottleneck = " / ".join(dict.fromkeys(bottlenecks)) or "не очевиден"

    if target == "max_fps":
        profile = "AGGRESSIVE" if power_tier >= 3 else "BALANCED"
        exclusive = True
    elif target == "quality":
        profile = "BALANCED" if power_tier >= 3 else "SAFE"
        exclusive = False
    elif target == "streamer":
        profile = "BALANCED"
        exclusive = False
    else:
        profile = "BALANCED"
        exclusive = False

    gc = suggested_gc_buffer("aggressive" if target == "max_fps" else "balanced", ram_gb or None)
    launch = launch_options("balanced", ram_gb or None, exclusive=exclusive)
    if str(gc) not in launch:
        launch = f"-nolog -gc.buffer {gc}" + (" -window-mode exclusive" if exclusive else "")

    warnings: List[str] = []
    reasons: List[str] = []
    actions: List[str] = []

    if ram_gb < 15:
        warnings.append("RAM меньше 16 GB — это почти гарантированный источник фризов в Rust. Лучший апгрейд: 32 GB.")
    elif ram_gb < 24:
        warnings.append("RAM около 16 GB — на больших серверах возможны статтеры. Закрывай браузер/стрим/запись.")
    else:
        reasons.append("RAM выглядит нормально для Rust; можно использовать увеличенный GC buffer.")

    if cpu_score <= 2:
        warnings.append("CPU выглядит слабым для Rust. Игра часто упирается в одно/несколько быстрых ядер.")
    elif cpu_score >= 4:
        reasons.append("CPU выглядит достаточно сильным; основной фокус — фоновые процессы, GPU и настройки графики.")

    if gpu_score <= 2:
        warnings.append("GPU/VRAM выглядит слабым местом. Держи тени, воду, траву и эффекты на минимуме.")
    elif vram_gb and vram_gb < 6:
        warnings.append(f"VRAM около {vram_gb} GB — не задирай Texture Quality и дальность объектов.")
    elif gpu_score >= 4:
        reasons.append("GPU выглядит нормальной; можно оставить картинку Balanced, но тени/воду всё равно не задирать.")

    vol = _volume_free_for_rust(info)
    if vol:
        drive, free, size = vol
        if free and free < 25 * 1024 ** 3:
            warnings.append(f"На диске Rust ({drive}:) свободно только {fmt_bytes(free)}. Освободи 25-50 GB для кэшей/обновлений.")

    if target == "streamer":
        actions += [
            "Ставь стабильный FPS cap (60/90/120), а не uncapped.",
            "Отключи Instant Replay/Replay Buffer, если не используешь; иначе оставь запас по GPU 15-20%.",
            "Не используй -window-mode exclusive, если часто Alt+Tab/OBS capture ломается.",
        ]
    elif target == "max_fps":
        actions += [
            "Проверь -window-mode exclusive: если Alt+Tab/оверлеи ломаются или хуже — убери его.",
            "После профиля AGGRESSIVE перезагрузи Windows, если включался HAGS/Ultimate Performance.",
        ]
    else:
        actions += [
            "Начни с профиля BALANCED и теста на своём основном сервере.",
            "Если после -gc.buffer стало хуже — уменьши значение или оставь только -nolog.",
        ]

    rust_found = bool(discover_rust_exes()) if is_windows() else False
    if rust_found:
        actions.append("Rust найден автоматически; можно применять GPU preference и fullscreen tweaks.")
    else:
        actions.append("Если Rust не найден, выбери RustClient.exe вручную во вкладке Оптимизация.")

    settings = _settings_for_target(target, power_tier, ram_gb, gpu_score)
    summary = [
        f"Target: {RUST_TUNING_TARGETS[target]}",
        f"Общий класс для Rust: {_score_to_label(power_tier)} ({power_tier}/5)",
        f"Вероятный bottleneck: {bottleneck}",
        f"Рекомендуемый профиль оптимизатора: {profile}",
        f"CPU: {cpu_name} — {_score_to_label(cpu_score)} ({cpu_score}/5)",
        f"GPU: {gpu_name} — {_score_to_label(gpu_score)} ({gpu_score}/5)" + (f", VRAM ~{vram_gb} GB" if vram_gb else ""),
        f"RAM: {ram_gb} GB — {_score_to_label(ram_score)} ({ram_score}/5)",
    ]

    return {
        "target": target,
        "target_label": RUST_TUNING_TARGETS[target],
        "power_tier": power_tier,
        "cpu_score": cpu_score,
        "gpu_score": gpu_score,
        "ram_score": ram_score,
        "cpu_name": cpu_name,
        "gpu_name": gpu_name,
        "ram_gb": ram_gb,
        "vram_gb": vram_gb,
        "bottleneck": bottleneck,
        "recommended_profile": profile,
        "launch_options": launch,
        "settings": settings,
        "summary": summary,
        "warnings": warnings,
        "reasons": reasons,
        "actions": actions,
        "cpu_meta": cpu_meta,
    }


def render_rust_tuning(tuning: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"{APP_NAME} v{APP_VERSION} — Rust settings recommendation")
    lines.append(f"Generated: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("[Итог]")
    for item in tuning.get("summary", []):
        lines.append(f"• {item}")
    lines.append("")
    lines.append("[Steam Launch Options]")
    lines.append(clean_value(tuning.get("launch_options")))
    lines.append("")
    lines.append("[Настройки Rust]")
    last_section = ""
    for st in tuning.get("settings", []):
        if not isinstance(st, dict):
            continue
        section = clean_value(st.get("section"))
        if section != last_section:
            lines.append(f"\n{section}:")
            last_section = section
        reason = clean_value(st.get("reason"))
        value = clean_value(st.get("value"))
        name = clean_value(st.get("name"))
        lines.append(f"  - {name}: {value}" + (f"  // {reason}" if reason != "—" else ""))
    lines.append("")
    if tuning.get("warnings"):
        lines.append("[Предупреждения]")
        for w in tuning.get("warnings", []):
            lines.append(f"• {w}")
        lines.append("")
    if tuning.get("reasons"):
        lines.append("[Почему так]")
        for r in tuning.get("reasons", []):
            lines.append(f"• {r}")
        lines.append("")
    if tuning.get("actions"):
        lines.append("[Что сделать]")
        for a in tuning.get("actions", []):
            lines.append(f"• {a}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class OptimizerApp:
    def __init__(self, root: "tk.Tk") -> None:
        self.root = root
        self.main_thread_id = threading.get_ident()
        self.state = load_state()
        self.ram_gb = get_total_ram_gb()
        self.busy = False
        self.spec_busy = False
        self.pc_info: Dict[str, Any] = {}
        self.pc_report_text = ""
        self.exclusive_var = tk.BooleanVar(value=False)

        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.geometry("1120x780")
        root.minsize(960, 650)
        root.configure(bg=DARK_BG)
        self._set_window_icon()
        self._configure_style()
        self._build_ui()

        self.refresh_status()
        self.log(f"{APP_NAME} v{APP_VERSION}")
        self.log("Не чит, не инжектор, EAC/игровую память не трогает.")
        if not is_windows():
            self.log("[warn] Сейчас не Windows. Утилита написана под Windows 10/11.")
        self.log("Готово. Совет: сначала SAFE, потом тест, потом BALANCED/AGGRESSIVE.")
        self.root.after(350, self.refresh_specs_async)

    # ----- UI setup -----
    def _set_window_icon(self) -> None:
        try:
            ico = resource_path("app.ico")
            if ico.exists():
                self.root.iconbitmap(str(ico))
        except Exception:
            pass

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=DARK_BG, foreground=TEXT_FG, fieldbackground=CARD_BG, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.configure("TFrame", background=DARK_BG)
        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("TLabel", background=DARK_BG, foreground=TEXT_FG, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=DARK_BG, foreground=MUTED_FG, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=DARK_BG, foreground=TEXT_FG, font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=DARK_BG, foreground=MUTED_FG, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7), background=CARD_BG, foreground=TEXT_FG)
        style.map("TButton", background=[("active", "#1F2A44"), ("disabled", "#111827")], foreground=[("disabled", "#64748B")])
        style.configure("Accent.TButton", background="#0EA5E9", foreground="#FFFFFF")
        style.map("Accent.TButton", background=[("active", "#0284C7")])
        style.configure("Danger.TButton", background="#7F1D1D", foreground="#FFFFFF")
        style.map("Danger.TButton", background=[("active", "#991B1B")])
        style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_BG, foreground=MUTED_FG, padding=(16, 9), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", CARD_BG)], foreground=[("selected", TEXT_FG)])
        style.configure("Treeview", background=PANEL_BG, foreground=TEXT_FG, fieldbackground=PANEL_BG, rowheight=27, bordercolor=BORDER)
        style.configure("Treeview.Heading", background=CARD_BG, foreground=TEXT_FG, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0EA5E9")], foreground=[("selected", "#FFFFFF")])
        style.configure("TEntry", fieldbackground=PANEL_BG, foreground=TEXT_FG, insertcolor=TEXT_FG, bordercolor=BORDER)
        style.configure("TCheckbutton", background=DARK_BG, foreground=TEXT_FG, font=("Segoe UI", 10))

    def _build_ui(self) -> None:
        self.action_buttons: List[Any] = []

        self._build_header()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self.tab_home = ttk.Frame(self.notebook)
        self.tab_opt = ttk.Frame(self.notebook)
        self.tab_specs = ttk.Frame(self.notebook)
        self.tab_launch = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_home, text="Главная")
        self.notebook.add(self.tab_opt, text="Оптимизация")
        self.notebook.add(self.tab_specs, text="ПК / Железо")
        self.notebook.add(self.tab_launch, text="Launch Options")
        self.notebook.add(self.tab_logs, text="Бэкапы / Лог")

        self._build_home_tab()
        self._build_optimization_tab()
        self._build_specs_tab()
        self._build_launch_tab()
        self._build_logs_tab()
        self.update_launch_options()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=DARK_BG)
        header.pack(fill="x", padx=16, pady=(14, 10))

        logo = tk.Canvas(header, width=54, height=54, bg=DARK_BG, bd=0, highlightthickness=0)
        logo.pack(side="left", padx=(0, 12))
        logo.create_oval(4, 4, 50, 50, fill="#0EA5E9", outline="#38BDF8", width=2)
        logo.create_text(27, 27, text="R", fill="white", font=("Segoe UI", 25, "bold"))

        title_box = tk.Frame(header, bg=DARK_BG)
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(title_box, text="Rust FPS Optimizer", bg=DARK_BG, fg=TEXT_FG, font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Windows 11/10 • FPS, статтеры, launch options, диагностика железа", bg=DARK_BG, fg=MUTED_FG, font=("Segoe UI", 10)).pack(anchor="w")

        right = tk.Frame(header, bg=DARK_BG)
        right.pack(side="right")
        self.admin_chip = tk.Label(right, text="", bg=CARD_BG, fg=TEXT_FG, font=("Segoe UI", 10, "bold"), padx=12, pady=6)
        self.admin_chip.pack(anchor="e", pady=(0, 6))
        tk.Label(right, text=f"v{APP_VERSION}", bg=DARK_BG, fg=MUTED_FG, font=("Segoe UI", 9)).pack(anchor="e")

    def make_card(self, parent, title: str = "", subtitle: str = "", accent: str = ACCENT) -> tk.Frame:
        outer = tk.Frame(parent, bg=BORDER)
        inner = tk.Frame(outer, bg=CARD_BG, padx=14, pady=12)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        if title:
            tk.Label(inner, text=title, bg=CARD_BG, fg=TEXT_FG, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(inner, text=subtitle, bg=CARD_BG, fg=MUTED_FG, font=("Segoe UI", 9), wraplength=760, justify="left").pack(anchor="w", pady=(2, 0))
        bar = tk.Frame(inner, bg=accent, height=2)
        bar.pack(fill="x", pady=(8, 8)) if title else None
        outer.inner = inner  # type: ignore[attr-defined]
        return outer

    def _build_home_tab(self) -> None:
        page = tk.Frame(self.tab_home, bg=DARK_BG)
        page.pack(fill="both", expand=True, padx=10, pady=10)

        grid = tk.Frame(page, bg=DARK_BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        status_card = self.make_card(grid, "Статус", "Автопоиск Steam/Rust, права админа, RAM и текущие подсказки.", ACCENT)
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 10))
        self.home_status_var = tk.StringVar(value="Сканирую...")
        tk.Label(status_card.inner, textvariable=self.home_status_var, bg=CARD_BG, fg=TEXT_FG, font=("Consolas", 10), justify="left", wraplength=500).pack(anchor="w", fill="x")
        ttk.Button(status_card.inner, text="Обновить статус", command=self.refresh_status).pack(anchor="w", pady=(10, 0))

        quick_card = self.make_card(grid, "Быстрый старт", "Рекомендованный порядок: SAFE → тест в Rust → BALANCED → AGGRESSIVE только при необходимости.", ACCENT_2)
        quick_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 10))
        row = tk.Frame(quick_card.inner, bg=CARD_BG)
        row.pack(fill="x")
        for label, profile, style in [
            ("SAFE", "safe", "Accent.TButton"),
            ("BALANCED", "balanced", "TButton"),
            ("AGGRESSIVE", "aggressive", "Danger.TButton"),
        ]:
            b = ttk.Button(row, text=label, style=style, command=lambda p=profile: self.run_profile(p))
            b.pack(side="left", padx=(0, 8), pady=4)
            self.action_buttons.append(b)
        row2 = tk.Frame(quick_card.inner, bg=CARD_BG)
        row2.pack(fill="x", pady=(6, 0))
        b = ttk.Button(row2, text="Скопировать options", command=lambda: self.copy_launch("balanced"))
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)
        b = ttk.Button(row2, text="Запустить Rust + High priority", command=self.launch_and_monitor)
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)

        reco_card = self.make_card(page, "Рекомендации по твоему ПК", "Обновляются после скана вкладки ПК / Железо.", WARN)
        reco_card.pack(fill="both", expand=True, pady=(0, 0))
        self.reco_text = tk.Text(reco_card.inner, height=11, wrap="word", bg=PANEL_BG, fg=TEXT_FG, insertbackground=TEXT_FG, relief="flat", padx=10, pady=10, font=("Segoe UI", 10))
        self.reco_text.pack(fill="both", expand=True)
        self._set_text(self.reco_text, "Пока нет данных. Открой вкладку ПК / Железо или нажми «Обновить сборку ПК».")

    def _build_optimization_tab(self) -> None:
        page = tk.Frame(self.tab_opt, bg=DARK_BG)
        page.pack(fill="both", expand=True, padx=10, pady=10)
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.columnconfigure(2, weight=1)

        profiles = [
            ("SAFE", "safe", ACCENT_2, "Минимум риска", [
                "Backup cfg и очистка логов",
                "Game Mode ON",
                "Xbox DVR/background capture OFF",
                "High performance GPU preference",
            ]),
            ("BALANCED", "balanced", ACCENT, "Оптимальный вариант для FPS/статтеров", [
                "Всё из SAFE",
                "High Performance power plan",
                "Disable fullscreen optimizations для Rust",
                "High priority можно включать при запуске",
            ]),
            ("AGGRESSIVE", "aggressive", DANGER, "Максимум FPS, но аккуратно", [
                "Всё из BALANCED",
                "Ultimate Performance",
                "Доп. GameDVR/FSE flags",
                "HAGS и transparency OFF, нужен reboot",
            ]),
        ]
        for col, (title, profile, color, subtitle, bullets) in enumerate(profiles):
            card = self.make_card(page, title, subtitle, color)
            card.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
            for bullet in bullets:
                tk.Label(card.inner, text="• " + bullet, bg=CARD_BG, fg=TEXT_FG, anchor="w", justify="left", wraplength=300, font=("Segoe UI", 10)).pack(anchor="w", pady=2)
            b = ttk.Button(card.inner, text=f"Применить {title}", style="Accent.TButton" if profile != "aggressive" else "Danger.TButton", command=lambda p=profile: self.run_profile(p))
            b.pack(anchor="w", pady=(14, 0))
            self.action_buttons.append(b)

        tools = self.make_card(page, "Дополнительные действия", "Откат, ручной выбор RustClient.exe, очистка shader cache.", WARN)
        tools.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=6, pady=(14, 6))
        row = tk.Frame(tools.inner, bg=CARD_BG)
        row.pack(fill="x")
        buttons = [
            ("Откатить последний профиль", self.undo_last, "TButton"),
            ("Backup cfg", self.backup_only, "TButton"),
            ("Очистить shader cache", self.clear_shader_cache_confirmed, "Danger.TButton"),
            ("Выбрать RustClient.exe вручную", self.pick_rust_exe, "TButton"),
            ("Перезапуск от админа", restart_as_admin, "TButton"),
        ]
        for text, cmd, style in buttons:
            b = ttk.Button(row, text=text, command=cmd, style=style)
            b.pack(side="left", padx=(0, 8), pady=4)
            self.action_buttons.append(b)

        self.status_var = tk.StringVar(value="")
        tk.Label(tools.inner, textvariable=self.status_var, bg=CARD_BG, fg=MUTED_FG, font=("Consolas", 9), wraplength=980, justify="left").pack(anchor="w", pady=(10, 0))

    def _build_specs_tab(self) -> None:
        page = tk.Frame(self.tab_specs, bg=DARK_BG)
        page.pack(fill="both", expand=True, padx=10, pady=10)

        top = tk.Frame(page, bg=DARK_BG)
        top.pack(fill="x", pady=(0, 8))
        self.spec_status_var = tk.StringVar(value="Нажми «Обновить сборку ПК».")
        tk.Label(top, textvariable=self.spec_status_var, bg=DARK_BG, fg=MUTED_FG, font=("Segoe UI", 10)).pack(side="left")
        ttk.Button(top, text="Обновить сборку ПК", command=self.refresh_specs_async, style="Accent.TButton").pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Скопировать отчёт", command=self.copy_pc_report).pack(side="right", padx=(8, 0))
        ttk.Button(top, text="Сохранить .txt", command=self.save_pc_report).pack(side="right", padx=(8, 0))

        body = tk.Frame(page, bg=DARK_BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        tree_frame = tk.Frame(body, bg=BORDER)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        inner = tk.Frame(tree_frame, bg=PANEL_BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.spec_tree = ttk.Treeview(inner, columns=("value",), show="tree headings")
        self.spec_tree.heading("#0", text="Параметр")
        self.spec_tree.heading("value", text="Значение")
        self.spec_tree.column("#0", width=260, anchor="w")
        self.spec_tree.column("value", width=540, anchor="w")
        yscroll = ttk.Scrollbar(inner, orient="vertical", command=self.spec_tree.yview)
        self.spec_tree.configure(yscrollcommand=yscroll.set)
        self.spec_tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.spec_tree.tag_configure("section", background=CARD_BG, foreground=ACCENT, font=("Segoe UI", 10, "bold"))

        report_card = self.make_card(body, "Отчёт / советы", "Можно скопировать и скинуть кому-то для диагностики.", ACCENT)
        report_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.pc_report_box = tk.Text(report_card.inner, wrap="word", bg=PANEL_BG, fg=TEXT_FG, insertbackground=TEXT_FG, relief="flat", padx=10, pady=10, font=("Consolas", 9))
        self.pc_report_box.pack(fill="both", expand=True)
        self._set_text(self.pc_report_box, "Отчёт пока не собран.")

    def _build_launch_tab(self) -> None:
        page = tk.Frame(self.tab_launch, bg=DARK_BG)
        page.pack(fill="both", expand=True, padx=10, pady=10)

        card = self.make_card(page, "Steam Launch Options", "Вставляется вручную: Steam → Rust → Properties → Launch Options.", ACCENT)
        card.pack(fill="x")
        row = tk.Frame(card.inner, bg=CARD_BG)
        row.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(row, text="добавить -window-mode exclusive", variable=self.exclusive_var, command=self.update_launch_options).pack(side="left")
        ttk.Button(row, text="SAFE", command=lambda: self.copy_launch("safe")).pack(side="left", padx=6)
        ttk.Button(row, text="BALANCED", command=lambda: self.copy_launch("balanced"), style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(row, text="AGGRESSIVE", command=lambda: self.copy_launch("aggressive"), style="Danger.TButton").pack(side="left", padx=6)

        self.launch_var = tk.StringVar(value="")
        entry = ttk.Entry(card.inner, textvariable=self.launch_var, font=("Consolas", 11))
        entry.pack(fill="x", pady=(4, 8))
        tk.Label(card.inner, text="Если после -gc.buffer хуже — уменьши значение или оставь только -nolog. Exclusive может поднять FPS, но Alt+Tab иногда хуже.", bg=CARD_BG, fg=MUTED_FG, font=("Segoe UI", 9), wraplength=980, justify="left").pack(anchor="w")

        run_card = self.make_card(page, "Запуск и приоритет", "High priority не патчит игру и не трогает EAC — это обычный приоритет процесса Windows.", ACCENT_2)
        run_card.pack(fill="x", pady=(12, 0))
        row2 = tk.Frame(run_card.inner, bg=CARD_BG)
        row2.pack(fill="x")
        b = ttk.Button(row2, text="Запустить Rust через Steam + High priority", command=self.launch_and_monitor, style="Accent.TButton")
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)
        b = ttk.Button(row2, text="Поставить High priority сейчас", command=lambda: self.run_in_thread(lambda: set_rust_priority_high(self.log)))
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)

        tips = self.make_card(page, "Мини-гайд", "Что чаще всего влияет на Rust.", WARN)
        tips.pack(fill="both", expand=True, pady=(12, 0))
        tips_text = (
            "• SSD/NVMe сильно важнее для прогрузок, чем кажется.\n"
            "• 16 GB RAM — минимум; 32 GB лучше для больших серверов.\n"
            "• Закрой браузер, Discord stream, ShadowPlay Instant Replay, OBS replay buffer.\n"
            "• В игре первыми режь Shadows, Water, Grass, Object Quality/Draw Distance.\n"
            "• После очистки shader cache первый запуск может быть хуже — кэш пересобирается."
        )
        tk.Label(tips.inner, text=tips_text, bg=CARD_BG, fg=TEXT_FG, justify="left", wraplength=980, font=("Segoe UI", 10)).pack(anchor="w")

    def _build_logs_tab(self) -> None:
        page = tk.Frame(self.tab_logs, bg=DARK_BG)
        page.pack(fill="both", expand=True, padx=10, pady=10)

        actions = tk.Frame(page, bg=DARK_BG)
        actions.pack(fill="x", pady=(0, 8))
        for text, cmd, style in [
            ("Открыть папку бэкапов", self.open_backup_folder, "TButton"),
            ("Открыть state/log", self.open_app_folder, "TButton"),
            ("Backup cfg", self.backup_only, "TButton"),
            ("Откатить последний профиль", self.undo_last, "Danger.TButton"),
        ]:
            b = ttk.Button(actions, text=text, command=cmd, style=style)
            b.pack(side="left", padx=(0, 8))
            self.action_buttons.append(b)

        log_frame = tk.Frame(page, bg=BORDER)
        log_frame.pack(fill="both", expand=True)
        inner = tk.Frame(log_frame, bg=PANEL_BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.log_box = scrolledtext.ScrolledText(inner, height=18, wrap="word", font=("Consolas", 9), bg="#050A14", fg=TEXT_FG, insertbackground=TEXT_FG, relief="flat")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=8)

    # ----- Thread-safe UI helpers -----
    def ui(self, func) -> None:
        try:
            if threading.get_ident() == self.main_thread_id:
                func()
            else:
                self.root.after(0, func)
        except Exception:
            pass

    def _set_text(self, widget: "tk.Text", text: str) -> None:
        def apply() -> None:
            try:
                widget.configure(state="normal")
                widget.delete("1.0", "end")
                widget.insert("1.0", text)
                widget.configure(state="disabled")
            except Exception:
                pass
        self.ui(apply)

    def log(self, text: str) -> None:
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {text}"
        try:
            with log_path().open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

        def append() -> None:
            if hasattr(self, "log_box"):
                self.log_box.insert("end", line + "\n")
                self.log_box.see("end")

        self.ui(append)

    def set_busy(self, busy: bool) -> None:
        self.busy = busy

        def apply_state() -> None:
            state = "disabled" if busy else "normal"
            for b in self.action_buttons:
                try:
                    b.configure(state=state)
                except Exception:
                    pass

        self.ui(apply_state)

    def run_in_thread(self, func) -> None:
        if self.busy:
            return
        self.set_busy(True)

        def wrapper():
            try:
                func()
            except Exception as exc:
                self.log(f"[err] {exc}")
                if messagebox:
                    self.ui(lambda: messagebox.showerror(APP_NAME, str(exc)))
            finally:
                self.set_busy(False)
                self.refresh_status()

        threading.Thread(target=wrapper, daemon=True).start()

    # ----- Status / specs -----
    def refresh_status(self) -> None:
        exes = discover_rust_exes() if is_windows() else []
        cfgs = discover_cfg_dirs() if is_windows() else []
        admin = "Admin" if is_admin() else "No admin"
        ram = f"RAM {self.ram_gb} GB" if self.ram_gb else "RAM ?"
        rust = f"Rust найден:\n{exes[0]}" if exes else "RustClient.exe не найден автоматически"
        status_line = f"{platform.system()} {platform.release()} | {admin} | {ram} | cfg dirs: {len(cfgs)}"
        home_text = f"{status_line}\n{rust}\n\nПапка данных оптимизатора:\n{app_dir()}"

        def apply() -> None:
            self.status_var.set(status_line) if hasattr(self, "status_var") else None
            self.home_status_var.set(home_text) if hasattr(self, "home_status_var") else None
            if hasattr(self, "admin_chip"):
                self.admin_chip.configure(text=admin, bg="#14532D" if is_admin() else "#7F1D1D")
            self.update_launch_options()

        self.ui(apply)

    def refresh_specs_async(self) -> None:
        if self.spec_busy:
            return
        self.spec_busy = True
        if hasattr(self, "spec_status_var"):
            self.spec_status_var.set("Сканирую железо через PowerShell/CIM...")

        def worker() -> None:
            try:
                info = collect_pc_info()
                report = render_pc_report(info)
                recommendations = make_pc_recommendations(info)
                sections = pc_spec_sections(info)
                self.pc_info = info
                self.pc_report_text = report

                def apply() -> None:
                    self.populate_specs(sections)
                    self._set_text(self.pc_report_box, report)
                    self._set_text(self.reco_text, recommendations)
                    self.spec_status_var.set(f"Готово: {_dt.datetime.now().strftime('%H:%M:%S')}")
                    self.refresh_status()

                self.ui(apply)
            except Exception as exc:
                self.log(f"[warn] Не смог собрать ПК: {exc}")
                if hasattr(self, "spec_status_var"):
                    self.ui(lambda: self.spec_status_var.set(f"Ошибка скана: {exc}"))
            finally:
                self.spec_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def populate_specs(self, sections: List[Tuple[str, List[Tuple[str, str]]]]) -> None:
        if not hasattr(self, "spec_tree"):
            return
        tree = self.spec_tree
        for item in tree.get_children():
            tree.delete(item)
        for section, rows in sections:
            parent = tree.insert("", "end", text=section, values=("",), open=True, tags=("section",))
            for key, value in rows:
                tree.insert(parent, "end", text=key, values=(value,))

    def copy_pc_report(self) -> None:
        text = self.pc_report_text or "Отчёт пока не собран. Нажми «Обновить сборку ПК»."
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("[ok] PC report скопирован в буфер.")
        if messagebox:
            messagebox.showinfo(APP_NAME, "Отчёт по ПК скопирован.")

    def save_pc_report(self) -> None:
        if not filedialog:
            return
        text = self.pc_report_text or render_pc_report(self.pc_info or collect_pc_info())
        default = f"rust_pc_report_{now_stamp()}.txt"
        p = filedialog.asksaveasfilename(title="Сохранить отчёт", defaultextension=".txt", initialfile=default, filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not p:
            return
        try:
            Path(p).write_text(text, encoding="utf-8")
            self.log(f"[ok] PC report сохранён: {p}")
        except Exception as exc:
            self.log(f"[err] Не смог сохранить отчёт: {exc}")

    # ----- Launch options -----
    def update_launch_options(self) -> None:
        if hasattr(self, "launch_var"):
            self.launch_var.set(launch_options("balanced", self.ram_gb, self.exclusive_var.get()))

    def copy_launch(self, profile: str) -> None:
        text = launch_options(profile, self.ram_gb, self.exclusive_var.get())
        if hasattr(self, "launch_var"):
            self.launch_var.set(text)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log(f"[ok] Launch options {profile.upper()} скопированы: {text}")
        if messagebox:
            messagebox.showinfo(APP_NAME, "Скопировано. Вставь в Steam → Rust → Properties → Launch Options.")

    # ----- Profile actions -----
    def run_profile(self, profile: str) -> None:
        clear_shader_after = False
        if profile == "aggressive" and messagebox:
            ok = messagebox.askyesno(
                APP_NAME,
                "Aggressive включает более жёсткие, но обратимые твики Windows.\n"
                "HAGS/Ultimate Performance могут требовать админ-права и перезагрузку.\n\n"
                "Продолжить?",
            )
            if not ok:
                return
            clear_shader_after = messagebox.askyesno(
                APP_NAME,
                "Дополнительно очистить shader cache Rust?\n\n"
                "Если кэш битый — может помочь. Но первый запуск/прогрузка после удаления может временно фризить сильнее.",
            )
        self.run_in_thread(lambda: self.apply_profile(profile, clear_shader_after))

    def apply_profile(self, profile: str, clear_shader_after: bool = False) -> None:
        if not is_windows():
            self.log("[err] Профили применяются только на Windows 10/11.")
            return
        self.log(f"=== APPLY {profile.upper()} ===")
        backup_dir = make_profile_backup_dir(profile)
        changes: List[Dict[str, Any]] = []

        backup_configs(backup_dir, self.log)
        clear_logs(backup_dir, self.log)

        if profile == "safe":
            apply_safe_tweaks(changes, self.log)
        elif profile == "balanced":
            apply_balanced_tweaks(changes, self.log)
        elif profile == "aggressive":
            apply_aggressive_tweaks(changes, self.log)
            if clear_shader_after:
                clear_shader_cache(self.log)
        else:
            self.log(f"[err] Неизвестный профиль: {profile}")
            return

        record = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "profile": profile,
            "backup_dir": str(backup_dir),
            "changes": changes,
            "rust_exes": [str(p) for p in discover_rust_exes()],
            "cfg_dirs": [str(p) for p in discover_cfg_dirs()],
        }
        self.state.setdefault("profiles", []).append(record)
        save_state(self.state)
        self.log(f"[done] {profile.upper()} применён. Изменений для отката: {len(changes)}. Backup: {backup_dir}")
        self.log(f"[tip] Launch options для этого профиля: {launch_options(profile, self.ram_gb, self.exclusive_var.get())}")

    def undo_last(self) -> None:
        if messagebox:
            if not messagebox.askyesno(APP_NAME, "Откатить последний применённый профиль? cfg-бэкапы останутся в папке backups."):
                return
        self.run_in_thread(self.undo_last_impl)

    def undo_last_impl(self) -> None:
        profiles = self.state.get("profiles", [])
        if not profiles:
            self.log("[info] Нет применённых профилей для отката.")
            return
        last = profiles.pop()
        self.log(f"=== UNDO {last.get('profile', '?').upper()} {last.get('timestamp', '')} ===")
        changes = last.get("changes", [])
        for ch in reversed(changes):
            if ch.get("type") == "registry":
                restore_reg_value(ch, self.log)
            elif ch.get("type") == "power_scheme":
                restore_power_scheme(ch, self.log)
            else:
                self.log(f"[warn] Unknown undo change: {ch.get('type')}")
        save_state(self.state)
        self.log("[done] Откат завершён.")

    def backup_only(self) -> None:
        self.run_in_thread(self.backup_only_impl)

    def backup_only_impl(self) -> None:
        backup_dir = make_profile_backup_dir("manual_backup")
        backup_configs(backup_dir, self.log)
        self.log(f"[done] Backup готов: {backup_dir}")

    def clear_shader_cache_confirmed(self) -> None:
        if messagebox:
            ok = messagebox.askyesno(
                APP_NAME,
                "Удалить Steam shader cache Rust?\n\n"
                "Если кэш битый — может помочь. Но первый запуск/прогрузка после удаления может временно фризить сильнее.",
            )
            if not ok:
                return
        self.run_in_thread(lambda: clear_shader_cache(self.log))

    def launch_and_monitor(self) -> None:
        def work():
            launch_rust_via_steam(self.log)
            monitor_priority(self.log, seconds=240)
        self.run_in_thread(work)

    # ----- Folder / file helpers -----
    def open_backup_folder(self) -> None:
        self.open_path(backup_root())

    def open_app_folder(self) -> None:
        self.open_path(app_dir())

    def open_path(self, p: Path) -> None:
        try:
            if is_windows():
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                self.log(str(p))
        except Exception as exc:
            self.log(f"[warn] Не смог открыть {p}: {exc}")

    def pick_rust_exe(self) -> None:
        if not filedialog:
            return
        p = filedialog.askopenfilename(title="Выбери RustClient.exe", filetypes=[("RustClient.exe", "RustClient.exe"), ("EXE", "*.exe")])
        if not p:
            return
        path = Path(p)
        if path.name.lower() != "rustclient.exe":
            if messagebox and not messagebox.askyesno(APP_NAME, "Это не RustClient.exe. Всё равно добавить GPU/FSE preference для этого exe?"):
                return
        changes: List[Dict[str, Any]] = []
        set_reg_value(
            "HKCU",
            r"Software\Microsoft\DirectX\UserGpuPreferences",
            str(path),
            "GpuPreference=2;",
            "REG_SZ",
            changes,
            self.log,
        )
        set_reg_value(
            "HKCU",
            r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
            str(path),
            "~ DISABLEDXMAXIMIZEDWINDOWEDMODE",
            "REG_SZ",
            changes,
            self.log,
        )
        record = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "profile": "manual_exe_preferences",
            "backup_dir": "",
            "changes": changes,
            "rust_exes": [str(path)],
        }
        self.state.setdefault("profiles", []).append(record)
        save_state(self.state)
        self.log(f"[done] Настройки для выбранного exe применены: {path}")
        self.refresh_status()


def main() -> int:
    if tk is None:
        print("Tkinter не найден. Установи Python с Tkinter или собери exe через PyInstaller на Windows.")
        return 1
    root = tk.Tk()
    OptimizerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
