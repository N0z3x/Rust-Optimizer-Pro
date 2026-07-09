#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rust FPS Optimizer Pro UI.

Modern CustomTkinter launcher-style interface over the safe backend from
RustFPSOptimizer.py.

Build:
    python -m pip install customtkinter psutil pyinstaller
    python -m PyInstaller --onefile --windowed --uac-admin --icon app.ico --add-data app.ico;. --collect-data customtkinter --hidden-import RustFPSOptimizer --hidden-import psutil --name RustFPSOptimizerPro RustFPSOptimizer_Pro.py
"""

from __future__ import annotations

import csv
import datetime as _dt
import os
import platform
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import customtkinter as ctk
except Exception as exc:  # pragma: no cover
    import tkinter as _tk
    from tkinter import messagebox as _messagebox

    root = _tk.Tk()
    root.withdraw()
    _messagebox.showerror(
        "Rust FPS Optimizer Pro",
        "Не установлена библиотека customtkinter.\n\n"
        "Запусти Run_Pro_Source_As_Admin.bat или установи вручную:\n"
        "python -m pip install customtkinter\n\n"
        f"Ошибка: {exc}",
    )
    raise SystemExit(1)

import tkinter as tk
from tkinter import filedialog, messagebox

# Backend lives in RustFPSOptimizer.py. Add the script folder explicitly so
# launching from another working directory or through an elevated PowerShell
# process still finds it.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    import RustFPSOptimizer as core
except ModuleNotFoundError as exc:
    if getattr(exc, "name", "") == "RustFPSOptimizer":
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Rust FPS Optimizer Pro",
            "Не найден backend-файл RustFPSOptimizer.py.\n\n"
            "Pro-версия должна лежать в одной папке с RustFPSOptimizer.py.\n"
            "Распакуй архив полностью, не вытаскивай один RustFPSOptimizer_Pro.py отдельно.\n\n"
            f"Папка запуска:\n{_SCRIPT_DIR}",
        )
        raise SystemExit(1)
    raise

PRO_VERSION = "1.0.0"
core.APP_VERSION = PRO_VERSION

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

# Pro palette
BG = "#070B14"
SIDEBAR = "#0B1220"
PANEL = "#101827"
PANEL_2 = "#131E31"
CARD = "#162238"
CARD_HOVER = "#1C2A43"
TEXT = "#E5E7EB"
MUTED = "#8FA3BF"
MUTED_2 = "#64748B"
BORDER = "#26334A"
BLUE = "#0EA5E9"
BLUE_2 = "#38BDF8"
GREEN = "#22C55E"
YELLOW = "#F59E0B"
RED = "#EF4444"
PURPLE = "#A855F7"
ORANGE = "#F97316"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def short_path(p: str, max_len: int = 72) -> str:
    if len(p) <= max_len:
        return p
    return p[:24] + "..." + p[-(max_len - 27):]


class ProApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.main_thread_id = threading.get_ident()
        self.state_data = core.load_state()
        self.ram_gb = core.get_total_ram_gb()
        self.busy = False
        self.spec_busy = False
        self.current_page = "dashboard"
        self.pages: Dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.action_buttons: List[ctk.CTkButton] = []
        self.pc_info: Dict[str, Any] = {}
        self.pc_report_text = ""
        self.current_tuning: Dict[str, Any] = {}
        self.tuning_report_text = ""
        self.tuning_target = tk.StringVar(value="balanced")
        self.exclusive_var = tk.BooleanVar(value=False)
        self.session_active = False
        self.session_changes: List[Dict[str, Any]] = []
        self.session_stop_event = threading.Event()
        self.session_profile_var = tk.StringVar(value="balanced")
        self.session_launch_var = tk.BooleanVar(value=True)
        self.session_priority_var = tk.BooleanVar(value=True)
        self.session_auto_restore_var = tk.BooleanVar(value=True)
        self.session_backup_var = tk.BooleanVar(value=True)
        self.session_close_browsers_var = tk.BooleanVar(value=False)
        self.session_close_recording_var = tk.BooleanVar(value=False)
        self.session_close_launchers_var = tk.BooleanVar(value=False)
        self.session_close_chat_var = tk.BooleanVar(value=False)
        self.session_force_close_var = tk.BooleanVar(value=False)
        self.monitor_active = False
        self.monitor_stop_event = threading.Event()
        self.monitor_samples: List[Dict[str, Any]] = []
        self.monitor_report_text = ""
        self.monitor_interval_var = tk.StringVar(value="2")
        self.monitor_auto_stop_var = tk.BooleanVar(value=True)
        self.monitor_auto_launch_var = tk.BooleanVar(value=False)
        self.cleaner_items: List[Dict[str, Any]] = []
        self.cleaner_vars: Dict[str, tk.BooleanVar] = {}
        self.config_files: List[Dict[str, Any]] = []
        self.config_snapshots: List[Dict[str, Any]] = []
        self.support_bundle: Dict[str, Any] = {}
        self.support_report_text = ""
        self.health_scan: Dict[str, Any] = {}
        self.health_report_text = ""

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"Rust FPS Optimizer Pro v{PRO_VERSION}")
        self.geometry("1240x800")
        self.minsize(1060, 680)
        self.configure(fg_color=BG)
        self._set_icon()

        self.grid_columnconfigure(0, minsize=245)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()
        self.show_page("dashboard")

        self.refresh_status()
        self.log(f"Rust FPS Optimizer Pro v{PRO_VERSION}")
        self.log("Не чит, не инжектор, EAC/игровую память не трогает.")
        self.log("Pro UI запущен. v1.0: добавлен Health Check / Auto Fix.")
        if not core.is_windows():
            self.log("[warn] Сейчас не Windows. Полный функционал рассчитан на Windows 10/11.")
        if self.state_data.get("active_session"):
            self.log("[warn] Найден незавершённый Game Session. Открой Game Session → Restore / End Session.")
            self.update_session_status("Найден незавершённый Game Session. Нажми Restore / End Session для отката.")

        self.after(450, self.refresh_specs_async)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------
    def _set_icon(self) -> None:
        try:
            ico = resource_path("app.ico")
            if ico.exists():
                self.iconbitmap(str(ico))
        except Exception:
            pass

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_rowconfigure(8, weight=1)

        logo_box = ctk.CTkFrame(side, fg_color="transparent")
        logo_box.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 16))

        logo = tk.Canvas(logo_box, width=58, height=58, bg=SIDEBAR, highlightthickness=0, bd=0)
        logo.pack(side="left", padx=(0, 12))
        logo.create_oval(4, 4, 54, 54, fill=BLUE, outline=BLUE_2, width=2)
        logo.create_text(29, 29, text="R", fill="white", font=("Segoe UI", 28, "bold"))
        logo.create_polygon(42, 7, 30, 31, 41, 31, 29, 55, 55, 24, 43, 24, fill=ORANGE, outline="")

        title = ctk.CTkFrame(logo_box, fg_color="transparent")
        title.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title, text="Rust FPS", text_color=TEXT, font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ctk.CTkLabel(title, text="Optimizer Pro", text_color=MUTED, font=("Segoe UI", 11)).pack(anchor="w")

        self.admin_badge = ctk.CTkLabel(
            side,
            text="checking...",
            fg_color=CARD,
            text_color=TEXT,
            corner_radius=10,
            height=34,
            font=("Segoe UI", 12, "bold"),
        )
        self.admin_badge.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 14))

        nav = [
            ("dashboard", "⌂  Главная"),
            ("health", "🛡  Health Check"),
            ("opt", "⚡  Оптимизация"),
            ("session", "🚀  Game Session"),
            ("monitor", "📈  Stutter Monitor"),
            ("cleaner", "🧹  Cleaner / Repair"),
            ("config", "🗂  Config Manager"),
            ("reports", "📋  Report Center"),
            ("tuning", "🎛  Rust Settings"),
            ("specs", "🖥  ПК / Железо"),
            ("launch", "▶  Launch Options"),
            ("logs", "▣  Бэкапы / Лог"),
        ]
        for idx, (page, label) in enumerate(nav, start=2):
            btn = ctk.CTkButton(
                side,
                text=label,
                command=lambda p=page: self.show_page(p),
                height=42,
                corner_radius=12,
                fg_color="transparent",
                hover_color=CARD,
                text_color=MUTED,
                anchor="w",
                font=("Segoe UI", 13, "bold"),
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=14, pady=4)
            self.nav_buttons[page] = btn

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        bottom.grid(row=9, column=0, sticky="sew", padx=18, pady=(12, 18))
        ctk.CTkLabel(bottom, text=f"v{PRO_VERSION}", text_color=MUTED_2, font=("Segoe UI", 11)).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            bottom,
            text="Safe Windows tweaks\nNo injection • No EAC bypass",
            text_color=MUTED_2,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w")

    def _build_main_area(self) -> None:
        self.main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self.main, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        self.header.grid_columnconfigure(0, weight=1)

        self.page_title = ctk.CTkLabel(self.header, text="", text_color=TEXT, font=("Segoe UI", 28, "bold"))
        self.page_title.grid(row=0, column=0, sticky="w")
        self.page_subtitle = ctk.CTkLabel(self.header, text="", text_color=MUTED, font=("Segoe UI", 12))
        self.page_subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.header_status = ctk.CTkLabel(
            self.header,
            text="",
            fg_color=PANEL,
            text_color=MUTED,
            corner_radius=12,
            height=38,
            padx=14,
            font=("Segoe UI", 11, "bold"),
        )
        self.header_status.grid(row=0, column=1, rowspan=2, sticky="e")

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(4, 20))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.pages["dashboard"] = self._page_dashboard(self.content)
        self.pages["health"] = self._page_health_check(self.content)
        self.pages["opt"] = self._page_optimization(self.content)
        self.pages["session"] = self._page_session(self.content)
        self.pages["monitor"] = self._page_monitor(self.content)
        self.pages["cleaner"] = self._page_cleaner(self.content)
        self.pages["config"] = self._page_config_manager(self.content)
        self.pages["reports"] = self._page_report_center(self.content)
        self.pages["tuning"] = self._page_tuning(self.content)
        self.pages["specs"] = self._page_specs(self.content)
        self.pages["launch"] = self._page_launch(self.content)
        self.pages["logs"] = self._page_logs(self.content)

    def card(self, parent, title: str = "", subtitle: str = "", color: str = BLUE, **grid_kwargs) -> ctk.CTkFrame:
        wrapper = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER)
        if grid_kwargs:
            wrapper.grid(**grid_kwargs)
        inner = ctk.CTkFrame(wrapper, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=15)
        if title:
            top = ctk.CTkFrame(inner, fg_color="transparent")
            top.pack(fill="x", pady=(0, 8))
            ctk.CTkFrame(top, width=4, height=26, fg_color=color, corner_radius=4).pack(side="left", padx=(0, 10))
            text_box = ctk.CTkFrame(top, fg_color="transparent")
            text_box.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text_box, text=title, text_color=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(text_box, text=subtitle, text_color=MUTED, font=("Segoe UI", 10), wraplength=660, justify="left").pack(anchor="w")
        wrapper.inner = inner  # type: ignore[attr-defined]
        return wrapper

    def _page_dashboard(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(2, weight=1)

        hero = ctk.CTkFrame(page, fg_color=PANEL, corner_radius=22, border_width=1, border_color=BORDER)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(hero, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ew", padx=20, pady=18)
        ctk.CTkLabel(left, text="Стабильнее Rust без мутных твиков", text_color=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ctk.CTkLabel(left, text="Профили Windows, диагностика железа, launch options и быстрый откат.", text_color=MUTED, font=("Segoe UI", 12)).pack(anchor="w", pady=(4, 0))
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(anchor="w", pady=(16, 0))
        b = ctk.CTkButton(btn_row, text="Применить SAFE", height=38, fg_color=GREEN, hover_color="#16A34A", command=lambda: self.run_profile("safe"))
        b.pack(side="left", padx=(0, 10))
        self.action_buttons.append(b)
        b = ctk.CTkButton(btn_row, text="Health Check", height=38, fg_color=BLUE, hover_color="#0284C7", command=lambda: self.show_page("health"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Скан ПК", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=self.refresh_specs_async)
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Подобрать Rust настройки", height=38, fg_color=PURPLE, hover_color="#9333EA", command=lambda: self.show_page("tuning"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Game Session", height=38, fg_color=ORANGE, hover_color="#EA580C", command=lambda: self.show_page("session"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Stutter Monitor", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("monitor"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Cleaner", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("cleaner"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Config Manager", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("config"))
        b.pack(side="left", padx=(0, 10))
        b = ctk.CTkButton(btn_row, text="Report Center", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("reports"))
        b.pack(side="left")

        self.status_card = self.card(page, "Статус", "Rust, права, RAM и пути", BLUE, row=1, column=0, sticky="nsew", padx=(0, 7), pady=(0, 14))
        self.home_status_text = ctk.CTkLabel(self.status_card.inner, text="Сканирую...", text_color=TEXT, font=("Consolas", 11), justify="left", anchor="w")
        self.home_status_text.pack(fill="x", pady=(4, 8))
        ctk.CTkButton(self.status_card.inner, text="Обновить", width=120, fg_color=CARD, hover_color=CARD_HOVER, command=self.refresh_status).pack(anchor="w")

        quick = self.card(page, "Быстрые действия", "Для FPS и статтеров", GREEN, row=1, column=1, sticky="nsew", padx=(7, 0), pady=(0, 14))
        qrow = ctk.CTkFrame(quick.inner, fg_color="transparent")
        qrow.pack(fill="x", pady=(4, 8))
        for text, profile, color in [("SAFE", "safe", GREEN), ("BALANCED", "balanced", BLUE), ("AGGRESSIVE", "aggressive", RED)]:
            b = ctk.CTkButton(qrow, text=text, width=118, height=36, fg_color=color, command=lambda p=profile: self.run_profile(p))
            b.pack(side="left", padx=(0, 8))
            self.action_buttons.append(b)
        qrow2 = ctk.CTkFrame(quick.inner, fg_color="transparent")
        qrow2.pack(fill="x")
        b = ctk.CTkButton(qrow2, text="Запустить Rust + High priority", height=36, fg_color=CARD, hover_color=CARD_HOVER, command=self.launch_and_monitor)
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)
        b = ctk.CTkButton(qrow2, text="Откат последнего", height=36, fg_color=CARD, hover_color=CARD_HOVER, command=self.undo_last)
        b.pack(side="left")
        self.action_buttons.append(b)

        reco = self.card(page, "Рекомендации по твоему ПК", "Автоматически после скана железа", YELLOW, row=2, column=0, columnspan=2, sticky="nsew")
        self.reco_box = ctk.CTkTextbox(reco.inner, fg_color="#08101F", text_color=TEXT, font=("Segoe UI", 12), wrap="word")
        self.reco_box.pack(fill="both", expand=True)
        self.set_textbox(self.reco_box, "Пока нет данных. Нажми «Скан ПК» или открой вкладку ПК / Железо.")
        return page

    def _page_health_check(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(1, weight=1)

        hero = self.card(
            page,
            "Health Check",
            "Проверяет Windows/Rust/RAM/диск/Game Mode/DVR/backups/фоновые приложения и даёт безопасный Fix.",
            GREEN,
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )
        top = ctk.CTkFrame(hero.inner, fg_color="transparent")
        top.pack(fill="x")
        self.health_score_label = ctk.CTkLabel(top, text="—/100", text_color=TEXT, font=("Segoe UI", 34, "bold"))
        self.health_score_label.pack(side="left", padx=(0, 18))
        status_box = ctk.CTkFrame(top, fg_color="transparent")
        status_box.pack(side="left", fill="x", expand=True)
        self.health_status_label = ctk.CTkLabel(status_box, text="Нажми Scan Health.", text_color=TEXT, font=("Segoe UI", 13, "bold"), anchor="w", justify="left")
        self.health_status_label.pack(anchor="w")
        ctk.CTkLabel(status_box, text="Auto Fix применяет только безопасные обратимые фиксы: cfg snapshot + Game Mode + Xbox DVR OFF + GPU preference.", text_color=MUTED, font=("Segoe UI", 10), wraplength=720, justify="left").pack(anchor="w", pady=(4, 0))
        btns = ctk.CTkFrame(hero.inner, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btns, text="Scan Health", fg_color=BLUE, hover_color="#0284C7", command=self.scan_health_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Auto Fix Safe Issues", fg_color=GREEN, hover_color="#16A34A", command=self.apply_health_safe_fixes_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Copy Report", fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_health_report).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Open Cleaner", fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("cleaner")).pack(side="left")

        left = self.card(page, "Issues", "BAD/WARN/INFO/OK", BLUE, row=1, column=0, sticky="nsew", padx=(0, 8))
        self.health_scroll = ctk.CTkScrollableFrame(left.inner, fg_color="#08101F", corner_radius=12)
        self.health_scroll.pack(fill="both", expand=True)

        right = self.card(page, "Health report", "Можно скопировать или добавить в Support Bundle", YELLOW, row=1, column=1, sticky="nsew", padx=(8, 0))
        self.health_report_box = ctk.CTkTextbox(right.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.health_report_box.pack(fill="both", expand=True)
        self.set_textbox(self.health_report_box, "Health Check пока не запускался.\n")
        self.after(500, self.scan_health_async)
        return page

    def _page_optimization(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        for col in (0, 1, 2):
            page.grid_columnconfigure(col, weight=1)
        page.grid_rowconfigure(1, weight=1)

        profiles = [
            ("SAFE", "safe", GREEN, "Минимум риска", ["Backup cfg", "Очистка логов", "Game Mode", "Xbox DVR OFF", "GPU preference"]),
            ("BALANCED", "balanced", BLUE, "Оптимально на каждый день", ["Всё из SAFE", "High Performance", "Fullscreen optimizations OFF", "High priority helper"]),
            ("AGGRESSIVE", "aggressive", RED, "Максимум FPS", ["Всё из BALANCED", "Ultimate Performance", "GameDVR/FSE flags", "HAGS", "Transparency OFF"]),
        ]
        for col, (title, profile, color, sub, bullets) in enumerate(profiles):
            card = self.card(page, title, sub, color, row=0, column=col, sticky="nsew", padx=7, pady=(0, 14))
            for bullet in bullets:
                ctk.CTkLabel(card.inner, text="• " + bullet, text_color=TEXT, font=("Segoe UI", 12), anchor="w", justify="left").pack(anchor="w", pady=2)
            b = ctk.CTkButton(card.inner, text=f"Применить {title}", height=40, fg_color=color, command=lambda p=profile: self.run_profile(p))
            b.pack(anchor="w", pady=(15, 0))
            self.action_buttons.append(b)

        tools = self.card(page, "Инструменты", "Откат, backup, shader cache, ручной exe", PURPLE, row=1, column=0, columnspan=3, sticky="nsew")
        row = ctk.CTkFrame(tools.inner, fg_color="transparent")
        row.pack(fill="x", pady=(2, 10))
        actions = [
            ("Откатить последний профиль", self.undo_last, RED),
            ("Backup cfg", self.backup_only, CARD),
            ("Очистить shader cache", self.clear_shader_cache_confirmed, RED),
            ("Выбрать RustClient.exe", self.pick_rust_exe, CARD),
            ("Перезапуск от админа", core.restart_as_admin, CARD),
        ]
        for text, cmd, color in actions:
            hover = CARD_HOVER if color == CARD else ("#DC2626" if color == RED else "#0284C7")
            b = ctk.CTkButton(row, text=text, height=36, fg_color=color, hover_color=hover, command=cmd)
            b.pack(side="left", padx=(0, 8), pady=4)
            self.action_buttons.append(b)
        self.opt_status_label = ctk.CTkLabel(tools.inner, text="", text_color=MUTED, font=("Consolas", 10), justify="left", anchor="w")
        self.opt_status_label.pack(fill="x", pady=(8, 0))
        return page

    def _page_session(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(2, weight=1)

        hero = self.card(page, "Game Session Mode", "Временный игровой режим: включает профиль, запускает Rust, ставит High priority и откатывает изменения после выхода.", ORANGE, row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.session_status_label = ctk.CTkLabel(hero.inner, text="Готово к запуску сессии.", text_color=TEXT, font=("Segoe UI", 12), justify="left", anchor="w", wraplength=900)
        self.session_status_label.pack(fill="x", pady=(0, 10))
        btns = ctk.CTkFrame(hero.inner, fg_color="transparent")
        btns.pack(fill="x")
        self.session_start_btn = ctk.CTkButton(btns, text="🚀 Start Game Session", height=40, fg_color=GREEN, hover_color="#16A34A", command=self.start_game_session)
        self.session_start_btn.pack(side="left", padx=(0, 8))
        self.session_end_btn = ctk.CTkButton(btns, text="Restore / End Session", height=40, fg_color=RED, hover_color="#DC2626", command=self.end_game_session)
        self.session_end_btn.pack(side="left", padx=(0, 8))
        self.action_buttons.append(self.session_start_btn)
        self.action_buttons.append(self.session_end_btn)
        ctk.CTkButton(btns, text="Открыть Launch Options", height=40, fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.show_page("launch")).pack(side="left")

        profile = self.card(page, "Профиль на время сессии", "Изменения будут записаны как active session и восстановятся после выхода из Rust.", BLUE, row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        self.session_profile_buttons: Dict[str, ctk.CTkButton] = {}
        prow = ctk.CTkFrame(profile.inner, fg_color="transparent")
        prow.pack(fill="x", pady=(0, 8))
        for prof, label, color in [("safe", "SAFE", GREEN), ("balanced", "BALANCED", BLUE), ("aggressive", "AGGRESSIVE", RED)]:
            b = ctk.CTkButton(prow, text=label, width=120, height=36, fg_color=CARD, hover_color=CARD_HOVER, command=lambda p=prof: self.set_session_profile(p))
            b.pack(side="left", padx=(0, 8))
            self.session_profile_buttons[prof] = b
        self.update_session_profile_buttons()
        ctk.CTkLabel(profile.inner, text="Совет: для обычной игры ставь BALANCED. AGGRESSIVE может требовать перезагрузку и лучше для тестов/макс FPS.", text_color=MUTED, font=("Segoe UI", 11), wraplength=430, justify="left").pack(anchor="w", pady=(6, 0))

        options = self.card(page, "Опции сессии", "Что делать перед запуском и во время игры", PURPLE, row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        opts_grid = ctk.CTkFrame(options.inner, fg_color="transparent")
        opts_grid.pack(fill="x")
        ctk.CTkCheckBox(opts_grid, text="Запустить Rust через Steam", variable=self.session_launch_var, text_color=TEXT).grid(row=0, column=0, sticky="w", padx=(0, 18), pady=4)
        ctk.CTkCheckBox(opts_grid, text="High priority во время запуска", variable=self.session_priority_var, text_color=TEXT).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)
        ctk.CTkCheckBox(opts_grid, text="Авто-откат после выхода из Rust", variable=self.session_auto_restore_var, text_color=TEXT).grid(row=1, column=0, sticky="w", padx=(0, 18), pady=4)
        ctk.CTkCheckBox(opts_grid, text="Backup cfg перед сессией", variable=self.session_backup_var, text_color=TEXT).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=4)

        bg = self.card(page, "Фоновые приложения", "Закрытие мягкое: через CloseMainWindow. Force — только если сам включишь.", YELLOW, row=2, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkCheckBox(bg.inner, text="Браузеры: Chrome/Edge/Firefox/Opera/Brave", variable=self.session_close_browsers_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(bg.inner, text="OBS/Streamlabs/Bandicam/XSplit", variable=self.session_close_recording_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(bg.inner, text="Лишние лаунчеры: Epic/Battle.net/Riot/EA/GOG", variable=self.session_close_launchers_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(bg.inner, text="Discord/Telegram/Skype (осторожно)", variable=self.session_close_chat_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(bg.inner, text="Force close оставшихся процессов", variable=self.session_force_close_var, text_color=RED).pack(anchor="w", pady=(14, 4))
        ctk.CTkLabel(bg.inner, text="Не закрываю Steam и EAC. Discord по умолчанию выключен, чтобы не выкинуть тебя из войса.", text_color=MUTED, font=("Segoe UI", 10), wraplength=430, justify="left").pack(anchor="w", pady=(8, 0))

        log_card = self.card(page, "Session Log", "Статус запуска, мониторинг RustClient.exe и откат", GREEN, row=2, column=1, sticky="nsew", padx=(8, 0))
        self.session_log_box = ctk.CTkTextbox(log_card.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.session_log_box.pack(fill="both", expand=True)
        self.set_textbox(self.session_log_box, "Game Session пока не запускался.\n")
        return page

    def _page_monitor(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(2, weight=1)

        hero = self.card(
            page,
            "Stutter Monitor",
            "Без оверлея и инжекта: CPU/RAM/Disk/Rust process telemetry → анализ причин фризов.",
            BLUE,
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )
        self.monitor_status_label = ctk.CTkLabel(
            hero.inner,
            text="Готов к мониторингу. Лучше запускать перед заходом на сервер и остановить после фризов/катки.",
            text_color=TEXT,
            font=("Segoe UI", 12),
            justify="left",
            anchor="w",
            wraplength=900,
        )
        self.monitor_status_label.pack(fill="x", pady=(0, 10))
        controls = ctk.CTkFrame(hero.inner, fg_color="transparent")
        controls.pack(fill="x")
        self.monitor_start_btn = ctk.CTkButton(controls, text="Start Monitor", height=38, fg_color=GREEN, hover_color="#16A34A", command=lambda: self.start_stutter_monitor(False))
        self.monitor_start_btn.pack(side="left", padx=(0, 8))
        self.monitor_launch_btn = ctk.CTkButton(controls, text="Start Rust + Monitor", height=38, fg_color=BLUE, hover_color="#0284C7", command=lambda: self.start_stutter_monitor(True))
        self.monitor_launch_btn.pack(side="left", padx=(0, 8))
        self.monitor_stop_btn = ctk.CTkButton(controls, text="Stop + Analyze", height=38, fg_color=RED, hover_color="#DC2626", command=self.stop_stutter_monitor)
        self.monitor_stop_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="Save CSV", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=self.save_monitor_csv).pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="Copy Report", height=38, fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_monitor_report).pack(side="left")
        self.action_buttons.extend([self.monitor_start_btn, self.monitor_launch_btn, self.monitor_stop_btn])

        live = self.card(page, "Live metrics", "Обновляется раз в выбранный интервал", GREEN, row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        metric_grid = ctk.CTkFrame(live.inner, fg_color="transparent")
        metric_grid.pack(fill="x")
        self.monitor_metric_labels: Dict[str, ctk.CTkLabel] = {}
        metrics = [
            ("cpu", "CPU", BLUE),
            ("ram", "RAM", PURPLE),
            ("disk", "Disk I/O", YELLOW),
            ("rust", "Rust RAM", ORANGE),
            ("samples", "Samples", GREEN),
        ]
        for idx, (key, title, color) in enumerate(metrics):
            box = ctk.CTkFrame(metric_grid, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
            box.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 8, 0), pady=2)
            metric_grid.grid_columnconfigure(idx, weight=1)
            ctk.CTkLabel(box, text=title, text_color=MUTED, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
            lbl = ctk.CTkLabel(box, text="—", text_color=TEXT, font=("Segoe UI", 18, "bold"))
            lbl.pack(anchor="w", padx=12, pady=(2, 10))
            self.monitor_metric_labels[key] = lbl

        options = self.card(page, "Опции", "Мониторинг безопасный: не читает FPS и не внедряется в игру", PURPLE, row=2, column=0, sticky="nsew", padx=(0, 8))
        optrow = ctk.CTkFrame(options.inner, fg_color="transparent")
        optrow.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(optrow, text="Интервал:", text_color=MUTED, font=("Segoe UI", 12, "bold")).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(optrow, variable=self.monitor_interval_var, values=["1", "2", "3", "5"], width=90).pack(side="left")
        ctk.CTkLabel(optrow, text="сек", text_color=MUTED, font=("Segoe UI", 12)).pack(side="left", padx=(6, 0))
        ctk.CTkCheckBox(options.inner, text="Авто-стоп после закрытия RustClient.exe", variable=self.monitor_auto_stop_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(options.inner, text="Автозапуск Rust при обычном Start Monitor", variable=self.monitor_auto_launch_var, text_color=TEXT).pack(anchor="w", pady=4)
        ctk.CTkLabel(
            options.inner,
            text="Что ловит: пики CPU, нехватку RAM, активность диска, рост памяти Rust. FPS/frametime напрямую не читаем, чтобы не лезть в игру/EAC.",
            text_color=MUTED,
            font=("Segoe UI", 11),
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        ctk.CTkButton(options.inner, text="Открыть папку отчётов", fg_color=CARD, hover_color=CARD_HOVER, command=self.open_monitor_folder).pack(anchor="w", pady=(14, 0))

        report = self.card(page, "Analysis Report", "После Stop + Analyze здесь будет вывод по вероятным причинам фризов", YELLOW, row=2, column=1, sticky="nsew", padx=(8, 0))
        self.monitor_report_box = ctk.CTkTextbox(report.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.monitor_report_box.pack(fill="both", expand=True)
        self.set_textbox(self.monitor_report_box, "Мониторинг пока не запускался.\n")
        return page

    def _page_cleaner(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        hero = self.card(
            page,
            "Cleaner / Repair Center",
            "Чистит только известные кэши/логи Rust/Windows и старые отчёты оптимизатора. Никаких рандомных системных удалений.",
            ORANGE,
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )
        self.cleaner_status_label = ctk.CTkLabel(
            hero.inner,
            text="Нажми Scan, выбери что чистить, потом Clean selected.",
            text_color=TEXT,
            font=("Segoe UI", 12),
            justify="left",
            anchor="w",
            wraplength=900,
        )
        self.cleaner_status_label.pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(hero.inner, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Scan junk", fg_color=BLUE, hover_color="#0284C7", command=self.scan_cleaner_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Clean selected", fg_color=RED, hover_color="#DC2626", command=self.clean_selected_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Steam Validate Rust", fg_color=GREEN, hover_color="#16A34A", command=lambda: core.open_steam_validate_rust(self.log)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open Rust LocalLow", fg_color=CARD, hover_color=CARD_HOVER, command=self.open_rust_locallow).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open backups", fg_color=CARD, hover_color=CARD_HOVER, command=self.open_backup_folder).pack(side="left")

        left = self.card(page, "Cleanup targets", "Safe = обычные логи/отчёты. Medium = кэши, после очистки первая прогрузка может быть дольше.", BLUE, row=1, column=0, sticky="nsew", padx=(0, 8))
        self.cleaner_scroll = ctk.CTkScrollableFrame(left.inner, fg_color="#08101F", corner_radius=12)
        self.cleaner_scroll.pack(fill="both", expand=True)

        right = self.card(page, "Cleaner log / repair tips", "После очистки тут будет результат", YELLOW, row=1, column=1, sticky="nsew", padx=(8, 0))
        self.cleaner_log_box = ctk.CTkTextbox(right.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.cleaner_log_box.pack(fill="both", expand=True)
        self.set_textbox(
            self.cleaner_log_box,
            "Cleaner пока не сканировал систему.\n\n"
            "Рекомендация:\n"
            "• Rust logs/crash dumps — можно чистить часто.\n"
            "• Rust shader cache / DirectX cache — чистить только если есть странные фризы/после обновлений драйвера.\n"
            "• После очистки shader cache первая загрузка может фризить, пока кэш пересобирается.\n",
        )
        self.after(700, self.scan_cleaner_async)
        return page

    def _page_config_manager(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        hero = self.card(
            page,
            "Rust Config Manager",
            "Безопасные snapshots cfg-файлов: backup, restore, export ZIP и запись human-readable рекомендаций без изменения игровых команд.",
            PURPLE,
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )
        self.config_status_label = ctk.CTkLabel(
            hero.inner,
            text="Нажми Scan configs или Create snapshot. Restore возвращает cfg-файлы из выбранного snapshot.",
            text_color=TEXT,
            font=("Segoe UI", 12),
            justify="left",
            anchor="w",
            wraplength=920,
        )
        self.config_status_label.pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(hero.inner, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Scan configs", fg_color=BLUE, hover_color="#0284C7", command=self.scan_config_manager_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Create snapshot", fg_color=GREEN, hover_color="#16A34A", command=self.create_config_snapshot_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Write recommended TXT", fg_color=PURPLE, hover_color="#9333EA", command=self.write_recommended_config_note).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open cfg folder", fg_color=CARD, hover_color=CARD_HOVER, command=self.open_first_cfg_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open snapshots", fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.open_path(core.config_backups_root())).pack(side="left")

        left = self.card(page, "Detected cfg files", "Файлы Rust cfg/json/txt/xml, найденные в cfg-папках", BLUE, row=1, column=0, sticky="nsew", padx=(0, 8))
        self.config_files_scroll = ctk.CTkScrollableFrame(left.inner, fg_color="#08101F", corner_radius=12)
        self.config_files_scroll.pack(fill="both", expand=True)

        right = self.card(page, "Snapshots", "Backup/restore/export cfg snapshots", GREEN, row=1, column=1, sticky="nsew", padx=(8, 0))
        self.config_snapshots_scroll = ctk.CTkScrollableFrame(right.inner, fg_color="#08101F", corner_radius=12)
        self.config_snapshots_scroll.pack(fill="both", expand=True)
        self.after(900, self.scan_config_manager_async)
        return page

    def _page_report_center(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(1, weight=1)

        hero = self.card(
            page,
            "Report Center / Support Bundle",
            "Собирает ПК-отчёт, Rust Settings, Cleaner scan, Config summary и последний Stutter Monitor report в HTML + ZIP.",
            BLUE,
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 12),
        )
        self.report_status_label = ctk.CTkLabel(
            hero.inner,
            text="Нажми Create Support Bundle. Получишь HTML-отчёт и ZIP, который можно скинуть другу/мастеру/мне для диагностики.",
            text_color=TEXT,
            font=("Segoe UI", 12),
            justify="left",
            anchor="w",
            wraplength=920,
        )
        self.report_status_label.pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(hero.inner, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Create Support Bundle", fg_color=GREEN, hover_color="#16A34A", command=self.create_support_bundle_async).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open HTML", fg_color=BLUE, hover_color="#0284C7", command=self.open_support_html).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Open reports folder", fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.open_path(core.reports_root())).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Copy summary", fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_support_summary).pack(side="left")

        left = self.card(page, "Bundle contents", "Что попадёт в отчёт", PURPLE, row=1, column=0, sticky="nsew", padx=(0, 8))
        content = (
            "• support_report.html — красивый HTML-отчёт\n"
            "• pc_report.txt — полный отчёт по ПК\n"
            "• health_check.txt — Health Check score/issues\n"
            "• rust_settings.txt — рекомендации Rust Settings\n"
            "• latest_stutter_report.txt — последний Stutter Monitor report\n"
            "• cleaner_scan.json — найденные логи/кэши\n"
            "• config_files.json — список cfg-файлов\n"
            "• config_snapshots.json — список snapshots\n"
            "• state_summary.json — только краткая сводка state, без registry details\n\n"
            "Личные Steam-токены/пароли не собираются. Registry backup values в bundle не кладутся."
        )
        ctk.CTkLabel(left.inner, text=content, text_color=TEXT, font=("Segoe UI", 12), justify="left", wraplength=420).pack(anchor="w")
        ctk.CTkButton(left.inner, text="Open latest ZIP", fg_color=CARD, hover_color=CARD_HOVER, command=self.open_support_zip_folder).pack(anchor="w", pady=(16, 0))

        right = self.card(page, "Preview / Summary", "После создания bundle тут будет краткая сводка", YELLOW, row=1, column=1, sticky="nsew", padx=(8, 0))
        self.report_box = ctk.CTkTextbox(right.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.report_box.pack(fill="both", expand=True)
        self.set_textbox(self.report_box, "Support Bundle пока не создан.\n")
        return page

    def _page_tuning(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(page, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)
        self.tuning_status_label = ctk.CTkLabel(
            top,
            text="Выбери цель и нажми «Подобрать настройки». Если скан ПК ещё не готов — сделаю его автоматически.",
            text_color=MUTED,
            font=("Segoe UI", 12),
        )
        self.tuning_status_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Подобрать настройки", fg_color=BLUE, command=self.generate_tuning_async).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(top, text="Скопировать Launch", fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_tuning_launch).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(top, text="Скопировать всё", fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_tuning_report).grid(row=0, column=3, padx=(8, 0))

        target_card = self.card(page, "Цель пресета", "Max FPS / Balanced / Quality / Streamer", PURPLE, row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self.tuning_target_buttons: Dict[str, ctk.CTkButton] = {}
        row = ctk.CTkFrame(target_card.inner, fg_color="transparent")
        row.pack(fill="x")
        targets = [
            ("max_fps", "Max FPS", RED),
            ("balanced", "Balanced", BLUE),
            ("quality", "Quality", PURPLE),
            ("streamer", "Streamer", GREEN),
        ]
        for target, label, color in targets:
            b = ctk.CTkButton(row, text=label, width=135, height=36, fg_color=CARD, hover_color=CARD_HOVER, command=lambda t=target: self.set_tuning_target(t))
            b.pack(side="left", padx=(0, 8))
            self.tuning_target_buttons[target] = b
        self.update_tuning_target_buttons()

        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        summary = self.card(left, "Итог подбора", "Профиль, bottleneck и launch options", BLUE, row=0, column=0, sticky="ew", pady=(0, 12))
        self.tuning_summary_label = ctk.CTkLabel(summary.inner, text="Пока нет расчёта.", text_color=TEXT, font=("Segoe UI", 12), justify="left", anchor="w", wraplength=650)
        self.tuning_summary_label.pack(fill="x", pady=(0, 10))
        self.tuning_launch_entry = ctk.CTkEntry(summary.inner, height=38, font=("Consolas", 12), fg_color="#08101F", border_color=BORDER)
        self.tuning_launch_entry.pack(fill="x", pady=(0, 10))
        action_row = ctk.CTkFrame(summary.inner, fg_color="transparent")
        action_row.pack(fill="x")
        self.apply_recommended_btn = ctk.CTkButton(action_row, text="Применить рекомендованный профиль", fg_color=GREEN, command=self.apply_recommended_profile)
        self.apply_recommended_btn.pack(side="left", padx=(0, 8))
        self.action_buttons.append(self.apply_recommended_btn)
        ctk.CTkButton(action_row, text="Сохранить .txt", fg_color=CARD, hover_color=CARD_HOVER, command=self.save_tuning_report).pack(side="left")

        settings_wrap = self.card(left, "Настройки Rust", "Ориентир для меню Graphics / Mesh / Image Effects", GREEN, row=1, column=0, sticky="nsew")
        self.tuning_settings_scroll = ctk.CTkScrollableFrame(settings_wrap.inner, fg_color="#08101F", corner_radius=12)
        self.tuning_settings_scroll.pack(fill="both", expand=True)

        report = self.card(page, "Полный отчёт", "Можно скопировать и сохранить", YELLOW, row=2, column=1, sticky="nsew", padx=(8, 0))
        self.tuning_report_box = ctk.CTkTextbox(report.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.tuning_report_box.pack(fill="both", expand=True)
        self.set_textbox(self.tuning_report_box, "Нажми «Подобрать настройки».")
        return page

    def _page_specs(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(page, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        top.grid_columnconfigure(0, weight=1)
        self.spec_status_label = ctk.CTkLabel(top, text="Нажми «Обновить сборку ПК».", text_color=MUTED, font=("Segoe UI", 12))
        self.spec_status_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Обновить сборку ПК", fg_color=BLUE, command=self.refresh_specs_async).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(top, text="Скопировать отчёт", fg_color=CARD, hover_color=CARD_HOVER, command=self.copy_pc_report).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(top, text="Сохранить .txt", fg_color=CARD, hover_color=CARD_HOVER, command=self.save_pc_report).grid(row=0, column=3, padx=(8, 0))

        self.spec_scroll = ctk.CTkScrollableFrame(page, fg_color=PANEL, corner_radius=18, border_width=1, border_color=BORDER)
        self.spec_scroll.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.spec_scroll.grid_columnconfigure(0, weight=1)

        report = self.card(page, "Отчёт / советы", "Можно скопировать и скинуть для диагностики", BLUE, row=1, column=1, sticky="nsew", padx=(8, 0))
        self.pc_report_box = ctk.CTkTextbox(report.inner, fg_color="#08101F", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.pc_report_box.pack(fill="both", expand=True)
        self.set_textbox(self.pc_report_box, "Отчёт пока не собран.")
        return page

    def _page_launch(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)

        opts = self.card(page, "Steam Launch Options", "Steam → Library → Rust → Properties → Launch Options", BLUE, row=0, column=0, sticky="ew", pady=(0, 14))
        row = ctk.CTkFrame(opts.inner, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        ctk.CTkCheckBox(row, text="добавить -window-mode exclusive", variable=self.exclusive_var, command=self.update_launch_options, text_color=TEXT).pack(side="left", padx=(0, 12))
        for text, profile, color in [("SAFE", "safe", GREEN), ("BALANCED", "balanced", BLUE), ("AGGRESSIVE", "aggressive", RED)]:
            ctk.CTkButton(row, text=text, width=110, fg_color=color, command=lambda p=profile: self.copy_launch(p)).pack(side="left", padx=(0, 8))

        self.launch_var = tk.StringVar(value="")
        self.launch_entry = ctk.CTkEntry(opts.inner, textvariable=self.launch_var, height=42, font=("Consolas", 13), fg_color="#08101F", border_color=BORDER)
        self.launch_entry.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(opts.inner, text="Если после -gc.buffer хуже — уменьши значение или оставь только -nolog. Exclusive может улучшить FPS, но Alt+Tab иногда хуже.", text_color=MUTED, font=("Segoe UI", 11), wraplength=900, justify="left").pack(anchor="w")

        launch = self.card(page, "Запуск и приоритет", "High priority — обычный приоритет процесса Windows, не инжект и не EAC bypass", GREEN, row=1, column=0, sticky="ew", pady=(0, 14))
        row2 = ctk.CTkFrame(launch.inner, fg_color="transparent")
        row2.pack(fill="x")
        b = ctk.CTkButton(row2, text="Запустить Rust через Steam + High priority", fg_color=GREEN, command=self.launch_and_monitor)
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)
        b = ctk.CTkButton(row2, text="High priority сейчас", fg_color=CARD, hover_color=CARD_HOVER, command=lambda: self.run_in_thread(lambda: core.set_rust_priority_high(self.log)))
        b.pack(side="left", padx=(0, 8))
        self.action_buttons.append(b)

        guide = self.card(page, "Мини-гайд для Rust", "Что чаще всего даёт результат", YELLOW, row=2, column=0, sticky="nsew")
        text = (
            "• Rust желательно держать на SSD/NVMe.\n"
            "• 16 GB RAM — минимум, 32 GB комфортнее для больших серверов.\n"
            "• Закрой браузер, Discord stream, ShadowPlay Instant Replay, OBS replay buffer.\n"
            "• В игре первыми режь Shadows, Water, Grass, Object Quality/Draw Distance.\n"
            "• После очистки shader cache первая загрузка может фризить сильнее — кэш пересобирается."
        )
        ctk.CTkLabel(guide.inner, text=text, text_color=TEXT, font=("Segoe UI", 13), justify="left", anchor="w").pack(anchor="w")
        return page

    def _page_logs(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        for text, cmd, color in [
            ("Открыть папку бэкапов", self.open_backup_folder, CARD),
            ("Открыть state/log", self.open_app_folder, CARD),
            ("Backup cfg", self.backup_only, BLUE),
            ("Откатить последний профиль", self.undo_last, RED),
        ]:
            hover = CARD_HOVER if color == CARD else ("#DC2626" if color == RED else "#0284C7")
            b = ctk.CTkButton(actions, text=text, fg_color=color, hover_color=hover, command=cmd)
            b.pack(side="left", padx=(0, 8))
            self.action_buttons.append(b)

        box = self.card(page, "Лог", "Все действия и ошибки", BLUE, row=1, column=0, sticky="nsew")
        self.log_box = ctk.CTkTextbox(box.inner, fg_color="#050A14", text_color=TEXT, font=("Consolas", 10), wrap="word")
        self.log_box.pack(fill="both", expand=True)
        return page

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def show_page(self, page: str) -> None:
        self.current_page = page
        titles = {
            "dashboard": ("Главная", "Быстрый старт и рекомендации"),
            "health": ("Health Check", "Скан проблем Windows/Rust и безопасный Auto Fix"),
            "opt": ("Оптимизация", "SAFE / BALANCED / AGGRESSIVE профили с откатом"),
            "session": ("Game Session", "Временный игровой режим: подготовка → запуск Rust → мониторинг → авто-откат"),
            "monitor": ("Stutter Monitor", "Диагностика фризов: CPU/RAM/Disk/Rust process без инжекта и оверлея"),
            "cleaner": ("Cleaner / Repair", "Очистка логов/кэшей Rust и быстрые repair-действия"),
            "config": ("Config Manager", "Snapshots, restore и export Rust cfg-файлов"),
            "reports": ("Report Center", "HTML/ZIP support bundle со всеми отчётами для диагностики"),
            "tuning": ("Rust Settings", "Автоподбор графики, launch options и профиля под твоё железо"),
            "specs": ("ПК / Железо", "Полный отчёт по сборке компьютера"),
            "launch": ("Launch Options", "Параметры запуска Steam и приоритет процесса"),
            "logs": ("Бэкапы / Лог", "История действий, backup и откат"),
        }
        for name, frame in self.pages.items():
            frame.grid_forget()
            btn = self.nav_buttons.get(name)
            if btn:
                if name == page:
                    btn.configure(fg_color=CARD, text_color=TEXT)
                else:
                    btn.configure(fg_color="transparent", text_color=MUTED)
        self.pages[page].grid(row=0, column=0, sticky="nsew")
        title, subtitle = titles.get(page, (page, ""))
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)

    def ui(self, func) -> None:
        try:
            if threading.get_ident() == self.main_thread_id:
                func()
            else:
                self.after(0, func)
        except Exception:
            pass

    def set_textbox(self, widget: ctk.CTkTextbox, text: str) -> None:
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
            with core.log_path().open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

        def append() -> None:
            if hasattr(self, "log_box"):
                try:
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", line + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                except Exception:
                    pass
        self.ui(append)

    def set_busy(self, busy: bool) -> None:
        self.busy = busy

        def apply() -> None:
            state = "disabled" if busy else "normal"
            for btn in self.action_buttons:
                try:
                    btn.configure(state=state)
                except Exception:
                    pass
        self.ui(apply)

    def run_in_thread(self, func) -> None:
        if self.busy:
            return
        self.set_busy(True)

        def worker() -> None:
            try:
                func()
            except Exception as exc:
                self.log(f"[err] {exc}")
                self.ui(lambda: messagebox.showerror("Rust FPS Optimizer Pro", str(exc)))
            finally:
                self.set_busy(False)
                self.refresh_status()
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Status / PC specs
    # ------------------------------------------------------------------
    def refresh_status(self) -> None:
        exes = core.discover_rust_exes() if core.is_windows() else []
        cfgs = core.discover_cfg_dirs() if core.is_windows() else []
        admin = "ADMIN" if core.is_admin() else "NO ADMIN"
        ram = f"RAM {self.ram_gb} GB" if self.ram_gb else "RAM ?"
        rust = str(exes[0]) if exes else "RustClient.exe не найден автоматически"
        status_short = f"{platform.system()} {platform.release()} • {admin} • {ram}"
        status_long = (
            f"{status_short}\n"
            f"Rust: {short_path(rust, 92)}\n"
            f"cfg dirs: {len(cfgs)}\n"
            f"data: {core.app_dir()}"
        )

        def apply() -> None:
            self.header_status.configure(text=status_short)
            self.admin_badge.configure(text=admin, fg_color="#14532D" if core.is_admin() else "#7F1D1D")
            if hasattr(self, "home_status_text"):
                self.home_status_text.configure(text=status_long)
            if hasattr(self, "opt_status_label"):
                self.opt_status_label.configure(text=status_long)
            self.update_launch_options()
        self.ui(apply)

    def refresh_specs_async(self) -> None:
        if self.spec_busy:
            return
        self.spec_busy = True
        if hasattr(self, "spec_status_label"):
            self.spec_status_label.configure(text="Сканирую железо через PowerShell/CIM...")

        def worker() -> None:
            try:
                info = core.collect_pc_info()
                report = core.render_pc_report(info)
                recommendations = core.make_pc_recommendations(info)
                sections = core.pc_spec_sections(info)
                tuning = core.generate_rust_tuning(info, self.tuning_target.get())
                tuning_report = core.render_rust_tuning(tuning)
                self.pc_info = info
                self.pc_report_text = report
                self.current_tuning = tuning
                self.tuning_report_text = tuning_report

                def apply() -> None:
                    self.populate_specs(sections)
                    self.set_textbox(self.pc_report_box, report)
                    self.set_textbox(self.reco_box, recommendations)
                    if hasattr(self, "tuning_report_box"):
                        self.populate_tuning(tuning, tuning_report)
                    self.spec_status_label.configure(text=f"Готово: {_dt.datetime.now().strftime('%H:%M:%S')}")
                    if hasattr(self, "tuning_status_label"):
                        self.tuning_status_label.configure(text="Автоподбор Rust Settings готов.")
                    self.refresh_status()
                self.ui(apply)
            except Exception as exc:
                self.log(f"[warn] Не смог собрать ПК: {exc}")
                self.ui(lambda: self.spec_status_label.configure(text=f"Ошибка скана: {exc}"))
            finally:
                self.spec_busy = False
        threading.Thread(target=worker, daemon=True).start()

    def populate_specs(self, sections: List[Tuple[str, List[Tuple[str, str]]]]) -> None:
        if not hasattr(self, "spec_scroll"):
            return
        for child in self.spec_scroll.winfo_children():
            child.destroy()
        for section, rows in sections:
            sec = ctk.CTkFrame(self.spec_scroll, fg_color=CARD, corner_radius=14)
            sec.pack(fill="x", padx=8, pady=7)
            ctk.CTkLabel(sec, text=section, text_color=BLUE_2, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=12, pady=(10, 6))
            for key, value in rows:
                row = ctk.CTkFrame(sec, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=2)
                ctk.CTkLabel(row, text=str(key), text_color=MUTED, font=("Segoe UI", 11, "bold"), width=190, anchor="w").pack(side="left", padx=(0, 8))
                ctk.CTkLabel(row, text=str(value), text_color=TEXT, font=("Segoe UI", 11), anchor="w", justify="left", wraplength=520).pack(side="left", fill="x", expand=True)
            ctk.CTkFrame(sec, height=6, fg_color="transparent").pack(fill="x")

    def copy_pc_report(self) -> None:
        text = self.pc_report_text or "Отчёт пока не собран. Нажми «Обновить сборку ПК»."
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("[ok] PC report скопирован в буфер.")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Отчёт по ПК скопирован.")

    def save_pc_report(self) -> None:
        text = self.pc_report_text or core.render_pc_report(self.pc_info or core.collect_pc_info())
        default = f"rust_pc_report_{core.now_stamp()}.txt"
        p = filedialog.asksaveasfilename(
            title="Сохранить отчёт",
            defaultextension=".txt",
            initialfile=default,
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            Path(p).write_text(text, encoding="utf-8")
            self.log(f"[ok] PC report сохранён: {p}")
        except Exception as exc:
            self.log(f"[err] Не смог сохранить отчёт: {exc}")

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------
    def health_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "health_status_label"):
                self.health_status_label.configure(text=text)
        self.ui(apply)

    def scan_health_async(self) -> None:
        if not hasattr(self, "health_scroll"):
            return
        self.health_status("Scanning health...")

        def worker() -> None:
            try:
                scan = core.health_check_scan()
                report = core.render_health_report(scan)
                self.health_scan = scan
                self.health_report_text = report
                self.ui(lambda: self.populate_health_check(scan, report))
            except Exception as exc:
                self.log(f"[health][err] scan failed: {exc}")
                self.health_status(f"Health scan error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def populate_health_check(self, scan: Dict[str, Any], report: str) -> None:
        score = int(scan.get("score", 0) or 0)
        label = str(scan.get("label", "—"))
        color = GREEN if score >= 85 else BLUE if score >= 70 else YELLOW if score >= 50 else RED
        if hasattr(self, "health_score_label"):
            self.health_score_label.configure(text=f"{score}/100", text_color=color)
        if hasattr(self, "health_status_label"):
            self.health_status_label.configure(text=f"{label} • generated {scan.get('generated', '—')}")
        if hasattr(self, "health_report_box"):
            self.set_textbox(self.health_report_box, report)

        if not hasattr(self, "health_scroll"):
            return
        for child in self.health_scroll.winfo_children():
            child.destroy()
        status_order = ["bad", "warn", "info", "ok"]
        status_colors = {"bad": RED, "warn": YELLOW, "info": BLUE, "ok": GREEN}
        for status in status_order:
            items = [x for x in scan.get("items", []) if x.get("status") == status]
            if not items:
                continue
            ctk.CTkLabel(self.health_scroll, text=status.upper(), text_color=status_colors.get(status, TEXT), font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
            for item in items:
                frame = ctk.CTkFrame(self.health_scroll, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
                frame.pack(fill="x", padx=8, pady=6)
                top = ctk.CTkFrame(frame, fg_color="transparent")
                top.pack(fill="x", padx=12, pady=(10, 2))
                ctk.CTkLabel(top, text=str(item.get("title", "")), text_color=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left", anchor="w")
                ctk.CTkLabel(top, text=str(item.get("category", "")), text_color=MUTED, font=("Segoe UI", 10, "bold")).pack(side="right")
                ctk.CTkLabel(frame, text=str(item.get("detail", "")), text_color=MUTED, font=("Segoe UI", 10), wraplength=430, justify="left").pack(anchor="w", padx=12, pady=(0, 4))
                if item.get("fix"):
                    ctk.CTkLabel(frame, text="Fix: " + str(item.get("fix")), text_color=BLUE_2, font=("Segoe UI", 10), wraplength=430, justify="left").pack(anchor="w", padx=12, pady=(0, 10))
                else:
                    ctk.CTkFrame(frame, height=8, fg_color="transparent").pack(fill="x")

    def apply_health_safe_fixes_async(self) -> None:
        ok = messagebox.askyesno(
            "Rust FPS Optimizer Pro",
            "Применить безопасные исправления?\n\n"
            "Будет создан cfg snapshot/backup, включён Game Mode, отключён Xbox DVR/background capture и выставлен GPU preference для Rust, если найден.\n"
            "Все registry-изменения можно откатить через Бэкапы / Лог → Откатить последний профиль.",
        )
        if not ok:
            return
        self.health_status("Applying safe fixes...")

        def worker() -> None:
            try:
                core.apply_health_safe_fixes(self.log)
                scan = core.health_check_scan()
                report = core.render_health_report(scan)
                self.health_scan = scan
                self.health_report_text = report
                self.ui(lambda: self.populate_health_check(scan, report))
                self.health_status("Safe fixes applied. Health re-scan готов.")
            except Exception as exc:
                self.log(f"[health][err] safe fix failed: {exc}")
                self.health_status(f"Safe fix error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def copy_health_report(self) -> None:
        text = self.health_report_text or "Health Check ещё не запускался."
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("[health] report copied.")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Health report скопирован.")

    # ------------------------------------------------------------------
    # Report Center / Support Bundle
    # ------------------------------------------------------------------
    def report_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "report_status_label"):
                self.report_status_label.configure(text=text)
        self.ui(apply)

    def create_support_bundle_async(self) -> None:
        self.report_status("Creating support bundle... Это может занять 10-40 секунд из-за скана ПК.")
        self.set_textbox(self.report_box, "Создаю Support Bundle...\n") if hasattr(self, "report_box") else None

        def worker() -> None:
            try:
                bundle = core.create_support_bundle(self.log, target=self.tuning_target.get())
                self.support_bundle = bundle
                summary = self.render_support_summary(bundle)
                self.support_report_text = summary
                self.set_textbox(self.report_box, summary)
                self.report_status(f"Bundle готов: {bundle.get('zip')}")
            except Exception as exc:
                self.log(f"[report][err] bundle failed: {exc}")
                self.report_status(f"Report error: {exc}")
                if hasattr(self, "report_box"):
                    self.set_textbox(self.report_box, f"Ошибка создания Support Bundle:\n{exc}")
        threading.Thread(target=worker, daemon=True).start()

    def render_support_summary(self, bundle: Dict[str, Any]) -> str:
        summary = bundle.get("summary", {}) if isinstance(bundle.get("summary"), dict) else {}
        lines = [
            f"Rust FPS Optimizer Pro v{PRO_VERSION} — Support Bundle",
            f"Generated: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"ZIP: {bundle.get('zip', '—')}",
            f"HTML: {bundle.get('html', '—')}",
            f"Folder: {bundle.get('dir', '—')}",
            "",
            "[Summary]",
            f"CPU: {summary.get('cpu', '—')}",
            f"GPU: {summary.get('gpu', '—')}",
            f"RAM: {summary.get('ram_gb', '—')} GB",
            f"Bottleneck: {summary.get('bottleneck', '—')}",
            f"Recommended profile: {summary.get('profile', '—')}",
            f"Launch options: {summary.get('launch_options', '—')}",
            f"Health: {summary.get('health_score', '—')}/100 — {summary.get('health_label', '—')}",
            f"Cleaner found: {core.fmt_bytes(summary.get('cleaner_bytes', 0))}",
            f"Config files: {summary.get('cfg_files', 0)}",
            f"Snapshots: {summary.get('snapshots', 0)}",
            "",
            "Открой support_report.html для красивого отчёта или скинь ZIP для диагностики.",
        ]
        return "\n".join(lines)

    def open_support_html(self) -> None:
        html = self.support_bundle.get("html") if isinstance(self.support_bundle, dict) else None
        if html and Path(str(html)).exists():
            self.open_path(Path(str(html)))
        else:
            messagebox.showinfo("Rust FPS Optimizer Pro", "HTML ещё не создан. Нажми Create Support Bundle.")

    def open_support_zip_folder(self) -> None:
        zip_path = self.support_bundle.get("zip") if isinstance(self.support_bundle, dict) else None
        if zip_path and Path(str(zip_path)).exists():
            self.open_path(Path(str(zip_path)).parent)
        else:
            self.open_path(core.reports_root())

    def copy_support_summary(self) -> None:
        text = self.support_report_text or "Support Bundle ещё не создан."
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("[report] summary copied.")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Support summary скопирован.")

    # ------------------------------------------------------------------
    # Rust Config Manager
    # ------------------------------------------------------------------
    def config_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "config_status_label"):
                self.config_status_label.configure(text=text)
        self.ui(apply)

    def scan_config_manager_async(self) -> None:
        if not hasattr(self, "config_files_scroll"):
            return
        self.config_status("Scanning Rust cfg files and snapshots...")

        def worker() -> None:
            try:
                files = core.config_file_summary()
                snaps = core.list_config_snapshots()
                self.config_files = files
                self.config_snapshots = snaps
                self.ui(lambda: self.populate_config_manager(files, snaps))
                total_files = len(files)
                self.config_status(f"Scan готов: cfg files {total_files}, snapshots {len(snaps)}.")
            except Exception as exc:
                self.log(f"[cfg][err] scan failed: {exc}")
                self.config_status(f"Scan error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def populate_config_manager(self, files: List[Dict[str, Any]], snapshots: List[Dict[str, Any]]) -> None:
        if hasattr(self, "config_files_scroll"):
            for child in self.config_files_scroll.winfo_children():
                child.destroy()
            if not files:
                ctk.CTkLabel(self.config_files_scroll, text="cfg-файлы не найдены. Запусти Rust хотя бы один раз.", text_color=MUTED).pack(anchor="w", padx=10, pady=10)
            for item in files:
                frame = ctk.CTkFrame(self.config_files_scroll, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
                frame.pack(fill="x", padx=8, pady=7)
                ctk.CTkLabel(frame, text=str(item.get("name", "cfg")), text_color=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
                ctk.CTkLabel(frame, text=f"{core.fmt_bytes(item.get('size_bytes'))} • modified {item.get('modified', '—')}", text_color=BLUE_2, font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(0, 4))
                ctk.CTkLabel(frame, text=short_path(str(item.get("path", "")), 96), text_color=MUTED, font=("Consolas", 9), wraplength=700, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        if hasattr(self, "config_snapshots_scroll"):
            for child in self.config_snapshots_scroll.winfo_children():
                child.destroy()
            if not snapshots:
                ctk.CTkLabel(self.config_snapshots_scroll, text="Snapshots пока нет. Нажми Create snapshot.", text_color=MUTED).pack(anchor="w", padx=10, pady=10)
            for snap in snapshots:
                path = str(snap.get("path", ""))
                frame = ctk.CTkFrame(self.config_snapshots_scroll, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
                frame.pack(fill="x", padx=8, pady=7)
                ctk.CTkLabel(frame, text=str(snap.get("name", "snapshot")), text_color=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
                ctk.CTkLabel(frame, text=f"{snap.get('timestamp', '—')} • {snap.get('file_count', 0)} files • {core.fmt_bytes(snap.get('size_bytes'))}", text_color=BLUE_2, font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(0, 6))
                btns = ctk.CTkFrame(frame, fg_color="transparent")
                btns.pack(fill="x", padx=12, pady=(0, 10))
                ctk.CTkButton(btns, text="Restore", width=90, height=30, fg_color=RED, hover_color="#DC2626", command=lambda p=path: self.restore_config_snapshot_ui(p)).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btns, text="Export ZIP", width=100, height=30, fg_color=CARD_HOVER, hover_color="#243044", command=lambda p=path: self.export_config_snapshot_ui(p)).pack(side="left", padx=(0, 6))
                ctk.CTkButton(btns, text="Open", width=70, height=30, fg_color=CARD_HOVER, hover_color="#243044", command=lambda p=path: self.open_path(Path(p))).pack(side="left")

    def create_config_snapshot_async(self) -> None:
        self.config_status("Creating cfg snapshot...")

        def worker() -> None:
            try:
                snap = core.create_config_snapshot(self.log)
                if snap:
                    self.log(f"[cfg] snapshot created: {snap}")
                self.config_files = core.config_file_summary()
                self.config_snapshots = core.list_config_snapshots()
                self.ui(lambda: self.populate_config_manager(self.config_files, self.config_snapshots))
                self.config_status("Snapshot готов." if snap else "Snapshot не создан: cfg не найден.")
            except Exception as exc:
                self.log(f"[cfg][err] snapshot failed: {exc}")
                self.config_status(f"Snapshot error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def restore_config_snapshot_ui(self, snapshot_path: str) -> None:
        ok = messagebox.askyesno(
            "Rust FPS Optimizer Pro",
            "Восстановить cfg-файлы из выбранного snapshot?\n\n"
            "Текущие cfg будут перезаписаны файлами из backup. Лучше сначала создать новый snapshot.",
        )
        if not ok:
            return
        self.config_status("Restoring cfg snapshot...")

        def worker() -> None:
            restored = core.restore_config_snapshot(Path(snapshot_path), self.log)
            self.config_files = core.config_file_summary()
            self.config_snapshots = core.list_config_snapshots()
            self.ui(lambda: self.populate_config_manager(self.config_files, self.config_snapshots))
            self.config_status(f"Restore готов: {restored} files.")
        threading.Thread(target=worker, daemon=True).start()

    def export_config_snapshot_ui(self, snapshot_path: str) -> None:
        default = Path(snapshot_path).name + ".zip"
        out = filedialog.asksaveasfilename(
            title="Export cfg snapshot ZIP",
            defaultextension=".zip",
            initialfile=default,
            filetypes=[("ZIP", "*.zip"), ("All files", "*.*")],
        )
        if not out:
            return
        exported = core.export_config_snapshot_zip(Path(snapshot_path), Path(out), self.log)
        if exported:
            messagebox.showinfo("Rust FPS Optimizer Pro", f"Snapshot exported:\n{exported}")

    def write_recommended_config_note(self) -> None:
        if not self.tuning_report_text:
            info = self.pc_info or core.collect_pc_info()
            tuning = core.generate_rust_tuning(info, self.tuning_target.get())
            self.current_tuning = tuning
            self.tuning_report_text = core.render_rust_tuning(tuning)
        outputs = core.write_recommended_settings_note(self.tuning_report_text, self.log)
        if outputs:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Recommended settings TXT записан:\n" + "\n".join(str(p) for p in outputs))
        else:
            messagebox.showwarning("Rust FPS Optimizer Pro", "Не получилось записать recommended settings TXT.")

    def open_first_cfg_folder(self) -> None:
        dirs = core.discover_cfg_dirs()
        if dirs:
            self.open_path(dirs[0])
        else:
            messagebox.showinfo("Rust FPS Optimizer Pro", "cfg-папка Rust не найдена. Запусти Rust хотя бы один раз.")

    # ------------------------------------------------------------------
    # Cleaner / Repair Center
    # ------------------------------------------------------------------
    def cleaner_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "cleaner_status_label"):
                self.cleaner_status_label.configure(text=text)
        self.ui(apply)

    def cleaner_log(self, text: str) -> None:
        self.log(f"[cleaner] {text}")
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {text}\n"

        def append() -> None:
            if hasattr(self, "cleaner_log_box"):
                try:
                    self.cleaner_log_box.configure(state="normal")
                    self.cleaner_log_box.insert("end", line)
                    self.cleaner_log_box.see("end")
                    self.cleaner_log_box.configure(state="disabled")
                except Exception:
                    pass
        self.ui(append)

    def scan_cleaner_async(self) -> None:
        if not hasattr(self, "cleaner_scroll"):
            return
        self.cleaner_status("Scanning cleanup targets...")

        def worker() -> None:
            try:
                items = core.scan_cleaner_targets()
                self.cleaner_items = items
                total = sum(int(i.get("size_bytes", 0) or 0) for i in items)

                def apply() -> None:
                    self.populate_cleaner_targets(items)
                    self.cleaner_status(f"Scan готов: найдено примерно {core.fmt_bytes(total)} мусора/кэшей.")
                self.ui(apply)
            except Exception as exc:
                self.cleaner_log(f"[err] scan failed: {exc}")
                self.cleaner_status(f"Scan error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def populate_cleaner_targets(self, items: List[Dict[str, Any]]) -> None:
        if not hasattr(self, "cleaner_scroll"):
            return
        for child in self.cleaner_scroll.winfo_children():
            child.destroy()
        self.cleaner_vars = {}
        if not items:
            ctk.CTkLabel(self.cleaner_scroll, text="Ничего не найдено.", text_color=MUTED).pack(anchor="w", padx=10, pady=10)
            return
        for item in items:
            tid = str(item.get("id"))
            exists = bool(item.get("exists"))
            risk = str(item.get("risk", "safe"))
            size = int(item.get("size_bytes", 0) or 0)
            files = int(item.get("file_count", 0) or 0)
            color = GREEN if risk == "safe" else YELLOW
            frame = ctk.CTkFrame(self.cleaner_scroll, fg_color=CARD if exists else "#101827", corner_radius=14, border_width=1, border_color=BORDER)
            frame.pack(fill="x", padx=8, pady=7)
            top = ctk.CTkFrame(frame, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 4))
            var = tk.BooleanVar(value=exists and risk == "safe")
            self.cleaner_vars[tid] = var
            cb = ctk.CTkCheckBox(top, text=str(item.get("title", tid)), variable=var, text_color=TEXT if exists else MUTED_2, font=("Segoe UI", 13, "bold"))
            cb.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(top, text=risk.upper(), text_color=color, font=("Segoe UI", 11, "bold")).pack(side="right", padx=(8, 0))
            ctk.CTkLabel(frame, text=str(item.get("description", "")), text_color=MUTED, font=("Segoe UI", 10), wraplength=680, justify="left").pack(anchor="w", padx=12, pady=(0, 4))
            ctk.CTkLabel(frame, text=f"{core.fmt_bytes(size)} • {files} files", text_color=BLUE_2 if exists else MUTED_2, font=("Consolas", 11, "bold")).pack(anchor="w", padx=12, pady=(0, 5))
            paths = item.get("paths", []) or []
            if paths:
                shown = "\n".join("• " + short_path(str(p), 92) for p in paths[:4])
                if len(paths) > 4:
                    shown += f"\n• ... +{len(paths)-4} paths"
                ctk.CTkLabel(frame, text=shown, text_color=MUTED_2, font=("Consolas", 9), justify="left", wraplength=720).pack(anchor="w", padx=12, pady=(0, 10))
            else:
                ctk.CTkLabel(frame, text="Не найдено", text_color=MUTED_2, font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(0, 10))

    def selected_cleaner_target_ids(self) -> List[str]:
        ids: List[str] = []
        for tid, var in self.cleaner_vars.items():
            try:
                if var.get():
                    ids.append(tid)
            except Exception:
                continue
        return ids

    def clean_selected_async(self) -> None:
        ids = self.selected_cleaner_target_ids()
        if not ids:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Ничего не выбрано для очистки.")
            return
        risky = [i for i in self.cleaner_items if i.get("id") in ids and i.get("risk") != "safe"]
        text = "Очистить выбранные элементы?"
        if risky:
            text += "\n\nВ выбранном есть shader/cache targets. После очистки первая загрузка Rust/игр может временно фризить сильнее."
        ok = messagebox.askyesno("Rust FPS Optimizer Pro", text)
        if not ok:
            return
        self.cleaner_status("Cleaning selected targets...")
        self.cleaner_log(f"Cleaning: {', '.join(ids)}")

        def worker() -> None:
            try:
                result = core.clean_selected_targets(ids, self.cleaner_log)
                msg = f"Готово: удалено примерно {core.fmt_bytes(int(result.get('bytes', 0) or 0))}, файлов: {result.get('files', 0)}"
                self.cleaner_log(msg)
                self.cleaner_status(msg)
                self.cleaner_items = core.scan_cleaner_targets()
                self.ui(lambda: self.populate_cleaner_targets(self.cleaner_items))
            except Exception as exc:
                self.cleaner_log(f"[err] clean failed: {exc}")
                self.cleaner_status(f"Clean error: {exc}")
        threading.Thread(target=worker, daemon=True).start()

    def open_rust_locallow(self) -> None:
        p = core.local_low_rust_dir()
        if p:
            self.open_path(p)
        else:
            messagebox.showinfo("Rust FPS Optimizer Pro", "LocalLow Rust папка не найдена. Возможно Rust ещё не запускался.")

    # ------------------------------------------------------------------
    # Stutter Monitor
    # ------------------------------------------------------------------
    def monitor_interval(self) -> float:
        try:
            value = float(self.monitor_interval_var.get())
            return max(1.0, min(10.0, value))
        except Exception:
            return 2.0

    def monitor_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "monitor_status_label"):
                self.monitor_status_label.configure(text=text)
        self.ui(apply)

    def start_stutter_monitor(self, launch_rust: bool = False) -> None:
        if psutil is None:
            messagebox.showerror(
                "Rust FPS Optimizer Pro",
                "Для Stutter Monitor нужна библиотека psutil.\n\n"
                "Запусти Run_Pro_Source_As_Admin.bat или установи вручную:\n"
                "python -m pip install psutil",
            )
            return
        if self.monitor_active:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Stutter Monitor уже запущен.")
            return
        self.monitor_active = True
        self.monitor_stop_event.clear()
        self.monitor_samples = []
        self.monitor_report_text = ""
        self.set_textbox(self.monitor_report_box, "Мониторинг запущен...\n") if hasattr(self, "monitor_report_box") else None
        self.monitor_status("Мониторинг запущен. Играй до фризов, потом Stop + Analyze.")
        self.update_monitor_metrics({"cpu_percent": 0, "ram_percent": 0, "disk_read_mb_s": 0, "disk_write_mb_s": 0, "rust_mem_mb": 0})
        if hasattr(self, "monitor_start_btn"):
            self.monitor_start_btn.configure(state="disabled")
            self.monitor_launch_btn.configure(state="disabled")
        do_launch = launch_rust or self.monitor_auto_launch_var.get()
        threading.Thread(target=lambda: self.stutter_monitor_worker(do_launch), daemon=True).start()

    def stop_stutter_monitor(self) -> None:
        if self.monitor_active:
            self.monitor_status("Останавливаю мониторинг и анализирую...")
            self.monitor_stop_event.set()
            return
        if self.monitor_samples:
            report = self.analyze_stutter_samples(self.monitor_samples)
            self.monitor_report_text = report
            self.set_textbox(self.monitor_report_box, report)
        else:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Нет samples для анализа.")

    def stutter_monitor_worker(self, launch_rust: bool = False) -> None:
        interval = self.monitor_interval()
        saw_rust = False
        rust_proc = None
        disk_prev = None
        disk_prev_time = time.time()
        try:
            if launch_rust:
                core.launch_rust_via_steam(lambda t: self.log(f"[monitor] {t}"))
            try:
                psutil.cpu_percent(interval=None)
                disk_prev = psutil.disk_io_counters()
            except Exception:
                disk_prev = None
            self.log(f"[monitor] started, interval={interval}s")
            while not self.monitor_stop_event.is_set():
                time.sleep(interval)
                now = time.time()
                sample = self.collect_monitor_sample(rust_proc, disk_prev, disk_prev_time)
                rust_proc = sample.pop("_rust_proc", rust_proc)
                disk_prev = sample.pop("_disk_now", disk_prev)
                disk_prev_time = sample.pop("_disk_time", now)
                self.monitor_samples.append(sample)
                if sample.get("rust_running"):
                    saw_rust = True
                self.update_monitor_metrics(sample)
                if self.monitor_auto_stop_var.get() and saw_rust and not sample.get("rust_running"):
                    self.log("[monitor] RustClient.exe closed, auto-stopping monitor.")
                    break
            report = self.analyze_stutter_samples(self.monitor_samples)
            self.monitor_report_text = report
            self.set_textbox(self.monitor_report_box, report)
            self.monitor_status("Мониторинг остановлен. Анализ готов.")
            self.auto_save_monitor_report(report)
        except Exception as exc:
            self.log(f"[monitor][err] {exc}")
            self.monitor_status(f"Ошибка мониторинга: {exc}")
        finally:
            self.monitor_active = False
            self.ui(lambda: self.monitor_start_btn.configure(state="normal") if hasattr(self, "monitor_start_btn") else None)
            self.ui(lambda: self.monitor_launch_btn.configure(state="normal") if hasattr(self, "monitor_launch_btn") else None)

    def find_rust_psutil_process(self):
        if psutil is None:
            return None
        try:
            for proc in psutil.process_iter(["name", "pid", "create_time"]):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name in {"rustclient.exe", "rustclient"}:
                        try:
                            proc.cpu_percent(interval=None)
                        except Exception:
                            pass
                        return proc
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def collect_monitor_sample(self, rust_proc, disk_prev, disk_prev_time: float) -> Dict[str, Any]:
        assert psutil is not None
        ts = _dt.datetime.now()
        cpu = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        disk_now = psutil.disk_io_counters()
        now = time.time()
        dt = max(0.001, now - disk_prev_time)
        read_mb_s = write_mb_s = disk_busy = 0.0
        if disk_now and disk_prev:
            read_mb_s = max(0.0, (disk_now.read_bytes - disk_prev.read_bytes) / (1024 ** 2) / dt)
            write_mb_s = max(0.0, (disk_now.write_bytes - disk_prev.write_bytes) / (1024 ** 2) / dt)
            busy_now = getattr(disk_now, "busy_time", None)
            busy_prev = getattr(disk_prev, "busy_time", None)
            if busy_now is not None and busy_prev is not None:
                disk_busy = max(0.0, min(100.0, (busy_now - busy_prev) / (dt * 1000.0) * 100.0))

        rust_running = False
        rust_pid = ""
        rust_mem_mb = 0.0
        rust_cpu = 0.0
        if rust_proc is None or not self._proc_alive(rust_proc):
            rust_proc = self.find_rust_psutil_process()
        if rust_proc is not None:
            try:
                rust_running = rust_proc.is_running()
                rust_pid = str(rust_proc.pid)
                rust_mem_mb = rust_proc.memory_info().rss / (1024 ** 2)
                rust_cpu = float(rust_proc.cpu_percent(interval=None))
            except Exception:
                rust_running = False
                rust_proc = None

        return {
            "timestamp": ts.isoformat(timespec="seconds"),
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(float(vm.percent), 1),
            "ram_used_gb": round(float(vm.used) / (1024 ** 3), 2),
            "ram_available_gb": round(float(vm.available) / (1024 ** 3), 2),
            "disk_read_mb_s": round(read_mb_s, 2),
            "disk_write_mb_s": round(write_mb_s, 2),
            "disk_busy_percent": round(disk_busy, 1),
            "rust_running": bool(rust_running),
            "rust_pid": rust_pid,
            "rust_mem_mb": round(rust_mem_mb, 1),
            "rust_cpu_percent": round(rust_cpu, 1),
            "sample_index": len(self.monitor_samples) + 1,
            "_rust_proc": rust_proc,
            "_disk_now": disk_now,
            "_disk_time": now,
        }

    def _proc_alive(self, proc) -> bool:
        try:
            return proc is not None and proc.is_running()
        except Exception:
            return False

    def update_monitor_metrics(self, sample: Dict[str, Any]) -> None:
        def apply() -> None:
            labels = getattr(self, "monitor_metric_labels", {})
            if not labels:
                return
            labels["cpu"].configure(text=f"{sample.get('cpu_percent', 0)}%")
            labels["ram"].configure(text=f"{sample.get('ram_percent', 0)}%")
            disk = float(sample.get("disk_read_mb_s", 0) or 0) + float(sample.get("disk_write_mb_s", 0) or 0)
            busy = sample.get("disk_busy_percent", 0)
            labels["disk"].configure(text=f"{disk:.1f} MB/s" + (f" • {busy}%" if busy else ""))
            if sample.get("rust_running"):
                labels["rust"].configure(text=f"{sample.get('rust_mem_mb', 0)} MB")
            else:
                labels["rust"].configure(text="not running")
            labels["samples"].configure(text=str(len(self.monitor_samples)))
        self.ui(apply)

    def analyze_stutter_samples(self, samples: List[Dict[str, Any]]) -> str:
        if not samples:
            return "Нет данных мониторинга."

        def maxv(key: str) -> float:
            vals = [float(s.get(key, 0) or 0) for s in samples]
            return max(vals) if vals else 0.0

        def avgv(key: str) -> float:
            vals = [float(s.get(key, 0) or 0) for s in samples]
            return sum(vals) / len(vals) if vals else 0.0

        duration_sec = max(1, len(samples) * self.monitor_interval())
        rust_seen = any(bool(s.get("rust_running")) for s in samples)
        cpu_max = maxv("cpu_percent")
        cpu_avg = avgv("cpu_percent")
        ram_max = maxv("ram_percent")
        ram_avg = avgv("ram_percent")
        ram_min_free = min(float(s.get("ram_available_gb", 999) or 999) for s in samples)
        disk_read_max = maxv("disk_read_mb_s")
        disk_write_max = maxv("disk_write_mb_s")
        disk_busy_max = maxv("disk_busy_percent")
        rust_ram_max = maxv("rust_mem_mb")
        rust_cpu_max = maxv("rust_cpu_percent")

        events: List[str] = []
        if cpu_max >= 92:
            events.append(f"CPU spike до {cpu_max:.1f}% — возможный CPU bottleneck/фоновые процессы.")
        if ram_max >= 90 or ram_min_free <= 2.0:
            events.append(f"RAM pressure: максимум {ram_max:.1f}%, минимум свободно {ram_min_free:.2f} GB — частая причина статтеров Rust.")
        if disk_busy_max >= 85:
            events.append(f"Disk busy до {disk_busy_max:.1f}% — возможны фризы при прогрузке ассетов/кэша.")
        if disk_read_max + disk_write_max >= 250:
            events.append(f"Высокий диск I/O: read {disk_read_max:.1f} MB/s, write {disk_write_max:.1f} MB/s.")
        if rust_ram_max >= 12000 and ram_min_free <= 4.0:
            events.append(f"Rust использовал до {rust_ram_max/1024:.1f} GB RAM, свободной памяти мало — вероятны GC/pagefile статтеры.")
        if not rust_seen:
            events.append("RustClient.exe не был найден во время мониторинга. Запусти монитор перед/во время игры.")

        recommendations: List[str] = []
        if ram_max >= 90 or ram_min_free <= 2.0:
            recommendations += [
                "Закрой браузер/Discord stream/OBS replay buffer перед Rust.",
                "Если у тебя 16 GB RAM — апгрейд до 32 GB чаще всего сильнее всего уменьшает фризы.",
                "Попробуй -gc.buffer 2048; если хуже — верни только -nolog.",
            ]
        if cpu_max >= 92:
            recommendations += [
                "Поставь профиль BALANCED или Game Session, закрой фоновые лаунчеры.",
                "В Rust снизь Draw Distance/Object Quality, они часто грузят CPU.",
            ]
        if disk_busy_max >= 85 or disk_read_max + disk_write_max >= 250:
            recommendations += [
                "Проверь, что Rust стоит на SSD/NVMe, не на HDD.",
                "Освободи 30-50 GB на диске с Rust и Windows.",
                "Если недавно чистил shader cache — первая прогрузка может временно фризить.",
            ]
        if rust_seen and not recommendations:
            recommendations += [
                "Критичных пиков не поймано. Повтори мониторинг именно в момент фризов на загруженном сервере.",
                "Попробуй стабильный FPS cap на 5-10 FPS ниже среднего, чтобы улучшить frametime.",
            ]

        lines: List[str] = []
        lines.append(f"Rust FPS Optimizer Pro v{PRO_VERSION} — Stutter Monitor Report")
        lines.append(f"Generated: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("[Summary]")
        lines.append(f"Samples: {len(samples)}")
        lines.append(f"Approx duration: {duration_sec/60:.1f} min")
        lines.append(f"Rust detected: {'yes' if rust_seen else 'no'}")
        lines.append(f"CPU avg/max: {cpu_avg:.1f}% / {cpu_max:.1f}%")
        lines.append(f"RAM avg/max: {ram_avg:.1f}% / {ram_max:.1f}%")
        lines.append(f"Min free RAM: {ram_min_free:.2f} GB")
        lines.append(f"Disk read max: {disk_read_max:.1f} MB/s")
        lines.append(f"Disk write max: {disk_write_max:.1f} MB/s")
        lines.append(f"Disk busy max: {disk_busy_max:.1f}%")
        lines.append(f"Rust RAM max: {rust_ram_max/1024:.2f} GB")
        lines.append(f"Rust CPU max: {rust_cpu_max:.1f}%")
        lines.append("")
        lines.append("[Likely causes]")
        if events:
            for e in events:
                lines.append(f"• {e}")
        else:
            lines.append("• Явных системных пиков не поймано.")
        lines.append("")
        lines.append("[Recommendations]")
        # preserve order, remove duplicates
        seen = set()
        for r in recommendations:
            if r not in seen:
                lines.append(f"• {r}")
                seen.add(r)
        lines.append("")
        lines.append("[Worst samples]")
        worst = sorted(samples, key=lambda s: (float(s.get("cpu_percent", 0) or 0) + float(s.get("ram_percent", 0) or 0) + float(s.get("disk_busy_percent", 0) or 0)), reverse=True)[:8]
        for s in worst:
            lines.append(
                f"{s.get('timestamp')} | CPU {s.get('cpu_percent')}% | RAM {s.get('ram_percent')}% "
                f"free {s.get('ram_available_gb')}GB | Disk busy {s.get('disk_busy_percent')}% "
                f"R {s.get('disk_read_mb_s')} W {s.get('disk_write_mb_s')} MB/s | Rust {s.get('rust_mem_mb')}MB"
            )
        lines.append("")
        lines.append("Note: монитор не читает FPS/frametime напрямую и не внедряется в Rust, чтобы не трогать EAC.")
        return "\n".join(lines)

    def monitor_report_dir(self) -> Path:
        p = core.app_dir() / "monitor_reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def auto_save_monitor_report(self, report: str) -> None:
        try:
            p = self.monitor_report_dir() / f"stutter_report_{core.now_stamp()}.txt"
            p.write_text(report, encoding="utf-8")
            self.log(f"[monitor] report saved: {p}")
        except Exception as exc:
            self.log(f"[monitor][warn] Не смог сохранить report: {exc}")

    def save_monitor_csv(self) -> None:
        if not self.monitor_samples:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Нет samples для CSV.")
            return
        default = f"stutter_samples_{core.now_stamp()}.csv"
        p = filedialog.asksaveasfilename(
            title="Сохранить Stutter Monitor CSV",
            defaultextension=".csv",
            initialfile=default,
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            keys = [
                "timestamp", "sample_index", "cpu_percent", "ram_percent", "ram_used_gb", "ram_available_gb",
                "disk_read_mb_s", "disk_write_mb_s", "disk_busy_percent", "rust_running", "rust_pid", "rust_mem_mb", "rust_cpu_percent",
            ]
            with Path(p).open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for s in self.monitor_samples:
                    writer.writerow({k: s.get(k, "") for k in keys})
            self.log(f"[monitor] CSV saved: {p}")
        except Exception as exc:
            self.log(f"[monitor][err] Не смог сохранить CSV: {exc}")

    def copy_monitor_report(self) -> None:
        text = self.monitor_report_text or (self.analyze_stutter_samples(self.monitor_samples) if self.monitor_samples else "Нет отчёта Stutter Monitor.")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log("[monitor] report copied.")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Stutter Monitor report скопирован.")

    def open_monitor_folder(self) -> None:
        self.open_path(self.monitor_report_dir())

    # ------------------------------------------------------------------
    # Game Session Mode
    # ------------------------------------------------------------------
    def set_session_profile(self, profile: str) -> None:
        if profile not in {"safe", "balanced", "aggressive"}:
            profile = "balanced"
        self.session_profile_var.set(profile)
        self.update_session_profile_buttons()

    def update_session_profile_buttons(self) -> None:
        if not hasattr(self, "session_profile_buttons"):
            return
        active = self.session_profile_var.get()
        colors = {"safe": GREEN, "balanced": BLUE, "aggressive": RED}
        for profile, btn in self.session_profile_buttons.items():
            if profile == active:
                btn.configure(fg_color=colors.get(profile, BLUE), text_color="#FFFFFF")
            else:
                btn.configure(fg_color=CARD, hover_color=CARD_HOVER, text_color=TEXT)

    def session_log(self, text: str) -> None:
        self.log(f"[session] {text}")
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {text}\n"

        def append() -> None:
            if hasattr(self, "session_log_box"):
                try:
                    self.session_log_box.configure(state="normal")
                    self.session_log_box.insert("end", line)
                    self.session_log_box.see("end")
                    self.session_log_box.configure(state="disabled")
                except Exception:
                    pass
        self.ui(append)

    def update_session_status(self, text: str) -> None:
        def apply() -> None:
            if hasattr(self, "session_status_label"):
                self.session_status_label.configure(text=text)
        self.ui(apply)

    def start_game_session(self) -> None:
        if self.session_active:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Game Session уже активен.")
            return
        if self.state_data.get("active_session"):
            ok = messagebox.askyesno(
                "Rust FPS Optimizer Pro",
                "Найден незавершённый Game Session из прошлого запуска.\n\n"
                "Сначала восстановить прошлые изменения?",
            )
            if ok:
                self.end_game_session()
                return
        profile = self.session_profile_var.get()
        if profile == "aggressive":
            ok = messagebox.askyesno(
                "Rust FPS Optimizer Pro",
                "Game Session с AGGRESSIVE включает более жёсткие твики.\n"
                "Они будут откатаны после выхода из Rust, но HAGS/некоторые изменения могут требовать перезагрузку.\n\n"
                "Продолжить?",
            )
            if not ok:
                return
        selected_groups = self.selected_process_groups()
        if selected_groups or self.session_force_close_var.get():
            ok = messagebox.askyesno(
                "Rust FPS Optimizer Pro",
                "Включено закрытие фоновых приложений.\n"
                "Несохранённые вкладки/проекты могут потеряться.\n\n"
                "Продолжить?",
            )
            if not ok:
                return
        self.session_active = True
        self.session_stop_event.clear()
        self.session_changes = []
        self.update_session_status("Game Session запускается...")
        if hasattr(self, "session_start_btn"):
            self.session_start_btn.configure(state="disabled")
        threading.Thread(target=self.game_session_worker, daemon=True).start()

    def selected_process_groups(self) -> List[str]:
        groups: List[str] = []
        if self.session_close_browsers_var.get():
            groups.append("browsers")
        if self.session_close_recording_var.get():
            groups.append("recording")
        if self.session_close_launchers_var.get():
            groups.append("launchers")
        if self.session_close_chat_var.get():
            groups.append("chat")
        return groups

    def game_session_worker(self) -> None:
        profile = self.session_profile_var.get()
        backup_dir = core.make_profile_backup_dir(f"game_session_{profile}")
        changes: List[Dict[str, Any]] = []
        record = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "profile": f"game_session_{profile}",
            "backup_dir": str(backup_dir),
            "changes": changes,
            "ui": "pro_session",
        }
        try:
            self.session_log(f"=== GAME SESSION START ({profile.upper()}) ===")
            if not core.is_windows():
                self.session_log("[err] Game Session работает только на Windows 10/11.")
                self.session_active = False
                return

            if self.session_backup_var.get():
                core.backup_configs(backup_dir, self.session_log)
                core.clear_logs(backup_dir, self.session_log)

            if profile == "safe":
                core.apply_safe_tweaks(changes, self.session_log)
            elif profile == "balanced":
                core.apply_balanced_tweaks(changes, self.session_log)
            elif profile == "aggressive":
                core.apply_aggressive_tweaks(changes, self.session_log)
            else:
                core.apply_balanced_tweaks(changes, self.session_log)

            self.session_changes = changes
            record["changes"] = changes
            self.state_data["active_session"] = record
            core.save_state(self.state_data)
            self.session_log(f"Профиль применён временно. Изменений для отката: {len(changes)}")

            self.close_selected_background_apps()

            if self.session_launch_var.get():
                core.launch_rust_via_steam(self.session_log)
            else:
                self.session_log("Автозапуск Rust выключен. Запусти Rust вручную.")

            if self.session_priority_var.get() or self.session_auto_restore_var.get():
                self.monitor_rust_session()
            else:
                self.session_log("Мониторинг выключен. Не забудь нажать Restore / End Session после игры.")
                self.update_session_status("Game Session активен. Откат вручную через Restore / End Session.")
        except Exception as exc:
            self.session_log(f"[err] Game Session: {exc}")
            if changes:
                self.restore_game_session_changes(changes, reason="ошибка запуска")
        finally:
            if not self.session_active:
                self.ui(lambda: self.session_start_btn.configure(state="normal") if hasattr(self, "session_start_btn") else None)

    def close_selected_background_apps(self) -> None:
        groups = self.selected_process_groups()
        if not groups:
            self.session_log("Закрытие фоновых приложений выключено.")
            return
        names: List[str] = []
        for group in groups:
            names.extend(core.BACKGROUND_PROCESS_GROUPS.get(group, []))
        self.session_log("Закрываю выбранные фоновые приложения мягко...")
        core.close_processes_by_names(names, self.session_log, force=self.session_force_close_var.get())

    def monitor_rust_session(self) -> None:
        self.session_log("Мониторю RustClient.exe. Как появится — выставлю High priority.")
        self.update_session_status("Ожидаю RustClient.exe...")
        saw_rust = False
        last_priority = 0.0
        started_wait = time.time()
        while not self.session_stop_event.is_set():
            running = core.rust_process_running()
            now = time.time()
            if running:
                if not saw_rust:
                    self.session_log("RustClient.exe найден. Сессия активна.")
                    self.update_session_status("Rust запущен. Мониторинг активен.")
                    saw_rust = True
                if self.session_priority_var.get() and now - last_priority > 18:
                    core.set_rust_priority_high(self.session_log, quiet_not_running=True)
                    last_priority = now
            else:
                if saw_rust:
                    self.session_log("RustClient.exe закрылся.")
                    break
                if now - started_wait > 360:
                    self.session_log("RustClient.exe не появился за 6 минут.")
                    if not self.session_launch_var.get():
                        self.session_log("Ожидание продолжается, потому что автозапуск был выключен.")
                        started_wait = now
                    else:
                        break
            time.sleep(4)

        if self.session_auto_restore_var.get():
            self.restore_game_session_changes(self.session_changes, reason="авто-откат после сессии")
        else:
            self.session_log("Авто-откат выключен. Нажми Restore / End Session вручную.")
            self.update_session_status("Game Session завершён/ожидает ручного отката.")

    def end_game_session(self) -> None:
        self.session_stop_event.set()
        changes = self.session_changes
        active = self.state_data.get("active_session")
        if not changes and isinstance(active, dict):
            changes = active.get("changes", [])
        if not changes:
            messagebox.showinfo("Rust FPS Optimizer Pro", "Нет активных session-изменений для отката.")
            self.session_active = False
            if hasattr(self, "session_start_btn"):
                self.session_start_btn.configure(state="normal")
            return
        ok = messagebox.askyesno("Rust FPS Optimizer Pro", "Восстановить изменения Game Session сейчас?")
        if not ok:
            return
        threading.Thread(target=lambda: self.restore_game_session_changes(changes, reason="ручной откат"), daemon=True).start()

    def restore_game_session_changes(self, changes: List[Dict[str, Any]], reason: str = "откат") -> None:
        if not changes:
            self.session_log("Нет изменений для восстановления.")
        else:
            self.session_log(f"=== GAME SESSION RESTORE ({reason}) ===")
            for ch in reversed(changes):
                if ch.get("type") == "registry":
                    core.restore_reg_value(ch, self.session_log)
                elif ch.get("type") == "power_scheme":
                    core.restore_power_scheme(ch, self.session_log)
                else:
                    self.session_log(f"[warn] Unknown restore change: {ch.get('type')}")
        try:
            self.state_data.pop("active_session", None)
            core.save_state(self.state_data)
        except Exception:
            pass
        self.session_changes = []
        self.session_active = False
        self.update_session_status("Game Session восстановлен. Можно запускать новую сессию.")
        self.session_log("[done] Game Session откатан.")
        self.ui(lambda: self.session_start_btn.configure(state="normal") if hasattr(self, "session_start_btn") else None)

    # ------------------------------------------------------------------
    # Auto Rust settings generator
    # ------------------------------------------------------------------
    def set_tuning_target(self, target: str) -> None:
        if target not in core.RUST_TUNING_TARGETS:
            target = "balanced"
        self.tuning_target.set(target)
        self.update_tuning_target_buttons()
        if self.pc_info:
            self.generate_tuning_async()

    def update_tuning_target_buttons(self) -> None:
        if not hasattr(self, "tuning_target_buttons"):
            return
        active = self.tuning_target.get()
        colors = {"max_fps": RED, "balanced": BLUE, "quality": PURPLE, "streamer": GREEN}
        for target, btn in self.tuning_target_buttons.items():
            if target == active:
                btn.configure(fg_color=colors.get(target, BLUE), text_color="#FFFFFF")
            else:
                btn.configure(fg_color=CARD, hover_color=CARD_HOVER, text_color=TEXT)

    def generate_tuning_async(self) -> None:
        if self.spec_busy:
            if hasattr(self, "tuning_status_label"):
                self.tuning_status_label.configure(text="Скан ПК уже идёт. Подожди пару секунд...")
            return
        if hasattr(self, "tuning_status_label"):
            self.tuning_status_label.configure(text="Подбираю настройки Rust под железо...")

        def worker() -> None:
            try:
                info = self.pc_info or core.collect_pc_info()
                tuning = core.generate_rust_tuning(info, self.tuning_target.get())
                report = core.render_rust_tuning(tuning)
                self.pc_info = info
                self.current_tuning = tuning
                self.tuning_report_text = report

                def apply() -> None:
                    self.populate_tuning(tuning, report)
                    if hasattr(self, "tuning_status_label"):
                        self.tuning_status_label.configure(text=f"Готово: {_dt.datetime.now().strftime('%H:%M:%S')}")
                self.ui(apply)
            except Exception as exc:
                self.log(f"[err] Auto Rust Settings: {exc}")
                self.ui(lambda: self.tuning_status_label.configure(text=f"Ошибка подбора: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def populate_tuning(self, tuning: Dict[str, Any], report: str = "") -> None:
        self.current_tuning = tuning
        self.tuning_report_text = report or core.render_rust_tuning(tuning)
        summary_lines = list(tuning.get("summary", []))
        warnings = tuning.get("warnings", [])
        if warnings:
            summary_lines.append("")
            summary_lines.append("Важно:")
            summary_lines += ["• " + str(w) for w in warnings[:3]]
        launch = str(tuning.get("launch_options", ""))
        profile = str(tuning.get("recommended_profile", "BALANCED"))

        if hasattr(self, "tuning_summary_label"):
            self.tuning_summary_label.configure(text="\n".join(summary_lines) if summary_lines else "Нет данных.")
        if hasattr(self, "tuning_launch_entry"):
            self.tuning_launch_entry.delete(0, "end")
            self.tuning_launch_entry.insert(0, launch)
        if hasattr(self, "apply_recommended_btn"):
            self.apply_recommended_btn.configure(text=f"Применить {profile}")
        if hasattr(self, "tuning_report_box"):
            self.set_textbox(self.tuning_report_box, self.tuning_report_text)

        if not hasattr(self, "tuning_settings_scroll"):
            return
        for child in self.tuning_settings_scroll.winfo_children():
            child.destroy()

        grouped: Dict[str, List[Dict[str, str]]] = {}
        for st in tuning.get("settings", []):
            if isinstance(st, dict):
                grouped.setdefault(str(st.get("section", "Other")), []).append(st)

        for section, rows in grouped.items():
            sec = ctk.CTkFrame(self.tuning_settings_scroll, fg_color=CARD, corner_radius=14)
            sec.pack(fill="x", padx=8, pady=7)
            ctk.CTkLabel(sec, text=section, text_color=BLUE_2, font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=12, pady=(10, 6))
            for st in rows:
                row = ctk.CTkFrame(sec, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=str(st.get("name", "")), text_color=MUTED, font=("Segoe UI", 11, "bold"), width=170, anchor="w").pack(side="left", padx=(0, 8))
                value_box = ctk.CTkFrame(row, fg_color="transparent")
                value_box.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(value_box, text=str(st.get("value", "")), text_color=TEXT, font=("Segoe UI", 11, "bold"), anchor="w", justify="left").pack(anchor="w")
                reason = str(st.get("reason", ""))
                if reason:
                    ctk.CTkLabel(value_box, text=reason, text_color=MUTED_2, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=520).pack(anchor="w")
            ctk.CTkFrame(sec, height=6, fg_color="transparent").pack(fill="x")

    def copy_tuning_launch(self) -> None:
        if not self.current_tuning:
            self.generate_tuning_async()
            return
        text = str(self.current_tuning.get("launch_options", ""))
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log(f"[ok] Auto launch options copied: {text}")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Launch Options скопированы.")

    def copy_tuning_report(self) -> None:
        if not self.tuning_report_text:
            self.generate_tuning_async()
            return
        self.clipboard_clear()
        self.clipboard_append(self.tuning_report_text)
        self.log("[ok] Rust settings report copied.")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Отчёт с настройками скопирован.")

    def save_tuning_report(self) -> None:
        if not self.tuning_report_text:
            self.generate_tuning_async()
            return
        default = f"rust_settings_{self.tuning_target.get()}_{core.now_stamp()}.txt"
        p = filedialog.asksaveasfilename(
            title="Сохранить настройки Rust",
            defaultextension=".txt",
            initialfile=default,
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if not p:
            return
        try:
            Path(p).write_text(self.tuning_report_text, encoding="utf-8")
            self.log(f"[ok] Rust settings report saved: {p}")
        except Exception as exc:
            self.log(f"[err] Не смог сохранить Rust settings report: {exc}")

    def apply_recommended_profile(self) -> None:
        if not self.current_tuning:
            self.generate_tuning_async()
            return
        profile = str(self.current_tuning.get("recommended_profile", "BALANCED")).lower()
        if profile not in {"safe", "balanced", "aggressive"}:
            profile = "balanced"
        self.run_profile(profile)

    # ------------------------------------------------------------------
    # Launch options
    # ------------------------------------------------------------------
    def update_launch_options(self) -> None:
        if hasattr(self, "launch_var"):
            self.launch_var.set(core.launch_options("balanced", self.ram_gb, self.exclusive_var.get()))

    def copy_launch(self, profile: str) -> None:
        text = core.launch_options(profile, self.ram_gb, self.exclusive_var.get())
        if hasattr(self, "launch_var"):
            self.launch_var.set(text)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log(f"[ok] Launch options {profile.upper()} скопированы: {text}")
        messagebox.showinfo("Rust FPS Optimizer Pro", "Скопировано. Вставь в Steam → Rust → Properties → Launch Options.")

    def launch_and_monitor(self) -> None:
        def work() -> None:
            core.launch_rust_via_steam(self.log)
            core.monitor_priority(self.log, seconds=240)
        self.run_in_thread(work)

    # ------------------------------------------------------------------
    # Optimization actions
    # ------------------------------------------------------------------
    def run_profile(self, profile: str) -> None:
        clear_shader_after = False
        if profile == "aggressive":
            ok = messagebox.askyesno(
                "Rust FPS Optimizer Pro",
                "Aggressive включает более жёсткие, но обратимые твики Windows.\n"
                "HAGS/Ultimate Performance могут требовать админ-права и перезагрузку.\n\n"
                "Продолжить?",
            )
            if not ok:
                return
            clear_shader_after = messagebox.askyesno(
                "Rust FPS Optimizer Pro",
                "Дополнительно очистить shader cache Rust?\n\n"
                "Если кэш битый — может помочь. Но первый запуск/прогрузка после удаления может временно фризить сильнее.",
            )
        self.run_in_thread(lambda: self.apply_profile(profile, clear_shader_after))

    def apply_profile(self, profile: str, clear_shader_after: bool = False) -> None:
        if not core.is_windows():
            self.log("[err] Профили применяются только на Windows 10/11.")
            return
        self.log(f"=== APPLY {profile.upper()} ===")
        backup_dir = core.make_profile_backup_dir(profile)
        changes: List[Dict[str, Any]] = []

        core.backup_configs(backup_dir, self.log)
        core.clear_logs(backup_dir, self.log)

        if profile == "safe":
            core.apply_safe_tweaks(changes, self.log)
        elif profile == "balanced":
            core.apply_balanced_tweaks(changes, self.log)
        elif profile == "aggressive":
            core.apply_aggressive_tweaks(changes, self.log)
            if clear_shader_after:
                core.clear_shader_cache(self.log)
        else:
            self.log(f"[err] Неизвестный профиль: {profile}")
            return

        record = {
            "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
            "profile": profile,
            "backup_dir": str(backup_dir),
            "changes": changes,
            "rust_exes": [str(p) for p in core.discover_rust_exes()],
            "cfg_dirs": [str(p) for p in core.discover_cfg_dirs()],
            "ui": "pro",
        }
        self.state_data.setdefault("profiles", []).append(record)
        core.save_state(self.state_data)
        self.log(f"[done] {profile.upper()} применён. Изменений для отката: {len(changes)}. Backup: {backup_dir}")
        self.log(f"[tip] Launch options: {core.launch_options(profile, self.ram_gb, self.exclusive_var.get())}")

    def undo_last(self) -> None:
        if not messagebox.askyesno("Rust FPS Optimizer Pro", "Откатить последний применённый профиль? cfg-бэкапы останутся в папке backups."):
            return
        self.run_in_thread(self.undo_last_impl)

    def undo_last_impl(self) -> None:
        profiles = self.state_data.get("profiles", [])
        if not profiles:
            self.log("[info] Нет применённых профилей для отката.")
            return
        last = profiles.pop()
        self.log(f"=== UNDO {str(last.get('profile', '?')).upper()} {last.get('timestamp', '')} ===")
        for ch in reversed(last.get("changes", [])):
            if ch.get("type") == "registry":
                core.restore_reg_value(ch, self.log)
            elif ch.get("type") == "power_scheme":
                core.restore_power_scheme(ch, self.log)
            else:
                self.log(f"[warn] Unknown undo change: {ch.get('type')}")
        core.save_state(self.state_data)
        self.log("[done] Откат завершён.")

    def backup_only(self) -> None:
        self.run_in_thread(self.backup_only_impl)

    def backup_only_impl(self) -> None:
        backup_dir = core.make_profile_backup_dir("manual_backup")
        core.backup_configs(backup_dir, self.log)
        self.log(f"[done] Backup готов: {backup_dir}")

    def clear_shader_cache_confirmed(self) -> None:
        ok = messagebox.askyesno(
            "Rust FPS Optimizer Pro",
            "Удалить Steam shader cache Rust?\n\n"
            "Если кэш битый — может помочь. Но первый запуск/прогрузка после удаления может временно фризить сильнее.",
        )
        if not ok:
            return
        self.run_in_thread(lambda: core.clear_shader_cache(self.log))

    def pick_rust_exe(self) -> None:
        p = filedialog.askopenfilename(title="Выбери RustClient.exe", filetypes=[("RustClient.exe", "RustClient.exe"), ("EXE", "*.exe")])
        if not p:
            return
        path = Path(p)
        if path.name.lower() != "rustclient.exe":
            if not messagebox.askyesno("Rust FPS Optimizer Pro", "Это не RustClient.exe. Всё равно добавить GPU/FSE preference для этого exe?"):
                return
        changes: List[Dict[str, Any]] = []
        core.set_reg_value(
            "HKCU",
            r"Software\Microsoft\DirectX\UserGpuPreferences",
            str(path),
            "GpuPreference=2;",
            "REG_SZ",
            changes,
            self.log,
        )
        core.set_reg_value(
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
            "ui": "pro",
        }
        self.state_data.setdefault("profiles", []).append(record)
        core.save_state(self.state_data)
        self.log(f"[done] Настройки для выбранного exe применены: {path}")
        self.refresh_status()

    # ------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------
    def open_backup_folder(self) -> None:
        self.open_path(core.backup_root())

    def open_app_folder(self) -> None:
        self.open_path(core.app_dir())

    def open_path(self, p: Path) -> None:
        try:
            if core.is_windows():
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                self.log(str(p))
        except Exception as exc:
            self.log(f"[warn] Не смог открыть {p}: {exc}")


def main() -> int:
    app = ProApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
