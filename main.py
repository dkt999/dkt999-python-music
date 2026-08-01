#!/usr/bin/env python3
"""
Lightweight Music Player — PyQt6 + QFluentWidgets Edition
Uses pygame for audio playback and PyQt6-Fluent-Widgets for modern Fluent Design
interface (built-in Light/Dark themes, Fluent icons, native Qt system tray).
"""

import os
import re
import sys
import time
import random

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QSize
from PyQt6.QtGui import QIcon, QPainter, QColor, QFont, QAction, QPixmap
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFileDialog, QMessageBox, QFrame, QSystemTrayIcon, QMenu,
    QSizePolicy, QListWidgetItem
)

from qfluentwidgets import (
    QConfig, ConfigItem, OptionsConfigItem, OptionsValidator, BoolValidator,
    ColorConfigItem, qconfig, setTheme, Theme, isDarkTheme, FluentIcon as FIF,
    Slider, TransparentToolButton, ToolButton, PushButton, ListWidget,
    SettingCardGroup, SwitchSettingCard, OptionsSettingCard, ScrollArea,
    ExpandLayout, InfoBar, InfoBarPosition, BodyLabel, CaptionLabel,
    RoundMenu, Action, themeColor,setThemeColor, 
    MSFluentWindow, CustomColorSettingCard
)

import pygame

SUPPORTED_EXT = (".mp3", ".ogg", ".wav", ".flac")


def _natural_key(path):
    """Sort key giúp 'Track 2.mp3' đứng trước 'Track 10.mp3' (thay vì string
    sort thô sẽ cho ra thứ tự 10, 2, 3...)."""
    name = os.path.basename(path).lower()
    return [int(tok) if tok.isdigit() else tok for tok in re.split(r"(\d+)", name)]


def _expand_startup_args(args):
    """Nhận danh sách argv (có thể là file lẻ hoặc cả thư mục, ví dụ khi mở
    bằng 'Open Folder With...' trên Ubuntu) và trả về:
    (danh sách file nhạc đã sort tự nhiên, có phải mở từ thư mục hay không).
    """
    files = []
    had_dir = False
    for a in args:
        if os.path.isdir(a):
            had_dir = True
            for root_dir, _, fnames in os.walk(a):
                matched = [f for f in fnames if f.lower().endswith(SUPPORTED_EXT)]
                for f in sorted(matched, key=_natural_key):
                    files.append(os.path.join(root_dir, f))
        elif os.path.isfile(a) and a.lower().endswith(SUPPORTED_EXT):
            files.append(a)
    files = sorted(dict.fromkeys(os.path.abspath(f) for f in files), key=_natural_key)
    return files, had_dir

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "dk_music_player")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config_qt.json")
IPC_SERVER_NAME = "dk_music_player_single_instance"

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

class MacApplication(QApplication):
    """
    Custom QApplication dành riêng cho macOS để hứng sự kiện 'FileOpen' (QFileOpenEvent)
    khi người dùng Double Click file nhạc từ Finder hoặc dùng 'Open With'.
    """
    def __init__(self, argv):
        super().__init__(argv)
        self.main_window = None

    def event(self, event):
        # EventType.FileOpen (Code 116 trong Qt) chính là QFileOpenEvent của macOS
        if event.type() == event.Type.FileOpen:
            file_path = event.file()
            if file_path and os.path.exists(file_path):
                print(f"[macOS Event] Mở file từ Finder: {file_path}")
                if self.main_window:
                    # Gọi hàm gom file có sẵn trong MainWindow của fen
                    self.main_window._queue_startup_files([file_path])
            return True
        return super().event(event)

class PrimaryPlayButton(PushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_playing = False
        self.setFixedSize(40, 40)

    def set_playing(self, playing: bool):
        self.is_playing = playing
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Vẽ nền tròn cyan
        c = themeColor()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(0, 0, self.width(), self.height())

        # 2. Tọa độ tâm
        cx, cy = self.width() / 2.0, self.height() / 2.0

        p.setBrush(QColor("white"))

        if self.is_playing:
            # --- VẼ ICON PAUSE (2 thanh đứng căn chuẩn đét) ---
            w, h = 3.5, 12.0  # Độ rộng và độ cao 2 thanh
            gap = 3.5         # Khoảng cách giữa 2 thanh
            
            x1 = cx - gap / 2.0 - w
            x2 = cx + gap / 2.0
            y = cy - h / 2.0

            p.drawRoundedRect(QRectF(x1, y, w, h), 1.5, 1.5)
            p.drawRoundedRect(QRectF(x2, y, w, h), 1.5, 1.5)
        else:
            # --- VẼ ICON PLAY (Tam giác căn chuẩn tâm) ---
            from PyQt6.QtGui import QPolygonF
            from PyQt6.QtCore import QPointF
            
            # Đã offset nhẹ 0.5px để tam giác nhìn cân thị giác
            poly = QPolygonF([
                QPointF(cx - 4, cy - 6),
                QPointF(cx - 4, cy + 6),
                QPointF(cx + 6, cy)
            ])
            p.drawPolygon(poly)

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

def get_tinted_icon(icon_path, size=24):
    """
    Load icon và tô màu nó bằng màu chủ đạo (themeColor) của app.
    Hoạt động với cả .svg và .png (chỉ cần có nền trong suốt).
    """
    # Load icon gốc ra Pixmap
    icon = QIcon(icon_path)
    pixmap = icon.pixmap(QSize(size, size))
    
    # Tạo một Pixmap trống, trong suốt hoàn toàn với cùng kích thước
    tinted_pixmap = QPixmap(pixmap.size())
    tinted_pixmap.fill(Qt.GlobalColor.transparent)
    
    # Dùng QPainter để vẽ lại
    painter = QPainter(tinted_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Bước 1: Vẽ cái bóng/khuôn của icon gốc lên
    painter.drawPixmap(0, 0, pixmap)
    
    # Bước 2: Chỉnh mode thành SourceIn (Chỉ vẽ đè lên những điểm ảnh không trong suốt)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    
    # Bước 3: Đổ màu accent (themeColor) lên toàn bộ
    painter.fillRect(tinted_pixmap.rect(), themeColor())
    painter.end()
    
    return QIcon(tinted_pixmap)

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
    openMode = OptionsConfigItem("General", "OpenMode", "single",
                                  OptionsValidator(["ask", "folder", "single"]))
    backgroundOnClose = ConfigItem("General", "BackgroundOnClose", False, BoolValidator())
    repeatMode = OptionsConfigItem("General", "RepeatMode", "off",
                                    OptionsValidator(["off", "all", "one"]))
    volume = ConfigItem("General", "Volume", 70)
    # Ghi đè màu accent mặc định (chỉ áp dụng cho lần chạy đầu tiên, khi
    # chưa có trong config_qt.json). Sau khi người dùng đổi màu trong Settings,
    # giá trị này không còn được dùng nữa — file config sẽ quyết định.
    themeColor = ColorConfigItem("General", "ThemeColor", "#FA5053")


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
        self.setMicaEffectEnabled(False)
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

    def update_playlist_ui(self):
        self.list_widget.clear()
        
        # Lấy theme suffix để chọn icon play_dark.png hoặc play_light.png
        theme_suffix = 'dark' if isDarkTheme() else 'light'
        play_icon = QIcon(resource_path(f"assets/icons/play_{theme_suffix}.png"))
        
        # Màu accent (cho bài đang play) và màu xám (cho bài đã play)
        accent_color = themeColor()
        gray_color = QColor("#888888") if isDarkTheme() else QColor("#666666")
        default_color = QColor("#FFFFFF") if isDarkTheme() else QColor("#000000")

        # Dùng played_indices (tập hợp các bài ĐÃ THỰC SỰ được phát) thay vì suy
        # theo vị trí index. So sánh theo vị trí (idx < current_index) chỉ đúng
        # khi phát tuần tự tăng dần, nên bị sai khi dùng Prev, khi Next lặp vòng
        # về đầu playlist, hoặc khi double-click mở thẳng một bài giữa danh sách.
        played = getattr(self.player, 'played_indices', set())

        for idx, song_path in enumerate(self.player.playlist):
            song_name = os.path.basename(song_path)
            item = QListWidgetItem(song_name)

            if idx == self.player.current_index:
                # 1. BÀI ĐANG PLAY: Hiện icon play + chữ màu accent
                item.setIcon(play_icon)
                item.setForeground(accent_color)
                # Set font đậm nhẹ cho nổi bật
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            elif idx in played:
                # 2. BÀI ĐÃ PLAY (không phải bài hiện tại): chữ xám
                item.setForeground(gray_color)

            else:
                # 3. BÀI CHƯA PLAY: màu mặc định
                item.setForeground(default_color)

            self.list_widget.addItem(item)

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
        # --- FIX CHỚP TRẮNG TRÊN WINDOWS ---
        palette = self.palette()
        # Màu 32,32,32 là màu nền tối mặc định của QFluentWidgets
        bg_color = QColor(32, 32, 32) if isDarkTheme() else QColor(243, 243, 243)
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)
        # -----------------------------------
        self.setMicaEffectEnabled(False) 
        self.setWindowTitle("Settings")
        self.setWindowIcon(get_app_icon())
        self.setFixedSize(620, 620)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()

        # Hide navigation sidebar
        self.navigationInterface.hide()

        # Layout & Content
        container = QWidget(self)
        container.setStyleSheet("QWidget{background: transparent}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)

        scroll = ScrollArea(container)
        scroll.setStyleSheet("QScrollArea{border: none; background: transparent}")
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setStyleSheet("QWidget{background: transparent}")
        v = QVBoxLayout(content)

        group = SettingCardGroup("General", content)

        open_mode_card = OptionsSettingCard(
            cfg.openMode, FIF.MUSIC_FOLDER,
            "When opening music from external files",
            "Behavior when double-clicking an audio file in File Manager",
            texts=["Always ask", "Play entire folder", "Play selected file only"],
        )
        group.addSettingCard(open_mode_card)
        color_card = CustomColorSettingCard(
            cfg.themeColor, # Tự động liên kết với biến themeColor mặc định của thư viện
            FIF.PALETTE,
            "Theme Color",
            "Change the primary accent color of the application"
        )
        group.addSettingCard(color_card)
        open_mode_card.setExpand(True)
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
    def __init__(self, startup_file=None, skip_ask=False):
        super().__init__()
        self.setMicaEffectEnabled(False)
        self.setWindowTitle("DK Music Player")
        app_icon = get_app_icon()
        self.setWindowIcon(app_icon)
        self.setFixedSize(750, 240)
        self.is_muted = False
        saved_vol = cfg.volume.value
        self.last_volume = saved_vol if saved_vol > 0 else 70
        self.volume = saved_vol / 100.0
        if sys.platform == "darwin":
            self.setMicaEffectEnabled(False)
            if hasattr(self.titleBar, 'setDoubleEnabled'):
                self.titleBar.setDoubleEnabled(False)

            # macOS đã có sẵn traffic-light (đỏ/vàng/xanh) native ở góc trái,
            # nên ẩn HẾT 3 nút Fluent tự vẽ, không show cái nào cả
            self.titleBar.minBtn.hide()
            self.titleBar.maxBtn.hide()
            self.titleBar.closeBtn.hide()
        else:
            self.titleBar.maxBtn.hide()
        # Hide sidebar and back button from Title Bar
        self.navigationInterface.hide()

        # Increased audio buffer to 2048 to prevent underruns/stuttering
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        self.shuffle_mode = False
        self.unplayed_indices = []
        self.shuffle_history = []
        self.shuffle_history_pos = -1
        self.played_indices = set()
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
        # Windows fix: HWND của cửa sổ con luôn được hệ điều hành vẽ nền
        # trắng mặc định trước khi QFluentWidgets kịp áp theme tối lên, gây
        # chớp trắng khi show() lần đầu (rõ nhất ở SettingsWindow/PlaylistWindow
        # vì UI của chúng dựng lâu hơn cửa sổ chính). Dựng sẵn 2 cửa sổ này
        # ngay khi app khởi động (ẩn đi ngay) để "trả" chi phí dựng UI +
        # native paint đó 1 lần lúc mở app, thay vì lúc người dùng bấm mở.
        #QTimer.singleShot(0, self._prewarm_child_windows)

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
        cfg.themeColorChanged.connect(self._on_theme_color_changed)

        # Hàng đợi + debounce cho file khởi động: khi mở nhiều file cùng lúc,
        # OS có thể spawn nhiều process gửi file tới lần lượt qua IPC. Nếu xử
        # lý (và play) ngay mỗi lần nhận 1 file, file đến sau cùng (thứ tự
        # ngẫu nhiên) sẽ "cướp" playback. Thay vào đó, gom hết file đến trong
        # một khoảng ngắn thành 1 batch rồi mới xử lý/play 1 lần duy nhất.
        self._pending_startup_files = []
        self._pending_startup_skip_ask = False
        self._startup_batch_timer = QTimer(self)
        self._startup_batch_timer.setSingleShot(True)
        self._startup_batch_timer.timeout.connect(self._flush_startup_batch)

        if startup_file:
            self._queue_startup_files(startup_file, initial_delay=200, skip_ask=skip_ask)

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

    def _prewarm_child_windows(self):
        """
        Dựng trước SettingsWindow/PlaylistWindow rồi show()->hide() ngay,
        thay vì đợi tới lúc người dùng bấm mở. windowOpacity(0) đảm bảo
        không có khung hình nào của lần show() "khởi động" này lọt ra
        màn hình. Từ lần sau, open_settings()/toggle_playlist_window() chỉ
        show() lại instance đã dựng + đã paint sẵn nên không còn flash.
        """
        if self.settings_win is None:
            self.settings_win = SettingsWindow()
            self.settings_win.setWindowOpacity(0)
            self.settings_win.show()
            self.settings_win.hide()
            self.settings_win.setWindowOpacity(1)

        if self.playlist_win is None:
            self.playlist_win = PlaylistWindow(self)
            self.playlist_win.update_playlist_ui()
            self.playlist_win.setWindowOpacity(0)
            self.playlist_win.show()
            self.playlist_win.hide()
            self.playlist_win.setWindowOpacity(1)

    def _on_theme_color_changed(self, color):
        # 1. Đồng bộ màu cho hệ thống (qfluentwidgets mặc định) và lưu ngay xuống file config.
        # Lưu ý: setThemeColor() và cfg.themeColor dùng chung 1 ConfigItem, nên nếu gọi
        # setThemeColor(color) trước rồi mới cfg.set(cfg.themeColor, color) thì item.value
        # đã bằng color từ bước trước -> QConfig.set() thấy "không đổi" và return sớm,
        # không bao giờ gọi self.save(). Truyền save=True thẳng vào đây để lưu đúng lúc.
        setThemeColor(color, save=True)
        
        # 2. Update giao diện tự vẽ
        self.play_btn.update()
        self.equalizer.update()
        self.seek_slider.update()
        
        if getattr(self, "shuffle_mode", False):
            active_icon = get_tinted_icon(resource_path("assets/icons/shuffle_active.svg"))
            self.shuffle_btn.setIcon(active_icon)
            
        if self.playlist_win is not None:
            self.playlist_win.update_playlist_ui()
            
        self._refresh_ab_buttons()

    def open_settings(self):
        if self.settings_win is None:
            self.settings_win = SettingsWindow()
            
        if not self.settings_win.isVisible():
            # Kỹ thuật chống chớp: Ép trong suốt -> Show (vẽ ngầm) -> Đợi 40ms -> Hiện lại
            self.settings_win.setWindowOpacity(0)
            self.settings_win.show()
            QTimer.singleShot(40, lambda: self.settings_win.setWindowOpacity(1))
            
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
        self.prev_btn.setIconSize(QSize(24, 24))
        self.prev_btn.clicked.connect(self.prev_song)
        controls.addWidget(self.prev_btn)

        self.play_btn = PrimaryPlayButton()
        self.play_btn.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_btn)

        self.stop_btn = TransparentToolButton(QIcon(resource_path("assets/icons/stop_dark.png")))
        self.stop_btn.setIconSize(QSize(24, 24))
        self.stop_btn.clicked.connect(self.stop_song)
        controls.addWidget(self.stop_btn)

        self.next_btn = TransparentToolButton(QIcon(resource_path("assets/icons/next_dark.png")))
        self.next_btn.setIconSize(QSize(24, 24))
        self.next_btn.clicked.connect(self.next_song)
        controls.addWidget(self.next_btn)

        controls.addWidget(self._vline())

        self.playlist_btn = TransparentToolButton(FIF.MENU)
        self.playlist_btn.clicked.connect(self.toggle_playlist_window)
        self.playlist_btn.setToolTip("Playlist")
        controls.addWidget(self.playlist_btn)

        self.repeat_btn = TransparentToolButton(QIcon(resource_path(f"assets/icons/repeat_{self.repeat_mode}.png")))
        self.repeat_btn.setIconSize(QSize(24, 24))
        self.repeat_btn.clicked.connect(self.cycle_repeat)
        self.repeat_btn.setToolTip("Repeat: Off / All / Single Track")
        controls.addWidget(self.repeat_btn)
        self.shuffle_btn = TransparentToolButton(QIcon(resource_path(f"assets/icons/shuffle_{'dark' if isDarkTheme() else 'light'}.png")))
        self.shuffle_btn.setIconSize(QSize(24, 24))
        self.shuffle_btn.setToolTip("Shuffle: Off")
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        controls.addWidget(self.shuffle_btn)


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
        # Chỉnh padding: 0px và set iconSize chuẩn để icon luôn vào chính giữa tâm nút
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setIconSize(QSize(20, 20))
        self.play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {c}; border-radius: 20px; border: none; padding: 0px; }}"
            f"QPushButton:hover {{ background-color: {c}; }}"
        )

    # ---------- Theme Handling ----------
    def toggle_theme(self):
        self.apply_theme(Theme.LIGHT if isDarkTheme() else Theme.DARK)

    def apply_theme(self, theme):
        setTheme(theme)
        self._style_play_button()
        bg_color = QColor(32, 32, 32) if isDarkTheme() else QColor(243, 243, 243)
        if self.settings_win is not None:
            pal = self.settings_win.palette()
            pal.setColor(self.settings_win.backgroundRole(), bg_color)
            self.settings_win.setPalette(pal)
            
        if self.playlist_win is not None:
            pal = self.playlist_win.palette()
            pal.setColor(self.playlist_win.backgroundRole(), bg_color)
            self.playlist_win.setPalette(pal)

        self.stop_btn.setIcon(QIcon(resource_path(
            f"assets/icons/stop_{'dark' if isDarkTheme() else 'light'}.png")))
        self.prev_btn.setIcon(QIcon(resource_path(
                    f"assets/icons/prev_{'dark' if isDarkTheme() else 'light'}.png")))
        self.next_btn.setIcon(QIcon(resource_path(
                    f"assets/icons/next_{'dark' if isDarkTheme() else 'light'}.png")))
        if not getattr(self, "shuffle_mode", False):
            self.shuffle_btn.setIcon(QIcon(resource_path(
                        f"assets/icons/shuffle_{'dark' if isDarkTheme() else 'light'}.png")))
        else:
            self.shuffle_btn.setIcon(QIcon(resource_path(
                        f"assets/icons/shuffle_active.png")))
        self.marquee.update()
        if hasattr(self, 'playlist_win') and self.playlist_win is not None:
            self.playlist_win.update_playlist_ui()

    # ---------- Playlist Window ----------
    def toggle_playlist_window(self):
        if self.playlist_win is None:
            self.playlist_win = PlaylistWindow(self)
            self.playlist_win.update_playlist_ui()
            
        if self.playlist_win.isVisible():
            self.playlist_win.hide()
        else:
            # Kỹ thuật chống chớp khi re-show
            self.playlist_win.setWindowOpacity(0)
            self.playlist_win.show()
            QTimer.singleShot(40, lambda: self.playlist_win.setWindowOpacity(1))
            self.playlist_win.raise_()
            self.playlist_win.activateWindow()

    # ---------- Startup File Handling ----------
    def _queue_startup_files(self, paths, initial_delay=None, skip_ask=False):
        if isinstance(paths, str):
            paths = [paths]
        self._pending_startup_files.extend(p for p in paths if p)
        if skip_ask:
            self._pending_startup_skip_ask = True
        # Mỗi lần có file mới tới, reset lại đồng hồ đếm 400ms — chỉ khi
        # "im lặng" không có file nào tới thêm trong 400ms thì mới xử lý
        # batch, để gom đủ hết các file được mở cùng lúc.
        delay = initial_delay if initial_delay is not None else 400
        self._startup_batch_timer.start(delay)

    def _flush_startup_batch(self):
        paths = self._pending_startup_files
        skip_ask = self._pending_startup_skip_ask
        self._pending_startup_files = []
        self._pending_startup_skip_ask = False
        if paths:
            self._handle_startup_file(paths, skip_ask=skip_ask)

    def _handle_startup_file(self, paths, skip_ask=False):
        # Chấp nhận cả 1 path đơn (str, tương thích ngược) lẫn 1 danh sách nhiều path.
        if isinstance(paths, str):
            paths = [paths]
        paths = [os.path.abspath(p) for p in paths if p]
        paths = [p for p in paths if os.path.isfile(p)]
        # Sắp xếp tự nhiên theo tên file để track 1 luôn được phát trước,
        # bất kể thứ tự các process/IPC message gửi file tới primary.
        paths = sorted(dict.fromkeys(paths), key=_natural_key)
        if not paths:
            return
        primary = paths[0]

        if skip_ask:
            # Người dùng mở thẳng 1 thư mục ("Open Folder With..." trên Ubuntu) —
            # ý định đã rõ ràng là phát toàn bộ nhạc trong đó, không cần hỏi lại,
            # và cũng không quét lại theo dirname(primary) vì paths ở đây đã là
            # danh sách đầy đủ (kể cả thư mục con) được quét sẵn từ trước.
            for p in paths:
                self._add_to_playlist(p)
            idx = self.playlist.index(primary) if primary in self.playlist else len(self.playlist) - 1
            if idx >= 0:
                self.current_index = idx
                self._play_current()
            return

        mode = cfg.openMode.value
        if mode == "ask":
            box = QMessageBox(self)
            box.setWindowTitle("Open Music")
            extra = f" (+{len(paths) - 1} file khác)" if len(paths) > 1 else ""
            box.setText(f"Do you want to play all audio files in the folder containing:\n"
                        f"{os.path.basename(primary)}{extra}\n\nYes = Play entire folder\nNo = Play this file only")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                                    QMessageBox.StandardButton.Cancel)
            ans = box.exec()
            if ans == QMessageBox.StandardButton.Cancel:
                return
            mode = "folder" if ans == QMessageBox.StandardButton.Yes else "single"

        if mode == "folder":
            folder = os.path.dirname(primary)
            self._scan_folder_into_playlist(folder)
            # Các file nằm ngoài folder đó (hiếm khi xảy ra) vẫn được thêm vào playlist
            for p in paths[1:]:
                if os.path.dirname(p) != folder:
                    self._add_to_playlist(p)
            idx = self.playlist.index(primary) if primary in self.playlist else (0 if self.playlist else -1)
        else:
            for p in paths:
                self._add_to_playlist(p)
            idx = self.playlist.index(primary) if primary in self.playlist else len(self.playlist) - 1

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
        if not folder:
            return
        first_new_index = len(self.playlist)
        self._scan_folder_into_playlist(folder)
        if len(self.playlist) > first_new_index:
            self.current_index = first_new_index
            self._play_current()

    def _scan_folder_into_playlist(self, folder):
        for root_dir, _, files in os.walk(folder):
            matched = [f for f in files if f.lower().endswith(SUPPORTED_EXT)]
            for f in sorted(matched, key=_natural_key):
                self._add_to_playlist(os.path.join(root_dir, f))

    def _add_to_playlist(self, path):
        path = os.path.abspath(path)
        if path in self.playlist:
            return
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
        # Dịch lại played_indices cho khớp với playlist sau khi xoá 1 bài
        self.played_indices = {
            (p - 1 if p > i else p) for p in self.played_indices if p != i
        }
        self.unplayed_indices = [
            (p - 1 if p > i else p) for p in self.unplayed_indices if p != i
        ]
        self.shuffle_history = [
            (p - 1 if p > i else p) for p in self.shuffle_history if p != i
        ]
        self.shuffle_history_pos = min(self.shuffle_history_pos, len(self.shuffle_history) - 1)
        if i == self.current_index:
            self.stop_song()
        elif i < self.current_index:
            self.current_index -= 1
        self._refresh_nav_buttons()
        if self.playlist_win is not None:
            self.playlist_win.update_playlist_ui()

    def clear_playlist(self):
        self.stop_song()
        self.playlist.clear()
        self.played_indices = set()
        self.unplayed_indices = []
        self.shuffle_history = []
        self.shuffle_history_pos = -1
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
        # Ghi nhận bài này đã thực sự được phát (dùng để tô màu xám đúng,
        # không phụ thuộc vào vị trí index như trước - lỗi khi dùng prev/next/mở từ playlist)
        self.played_indices.add(self.current_index)

        # Đồng bộ túi shuffle + lịch sử shuffle với bài vừa mở, kể cả khi bài
        # này được mở bằng double-click/play_index chứ không qua Next/Prev.
        if self.shuffle_mode:
            if self.current_index in self.unplayed_indices:
                self.unplayed_indices.remove(self.current_index)
            if (not self.shuffle_history
                    or self.shuffle_history[self.shuffle_history_pos] != self.current_index):
                # Cắt bỏ phần lịch sử "đi tiếp" cũ nếu người dùng vừa mở 1 bài khác
                self.shuffle_history = self.shuffle_history[: self.shuffle_history_pos + 1]
                self.shuffle_history.append(self.current_index)
                self.shuffle_history_pos = len(self.shuffle_history) - 1

        self.paused = False
        self.manually_stopped = False
        self.offset = 0
        self.start_time = time.time()
        self.play_btn.set_playing(True)
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
        if hasattr(self, 'playlist_win') and self.playlist_win is not None:
            self.playlist_win.update_playlist_ui()

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
            self.play_btn.set_playing(True)
            self.equalizer.set_playing(True)
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                self.paused = True
                self.offset = time.time() - self.start_time
                self.play_btn.set_playing(False)
                self.equalizer.set_playing(False)
            else:
                self._play_current()

    def stop_song(self):
        self.manually_stopped = True
        pygame.mixer.music.stop()
        self.play_btn.set_playing(False)
        self.equalizer.set_playing(False)
        self.marquee.set_text("No track playing")
        self.time_label.setText("00:00 / 00:00")
        # Phải chặn tín hiệu valueChanged khi set slider về 0, nếu không
        # sẽ trigger _on_seek_value_changed -> _seek_to(0) -> phát lại bài
        # hát từ đầu ngay sau khi vừa Stop!
        self._block_seek_signal = True
        self.seek_slider.setValue(0)
        self._block_seek_signal = False
        self.paused = False
        self.offset = 0


    def next_song(self):
        if not self.playlist:
            return
        if self.shuffle_mode:
            self._advance_shuffle(forward=True)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self._play_current()

    def prev_song(self):
        if not self.playlist:
            return
        if self.shuffle_mode:
            self._advance_shuffle(forward=False)
        else:
            self.current_index = (self.current_index - 1) % len(self.playlist)
        self._play_current()

    def _advance_shuffle(self, forward: bool):
        """Chọn bài kế tiếp/trước đó theo chế độ Shuffle.

        Dùng self.unplayed_indices làm "túi" các bài chưa random tới trong vòng
        hiện tại, và self.shuffle_history để Prev có thể lùi lại đúng bài ngẫu
        nhiên vừa phát (thay vì random 1 bài mới mỗi lần bấm Prev).
        """
        if forward:
            # Nếu đang đứng giữa lịch sử (vừa Prev xong) -> đi tiếp trong lịch sử
            # đó trước khi random bài mới.
            if self.shuffle_history_pos < len(self.shuffle_history) - 1:
                self.shuffle_history_pos += 1
                self.current_index = self.shuffle_history[self.shuffle_history_pos]
                return
            if not self.unplayed_indices:
                # Đã random hết 1 lượt toàn bộ playlist -> random lại vòng mới
                self._reset_unplayed_indices()
            if not self.unplayed_indices:
                return
            self.current_index = self.unplayed_indices.pop()
            self.shuffle_history.append(self.current_index)
            self.shuffle_history_pos = len(self.shuffle_history) - 1
        else:
            if self.shuffle_history_pos > 0:
                self.shuffle_history_pos -= 1
                self.current_index = self.shuffle_history[self.shuffle_history_pos]
            # Nếu chưa có lịch sử để lùi thì giữ nguyên bài hiện tại (không có gì để Prev)

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
                        # repeat off: chỉ next tiếp nếu còn bài chưa nghe
                        has_more = (bool(self.unplayed_indices) if self.shuffle_mode
                                    else self.current_index < len(self.playlist) - 1)
                        if self.playlist and has_more:
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
        else:
            e.ignore()
            self.showMinimized()

    def do_quit(self):
        pygame.mixer.music.stop()
        pygame.mixer.quit()
        qconfig.save()
        cfg.save()
        QApplication.quit()

    def handle_ipc_message(self, message):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if not message:
            return
        lines = message.split("\n")
        # Dòng đầu là cờ "D" (mở từ thư mục, skip dialog) hoặc "F" (file thường)
        skip_ask = lines and lines[0] == "D"
        paths = [p for p in lines[1:] if p] if lines and lines[0] in ("D", "F") else [p for p in lines if p]
        if paths:
            self._queue_startup_files(paths, skip_ask=skip_ask)

    def _reset_unplayed_indices(self):
        """Khởi tạo lại danh sách các bài chưa phát ngoại trừ bài hiện tại."""
        if not self.playlist:
            self.unplayed_indices = []
            return
        self.unplayed_indices = [i for i in range(len(self.playlist)) if i != self.current_index]
        random.shuffle(self.unplayed_indices)

    def toggle_shuffle(self):
        """Bật / Tắt Chế độ Shuffle."""
        self.shuffle_mode = not self.shuffle_mode
        
        if self.shuffle_mode:
            self._reset_unplayed_indices()
            self.shuffle_history = [self.current_index] if self.current_index != -1 else []
            self.shuffle_history_pos = len(self.shuffle_history) - 1
            self.shuffle_btn.setToolTip("Shuffle: On (Play all tracks once)")
            # Đổi sang icon active (không cần phân biệt theme)
            active_icon = get_tinted_icon(resource_path("assets/icons/shuffle_active.svg"))
            self.shuffle_btn.setIcon(active_icon)
        else:
            self.unplayed_indices = []
            self.shuffle_history = []
            self.shuffle_history_pos = -1
            self.shuffle_btn.setToolTip("Shuffle: Off")
            # Trả lại icon theo theme hiện tại
            theme_suffix = 'dark' if isDarkTheme() else 'light'
            normal_icon = QIcon(resource_path(f"assets/icons/shuffle_{theme_suffix}.png"))
            self.shuffle_btn.setIcon(normal_icon)


def _send_to_running_instance(socket, startup_files, skip_ask):
    prefix = "D" if skip_ask else "F"
    payload = prefix + "\n" + "\n".join(startup_files)
    socket.write(payload.encode("utf-8"))
    socket.flush()  # Đẩy dữ liệu đi ngay
    socket.waitForBytesWritten(1000)  # Tăng timeout an toàn cho Windows
    socket.disconnectFromServer()


def _try_connect_running_instance(timeout_ms=200):
    """Thử connect tới instance đang chạy (nếu có). Trả về socket đã
    connected, hoặc None nếu không có ai đang chạy trong khoảng timeout."""
    sock = QLocalSocket()
    sock.connectToServer(IPC_SERVER_NAME)
    if sock.waitForConnected(timeout_ms):
        return sock
    sock.close()
    return None


def main():
    startup_files, skip_ask = _expand_startup_args(sys.argv[1:])

    # --- BỔ SUNG: Dùng MacApplication nếu chạy trên macOS ---
    if sys.platform == "darwin":
        app = MacApplication(sys.argv)
    else:
        app = QApplication(sys.argv)
        
    app.setQuitOnLastWindowClosed(False)

    # --- Bầu ai là "primary" (Code giữ nguyên của fen) ---
    sock = _try_connect_running_instance(200)
    if sock is None:
        for _ in range(14):  # 14 x 200ms ~= 2.8s tổng cộng
            time.sleep(0.2)
            sock = _try_connect_running_instance(200)
            if sock is not None:
                break
    if sock is not None:
        _send_to_running_instance(sock, startup_files, skip_ask)
        return

    QLocalServer.removeServer(IPC_SERVER_NAME)
    ipc_server = QLocalServer()
    if not ipc_server.listen(IPC_SERVER_NAME):
        retry_sock = None
        for _ in range(10):  # ~2s
            retry_sock = _try_connect_running_instance(200)
            if retry_sock is not None:
                break
            time.sleep(0.2)
        if retry_sock is not None:
            _send_to_running_instance(retry_sock, startup_files, skip_ask)
        return

    setTheme(cfg.themeMode.value)
    setThemeColor(cfg.themeColor.value)

    win = MainWindow(startup_file=startup_files, skip_ask=skip_ask)

    # --- BỔ SUNG: Liên kết MacApplication với MainWindow ---
    if sys.platform == "darwin":
        app.main_window = win

    # --- XỬ LÝ IPC MULTI-CONNECTION HOÀN CHỈNH ---
    def _on_new_ipc_connection():
        while ipc_server.hasPendingConnections():
            sock = ipc_server.nextPendingConnection()
            if sock is None:
                continue
            if sock.waitForReadyRead(500):
                data = bytes(sock.readAll()).decode("utf-8")
                if data:
                    win.handle_ipc_message(data)
            sock.disconnectFromServer()

    ipc_server.newConnection.connect(_on_new_ipc_connection)
    win._ipc_server = ipc_server

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()