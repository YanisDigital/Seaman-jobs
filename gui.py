"""Графический интерфейс (Tkinter) для сбора вакансий.

Запуск из исходников:  python gui.py
В собранном .exe это окно открывается двойным кликом.
"""
from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from scraper import catalog
from scraper.runner import run_scrape
from scraper.settings import MaritimeZoneSettings, RequestSettings, Settings


def app_base_dir() -> Path:
    """Папка приложения: рядом с .exe (frozen) или рядом с gui.py (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class QueueLogHandler(logging.Handler):
    """Логи из рабочего потока кладём в очередь; окно читает их в UI-потоке."""

    def __init__(self, q: "queue.Queue[str]"):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put_nowait(self.format(record))
        except Exception:  # noqa: BLE001
            pass


class CheckList(ttk.LabelFrame):
    """Прокручиваемый список галочек + поле «добавить своё»."""

    def __init__(self, master, title: str, options):
        super().__init__(master, text=title)
        self.vars = []  # list[(BooleanVar, [keywords])]

        canvas = tk.Canvas(self, height=240, width=250, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        for label, keywords in options:
            var = tk.BooleanVar(value=False)
            ttk.Checkbutton(inner, text=label, variable=var).pack(anchor="w", padx=4)
            self.vars.append((var, keywords))

        def _wheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        ttk.Label(self, text="Добавить своё (через запятую):").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=4)
        self.extra = ttk.Entry(self)
        self.extra.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))

    def selected_keywords(self):
        kws = []
        for var, keywords in self.vars:
            if var.get():
                kws.extend(keywords)
        for token in self.extra.get().split(","):
            token = token.strip()
            if token:
                kws.append(token)
        return kws


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Поиск вакансий моряков")
        self.geometry("780x720")
        self.minsize(680, 600)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.worker: "threading.Thread | None" = None
        self.running = False
        self.stop_flag = False
        self.result_path: "Path | None" = None
        self.output_dir = app_base_dir() / "output"

        self._build_ui()
        self._setup_logging()
        self.after(150, self._drain_log)

    # ---------- интерфейс ----------
    def _build_ui(self) -> None:
        pad = dict(padx=8, pady=4)

        ttk.Label(self, text="Отметьте нужные должности и типы судов, выберите сайты и нажмите «Старт».",
                  font=("", 10, "bold")).pack(anchor="w", **pad)

        top = ttk.Frame(self)
        top.pack(fill="both", expand=False, **pad)
        self.positions = CheckList(top, "Должности", catalog.POSITIONS)
        self.positions.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.vessels = CheckList(top, "Типы судов", catalog.VESSEL_TYPES)
        self.vessels.pack(side="left", fill="both", expand=True, padx=(6, 0))

        sites_box = ttk.LabelFrame(self, text="Сайты")
        sites_box.pack(fill="x", **pad)
        self.site_vars = []  # list[(BooleanVar, key)]
        for label, key in catalog.SITES:
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(sites_box, text=label, variable=var).pack(side="left", padx=8, pady=4)
            self.site_vars.append((var, key))

        opts = ttk.LabelFrame(self, text="Параметры")
        opts.pack(fill="x", **pad)
        self.details_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Грузить детали (больше информации, медленнее)",
                        variable=self.details_var).grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        self.show_browser_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="maritime-zone: показать окно браузера (полные детали)",
                        variable=self.show_browser_var).grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        ttk.Label(opts, text="Лимит страниц с сайта (0 = все):").grid(row=2, column=0, sticky="w", padx=8, pady=2)
        self.limit_var = tk.StringVar(value="0")
        ttk.Spinbox(opts, from_=0, to=999, width=6, textvariable=self.limit_var).grid(
            row=2, column=1, sticky="w", pady=2)

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="▶ Старт", command=self.on_start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(btns, text="■ Стоп", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)
        self.open_btn = ttk.Button(btns, text="Открыть Excel", command=self.on_open_excel, state="disabled")
        self.open_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="Открыть папку", command=self.on_open_folder).pack(side="left", padx=6)

        self.status = ttk.Label(self, text="Готово к запуску.")
        self.status.pack(anchor="w", padx=8)

        log_frame = ttk.LabelFrame(self, text="Журнал")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        log_sb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

    def _setup_logging(self) -> None:
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)

    # ---------- журнал ----------
    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_log(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)
        # завершился ли рабочий поток?
        if self.running and self.worker is not None and not self.worker.is_alive():
            self.running = False
            self._on_done()
        self.after(150, self._drain_log)

    # ---------- запуск/остановка ----------
    def _build_settings(self) -> "Settings | None":
        sites = [key for var, key in self.site_vars if var.get()]
        if not sites:
            messagebox.showwarning("Нет сайтов", "Отметьте хотя бы один сайт.")
            return None
        try:
            limit = max(0, int(self.limit_var.get() or "0"))
        except ValueError:
            limit = 0
        positions = self.positions.selected_keywords()
        vessels = self.vessels.selected_keywords()
        if not positions and not vessels:
            if not messagebox.askyesno(
                    "Без фильтра",
                    "Не выбрано ни должностей, ни типов судов — будут собраны ВСЕ вакансии. Продолжить?"):
                return None
        return Settings(
            positions=positions,
            vessel_types=vessels,
            sites=sites,
            request=RequestSettings(max_pages_per_site=limit, fetch_details=self.details_var.get()),
            maritime_zone=MaritimeZoneSettings(headless=not self.show_browser_var.get()),
            output_dir=str(self.output_dir),
        )

    def on_start(self) -> None:
        if self.running:
            return
        settings = self._build_settings()
        if settings is None:
            return
        self.stop_flag = False
        self.result_path = None
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self.status.configure(text="Идёт сбор…")
        self._append_log("=== Старт ===")
        self.worker = threading.Thread(target=self._run, args=(settings,), daemon=True)
        self.worker.start()

    def _run(self, settings: Settings) -> None:
        try:
            vacs, path = run_scrape(settings, should_stop=lambda: self.stop_flag)
            self.result_path = path
            self.log_queue.put(f"=== Готово. Найдено вакансий: {len(vacs)} ===")
        except Exception as exc:  # noqa: BLE001
            self.log_queue.put(f"ОШИБКА: {exc}")
            logging.getLogger("scraper.gui").exception("Сбой прогона")

    def _on_done(self) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        if self.result_path and Path(self.result_path).exists():
            self.open_btn.configure(state="normal")
            self.status.configure(text=f"Готово. Файл: {self.result_path}")
        else:
            self.status.configure(text="Завершено.")

    def on_stop(self) -> None:
        self.stop_flag = True
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="Останавливаю после текущего шага…")
        self._append_log("=== Запрошена остановка ===")

    def on_open_excel(self) -> None:
        if self.result_path and Path(self.result_path).exists():
            try:
                os.startfile(str(self.result_path))  # noqa: S606 - Windows
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Не удалось открыть", str(exc))

    def on_open_folder(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(self.output_dir))  # noqa: S606 - Windows
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Не удалось открыть", str(exc))


def _run_selftest() -> int:
    """Скрытая самопроверка собранного .exe: один прогон maritime-zone (упакованный
    браузер) без окна. Результат пишется в selftest_result.txt рядом с программой."""
    out = app_base_dir() / "selftest_result.txt"
    try:
        settings = Settings(
            positions=[], vessel_types=[], sites=["maritime_zone"],
            request=RequestSettings(max_pages_per_site=1, fetch_details=False),
            maritime_zone=MaritimeZoneSettings(headless=True),
            output_dir=str(app_base_dir() / "output"),
        )
        vacs, path = run_scrape(settings)
        out.write_text(f"OK collected={len(vacs)} file={path}\n", encoding="utf-8")
        return 0 if vacs else 2
    except Exception as exc:  # noqa: BLE001
        out.write_text(f"FAIL {exc!r}\n", encoding="utf-8")
        return 1


def main() -> None:
    if "--selftest" in sys.argv:
        raise SystemExit(_run_selftest())
    App().mainloop()


if __name__ == "__main__":
    main()
