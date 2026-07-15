#!/usr/bin/env python3
"""The first desktop surface for the local lecture-study assistant.

This module deliberately contains only the library and new-lecture entry flow.
Importing BBB recordings and processing them is added in later stages.
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import font, ttk

from bbb_import import BBBImportError, BBBRecording, inspect_bbb_recording, load_library, save_to_library
from local_pipeline import LocalProcessingError, lecture_is_prepared, prepare_lecture


PALETTE = {
    "canvas": "#FFFFFF",
    "sidebar": "#F3F6F4",
    "surface": "#FFFFFF",
    "surface_soft": "#F7FAF8",
    "ink": "#17211D",
    "muted": "#55635C",
    "faint": "#7B8981",
    "line": "#DDE5E0",
    "primary": "#176B45",
    "primary_hover": "#105A39",
    "primary_pressed": "#0B482D",
    "primary_soft": "#E8F3EC",
    "focus": "#0D7A4A",
    "success": "#176B45",
    "danger": "#A43D31",
}


@dataclass(frozen=True)
class Typography:
    family: str
    title: tuple[str, int, str]
    heading: tuple[str, int, str]
    body: tuple[str, int]
    body_bold: tuple[str, int, str]
    small: tuple[str, int]


class StudyApp(tk.Tk):
    """A calm desktop shell for managing study lectures."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Конспект — учебные материалы")
        self.geometry("1180x760")
        self.minsize(980, 660)
        self.configure(background=PALETTE["canvas"])

        self.type = self._create_typography()
        self.style = ttk.Style(self)
        self._configure_styles()
        self._current_screen: ttk.Frame | None = None
        self.library: list[BBBRecording] = self._load_library_safely()
        self._bbb_url = tk.StringVar()
        self._import_status = tk.StringVar()
        self._import_button: ttk.Button | None = None
        self._import_status_label: tk.Label | None = None
        self._processing_status = tk.StringVar()
        self._processing_progress: ttk.Progressbar | None = None
        self._processing_return_button: ttk.Button | None = None

        self._build_shell()
        self.show_library(animated=False)

    def _create_typography(self) -> Typography:
        preferred = "Segoe UI Variable"
        available = set(font.families())
        family = preferred if preferred in available else "Segoe UI"
        return Typography(
            family=family,
            title=(family, 27, "bold"),
            heading=(family, 18, "bold"),
            body=(family, 11),
            body_bold=(family, 11, "bold"),
            small=(family, 9),
        )

    def _configure_styles(self) -> None:
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=PALETTE["canvas"])
        self.style.configure(
            "Primary.TButton",
            background=PALETTE["primary"],
            foreground="#FFFFFF",
            borderwidth=0,
            focuscolor=PALETTE["focus"],
            font=self.type.body_bold,
            padding=(18, 11),
        )
        self.style.map(
            "Primary.TButton",
            background=[
                ("disabled", "#E1E9E4"),
                ("pressed", PALETTE["primary_pressed"]),
                ("active", PALETTE["primary_hover"]),
            ],
            foreground=[("disabled", "#C8D9CF")],
        )
        self.style.configure(
            "Secondary.TButton",
            background=PALETTE["surface"],
            foreground=PALETTE["ink"],
            borderwidth=1,
            relief="solid",
            focuscolor=PALETTE["focus"],
            font=self.type.body_bold,
            padding=(16, 10),
        )
        self.style.map(
            "Secondary.TButton",
            background=[
                ("disabled", "#F4F7F5"),
                ("active", PALETTE["surface_soft"]),
            ],
            foreground=[("disabled", PALETTE["faint"])],
        )
        self.style.configure(
            "Nav.TButton",
            background=PALETTE["sidebar"],
            foreground=PALETTE["ink"],
            borderwidth=0,
            font=self.type.body_bold,
            anchor="w",
            padding=(14, 10),
        )
        self.style.map(
            "Nav.TButton",
            background=[("active", PALETTE["primary_soft"])],
        )
        self.style.configure(
            "Source.TEntry",
            fieldbackground=PALETTE["surface"],
            foreground=PALETTE["ink"],
            bordercolor=PALETTE["line"],
            lightcolor=PALETTE["line"],
            darkcolor=PALETTE["line"],
            insertcolor=PALETTE["ink"],
            padding=(12, 10),
            font=self.type.body,
        )
        self.style.map(
            "Source.TEntry",
            bordercolor=[("focus", PALETTE["focus"])],
            lightcolor=[("focus", PALETTE["focus"])],
            darkcolor=[("focus", PALETTE["focus"])],
        )

    def _build_shell(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(
            self,
            background=PALETTE["sidebar"],
            highlightbackground=PALETTE["line"],
            highlightthickness=1,
            width=248,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = tk.Frame(sidebar, background=PALETTE["sidebar"])
        brand.pack(fill="x", padx=26, pady=(30, 36))
        mark = tk.Canvas(
            brand,
            width=28,
            height=28,
            background=PALETTE["sidebar"],
            highlightthickness=0,
        )
        mark.create_oval(3, 3, 25, 25, fill=PALETTE["primary"], outline="")
        mark.create_line(14, 8, 14, 20, fill="#FFFFFF", width=2)
        mark.create_line(9, 14, 19, 14, fill="#FFFFFF", width=2)
        mark.pack(side="left")
        tk.Label(
            brand,
            text="Конспект",
            font=(self.type.family, 16, "bold"),
            foreground=PALETTE["ink"],
            background=PALETTE["sidebar"],
        ).pack(side="left", padx=(10, 0), pady=(2, 0))

        ttk.Button(
            sidebar,
            text="Лекции",
            style="Nav.TButton",
            command=self.show_library,
        ).pack(fill="x", padx=14)

        footer = tk.Frame(sidebar, background=PALETTE["sidebar"])
        footer.pack(side="bottom", fill="x", padx=26, pady=28)
        tk.Label(
            footer,
            text="Данные хранятся\nна этом компьютере",
            justify="left",
            font=self.type.small,
            foreground=PALETTE["muted"],
            background=PALETTE["sidebar"],
        ).pack(anchor="w")

        workspace = tk.Frame(self, background=PALETTE["canvas"])
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_columnconfigure(0, weight=1)
        workspace.grid_rowconfigure(1, weight=1)
        self.workspace = workspace

        header = tk.Frame(workspace, background=PALETTE["canvas"], height=78)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        tk.Label(
            header,
            text="Учебные материалы",
            font=self.type.body_bold,
            foreground=PALETTE["ink"],
            background=PALETTE["canvas"],
        ).pack(side="left", padx=40, pady=28)
        tk.Label(
            header,
            text="Локальный режим",
            font=self.type.small,
            foreground=PALETTE["muted"],
            background=PALETTE["primary_soft"],
            padx=10,
            pady=5,
        ).pack(side="right", padx=40, pady=21)

        content = tk.Frame(workspace, background=PALETTE["canvas"])
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.content = content

    def show_library(self, animated: bool = True) -> None:
        screen = ttk.Frame(self.content, style="TFrame")
        screen.configure(padding=(40, 28, 40, 40))
        screen.grid_columnconfigure(0, weight=1)
        screen.grid_rowconfigure(2, weight=1)

        intro = tk.Frame(screen, background=PALETTE["canvas"])
        intro.grid(row=0, column=0, sticky="ew")
        intro.grid_columnconfigure(0, weight=1)
        tk.Label(
            intro,
            text="Моя библиотека",
            font=self.type.title,
            foreground=PALETTE["ink"],
            background=PALETTE["canvas"],
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            intro,
            text="Все записи, конспекты и материалы по лекциям будут собраны здесь.",
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["canvas"],
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            intro,
            text="Новая лекция  →",
            style="Primary.TButton",
            command=self.show_new_lecture,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        divider = tk.Frame(screen, background=PALETTE["line"], height=1)
        divider.grid(row=1, column=0, sticky="ew", pady=(32, 0))

        if self.library:
            self._build_library_list(screen)
        else:
            self._build_empty_library(screen)

        self._show_screen(screen, animated)

    def _build_empty_library(self, screen: ttk.Frame) -> None:
        empty = tk.Frame(screen, background=PALETTE["canvas"])
        empty.grid(row=2, column=0, sticky="nsew")
        empty.grid_columnconfigure(0, weight=1)
        empty.grid_rowconfigure(0, weight=1)

        message = tk.Frame(empty, background=PALETTE["canvas"])
        message.grid(row=0, column=0)
        icon = tk.Canvas(
            message,
            width=56,
            height=56,
            background=PALETTE["canvas"],
            highlightthickness=0,
        )
        icon.create_rectangle(
            13,
            10,
            43,
            46,
            outline=PALETTE["primary"],
            width=2,
        )
        icon.create_line(19, 21, 37, 21, fill=PALETTE["primary"], width=2)
        icon.create_line(19, 28, 37, 28, fill=PALETTE["primary"], width=2)
        icon.create_line(19, 35, 31, 35, fill=PALETTE["primary"], width=2)
        icon.pack(pady=(0, 18))
        tk.Label(
            message,
            text="Библиотека пока пуста",
            font=self.type.heading,
            foreground=PALETTE["ink"],
            background=PALETTE["canvas"],
        ).pack()
        tk.Label(
            message,
            text="Добавь первую запись — здесь появится её конспект\nи все материалы для повторения.",
            justify="center",
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["canvas"],
        ).pack(pady=(8, 20))
        ttk.Button(
            message,
            text="Добавить первую лекцию",
            style="Secondary.TButton",
            command=self.show_new_lecture,
        ).pack()

    def _build_library_list(self, screen: ttk.Frame) -> None:
        listing = tk.Frame(screen, background=PALETTE["canvas"])
        listing.grid(row=2, column=0, sticky="nsew", pady=(22, 0))
        listing.grid_columnconfigure(0, weight=1)

        tk.Label(
            listing,
            text=f"В библиотеке: {len(self.library)}",
            font=self.type.small,
            foreground=PALETTE["muted"],
            background=PALETTE["canvas"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        for index, recording in enumerate(self.library):
            row = tk.Frame(
                listing,
                background=PALETTE["surface_soft"],
                highlightbackground=PALETTE["line"],
                highlightthickness=1,
                padx=20,
                pady=18,
            )
            row.grid(row=index + 1, column=0, sticky="ew", pady=(0, 10))
            row.grid_columnconfigure(0, weight=1)
            tk.Label(
                row,
                text=recording.title,
                font=self.type.body_bold,
                foreground=PALETTE["ink"],
                background=PALETTE["surface_soft"],
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                row,
                text=self._recording_summary(recording),
                font=self.type.small,
                foreground=PALETTE["muted"],
                background=PALETTE["surface_soft"],
            ).grid(row=1, column=0, sticky="w", pady=(7, 0))
            prepared = lecture_is_prepared(recording)
            action_text = "Материалы готовы" if prepared else "Подготовить"
            action_style = "Secondary.TButton" if prepared else "Primary.TButton"
            action = (
                self.show_library
                if prepared
                else lambda item=recording: self.start_local_processing(item)
            )
            ttk.Button(
                row,
                text=action_text,
                style=action_style,
                command=action,
            ).grid(row=0, column=1, rowspan=2, sticky="e")

    def show_new_lecture(self) -> None:
        self._import_status.set("")
        screen = ttk.Frame(self.content, style="TFrame")
        screen.configure(padding=(40, 28, 40, 40))
        screen.grid_columnconfigure(0, weight=1)

        ttk.Button(
            screen,
            text="← К библиотеке",
            style="Secondary.TButton",
            command=self.show_library,
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            screen,
            text="Новая лекция",
            font=self.type.title,
            foreground=PALETTE["ink"],
            background=PALETTE["canvas"],
        ).grid(row=1, column=0, sticky="w", pady=(34, 0))
        tk.Label(
            screen,
            text="Вставь публичную ссылку на запись BigBlueButton. Мы быстро проверим доступные материалы.",
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["canvas"],
        ).grid(row=2, column=0, sticky="w", pady=(8, 26))

        choices = tk.Frame(
            screen,
            background=PALETTE["surface_soft"],
            highlightbackground=PALETTE["line"],
            highlightthickness=1,
            padx=24,
            pady=24,
        )
        choices.grid(row=3, column=0, sticky="ew")
        choices.grid_columnconfigure(1, weight=1)
        tk.Label(
            choices,
            text="Источник записи",
            font=self.type.body_bold,
            foreground=PALETTE["ink"],
            background=PALETTE["surface_soft"],
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(
            choices,
            text="Видео не будет скачиваться сейчас: сначала сохраним потоки и тексты слайдов в библиотеку.",
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["surface_soft"],
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 20))
        tk.Label(
            choices,
            text="Ссылка на BBB playback",
            font=self.type.small,
            foreground=PALETTE["muted"],
            background=PALETTE["surface_soft"],
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 7))
        source_entry = ttk.Entry(
            choices,
            textvariable=self._bbb_url,
            style="Source.TEntry",
        )
        source_entry.grid(row=3, column=0, columnspan=2, sticky="ew")
        source_entry.focus_set()
        source_entry.bind("<Return>", lambda _: self.start_bbb_import())

        self._import_button = ttk.Button(
            choices,
            text="Проверить и добавить",
            style="Primary.TButton",
            command=self.start_bbb_import,
        )
        self._import_button.grid(row=4, column=0, sticky="w", pady=(16, 0))
        ttk.Button(
            choices,
            text="Видео с компьютера — позже",
            style="Secondary.TButton",
            state="disabled",
        ).grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(16, 0))
        self._import_status_label = tk.Label(
            choices,
            textvariable=self._import_status,
            font=self.type.small,
            foreground=PALETTE["muted"],
            background=PALETTE["surface_soft"],
            wraplength=700,
            justify="left",
        )
        self._import_status_label.grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(14, 0),
        )

        self._show_screen(screen, animated=True)

    def start_bbb_import(self) -> None:
        playback_url = self._bbb_url.get().strip()
        if not playback_url:
            self._set_import_status(
                "Вставь ссылку вида https://…/playback.html?meetingId=…",
                PALETTE["danger"],
            )
            return
        if self._import_button is not None:
            self._import_button.state(["disabled"])
        self._set_import_status("Проверяем запись BBB и доступные материалы…", PALETTE["muted"])
        threading.Thread(
            target=self._import_bbb_worker,
            args=(playback_url,),
            daemon=True,
        ).start()

    def _import_bbb_worker(self, playback_url: str) -> None:
        try:
            recording = inspect_bbb_recording(playback_url)
            save_to_library(recording)
        except BBBImportError as exc:
            self.after(0, lambda: self._finish_import_error(str(exc)))
        except Exception:
            self.after(
                0,
                lambda: self._finish_import_error(
                    "Не удалось подключиться к записи. Проверь ссылку и попробуй ещё раз."
                ),
            )
        else:
            self.after(0, lambda: self._finish_import_success(recording))

    def _finish_import_success(self, recording: BBBRecording) -> None:
        self.library = self._load_library_safely()
        parts = ["звук"]
        if recording.has_screen_share:
            parts.append("демонстрация экрана")
        if recording.slides:
            parts.append(f"слайды: {len(recording.slides)}")
        self._set_import_status(
            f"«{recording.title}» добавлена: {', '.join(parts)}. Открой библиотеку, чтобы проверить запись.",
            PALETTE["success"],
        )
        if self._import_button is not None and self._import_button.winfo_exists():
            self._import_button.state(["!disabled"])

    def _finish_import_error(self, message: str) -> None:
        self._set_import_status(message, PALETTE["danger"])
        if self._import_button is not None and self._import_button.winfo_exists():
            self._import_button.state(["!disabled"])

    def _set_import_status(self, text: str, color: str) -> None:
        self._import_status.set(text)
        if self._import_status_label is not None and self._import_status_label.winfo_exists():
            self._import_status_label.configure(foreground=color)

    @staticmethod
    def _recording_summary(recording: BBBRecording) -> str:
        parts = ["BBB", "звук"]
        if recording.has_screen_share:
            parts.append("экран")
        if recording.slides:
            parts.append(f"слайдов: {len(recording.slides)}")
        return " · ".join(parts)

    @staticmethod
    def _load_library_safely() -> list[BBBRecording]:
        try:
            return load_library()
        except BBBImportError:
            return []

    def start_local_processing(self, recording: BBBRecording) -> None:
        self._processing_status.set("Подготовка начнётся после проверки локальных инструментов…")
        self.show_processing_screen(recording)
        threading.Thread(
            target=self._local_processing_worker,
            args=(recording,),
            daemon=True,
        ).start()

    def show_processing_screen(self, recording: BBBRecording) -> None:
        screen = ttk.Frame(self.content, style="TFrame")
        screen.configure(padding=(40, 40, 40, 40))
        screen.grid_columnconfigure(0, weight=1)
        screen.grid_rowconfigure(1, weight=1)

        tk.Label(
            screen,
            text="Подготавливаем материалы",
            font=self.type.title,
            foreground=PALETTE["ink"],
            background=PALETTE["canvas"],
        ).grid(row=0, column=0, sticky="w")

        panel = tk.Frame(
            screen,
            background=PALETTE["surface_soft"],
            highlightbackground=PALETTE["line"],
            highlightthickness=1,
            padx=28,
            pady=28,
        )
        panel.grid(row=1, column=0, sticky="nsew", pady=(26, 0))
        panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            panel,
            text=recording.title,
            font=self.type.heading,
            foreground=PALETTE["ink"],
            background=PALETTE["surface_soft"],
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            panel,
            text="Аудио и кадры будут обработаны на этом компьютере. Платные API не используются.",
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["surface_soft"],
        ).grid(row=1, column=0, sticky="w", pady=(8, 22))
        self._processing_progress = ttk.Progressbar(panel, mode="indeterminate")
        self._processing_progress.grid(row=2, column=0, sticky="ew")
        self._processing_progress.start(12)
        tk.Label(
            panel,
            textvariable=self._processing_status,
            font=self.type.body,
            foreground=PALETTE["muted"],
            background=PALETTE["surface_soft"],
            justify="left",
            wraplength=720,
        ).grid(row=3, column=0, sticky="w", pady=(18, 20))
        self._processing_return_button = ttk.Button(
            panel,
            text="Вернуться в библиотеку",
            style="Secondary.TButton",
            command=self.show_library,
            state="disabled",
        )
        self._processing_return_button.grid(row=4, column=0, sticky="w")

        self._show_screen(screen, animated=True)

    def _local_processing_worker(self, recording: BBBRecording) -> None:
        try:
            prepared = prepare_lecture(
                recording,
                progress=lambda message: self.after(
                    0,
                    lambda: self._processing_status.set(message),
                ),
            )
        except LocalProcessingError as exc:
            self.after(0, lambda: self._finish_processing_error(str(exc)))
        except Exception:
            self.after(
                0,
                lambda: self._finish_processing_error(
                    "Подготовка остановлена из-за неожиданной ошибки. Исходная запись сохранена в библиотеке."
                ),
            )
        else:
            self.after(0, lambda: self._finish_processing_success(prepared))

    def _finish_processing_success(self, prepared) -> None:
        if self._processing_progress is not None and self._processing_progress.winfo_exists():
            self._processing_progress.stop()
        ocr = "и OCR экрана" if prepared.screen_notes_path else "без OCR экрана"
        self._processing_status.set(
            f"Готово: транскрипция, {prepared.frame_count} кадров {ocr} сохранены локально."
        )
        self._enable_processing_return()

    def _finish_processing_error(self, message: str) -> None:
        if self._processing_progress is not None and self._processing_progress.winfo_exists():
            self._processing_progress.stop()
        self._processing_status.set(message)
        self._enable_processing_return()

    def _enable_processing_return(self) -> None:
        if (
            self._processing_return_button is not None
            and self._processing_return_button.winfo_exists()
        ):
            self._processing_return_button.state(["!disabled"])

    def _show_screen(self, screen: ttk.Frame, animated: bool) -> None:
        previous = self._current_screen
        self._current_screen = screen
        screen.place(x=0, y=0, relwidth=1, relheight=1)

        if previous is None:
            return
        if not animated or self._reduce_motion():
            previous.destroy()
            return

        duration_ms = 180
        frames = 9

        def advance(frame: int = 0) -> None:
            progress = min(frame / frames, 1)
            # A short cross-slide makes navigation clear without delaying work.
            screen.place_configure(x=round((1 - progress) * 18))
            previous.place_configure(x=-round(progress * 12))
            if progress < 1:
                self.after(duration_ms // frames, lambda: advance(frame + 1))
            else:
                screen.place_configure(x=0)
                previous.destroy()

        advance()

    @staticmethod
    def _reduce_motion() -> bool:
        # Tk does not expose the Windows accessibility preference portably.
        # A command-line escape hatch keeps motion optional for now.
        return "--reduce-motion" in sys.argv


def main() -> None:
    app = StudyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
