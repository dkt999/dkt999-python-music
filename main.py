#!/usr/bin/env python3
"""
Lightweight Music Player — PyQt6 + QFluentWidgets Edition
Uses pygame for audio playback and PyQt6-Fluent-Widgets for modern Fluent Design
interface (built-in Light/Dark themes, Fluent icons, native Qt system tray).
"""

import os
import sys
import time
import random

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QIcon, QPainter, QColor, QFont, QAction, QActionGroup
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QMessageBox, QFrame, QSystemTrayIcon, QMenu,
    QSizePolicy, QListWidgetItem
)

from qfluentwidgets import (
    QConfig, ConfigItem, OptionsConfigItem, OptionsValidator, BoolValidator,
    qconfig, setTheme, Theme, isDarkTheme, FluentIcon as FIF,
    Slider, TransparentToolButton, ToolButton, PushButton, ListWidget,
    SettingCardGroup, SwitchSettingCard, OptionsSettingCard, ScrollArea,
    ExpandLayout, InfoBar, InfoBarPosition, BodyLabel, CaptionLabel,
    RoundMenu, Action, themeColor,
    MSFluentWindow  # Uses MSFluentWindow for standard Fluent Title Bar
)

import pygame

SUPPORTED_EXT = (".mp3", ".ogg", ".wav", ".flac")

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "gon_nhe_music_player")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config_qt.json")
IPC_SERVER_NAME = "gon_nhe_music_player_single_instance"

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


class VolumeSlider(Slider):
    """
    Custom Volume Slider: When Muted (disabled), still captures mouse press/drag 
    events to automatically unmute!
    """
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)

    def mousePressEvent(self, e):
        # If disabled (Muted), calculate click position to unmute audio
        if not self.isEnabled() and e.button() == Qt.MouseButton.LeftButton:
            usable = max(1, self.width())
            click_x = max(0, min(e.pos().x(), usable))
            val = int((click_x / usable) * self.maximum())
            self.setEnabled(True)  # Re-enable slider
            self.setValue(val)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self.isEnabled() and e.buttons() & Qt.MouseButton.LeftButton:
            usable = max(1, self.width())
            move_x = max(0, min(e.pos().x(), usable))
            val = int((move_x / usable) * self.maximum())
            self.setEnabled(True)
            self.setValue(val)
            e.accept()
            return
        super().mouseMoveEvent(e)

def get_app_icon():
    """
    Ưu tiên lấy icon.ico hoặc icon.png trong thư mục assets.
    """
    for icon_name in ["icon.ico", "icon.png"]:
        path = resource_path(f"assets/{icon_name}")
        if os.path.exists(path):
            return QIcon(path)
    return QIcon()

def resource_path(relative):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def get_action_icon(svg_name, fluent_icon):
    """
    Prefers SVG icon from assets folder; falls back to default FluentIcon if not found.
    """
    paths_to_check = [
        resource_path(f"assets/icons/{svg_name}"),
        resource_path(f"assets/image/icon/{svg_name}")
    ]
    for path in paths_to_check:
        if os.path.exists(path):
            return QIcon(path)
            
    return fluent_icon


def get_display_title(path):
    if HAS_MUTAGEN:
        try:
            audio = MutagenFile(path, easy=True)
            if audio and audio.tags:
                title = (audio.tags.get("title") or [None])[0]
                artist = (audio.tags.get("artist") or [None])[0]
                if title:
                    return f"{artist + ' - ' if artist else ''}{title}"
        except Exception:
            pass
    return os.path.basename(path)


# ============================================================================
# Configuration
# ============================================================================
class Config(QConfig):
    openMode = OptionsConfigItem("General", "OpenMode", "ask",
                                  OptionsValidator(["ask", "folder", "single"]))
    backgroundOnClose = ConfigItem("General", "BackgroundOnClose", True, BoolValidator())
    repeatMode = OptionsConfigItem("General", "RepeatMode", "off",
                                    OptionsValidator(["off", "all", "one"]))
    volume = ConfigItem("General", "Volume", 70)


cfg = Config()
os.makedirs(CONFIG_DIR, exist_ok=True)
qconfig.load(CONFIG_PATH, cfg)


# ============================================================================
# Widget: Marquee
# ============================================================================
class MarqueeLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.text = ""
        self.offset = 0
        self.text_width = 0
        self.font_ = QFont()
        self.font_.setPointSize(10)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def set_text(self, text):
        self.text = text
        self.offset = 0
        fm = self.fontMetrics()
        self.text_width = fm.horizontalAdvance(text)
        if self.text_width > self.width():
            self.timer.start(35)
        else:
            self.timer.stop()
        self.update()

    def resizeEvent(self, e):
        if self.text_width > self.width():
            if not self.timer.isActive():
                self.timer.start(35)
        else:
            self.timer.stop()
            self.offset = 0
        self.update()
        super().resizeEvent(e)

    def _tick(self):
        gap = 60
        self.offset -= 2
        if self.offset < -(self.text_width + gap):
            self.offset = self.width()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self.font_)
        p.setPen(QColor("#f2f2f5") if isDarkTheme() else QColor("#1c1c22"))
        if self.text_width <= self.width():
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter, self.text)
        else:
            y = self.height() // 2 + 5
            p.drawText(self.offset, y, self.text)


# ============================================================================
# Widget: Equalizer
# ============================================================================
class EqualizerWidget(QWidget):
    def __init__(self, bars=4, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 22)
        self.bars_count = bars
        self.heights = [0.12] * bars
        self.targets = [0.12] * bars
        self.playing = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(110)

    def set_playing(self, playing):
        self.playing = playing

    def _tick(self):
        for i in range(self.bars_count):
            if self.playing:
                if random.random() < 0.4:
                    self.targets[i] = random.uniform(0.15, 1.0)
            else:
                self.targets[i] = 0.12
            self.heights[i] += (self.targets[i] - self.heights[i]) * 0.35
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = themeColor()
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        gap = 3
        bar_w = max(2, (w - gap * (self.bars_count + 1)) / self.bars_count)
        for i in range(self.bars_count):
            x0 = gap + i * (bar_w + gap)
            bar_h = max(2, self.heights[i] * h)
            p.drawRoundedRect(QRectF(x0, h - bar_h, bar_w, bar_h), 1, 1)


# ============================================================================
# Widget: MarkerSlider
# ============================================================================
class MarkerSlider(Slider):
    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None):
        super().__init__(orientation, parent)
        self.markers = []

    def set_markers(self, markers):
        self.markers = markers
        self.update()

    # Synchronizes progress bar position when setValue is called from QTimer
    def setValue(self, val):
        super().setValue(val)
        self.setSliderPosition(val)
        self.update()

    # Enables direct clicking anywhere on the slider track to jump to position
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            margin = 8
            usable = max(1, self.width() - margin * 2)
            click_x = max(0, min(e.pos().x() - margin, usable))
            val = int((click_x / usable) * self.maximum())
            
            self.setValue(val)
            e.accept()
        super().mousePressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self.markers:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 8
        usable = max(1, self.width() - margin * 2)
        for pos, color in self.markers:
            frac = pos / max(1, self.maximum())
            x = margin + usable * frac
            p.setPen(QColor(color))
            p.drawLine(int(x), 4, int(x), self.height() - 4)


# ============================================================================
# Playlist Window
# ============================================================================
class PlaylistWindow(MSFluentWindow):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.setWindowTitle("Playlist")
        self.setWindowIcon(get_app_icon())
        self.resize(420, 540)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()
        # Hide navigation sidebar
        self.navigationInterface.hide()

        # Layout & UI
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)

        toolbar = QHBoxLayout()
        for text, slot in [("Add File", player.add_files), ("Add Folder", player.add_folder),
                            ("Remove Item", self.remove_selected), ("Clear All", player.clear_playlist)]:
            btn = PushButton(text)
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)
        layout.addLayout(toolbar)

        self.list_widget = ListWidget(self)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        self.stackedWidget.addWidget(container)

    def remove_selected(self):
        rows = sorted({i.row() for i in self.list_widget.selectedIndexes()}, reverse=True)
        for r in rows:
            self.player.remove_at(r)

    def _on_double_click(self, item):
        row = self.list_widget.row(item)
        self.player.play_index(row)

    # When close button (X) is pressed -> Hide window instead of exiting
    def closeEvent(self, e):
        e.ignore()
        self.hide()


# ============================================================================
# Settings Window
# ============================================================================
class SettingsWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        self.setWindowIcon(get_app_icon())
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(620, 320)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()

        # Hide navigation sidebar
        self.navigationInterface.hide()

        # Layout & Content
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)

        scroll = ScrollArea(container)
        scroll.setWidgetResizable(True)
        content = QWidget()
        v = QVBoxLayout(content)

        group = SettingCardGroup("General", content)

        open_mode_card = OptionsSettingCard(
            cfg.openMode, FIF.MUSIC_FOLDER,
            "When opening music from external files",
            "Behavior when double-clicking an audio file in File Manager",
            texts=["Always ask", "Play entire folder", "Play selected file only"],
        )
        group.addSettingCard(open_mode_card)

        bg_card = SwitchSettingCard(
            FIF.MINIMIZE,
            "Run in background on close",
            "On: Clicking X minimizes to system tray, music continues playing.\n"
            "Off: Clicking X exits the application completely.",
            configItem=cfg.backgroundOnClose,
        )
        group.addSettingCard(bg_card)

        v.addWidget(group)
        v.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.stackedWidget.addWidget(container)

    # Close button (X) hides the Settings window
    def closeEvent(self, e):
        e.ignore()
        self.hide()


# ============================================================================
# Main Window
# ============================================================================
class MainWindow(MSFluentWindow):
    def __init__(self, startup_file=None):
        super().__init__()
        self.setWindowTitle("DK Music Player")
        app_icon = get_app_icon()
        self.setWindowIcon(app_icon)
        self.resize(640, 260)
        self.setFixedSize(680, 240)
        self.is_muted = False
        saved_vol = cfg.volume.value
        self.last_volume = saved_vol if saved_vol > 0 else 70
        self.volume = saved_vol / 100.0
        self.titleBar.maxBtn.hide()
        # Hide sidebar and back button from Title Bar
        self.navigationInterface.hide()

        # Increased audio buffer to 2048 to prevent underruns/stuttering
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

        self.playlist = []
        self.current_index = -1
        self.paused = False
        self.song_length = 0
        self.start_time = 0
        self.offset = 0
        self.volume = 0.7
        self.manually_stopped = False
        self.loop_a = None
        self.loop_b = None
        self.repeat_mode = cfg.repeatMode.value
        self.tray = None
        self.playlist_win = None
        self.settings_win = None

        # Container holding all UI elements
        self.main_container = QWidget(self)
        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(14, 4, 14, 12)
        self.main_layout.setSpacing(6)

        self.stackedWidget.addWidget(self.main_container)

        self._build_ui()
        self._build_tray()
        self.apply_theme(cfg.themeMode.value)
        self._refresh_nav_buttons()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_loop)
        self.timer.start(200)

        if startup_file:
            QTimer.singleShot(200, lambda: self._handle_startup_file(startup_file))

    # ---------- Menu ----------
    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar

        menubar = QMenuBar(self)
        self.main_layout.setMenuBar(menubar)

        # 1. File Menu
        file_menu = menubar.addMenu("File")
        act_add_files = QAction("Add Files...", self)
        act_add_files.triggered.connect(self.add_files)
        file_menu.addAction(act_add_files)
        
        act_add_folder = QAction("Add Folder...", self)
        act_add_folder.triggered.connect(self.add_folder)
        file_menu.addAction(act_add_folder)
        
        file_menu.addSeparator()
        
        act_quit = QAction("Exit", self)
        act_quit.triggered.connect(self.do_quit)
        file_menu.addAction(act_quit)

        # 2. View Menu
        view_menu = menubar.addMenu("View")
        act_playlist = QAction("Show/Hide Playlist", self)
        act_playlist.triggered.connect(self.toggle_playlist_window)
        view_menu.addAction(act_playlist)

    def open_settings(self):
        if self.settings_win is None:
            self.settings_win = SettingsWindow()
        self.settings_win.show()
        self.settings_win.raise_()
        self.settings_win.activateWindow()

    # ---------- UI Construction ----------
    def _build_ui(self):
        # --- Title Row ---
        title_row = QHBoxLayout()
        self.equalizer = EqualizerWidget()
        title_row.addWidget(self.equalizer)
        self.marquee = MarqueeLabel()
        title_row.addWidget(self.marquee, 1)
        self.marquee.set_text("No track playing")
        self.theme_btn = TransparentToolButton(FIF.CONSTRACT)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setToolTip("Toggle Light/Dark Theme")
        title_row.addWidget(self.theme_btn)
        self.main_layout.addLayout(title_row)

        # --- Progress Bar ---
        seek_row = QHBoxLayout()
        self.seek_slider = MarkerSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self._on_seek_release)
        self.seek_slider.valueChanged.connect(self._on_seek_value_changed)
        self._seek_dragging = False
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_seek_dragging", True))
        seek_row.addWidget(self.seek_slider, 1)
        self.time_label = CaptionLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(90)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self.time_label)
        self.main_layout.addLayout(seek_row)

        # --- Single Controls & Volume Row ---
        controls = QHBoxLayout()
        controls.setSpacing(4)

        # Open File Button
        file_icon = get_action_icon("file.svg", FIF.DOCUMENT)
        self.open_file_btn = TransparentToolButton(file_icon)
        self.open_file_btn.setToolTip("Add Audio File")
        self.open_file_btn.clicked.connect(self.add_files)
        controls.addWidget(self.open_file_btn)

        # Open Folder Button
        folder_icon = get_action_icon("folder.svg", FIF.FOLDER)
        self.open_folder_btn = TransparentToolButton(folder_icon)
        self.open_folder_btn.setToolTip("Add Audio Folder")
        self.open_folder_btn.clicked.connect(self.add_folder)
        controls.addWidget(self.open_folder_btn)

        controls.addWidget(self._vline()) 

        self.prev_btn = TransparentToolButton(QIcon(resource_path("assets/icons/prev_dark.png")))
        self.prev_btn.clicked.connect(self.prev_song)
        controls.addWidget(self.prev_btn)

        self.play_btn = PushButton()
        self.play_btn.setFixedSize(44, 44)
        self.play_btn.setIcon(FIF.PLAY.icon(color=QColor("white")))
        self.play_btn.setIconSize(self.play_btn.iconSize())
        self._style_play_button()
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)

        self.stop_btn = TransparentToolButton(QIcon(resource_path("assets/icons/stop_dark.png")))
        self.stop_btn.clicked.connect(self.stop_song)
        controls.addWidget(self.stop_btn)

        self.next_btn = TransparentToolButton(QIcon(resource_path("assets/icons/next_dark.png")))
        self.next_btn.clicked.connect(self.next_song)
        controls.addWidget(self.next_btn)

        controls.addWidget(self._vline())

        self.playlist_btn = TransparentToolButton(FIF.MENU)
        self.playlist_btn.clicked.connect(self.toggle_playlist_window)
        self.playlist_btn.setToolTip("Playlist")
        controls.addWidget(self.playlist_btn)

        self.repeat_btn = TransparentToolButton(QIcon(resource_path(f"assets/icons/repeat_{self.repeat_mode}.png")))
        self.repeat_btn.clicked.connect(self.cycle_repeat)
        self.repeat_btn.setToolTip("Repeat: Off / All / Single Track")
        controls.addWidget(self.repeat_btn)

        controls.addWidget(self._vline())

        self.a_btn = ToolButton()
        self.a_btn.setText("A")
        self.a_btn.setFixedSize(28, 28)
        self.a_btn.clicked.connect(self.toggle_a)
        controls.addWidget(self.a_btn)

        self.b_btn = ToolButton()
        self.b_btn.setText("B")
        self.b_btn.setFixedSize(28, 28)
        self.b_btn.clicked.connect(self.toggle_b)
        controls.addWidget(self.b_btn)

        self.ab_clear_btn = TransparentToolButton(FIF.CLOSE)
        self.ab_clear_btn.setToolTip("Clear A-B Loop Points")
        self.ab_clear_btn.clicked.connect(self.clear_ab)
        controls.addWidget(self.ab_clear_btn)

        controls.addStretch(1)

        self.vol_icon = TransparentToolButton(FIF.VOLUME)
        self.vol_icon.setToolTip("Mute/Unmute")
        self.vol_icon.clicked.connect(self.toggle_mute)
        controls.addWidget(self.vol_icon)

        self.vol_slider = Slider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(self.last_volume)
        self.vol_slider.setFixedWidth(110)
        self.vol_slider.valueChanged.connect(self._on_volume_change)
        controls.addWidget(self.vol_slider)

        self.settings_btn = TransparentToolButton(FIF.SETTING)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        controls.addWidget(self.settings_btn)

        self.main_layout.addLayout(controls)

    def _on_seek_value_changed(self, val):
        if getattr(self, "_block_seek_signal", False):
            return
        if not self._seek_dragging and self.song_length > 0 and self.current_index != -1:
            pct = val / 1000
            self._seek_to(pct * self.song_length)

    def _on_seek_release(self):
        self._seek_dragging = False
        if self.song_length > 0 and self.current_index != -1:
            pct = self.seek_slider.value() / 1000
            self._seek_to(pct * self.song_length)

    def _vline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(24)
        return line

    def _style_play_button(self):
        c = themeColor().name()
        self.play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {c}; border-radius: 22px; border: none; }}"
            f"QPushButton:hover {{ background-color: {c}; }}"
        )

    # ---------- Theme Handling ----------
    def toggle_theme(self):
        self.apply_theme(Theme.LIGHT if isDarkTheme() else Theme.DARK)

    def apply_theme(self, theme):
        setTheme(theme)
        self._style_play_button()
        self.stop_btn.setIcon(QIcon(resource_path(
            f"assets/icons/stop_{'dark' if isDarkTheme() else 'light'}.png")))
        self.prev_btn.setIcon(QIcon(resource_path(
                    f"assets/icons/prev_{'dark' if isDarkTheme() else 'light'}.png")))
        self.next_btn.setIcon(QIcon(resource_path(
                    f"assets/icons/next_{'dark' if isDarkTheme() else 'light'}.png")))
        self.marquee.update()

    # ---------- Playlist Window ----------
    def toggle_playlist_window(self):
        if self.playlist_win is None:
            self.playlist_win = PlaylistWindow(self) 
            for path in self.playlist:
                self.playlist_win.list_widget.addItem(os.path.basename(path))
        if self.playlist_win.isVisible():
            self.playlist_win.hide()
        else:
            self.playlist_win.show()
            self.playlist_win.raise_()

    # ---------- Startup File Handling ----------
    def _handle_startup_file(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return
        mode = cfg.openMode.value
        if mode == "ask":
            box = QMessageBox(self)
            box.setWindowTitle("Open Music")
            box.setText(f"Do you want to play all audio files in the folder containing:\n"
                        f"{os.path.basename(path)}\n\nYes = Play entire folder\nNo = Play this file only")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                                    QMessageBox.StandardButton.Cancel)
            ans = box.exec()
            if ans == QMessageBox.StandardButton.Cancel:
                return
            mode = "folder" if ans == QMessageBox.StandardButton.Yes else "single"

        if mode == "folder":
            folder = os.path.dirname(path)
            self._scan_folder_into_playlist(folder)
            idx = self.playlist.index(path) if path in self.playlist else (0 if self.playlist else -1)
        else:
            self._add_to_playlist(path)
            idx = len(self.playlist) - 1

        if idx >= 0:
            self.current_index = idx
            self._play_current()

    # ---------- Playlist Management ----------
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "", "Audio (*.mp3 *.ogg *.wav *.flac);;All Files (*.*)")
        if not files:
            return
        first_new_index = len(self.playlist)
        for f in files:
            self._add_to_playlist(f)
        self.current_index = first_new_index
        self._play_current()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Folder")
        if folder:
            self._scan_folder_into_playlist(folder)

    def _scan_folder_into_playlist(self, folder):
        for root_dir, _, files in os.walk(folder):
            for f in sorted(files):
                if f.lower().endswith(SUPPORTED_EXT):
                    self._add_to_playlist(os.path.join(root_dir, f))

    def _add_to_playlist(self, path):
        self.playlist.append(path)
        if self.playlist_win is not None:
            self.playlist_win.list_widget.addItem(os.path.basename(path))
        self._refresh_nav_buttons()

    def remove_at(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        del self.playlist[i]
        if self.playlist_win is not None:
            self.playlist_win.list_widget.takeItem(i)
        if i == self.current_index:
            self.stop_song()
        self._refresh_nav_buttons()

    def clear_playlist(self):
        self.stop_song()
        self.playlist.clear()
        if self.playlist_win is not None:
            self.playlist_win.list_widget.clear()
        self._refresh_nav_buttons()

    def _refresh_nav_buttons(self):
        enabled = len(self.playlist) > 1
        self.prev_btn.setEnabled(enabled)
        self.next_btn.setEnabled(enabled)

    def play_index(self, i):
        self.current_index = i
        self._play_current()

    # ---------- Playback Controls ----------
    def _play_current(self):
        if not (0 <= self.current_index < len(self.playlist)):
            return
        path = self.playlist[self.current_index]
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot play file:\n{path}\n{e}")
            return
        self.paused = False
        self.manually_stopped = False
        self.offset = 0
        self.start_time = time.time()
        self.play_btn.setIcon(FIF.PAUSE.icon(color=QColor("white")))
        self.equalizer.set_playing(True)

        display = get_display_title(path)
        self.marquee.set_text(f"Now playing: {display}")
        if self.playlist_win is not None:
            self.playlist_win.list_widget.setCurrentRow(self.current_index)
        self.song_length = self._get_length(path)

        self.loop_a = None
        self.loop_b = None
        self._refresh_ab_buttons()
        self._refresh_markers()

    def _get_length(self, path):
        if HAS_MUTAGEN:
            try:
                audio = MutagenFile(path)
                if audio and audio.info and audio.info.length:
                    return audio.info.length
            except Exception:
                pass
        try:
            return pygame.mixer.Sound(path).get_length()
        except Exception:
            return 0

    def toggle_play(self):
        if self.current_index == -1:
            if self.playlist:
                self.current_index = 0
                self._play_current()
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.start_time = time.time() - self.offset
            self.play_btn.setIcon(FIF.PAUSE.icon(color=QColor("white")))
            self.equalizer.set_playing(True)
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                self.paused = True
                self.offset = time.time() - self.start_time
                self.play_btn.setIcon(FIF.PLAY.icon(color=QColor("white")))
                self.equalizer.set_playing(False)
            else:
                self._play_current()

    def stop_song(self):
        self.manually_stopped = True
        pygame.mixer.music.stop()
        self.play_btn.setIcon(FIF.PLAY.icon(color=QColor("white")))
        self.equalizer.set_playing(False)
        self.marquee.set_text("No track playing")
        self.time_label.setText("00:00 / 00:00")
        self.seek_slider.setValue(0)
        self.paused = False
        self.offset = 0

    def next_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self._play_current()

    def prev_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self._play_current()

    def mute(self):
        if self.is_muted:
            return
        
        self.last_volume = self.vol_slider.value() if self.vol_slider.value() > 0 else 70
        self.is_muted = True

        pygame.mixer.music.set_volume(0)

        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(0)
        self.vol_slider.blockSignals(False)

        mute_icon = get_action_icon("mute.png", FIF.MUTE)
        self.vol_icon.setIcon(mute_icon)

    def toggle_mute(self):
        if self.is_muted:
            self.unmute()
        else:
            self.mute()

    def unmute(self):
        if not self.is_muted:
            return
        self.is_muted = False

        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(self.last_volume)
        self.vol_slider.blockSignals(False)

        self.volume = self.last_volume / 100
        pygame.mixer.music.set_volume(self.volume)

        vol_icon = get_action_icon("volume.png", FIF.VOLUME)
        self.vol_icon.setIcon(vol_icon)

    def _on_volume_change(self, val):
        self.volume = val / 100
        pygame.mixer.music.set_volume(self.volume)

        if val > 0:
            self.last_volume = val
            if self.is_muted:
                self.is_muted = False
                vol_icon = get_action_icon("volume.png", FIF.VOLUME)
                self.vol_icon.setIcon(vol_icon)
        else:
            self.is_muted = True
            mute_icon = get_action_icon("mute.png", FIF.MUTE)
            self.vol_icon.setIcon(mute_icon)

        cfg.set(cfg.volume, val)

    def _seek_to(self, seconds):
        try:
            pygame.mixer.music.play(start=seconds)
            self.offset = seconds
            self.start_time = time.time() - seconds
            self.paused = False
            self.manually_stopped = False
            self.play_btn.setIcon(FIF.PAUSE.icon(color=QColor("white")))
            self.equalizer.set_playing(True)
        except Exception:
            pass

    def _current_elapsed(self):
        return self.offset if self.paused else (time.time() - self.start_time)

    @staticmethod
    def _fmt(seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    # ---------- Repeat Handling ----------
    def cycle_repeat(self):
        order = ["off", "all", "one"]
        self.repeat_mode = order[(order.index(self.repeat_mode) + 1) % len(order)]
        cfg.set(cfg.repeatMode, self.repeat_mode)
        self.repeat_btn.setIcon(QIcon(resource_path(f"assets/icons/repeat_{self.repeat_mode}.png")))

    # ---------- A-B Repeat Handling ----------
    def toggle_a(self):
        if self.current_index == -1 or self.song_length <= 0:
            return
        if self.loop_a is None:
            self.loop_a = self._current_elapsed()
            if self.loop_b is not None and self.loop_b <= self.loop_a:
                self.loop_b = None
        else:
            self.loop_a = None
            self.loop_b = None
        self._refresh_ab_buttons()
        self._refresh_markers()

    def toggle_b(self):
        if self.current_index == -1 or self.song_length <= 0 or self.loop_a is None:
            return
        if self.loop_b is None:
            b = self._current_elapsed()
            if b > self.loop_a + 0.3:
                self.loop_b = b
        else:
            self.loop_b = None
        self._refresh_ab_buttons()
        self._refresh_markers()

    def clear_ab(self):
        self.loop_a = None
        self.loop_b = None
        self._refresh_ab_buttons()
        self._refresh_markers()

    def _refresh_ab_buttons(self):
        c = themeColor().name()
        for btn, active in ((self.a_btn, self.loop_a is not None), (self.b_btn, self.loop_b is not None)):
            if active:
                btn.setStyleSheet(f"QToolButton {{ background-color: {c}; color: white; border-radius: 6px; }}")
            else:
                btn.setStyleSheet("")

    def _refresh_markers(self):
        markers = []
        if self.song_length > 0:
            if self.loop_a is not None:
                markers.append((self.loop_a / self.song_length * 1000, "#2ecc71"))
            if self.loop_b is not None:
                markers.append((self.loop_b / self.song_length * 1000, "#e74c3c"))
        self.seek_slider.set_markers(markers)

    # ---------- UI Update Loop ----------
    def _update_loop(self):
        if self.current_index != -1 and not self.paused:
            if pygame.mixer.music.get_busy():
                elapsed = time.time() - self.start_time
                if self.loop_a is not None and self.loop_b is not None and elapsed >= self.loop_b:
                    self._seek_to(self.loop_a)
                else:
                    if not self._seek_dragging and self.song_length > 0:
                        val = int(min(elapsed / self.song_length, 1.0) * 1000)
                        
                        self._block_seek_signal = True
                        self.seek_slider.setValue(val)
                        self._block_seek_signal = False
                        
                    self.time_label.setText(f"{self._fmt(elapsed)} / {self._fmt(self.song_length)}")
            else:
                if not self.manually_stopped:
                    if self.repeat_mode == "one":
                        self._play_current()
                    elif self.repeat_mode == "all":
                        self.next_song()
                    else:
                        if self.playlist and self.current_index < len(self.playlist) - 1:
                            self.next_song()
                        else:
                            self.stop_song()

    # ---------- System Tray ----------
    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        icon_path = resource_path("assets/icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("DK Music Player")
        menu = QMenu()
        act_show = menu.addAction("Restore Window")
        act_show.triggered.connect(self._restore_from_tray)
        act_quit = menu.addAction("Exit")
        act_quit.triggered.connect(self.do_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._restore_from_tray() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)

    def _restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        if not cfg.backgroundOnClose.value:
            e.accept()
            self.do_quit()
            return
        if self.tray is not None:
            e.ignore()
            self.hide()
            if self.playlist_win is not None:
                self.playlist_win.hide()
            self.tray.show()
            self.tray.showMessage("Playing audio in background",
                                   "Click system tray icon to restore window.",
                                   QSystemTrayIcon.MessageIcon.Information, 4000)
        else:
            e.ignore()
            self.showMinimized()

    def do_quit(self):
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        qconfig.save()
        QApplication.quit()

    def handle_ipc_message(self, file_path):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if file_path:
            self._handle_startup_file(file_path)


def main():
    startup_file = None
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        startup_file = sys.argv[1]

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    probe = QLocalSocket()
    probe.connectToServer(IPC_SERVER_NAME)
    if probe.waitForConnected(200):
        probe.write((startup_file or "").encode("utf-8"))
        probe.waitForBytesWritten(200)
        probe.disconnectFromServer()
        return
    probe.close()

    setTheme(cfg.themeMode.value)

    win = MainWindow(startup_file=startup_file)

    QLocalServer.removeServer(IPC_SERVER_NAME)
    ipc_server = QLocalServer()
    ipc_server.listen(IPC_SERVER_NAME)

    def _on_new_ipc_connection():
        sock = ipc_server.nextPendingConnection()
        if sock is None:
            return
        if sock.waitForReadyRead(300):
            data = bytes(sock.readAll()).decode("utf-8")
            win.handle_ipc_message(data if data else None)
        sock.disconnectFromServer()

    ipc_server.newConnection.connect(_on_new_ipc_connection)
    win._ipc_server = ipc_server

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()