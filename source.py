#!/usr/bin/env python3
"""
GUI для yt-dlp в стиле macOS Dark Mode
Добавлен реальный прогресс-бар (парсинг процентов из вывода yt-dlp)
"""

import subprocess
import os
import sys
import re
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QLineEdit, QPushButton,
                              QComboBox, QTextEdit, QProgressBar, QFileDialog,
                              QMessageBox, QFrame)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

# Цвета в стиле macOS Dark
BG_COLOR = "#1e1e1e"
SURFACE_COLOR = "#2d2d2d"
ACCENT_COLOR = "#0a84ff"
ACCENT_PRESSED = "#0066cc"
TEXT_COLOR = "#ffffff"
TEXT_SECONDARY = "#8e8e93"
BORDER_COLOR = "#3d3d3d"
SUCCESS_COLOR = "#30d158"
ERROR_COLOR = "#ff453a"

class DownloadThread(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)  # процент (0-100)
    finished_signal = Signal(bool, str)

    def __init__(self, url, output_dir, format_choice, quality, audio_format,
                 video_format, yt_dlp_path, ffmpeg_path):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.format_choice = format_choice
        self.quality = quality
        self.audio_format = audio_format
        self.video_format = video_format  # 'any', 'mp4', 'webm', 'mkv'
        self.yt_dlp_path = yt_dlp_path
        self.ffmpeg_path = ffmpeg_path

    def run(self):
        try:
            if not os.path.exists(self.yt_dlp_path):
                self.finished_signal.emit(False, f"yt-dlp не найден: {self.yt_dlp_path}")
                return
            if not os.path.exists(self.ffmpeg_path):
                self.finished_signal.emit(False, f"ffmpeg не найден: {self.ffmpeg_path}")
                return

            cmd = self._build_command()
            self.log_signal.emit(f"Команда: {' '.join(cmd)}")

            # Запуск процесса
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )

            # Чтение вывода с парсингом прогресса
            output_lines = []
            for line in process.stdout:
                output_lines.append(line.strip())
                self.log_signal.emit(line.strip())
                # Парсим процент
                percent = self._parse_progress(line)
                if percent is not None:
                    self.progress_signal.emit(percent)

            process.wait()

            # Если ошибка "Requested format is not available" – пробуем fallback
            if process.returncode != 0 and any("Requested format is not available" in line for line in output_lines):
                self.log_signal.emit("Запрошенный формат недоступен, пробуем лучший доступный...")
                success = self._run_fallback()
                if success:
                    self.finished_signal.emit(True, "Загрузка завершена (fallback)!")
                else:
                    self.finished_signal.emit(False, "Ошибка загрузки даже в fallback режиме")
                return

            if process.returncode == 0:
                self.finished_signal.emit(True, "Загрузка завершена!")
            else:
                self.finished_signal.emit(False, "Ошибка загрузки")

        except Exception as e:
            self.finished_signal.emit(False, f"Исключение: {str(e)}")

    def _build_command(self):
        """Строит команду yt-dlp на основе параметров."""
        cmd = [self.yt_dlp_path]

        if self.format_choice == "audio":
            cmd.extend(["-x", "--audio-format", self.audio_format, "-f", "bestaudio"])
        else:
            if self.quality == "best":
                if self.format_choice == "video+audio":
                    cmd.extend(["-f", "bestvideo+bestaudio"])
                else:  # video only
                    cmd.extend(["-f", "bestvideo"])
            else:
                height = self.quality.replace("p", "")
                if self.format_choice == "video+audio":
                    cmd.extend(["-f", f"bestvideo[height<={height}]+bestaudio"])
                else:  # video only
                    cmd.extend(["-f", f"bestvideo[height<={height}]"])

            if self.video_format != "any":
                cmd.extend(["-S", f"ext:{self.video_format}"])
                try:
                    f_index = cmd.index("-f") + 1
                    if f_index < len(cmd) and "+" in cmd[f_index]:
                        cmd.extend(["--merge-output-format", self.video_format])
                except ValueError:
                    pass

        cmd.extend(["--ffmpeg-location", self.ffmpeg_path])
        cmd.extend(["-o", os.path.join(self.output_dir, "%(title)s.%(ext)s")])
        cmd.append(self.url)
        return cmd

    def _build_fallback_command(self):
        """Строит fallback команду (без ограничений качества)."""
        cmd = [self.yt_dlp_path]
        if self.format_choice == "audio":
            cmd.extend(["-x", "--audio-format", self.audio_format, "-f", "bestaudio"])
        elif self.format_choice == "video+audio":
            cmd.extend(["-f", "best"])
        else:  # video only
            cmd.extend(["-f", "bestvideo"])

        if self.video_format != "any" and self.format_choice != "audio":
            cmd.extend(["-S", f"ext:{self.video_format}"])
            if self.format_choice == "video+audio":
                cmd.extend(["--merge-output-format", self.video_format])

        cmd.extend(["--ffmpeg-location", self.ffmpeg_path,
                    "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s"),
                    self.url])
        return cmd

    def _run_fallback(self):
        """Запускает fallback команду и возвращает True при успехе."""
        fallback_cmd = self._build_fallback_command()
        self.log_signal.emit(f"Fallback команда: {' '.join(fallback_cmd)}")

        fallback_process = subprocess.Popen(
            fallback_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1
        )

        for line in fallback_process.stdout:
            self.log_signal.emit(line.strip())
            percent = self._parse_progress(line)
            if percent is not None:
                self.progress_signal.emit(percent)

        fallback_process.wait()
        return fallback_process.returncode == 0

    @staticmethod
    def _parse_progress(line):
        """
        Извлекает процент выполнения из строки вывода yt-dlp.
        Возвращает целое число от 0 до 100 или None.
        """
        # Ищем шаблон типа "[download]  45.5% of ~"
        match = re.search(r'(\d+(?:\.\d+)?)%', line)
        if match:
            try:
                percent = float(match.group(1))
                return int(round(percent))
            except ValueError:
                return None
        return None

class YTDLP_GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setGeometry(100, 100, 850, 620)

        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        if sys.platform.startswith('win'):
            self.exe_ext = '.exe'
        else:
            self.exe_ext = ''

        self.yt_dlp_path = os.path.join(self.base_path, f"yt-dlp{self.exe_ext}")
        ffmpeg_dir = os.path.join(self.base_path, "ffmpeg_tools")
        self.ffmpeg_path = os.path.join(ffmpeg_dir, f"ffmpeg{self.exe_ext}")

        self.download_folder = os.path.expanduser("~/Downloads")
        self.download_thread = None

        self.init_ui()
        self.apply_dark_style()
        self.check_executables()

    def closeEvent(self, event):
        """При закрытии окна, если идёт загрузка, спрашиваем подтверждение."""
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(self, 'Подтверждение',
                                         'Загрузка ещё выполняется. Закрыть окно?',
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.download_thread.terminate()
                self.download_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def apply_dark_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {BG_COLOR}; }}
            QLabel {{ color: {TEXT_COLOR}; background: transparent; }}
            QLineEdit {{
                background-color: {SURFACE_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT_COLOR}; }}
            QComboBox {{
                background-color: {SURFACE_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                min-width: 100px;
            }}
            QComboBox::drop-down {{ border: none; width: 25px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {TEXT_SECONDARY};
                margin-right: 8px;
            }}
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {ACCENT_PRESSED}; }}
            QPushButton:pressed {{ background-color: {ACCENT_PRESSED}; }}
            QPushButton:disabled {{ background-color: {BORDER_COLOR}; color: {TEXT_SECONDARY}; }}
            QTextEdit {{
                background-color: {SURFACE_COLOR};
                color: {TEXT_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }}
            QProgressBar {{
                background-color: {SURFACE_COLOR};
                border: none;
                border-radius: 4px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{ background-color: {ACCENT_COLOR}; border-radius: 4px; }}
            QFrame {{
                background-color: {SURFACE_COLOR};
                border-radius: 12px;
            }}
            QMessageBox {{ background-color: {BG_COLOR}; }}
            QMessageBox QLabel {{ color: {TEXT_COLOR}; font-size: 13px; }}
            QDialogButtonBox QPushButton {{
                background-color: {ACCENT_COLOR};
                color: {TEXT_COLOR};
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
            }}
            QDialogButtonBox QPushButton:hover {{ background-color: {ACCENT_PRESSED}; }}
        """)

    def check_executables(self):
        missing = []
        if not os.path.exists(self.yt_dlp_path):
            missing.append(f"yt-dlp{self.exe_ext}")
        if not os.path.exists(self.ffmpeg_path):
            missing.append(f"ffmpeg{self.exe_ext} (в папке ffmpeg_tools)")

        if missing:
            msg = ("Не найдены необходимые компоненты:\n" + "\n".join(missing) +
                   "\n\nПоместите их в папку программы.")
            QMessageBox.warning(self, "Отсутствуют файлы", msg)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("YouTube Downloader")
        title.setFont(QFont("-apple-system, BlinkMacSystemFont, 'SF Pro Display'", 26, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # URL
        url_frame = QFrame()
        url_layout = QVBoxLayout(url_frame)
        url_layout.setContentsMargins(16, 14, 16, 14)

        url_label = QLabel("Ссылка на видео")
        url_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        url_layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://youtube.com/watch?v=...")
        url_layout.addWidget(self.url_input)

        layout.addWidget(url_frame)

        # Строка настроек
        settings_frame = QFrame()
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setContentsMargins(16, 14, 16, 14)

        # Формат
        format_layout = QVBoxLayout()
        format_label = QLabel("Формат")
        format_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        format_layout.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Видео + Аудио", "Только Видео", "Аудио"])
        self.format_combo.setFixedHeight(40)
        format_layout.addWidget(self.format_combo)

        # Качество
        quality_layout = QVBoxLayout()
        quality_label = QLabel("Качество")
        quality_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        quality_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.setFixedHeight(40)
        self.quality_combo.addItems(["Лучшее", "1080p", "720p", "480p", "360p"])
        quality_layout.addWidget(self.quality_combo)

        # Аудио формат
        audio_format_layout = QVBoxLayout()
        audio_format_label = QLabel("Аудио формат")
        audio_format_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        audio_format_layout.addWidget(audio_format_label)
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.setFixedHeight(40)
        self.audio_format_combo.addItems(["mp3", "aac", "flac", "m4a", "opus", "wav", "vorbis"])
        audio_format_layout.addWidget(self.audio_format_combo)

        # Видео контейнер
        video_format_layout = QVBoxLayout()
        video_format_label = QLabel("Видео контейнер")
        video_format_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        video_format_layout.addWidget(video_format_label)
        self.video_format_combo = QComboBox()
        self.video_format_combo.setFixedHeight(40)
        self.video_format_combo.addItems(["Любой", "mp4", "webm", "mkv"])
        video_format_layout.addWidget(self.video_format_combo)

        settings_layout.addLayout(format_layout, stretch=1)
        settings_layout.addLayout(quality_layout, stretch=1)
        settings_layout.addLayout(audio_format_layout, stretch=1)
        settings_layout.addLayout(video_format_layout, stretch=1)

        layout.addWidget(settings_frame)

        # Папка
        folder_frame = QFrame()
        folder_layout = QVBoxLayout(folder_frame)
        folder_layout.setContentsMargins(16, 14, 16, 14)

        folder_label = QLabel("Папка сохранения")
        folder_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        folder_layout.addWidget(folder_label)

        folder_input_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setText(self.download_folder)
        folder_input_layout.addWidget(self.folder_input)

        browse_btn = QPushButton("📂")
        browse_btn.setFixedSize(55, 40)
        browse_btn.setStyleSheet(f"QPushButton {{ background-color: {ACCENT_COLOR}; font-size: 16px; }} QPushButton:hover {{ background-color: {ACCENT_PRESSED}; }}")
        browse_btn.clicked.connect(self.browse_folder)
        folder_input_layout.addWidget(browse_btn)

        folder_layout.addLayout(folder_input_layout)
        layout.addWidget(folder_frame)

        # Кнопка
        self.download_btn = QPushButton("⬇ Скачать видео")
        self.download_btn.setFixedHeight(48)
        self.download_btn.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        # Прогресс
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Лог
        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(14, 14, 14, 14)

        log_label = QLabel("Лог загрузки")
        log_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        log_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(140)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_frame)
        layout.addStretch()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку", self.download_folder)
        if folder:
            self.folder_input.setText(folder)

    def log(self, message):
        self.log_text.append(message)

    def start_download(self):
        url = self.url_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Ошибка", "Введите URL видео!")
            return

        if not url.startswith("http"):
            QMessageBox.warning(self, "Ошибка", "Введите корректный URL!")
            return

        if not os.path.exists(self.yt_dlp_path) or not os.path.exists(self.ffmpeg_path):
            self.check_executables()
            return

        format_map = {0: "video+audio", 1: "video", 2: "audio"}
        format_choice = format_map[self.format_combo.currentIndex()]

        quality_map = {0: "best", 1: "1080p", 2: "720p", 3: "480p", 4: "360p"}
        quality = quality_map[self.quality_combo.currentIndex()]

        audio_formats = ["mp3", "aac", "flac", "m4a", "opus", "wav", "vorbis"]
        audio_format = audio_formats[self.audio_format_combo.currentIndex()]

        video_format_map = {0: "any", 1: "mp4", 2: "webm", 3: "mkv"}
        video_format = video_format_map[self.video_format_combo.currentIndex()]

        output_dir = self.folder_input.text() or self.download_folder

        self.download_btn.setEnabled(False)
        self.download_btn.setText("⏳ Загрузка...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)   # детерминированный режим
        self.progress_bar.setValue(0)
        self.status_label.setText("Загрузка...")
        self.status_label.setStyleSheet(f"color: {ACCENT_COLOR}; font-size: 12px;")
        self.log_text.clear()

        self.log(f"URL: {url}")
        self.log(f"Формат: {format_choice}")
        self.log(f"Качество: {quality}")
        self.log(f"Аудио формат: {audio_format}")
        self.log(f"Видео контейнер: {video_format}")
        self.log(f"Папка: {output_dir}")

        self.download_thread = DownloadThread(
            url, output_dir, format_choice, quality, audio_format, video_format,
            self.yt_dlp_path, self.ffmpeg_path
        )
        self.download_thread.log_signal.connect(self.log)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()

    def update_progress(self, value):
        """Обновление прогресс-бара (0-100)."""
        self.progress_bar.setValue(value)

    def download_finished(self, success, message):
        self.download_btn.setEnabled(True)
        self.download_btn.setText("⬇ Скачать видео")
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText("✓ Загрузка завершена!")
            self.status_label.setStyleSheet(f"color: {SUCCESS_COLOR}; font-size: 12px;")
            self.log("✅ " + message)
            QMessageBox.information(self, "Готово!", "Видео успешно загружено!")
        else:
            self.status_label.setText("✗ Ошибка загрузки")
            self.status_label.setStyleSheet(f"color: {ERROR_COLOR}; font-size: 12px;")
            self.log("❌ " + message)
            QMessageBox.critical(self, "Ошибка", message)

def main():
    app = QApplication()
    app.setStyle("Fusion")

    app.setStyleSheet(f"""
        QMessageBox {{ background-color: {BG_COLOR}; }}
        QMessageBox QLabel {{ color: {TEXT_COLOR}; font-size: 13px; padding: 10px; }}
        QMessageBox QPushButton {{ background-color: {ACCENT_COLOR}; color: {TEXT_COLOR}; border: none; border-radius: 8px; padding: 8px 20px; margin: 5px; }}
        QMessageBox QPushButton:hover {{ background-color: {ACCENT_PRESSED}; }}
        QFileDialog {{ background-color: {BG_COLOR}; }}
    """)

    window = YTDLP_GUI()
    window.show()
    app.exec()

if __name__ == "__main__":
    main()
    