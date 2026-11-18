"""
Masaüstü Robot Süpürge — Giriş Noktası & Orkestrasyon
======================================================
Başlangıç akışı:
  1. SettingsDialog otomatik açılır.
  2. Kullanıcı ayarları kaydeder veya iptal eder → dialog kapanır.
  3. Uygulama bekleme modunda kalır; robot overlay + kontrol paneli görünür.
  4. Kullanıcı "▶ Süpür" butonuna basınca tarama başlar.
  5. Animasyon tamamlanınca ReportDialog gösterilir.
"""

from __future__ import annotations

import sys
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QPushButton,
    QGraphicsDropShadowEffect,
)

import config
from robot_widget import RobotOverlay
from file_scanner import FileScanner, ScanResult
from file_mover import FileMover
from report_dialog import ReportDialog
from settings_dialog import SettingsDialog


# ---------------------------------------------------------------------------
# Yüzen Kontrol Paneli (▶ Süpür | ⚙ | ✕)
# ---------------------------------------------------------------------------

class ControlPanel(QWidget):
    """Ekranın sağ üst köşesinde yüzen üç butonlu kontrol şeridi."""

    start_clicked    = pyqtSignal()
    settings_clicked = pyqtSignal()
    quit_clicked     = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── ▶ Süpür ────────────────────────────────────────────────────
        self.btn_start = QPushButton("▶  Süpür")
        self.btn_start.setFixedHeight(42)
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: rgba(40, 180, 100, 230);
                color: white;
                border: 1px solid rgba(80, 220, 140, 200);
                border-radius: 21px;
                padding: 0 18px;
            }
            QPushButton:hover   { background: rgba(55, 205, 120, 245); }
            QPushButton:pressed { background: rgba(30, 150,  85, 255); }
            QPushButton:disabled {
                background: rgba(60, 65, 85, 180);
                color: rgba(150, 155, 175, 160);
                border: 1px solid rgba(80, 85, 110, 120);
            }
        """)

        # ── ⚙ Ayarlar ──────────────────────────────────────────────────
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(42, 42)
        self.btn_settings.setFont(QFont("Segoe UI Emoji", 16))
        self.btn_settings.setToolTip("Ayarları Aç")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background: rgba(22, 26, 42, 220);
                color: rgba(180, 195, 235, 240);
                border: 1px solid rgba(70, 80, 120, 180);
                border-radius: 21px;
            }
            QPushButton:hover {
                background: rgba(55, 120, 215, 230);
                color: white;
            }
        """)

        # ── ✕ Çıkış ────────────────────────────────────────────────────
        self.btn_quit = QPushButton("✕")
        self.btn_quit.setFixedSize(42, 42)
        self.btn_quit.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.btn_quit.setToolTip("Kapat")
        self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quit.setStyleSheet("""
            QPushButton {
                background: rgba(22, 26, 42, 220);
                color: rgba(240, 110, 110, 230);
                border: 1px solid rgba(90, 50, 60, 180);
                border-radius: 21px;
            }
            QPushButton:hover {
                background: rgba(220, 60, 60, 230);
                color: white;
            }
        """)

        # Gölge & layout
        for btn in (self.btn_start, self.btn_settings, self.btn_quit):
            sh = QGraphicsDropShadowEffect(self)
            sh.setBlurRadius(14)
            sh.setOffset(0, 3)
            sh.setColor(QColor(0, 0, 0, 140))
            btn.setGraphicsEffect(sh)
            layout.addWidget(btn)

        self.btn_start.clicked.connect(self.start_clicked)
        self.btn_settings.clicked.connect(self.settings_clicked)
        self.btn_quit.clicked.connect(self.quit_clicked)

        self.adjustSize()
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20, 18)


# ---------------------------------------------------------------------------
# Orkestratör
# ---------------------------------------------------------------------------

class Controller(QObject):
    """
    Tüm bileşenleri koordine eden ince katman.

    Başlangıç akışı
    ---------------
    __init__  → SettingsDialog aç (uygulama bekler)
    _on_startup_settings_closed → robot overlay + kontrol paneli göster
    btn_start → _start_scan → animasyon → FileMover → ReportDialog
    """

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app        = app
        self._result:    Optional[ScanResult]   = None
        self._report:    Optional[ReportDialog] = None
        self._settings_dlg: Optional[SettingsDialog] = None
        self._start_time: float = 0.0
        self._is_running: bool  = False

        # Robot overlay — henüz gizli; ayarlar kapanınca gösterilecek
        self._robot = RobotOverlay()

        # Kontrol paneli — henüz gizli
        self._panel = ControlPanel()
        self._panel.start_clicked.connect(self._start_scan)
        self._panel.settings_clicked.connect(self._open_settings)
        self._panel.quit_clicked.connect(self._app.quit)

        # Robot sinyalleri
        self._robot.settings_requested.connect(self._open_settings)
        self._robot.target_reached.connect(self._on_target_reached)
        self._robot.all_targets_done.connect(self._on_animation_done)

        # ── Başlangıçta SettingsDialog'u aç ──────────────────────────
        QTimer.singleShot(200, self._open_startup_settings)

    # ------------------------------------------------------------------
    # Başlangıç: ayarlar penceresi
    # ------------------------------------------------------------------

    def _open_startup_settings(self) -> None:
        """Uygulama ilk açıldığında ayarları göster."""
        dlg = SettingsDialog(config.get_settings())
        dlg.settings_saved.connect(self._on_settings_saved)
        # Kapanınca (kaydet veya iptal) ana ekranı göster
        dlg.finished.connect(self._on_startup_settings_closed)
        self._settings_dlg = dlg
        dlg.show()

    def _on_startup_settings_closed(self) -> None:
        """Ayarlar penceresi kapandı → robot + kontrol panelini göster."""
        self._robot.set_status(
            "🤖  Hazır! — Başlamak için '▶ Süpür'e tıkla."
        )
        self._robot.show()
        self._panel.show()

    # ------------------------------------------------------------------
    # Çalışma sırasında ayarlar
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        """Çalışma sırasında ayarlar butonuna basıldı."""
        if self._is_running:
            return
        if self._settings_dlg is not None and self._settings_dlg.isVisible():
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        self._settings_dlg = SettingsDialog(config.get_settings())
        self._settings_dlg.settings_saved.connect(self._on_settings_saved)
        self._settings_dlg.show()

    def _on_settings_saved(self, new_settings: config.AppSettings) -> None:
        self._robot.set_status("✅  Ayarlar kaydedildi! '▶ Süpür'e tıkla.")

    # ------------------------------------------------------------------
    # Tarama & animasyon
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._is_running:
            return

        self._robot.set_status("🔍  Masaüstü taranıyor...")
        scanner    = FileScanner()
        raw_result = scanner.scan()

        # Ayarlara göre "skip" olanları filtrele
        settings = config.get_settings()
        active = [
            item for item in raw_result.items
            if settings.category_rules.get(
                item.category.name, config.ACTION_MOVE
            ) != config.ACTION_SKIP
        ]
        self._result = ScanResult(
            items=active,
            desktop_path=raw_result.desktop_path,
        )

        if self._result.total == 0:
            self._robot.set_status(
                "✅  Temizlenecek dosya yok. Tekrar için '▶ Süpür'e bas."
            )
            return

        self._is_running = True
        self._panel.btn_start.setEnabled(False)
        self._panel.btn_start.setText("⏳  Süpürülüyor...")
        self._panel.btn_settings.setEnabled(False)

        self._robot.set_status(
            f"🤖  {self._result.total} dosya bulundu — başlıyor!"
        )

        positions = [item.screen_pos  for item in self._result.items]
        labels    = [item.path.name   for item in self._result.items]
        self._robot.set_targets(positions, labels)
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Sinyal işleyiciler
    # ------------------------------------------------------------------

    def _on_target_reached(self, idx: int) -> None:
        if self._result is None:
            return
        items = self._result.items
        if not (0 <= idx < len(items)):
            return

        item  = items[idx]
        mover = FileMover(
            ScanResult(items=[item], desktop_path=self._result.desktop_path)
        )
        mover.status_update.connect(self._robot.set_status)
        mover.finished.connect(mover.deleteLater)
        mover.start()

    def _on_animation_done(self, done_count: int) -> None:
        elapsed          = time.monotonic() - self._start_time
        self._is_running = False

        self._robot.hide()
        self._panel.hide()

        self._report = ReportDialog(self._result, elapsed)
        self._report.closed.connect(self._app.quit)
        self._report.show()


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Masaüstü Robot Süpürge")
    app.setQuitOnLastWindowClosed(False)   # rapor kapanınca biz çıkartırız

    controller = Controller(app)   # noqa: F841 — referansı canlı tut

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
