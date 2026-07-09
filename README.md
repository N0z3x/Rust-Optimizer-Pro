# Rust FPS Optimizer Pro v1.0

Windows-утилита для Rust под **FPS, фризы, диагностику, очистку, config-backups и отчёты**.

Важно: это **не чит, не инжектор и не обход EAC**. Программа не лезет в память игры, не патчит античит и не внедряется в Rust.

## Что нового в v1.0

Добавлен **Health Check / Auto Fix**.

Новая вкладка:

```text
Health Check
```

Она проверяет:

- Windows/админ-права;
- найден ли Rust;
- объём RAM;
- свободное место на диске с Rust;
- примерный тип диска Rust: SSD/NVMe/HDD, если Windows отдаёт данные;
- текущий power plan;
- Game Mode;
- Xbox DVR/background capture;
- HAGS;
- есть ли cfg snapshot;
- есть ли Stutter Monitor report;
- сколько найдено логов/кэшей Cleaner;
- активный незавершённый Game Session;
- фоновые приложения из списка;
- доступен ли `psutil` для Stutter Monitor.

Показывает score:

```text
0-100 Health Score
BAD / WARN / INFO / OK issues
```

### Auto Fix Safe Issues

Кнопка:

```text
Auto Fix Safe Issues
```

Делает только безопасные обратимые фиксы:

- создаёт cfg snapshot/backup;
- включает Game Mode;
- отключает Xbox DVR/background capture;
- выставляет High performance GPU preference для Rust, если Rust найден.

Registry-изменения можно откатить через:

```text
Бэкапы / Лог → Откатить последний профиль
```

## Что есть в Pro

- **Health Check** — score, проблемы, безопасный Auto Fix.
- **Оптимизация** — SAFE / BALANCED / AGGRESSIVE.
- **Game Session** — временный игровой режим с авто-откатом после выхода из Rust.
- **Stutter Monitor** — диагностика фризов по CPU/RAM/Disk/Rust process.
- **Cleaner / Repair** — очистка логов/кэшей и Steam Validate Rust.
- **Config Manager** — backup/restore/export cfg-файлов.
- **Report Center** — HTML/ZIP diagnostic bundle.
- **Rust Settings** — автоподбор настроек Rust под железо.
- **ПК / Железо** — полный отчёт по сборке ПК.
- **Launch Options** — генератор параметров запуска Steam.
- **Бэкапы / Лог** — логи и откат.

## Report Center

Создаёт ZIP и красивый HTML:

- `support_report.html`;
- `pc_report.txt`;
- `health_check.txt`;
- `rust_settings.txt`;
- `latest_stutter_report.txt`;
- `cleaner_scan.json`;
- `config_files.json`;
- `config_snapshots.json`;
- `state_summary.json`.

Отчёты:

```text
%LOCALAPPDATA%\RustFPSOptimizer\reports\
```

## Config Manager

Умеет:

- находить cfg/json/txt/xml файлы Rust;
- создавать snapshot cfg-файлов;
- восстанавливать cfg из snapshot;
- экспортировать snapshot в `.zip`;
- записывать `RustOptimizer_recommended_settings.txt` с рекомендациями.

Snapshot:

```text
%LOCALAPPDATA%\RustFPSOptimizer\config_backups\
```

## Cleaner / Repair

Чистит только известные пути:

- Rust logs;
- Steam shader cache Rust `appid 252490`;
- Rust crash dumps;
- DirectX/GPU shader cache пользователя;
- старые Stutter Monitor reports;
- старые backups оптимизатора.

После очистки shader cache первый запуск может временно фризить сильнее, пока кэш пересобирается.

## Game Session

Рекомендованный режим:

```text
Profile: BALANCED
Launch Rust: ON
High priority: ON
Auto restore: ON
Backup cfg: ON
Force close: OFF
```

Game Session применяет профиль временно, запускает Rust, ставит High priority и откатывает registry/power plan после выхода из игры.

## Stutter Monitor

Безопасная диагностика без оверлея и инжекта:

- CPU usage;
- RAM usage;
- свободная RAM;
- Disk read/write;
- Disk busy;
- Rust RAM;
- Rust CPU;
- worst samples;
- текстовый отчёт и CSV.

## Rust Settings

Автоподбор:

- рекомендуемый профиль оптимизатора;
- launch options;
- настройки Graphics/Mesh/Image Effects;
- bottleneck CPU/GPU/RAM;
- предупреждения и советы.

Цели:

- Max FPS;
- Balanced;
- Quality;
- Streamer.

## Запуск

Распакуй архив полностью. В папке должны быть:

```text
RustFPSOptimizer_Pro.py
RustFPSOptimizer.py
Run_Pro_Source_As_Admin.bat
Build_EXE_Pro_Windows.bat
app.ico
requirements.txt
README.md
```

Запуск исходника от администратора:

```bat
Run_Pro_Source_As_Admin.bat
```

Сборка `.exe`:

```bat
Build_EXE_Pro_Windows.bat
```

Готовый файл:

```text
dist\RustFPSOptimizerPro.exe
```

Ручная сборка:

```bat
python -m pip install --upgrade customtkinter psutil pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --icon app.ico --add-data app.ico;. --collect-data customtkinter --hidden-import RustFPSOptimizer --hidden-import psutil --name RustFPSOptimizerPro RustFPSOptimizer_Pro.py
```

## Рекомендованный порядок

1. Запусти Pro от администратора.
2. **Health Check** → Scan Health → Auto Fix Safe Issues, если нужно.
3. **ПК / Железо** → скан.
4. **Config Manager** → Create snapshot.
5. **Rust Settings** → подобрать настройки.
6. **Cleaner / Repair** → почистить safe-мусор.
7. **Game Session** → запуск через BALANCED.
8. Если фризы остались — **Stutter Monitor** → записать катку и посмотреть отчёт.
9. **Report Center** → Create Support Bundle, если нужно скинуть диагностику.

## Файлы в v1.0 пакете

- `RustFPSOptimizer_Pro.py` — Pro GUI.
- `RustFPSOptimizer.py` — backend-функции, нужен Pro-версии.
- `app.ico` — иконка.
- `Build_EXE_Pro_Windows.bat` — сборка Pro `.exe`.
- `Run_Pro_Source_As_Admin.bat` — запуск Pro исходника от администратора.
- `requirements.txt` — зависимости.
- `README.md` — инструкция.
