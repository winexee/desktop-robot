"""
Masaüstü Robot Süpürge -- Giriş Noktası & Orkestrasyon
=======================================================
Başlangıç akışı:
  1. SettingsDialog otomatik açılır.
  2. Kullanıcı ayarları kaydeder veya iptal eder -> dialog kapanır.
  3. Uygulama bekleme modunda kalır; robot overlay (boşta, %0 CPU) + kontrol paneli görünür.
  4. Kullanıcı "> Süpür" butonuna basınca arka planda tarama başlar.
  5. Doğrulama & onay sonrası animasyon ile FileWorkerThread eşzamanlı çalışır.
  6. İkisi de tamamlanınca (veya iptal edilince) ReportDialog gösterilir.
"""

from __future__ import annotations

import pathlib
import sys
import time
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QTimer, QObject, QRect, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QBrush
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config
from file_mover import FileResult, FileStatus, FileWorkerThread, HAS_SEND2TRASH
from file_scanner import ScanResult, ScanWorkerThread
from report_dialog import ReportDialog
from robot_widget import RobotOverlay
from settings_dialog import SettingsDialog


# ---------------------------------------------------------------------------
# Sürükleme tutamacı ve Modern Tek Parça Kontrol Çubuğu
# ---------------------------------------------------------------------------

class _DragGrip(QWidget):
    """Kontrol çubuğunun sol kenarında 6 noktalı sürükleme tutamacı."""

    def __init__(self, color: str, bg_color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._dot_color = color
        self._bg_color = bg_color
        self.setFixedSize(22, 32)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Kontrol çubuğunu sürükleyerek taşıyın")

    def set_colors(self, dot_color: str, bg_color: str) -> None:
        self._dot_color = dot_color
        self._bg_color = bg_color
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), QColor(self._bg_color))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(self._dot_color)))
            for row in range(3):
                for col in range(2):
                    x = 7 + col * 5
                    y = 8 + row * 6
                    p.drawEllipse(x, y, 3, 3)
        finally:
            p.end()


class ControlPanel(QWidget):
    """
    Tek birleşik, ince kenarlıklı, sürüklenebilir Windows 11 / Fluent tarzı
    kompakt kontrol çubuğu.
    """

    start_clicked    = pyqtSignal()
    cancel_clicked   = pyqtSignal()
    settings_clicked = pyqtSignal()
    quit_clicked     = pyqtSignal()

    def __init__(
        self,
        theme: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # WA_TranslucentBackground yalnızca dış 10px yuvarlatılmış köşe kırpması içindir;
        # içerideki tüm QSS renkleri %100 opaktır.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pal = config.get_theme_palette(theme)
        self._dragging = False
        self._drag_offset = QPoint()
        self._user_moved = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        self._bar = QFrame()
        self._bar.setObjectName("toolbar_card")
        bar_lay = QHBoxLayout(self._bar)
        bar_lay.setContentsMargins(6, 5, 6, 5)
        bar_lay.setSpacing(4)

        self._grip = _DragGrip(self._pal["muted"], self._pal["surface"], self._bar)

        # -- Süpür -------------------------------------------------------
        self.btn_start = QPushButton("Süpür")
        self.btn_start.setFixedHeight(32)
        self.btn_start.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)

        self._sep_start = self._make_divider()

        # -- İptal (yalnızca çalışma sırasında görünür/aktif) ------------
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.hide()

        self._sep_cancel = self._make_divider()
        self._sep_cancel.hide()

        # -- Ayarlar -----------------------------------------------------
        self.btn_settings = QPushButton("Ayarlar")
        self.btn_settings.setFixedHeight(32)
        self.btn_settings.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.btn_settings.setToolTip("Ayarları Aç")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)

        self._sep_settings = self._make_divider()

        # -- Kapat -------------------------------------------------------
        self.btn_quit = QPushButton("Kapat")
        self.btn_quit.setFixedHeight(32)
        self.btn_quit.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.btn_quit.setToolTip("Uygulamayı Kapat")
        self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)

        bar_lay.addWidget(self._grip)
        bar_lay.addWidget(self.btn_start)
        bar_lay.addWidget(self._sep_start)
        bar_lay.addWidget(self.btn_cancel)
        bar_lay.addWidget(self._sep_cancel)
        bar_lay.addWidget(self.btn_settings)
        bar_lay.addWidget(self._sep_settings)
        bar_lay.addWidget(self.btn_quit)

        outer.addWidget(self._bar)

        self.btn_start.clicked.connect(self.start_clicked)
        self.btn_cancel.clicked.connect(self.cancel_clicked)
        self.btn_settings.clicked.connect(self.settings_clicked)
        self.btn_quit.clicked.connect(self.quit_clicked)

        self._apply_palette(self._pal)
        self._reposition()

    @staticmethod
    def _make_divider() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedSize(1, 20)
        return sep

    def apply_theme(self, theme_name: str) -> None:
        """Kontrol çubuğunu belirtilen opak temaya geçir."""
        self._pal = config.get_theme_palette(theme_name)
        self._apply_palette(self._pal)

    def _apply_palette(self, p: dict[str, str]) -> None:
        self._bar.setStyleSheet(f"""
            QFrame#toolbar_card {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 10px;
            }}
        """)
        self._grip.set_colors(p["muted"], p["surface"])

        sep_qss = f"background-color: {p['border']}; border: none;"
        self._sep_start.setStyleSheet(sep_qss)
        self._sep_cancel.setStyleSheet(sep_qss)
        self._sep_settings.setStyleSheet(sep_qss)

        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['toolbar_start_bg']};
                color: {p['toolbar_start_fg']};
                border: none;
                border-radius: 6px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {p['toolbar_start_hv']};
                color: {p['toolbar_start_fg']};
            }}
            QPushButton:pressed {{
                background-color: {p['toolbar_start_pr']};
                color: {p['toolbar_start_fg']};
            }}
            QPushButton:disabled {{
                background-color: {p['disabled_bg']};
                color: {p['disabled_fg']};
            }}
        """)

        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['toolbar_cancel_bg']};
                color: {p['toolbar_cancel_fg']};
                border: none;
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {p['toolbar_cancel_hv']};
                color: {p['toolbar_cancel_fg']};
            }}
            QPushButton:pressed {{
                background-color: {p['toolbar_cancel_pr']};
                color: {p['toolbar_cancel_fg']};
            }}
            QPushButton:disabled {{
                background-color: {p['disabled_bg']};
                color: {p['disabled_fg']};
            }}
        """)

        self.btn_settings.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['surface']};
                color: {p['text']};
                border: none;
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {p['hover']};
                color: {p['text']};
            }}
            QPushButton:pressed {{
                background-color: {p['pressed']};
                color: {p['text']};
            }}
            QPushButton:disabled {{
                background-color: {p['surface']};
                color: {p['disabled_fg']};
            }}
        """)

        self.btn_quit.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['surface']};
                color: {p['muted']};
                border: none;
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {p['toolbar_quit_hv']};
                color: {p['toolbar_quit_fg']};
            }}
            QPushButton:pressed {{
                background-color: {p['toolbar_quit_pr']};
                color: {p['toolbar_quit_fg']};
            }}
            QPushButton:disabled {{
                background-color: {p['surface']};
                color: {p['disabled_fg']};
            }}
        """)

    # ------------------------------------------------------------------
    # Sürükleme (Fare ile ekranın istenilen yerine taşıma)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            self._grip.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            gpos = event.globalPosition().toPoint()
            target = gpos - self._drag_offset
            clamped = self._clamp_to_screen(target, gpos)
            self.move(clamped)
            self._user_moved = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._grip.setCursor(Qt.CursorShape.OpenHandCursor)
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _clamp_to_screen(self, pos: QPoint, ref_global: Optional[QPoint] = None) -> QPoint:
        screen = QApplication.screenAt(ref_global) if ref_global is not None else None
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None and QApplication.screens():
            screen = QApplication.screens()[0]
        geom = screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)
        max_x = max(geom.x(), geom.x() + geom.width() - self.width())
        max_y = max(geom.y(), geom.y() + geom.height() - self.height())
        return QPoint(
            max(geom.x(), min(pos.x(), max_x)),
            max(geom.y(), min(pos.y(), max_y)),
        )

    def _reposition(self) -> None:
        """Boyutu güncelle; kullanıcı taşıdıysa mevcut konumu koruyarak ekrana sığdır."""
        self.adjustSize()
        if self._user_moved:
            self.move(self._clamp_to_screen(self.pos(), self.pos()))
            return
        screen = QApplication.primaryScreen()
        if screen is None and QApplication.screens():
            screen = QApplication.screens()[0]
        geom = screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)
        self.move(
            geom.x() + geom.width() - self.width() - 20,
            geom.y() + 18,
        )

    def set_scanning_state(self, scanning: bool) -> None:
        """Tarama sırasında buton durumlarını güncelle."""
        if scanning:
            self.btn_start.setEnabled(False)
            self.btn_start.setText("Taranıyor...")
            self.btn_settings.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.hide()
            self._sep_cancel.hide()
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("Süpür")
            self.btn_settings.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.hide()
            self._sep_cancel.hide()
        self._reposition()

    def set_running_state(self, running: bool) -> None:
        """Temizlik çalışması sırasında buton durumlarını güncelle."""
        if running:
            self.btn_start.setEnabled(False)
            self.btn_start.setText("Süpürülüyor...")
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.show()
            self._sep_cancel.show()
            self.btn_settings.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("Süpür")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.hide()
            self._sep_cancel.hide()
            self.btn_settings.setEnabled(True)
        self._reposition()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            if self.btn_cancel.isEnabled() and self.btn_cancel.isVisible():
                self.cancel_clicked.emit()
                event.accept()
                return
        super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Temizlik Onay Özeti Diyaloğu (koyu tema, tamamen opak, sıfır emoji)
# ---------------------------------------------------------------------------

class _ConfirmCleanDialog(QDialog):
    """
    Temizlik başlamadan önce kullanıcıya dosya sayılarını, tarama dışı
    öğeleri ve kalıcı silme uyarısını gösteren opak onay penceresi.
    """

    def __init__(
        self,
        move_count: int,
        trash_count: int,
        delete_count: int,
        skip_count: int,
        target_root: pathlib.Path,
        scan_result: ScanResult,
        theme: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._delete_count = delete_count
        self._pal = config.get_theme_palette(theme)
        self._build_ui(
            move_count=move_count,
            trash_count=trash_count,
            delete_count=delete_count,
            skip_count=skip_count,
            target_root=target_root,
            scan_result=scan_result,
        )

    def _build_ui(
        self,
        move_count: int,
        trash_count: int,
        delete_count: int,
        skip_count: int,
        target_root: pathlib.Path,
        scan_result: ScanResult,
    ) -> None:
        p = self._pal
        self.setWindowTitle("Temizlik Onayı")
        self.setMinimumWidth(500)
        self.setWindowIcon(QIcon(str(config.get_asset_path("robot_supurge.png"))))
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg']};
                color: {p['text_body']};
            }}
            QLabel {{
                background-color: {p['bg']};
                color: {p['text_body']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Başlık
        title = QLabel("Temizlik İşlemi Özeti")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"background-color: {p['bg']}; color: {p['text']};")
        root.addWidget(title)

        subtitle = QLabel(
            f"Hedef klasör: {target_root}"
        )
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"background-color: {p['bg']}; color: {p['muted']};")
        root.addWidget(subtitle)

        # Özet kartı
        summary_card = QFrame()
        summary_card.setStyleSheet(f"""
            QFrame {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(summary_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        rows = [
            ("Taşınacak dosya", f"{move_count}", p["status_moved"]),
            ("Çöp kutusuna gönderilecek", f"{trash_count}", p["status_trashed"]),
            ("Kalıcı olarak silinecek", f"{delete_count}", p["status_failed"] if delete_count > 0 else p["muted"]),
            ("Atlanacak (kategori kuralı)", f"{skip_count}", p["muted"]),
            ("Tarama dışı bırakılan klasör", f"{len(scan_result.skipped_dirs)}", p["dim"]),
            ("Tarama dışı gizli / sistem dosyası", f"{len(scan_result.skipped_names)}", p["dim"]),
        ]

        for label_text, val_text, val_color in rows:
            row_w = QWidget()
            row_w.setStyleSheet(f"background-color: {p['surface']};")
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)

            lbl_k = QLabel(label_text)
            lbl_k.setFont(QFont("Segoe UI", 10))
            lbl_k.setStyleSheet(f"background-color: {p['surface']}; color: {p['text']}; border: none;")

            lbl_v = QLabel(val_text)
            lbl_v.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_v.setStyleSheet(f"background-color: {p['surface']}; color: {val_color}; border: none;")

            row_l.addWidget(lbl_k, 1)
            row_l.addWidget(lbl_v)
            card_layout.addWidget(row_w)

        root.addWidget(summary_card)

        # Bilgilendirme notları
        notes: list[str] = [
            "Alt klasörler taranmaz; yalnızca masaüstünün üst düzeyindeki dosyalar işlenir."
        ]
        if scan_result.scan_subfolders_note:
            notes.append(scan_result.scan_subfolders_note)
        if getattr(scan_result, "positions_simulated", True):
            notes.append(
                "Masaüstü simge konumları bu sistemde doğrudan okunamadığından "
                "animasyon için simüle edilmiş ızgara konumları kullanılacaktır."
            )

        notes_frame = QFrame()
        notes_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 6px;
            }}
        """)
        notes_layout = QVBoxLayout(notes_frame)
        notes_layout.setContentsMargins(12, 10, 12, 10)
        notes_layout.setSpacing(4)
        for note_text in notes:
            lbl_note = QLabel(f"Not: {note_text}")
            lbl_note.setWordWrap(True)
            lbl_note.setFont(QFont("Segoe UI", 9))
            lbl_note.setStyleSheet(
                f"background-color: {p['surface']}; color: {p['muted']}; border: none;"
            )
            notes_layout.addWidget(lbl_note)
        root.addWidget(notes_frame)

        # Kalıcı silme uyarısı (yalnızca delete_count > 0 ise)
        self._chk_confirm_delete: Optional[QCheckBox] = None
        if delete_count > 0:
            warn_frame = QFrame()
            warn_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {p['warn_bg']};
                    border: 1px solid {p['warn_border']};
                    border-radius: 8px;
                }}
            """)
            warn_layout = QVBoxLayout(warn_frame)
            warn_layout.setContentsMargins(14, 12, 14, 12)
            warn_layout.setSpacing(8)

            lbl_warn = QLabel(
                f"UYARI: {delete_count} dosya kalıcı olarak silinecek! "
                "Bu işlem geri alınamaz ve dosyalar Geri Dönüşüm Kutusu'na taşınmaz."
            )
            lbl_warn.setWordWrap(True)
            lbl_warn.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl_warn.setStyleSheet(
                f"background-color: {p['warn_bg']}; color: {p['warn_text']}; border: none;"
            )
            warn_layout.addWidget(lbl_warn)

            self._chk_confirm_delete = QCheckBox("Kalıcı silme işlemini onaylıyorum")
            self._chk_confirm_delete.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._chk_confirm_delete.setStyleSheet(f"""
                QCheckBox {{
                    background-color: {p['warn_bg']};
                    color: {p['text']};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid {p['warn_border']};
                    border-radius: 3px;
                    background-color: {p['bg']};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {p['warn_border']};
                    border: 1px solid {p['warn_border']};
                }}
            """)
            warn_layout.addWidget(self._chk_confirm_delete)
            root.addWidget(warn_frame)

        # Alt butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setMinimumWidth(100)
        btn_cancel.setFont(QFont("Segoe UI", 10))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['hover']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover   {{ background-color: {p['pressed']}; }}
            QPushButton:pressed {{ background-color: {p['surface']}; }}
        """)
        btn_cancel.clicked.connect(self.reject)

        self._btn_start = QPushButton("Başlat")
        self._btn_start.setFixedHeight(36)
        self._btn_start.setMinimumWidth(120)
        self._btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['toolbar_start_bg']};
                color: {p['toolbar_start_fg']};
                border: none;
                border-radius: 6px;
                padding: 0 18px;
            }}
            QPushButton:hover   {{ background-color: {p['toolbar_start_hv']}; }}
            QPushButton:pressed {{ background-color: {p['toolbar_start_pr']}; }}
            QPushButton:disabled {{
                background-color: {p['disabled_bg']};
                color: {p['disabled_fg']};
            }}
        """)
        self._btn_start.clicked.connect(self.accept)

        if self._chk_confirm_delete is not None:
            self._btn_start.setEnabled(False)
            self._chk_confirm_delete.toggled.connect(self._btn_start.setEnabled)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(self._btn_start)
        root.addLayout(btn_row)


# ---------------------------------------------------------------------------
# Orkestratör
# ---------------------------------------------------------------------------

class Controller(QObject):
    """
    Tüm bileşenleri koordine eden ince katman.

    Akış
    ----
    __init__  -> SettingsDialog aç (uygulama bekler)
    _on_startup_settings_closed -> robot (idle, %0 CPU) + kontrol paneli göster
    btn_start -> ScanWorkerThread -> ön doğrulama & onay -> animasyon + FileWorkerThread -> ReportDialog
    """

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._app.aboutToQuit.connect(self._on_app_quit)

        self._raw_scan:    Optional[ScanResult]   = None
        self._result:      Optional[ScanResult]   = None
        self._target_root: pathlib.Path           = config.get_organized_root()
        self._report:      Optional[ReportDialog] = None
        self._settings_dlg: Optional[SettingsDialog] = None

        self._start_time:    float = 0.0
        self._is_scanning:   bool  = False
        self._is_running:    bool  = False
        self._is_cancelling: bool  = False
        self._quitting:      bool  = False

        # Eşzamanlılık & sonuç durumu
        self._animation_done:      bool             = False
        self._worker_done:         bool             = False
        self._pre_skipped_results: list[FileResult] = []
        self._results_list:        list[FileResult] = []
        self._remaining_cancelled: list[FileResult] = []
        self._sent_indices:        set[int]         = set()

        # Arka plan iş parçacıkları (GC koruması)
        self._scan_worker: Optional[ScanWorkerThread] = None
        self._worker:      Optional[FileWorkerThread] = None

        # Robot overlay -- henüz gizli; ayarlar kapanınca gösterilecek
        self._robot = RobotOverlay()

        # Kontrol paneli -- henüz gizli
        self._panel = ControlPanel(theme=config.get_settings().theme)
        self._panel.start_clicked.connect(self._start_scan)
        self._panel.cancel_clicked.connect(self._cancel_cleaning)
        self._panel.settings_clicked.connect(self._open_settings)
        self._panel.quit_clicked.connect(self._quit)

        # Robot sinyalleri
        self._robot.settings_requested.connect(self._open_settings)
        self._robot.target_reached.connect(self._on_target_reached)
        self._robot.all_targets_done.connect(self._on_animation_done)
        self._robot.cancel_requested.connect(self._cancel_cleaning)

        # Başlangıçta SettingsDialog'u aç
        QTimer.singleShot(200, self._open_startup_settings)

    # ------------------------------------------------------------------
    # Başlangıç: ayarlar penceresi
    # ------------------------------------------------------------------

    def _open_startup_settings(self) -> None:
        """Uygulama ilk açıldığında ayarları göster."""
        dlg = SettingsDialog(config.get_settings())
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.theme_preview_requested.connect(self._on_theme_preview)
        dlg.rejected.connect(self._on_settings_rejected)
        dlg.finished.connect(self._on_startup_settings_closed)
        self._settings_dlg = dlg
        dlg.show()

    def _on_startup_settings_closed(self) -> None:
        """Ayarlar penceresi kapandı -> robot (boşta, %0 CPU) + kontrol panelini göster."""
        self._robot.set_idle("Hazır -- Başlamak için Süpür butonuna tıklayın.")
        self._robot.show()
        self._panel.show()

    # ------------------------------------------------------------------
    # Çalışma sırasında ayarlar & canlı tema/hız güncelleme
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        """Çalışma sırasında ayarlar butonuna basıldı."""
        if self._is_running or self._is_scanning:
            return
        if self._settings_dlg is not None and self._settings_dlg.isVisible():
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        self._settings_dlg = SettingsDialog(config.get_settings())
        self._settings_dlg.settings_saved.connect(self._on_settings_saved)
        self._settings_dlg.theme_preview_requested.connect(self._on_theme_preview)
        self._settings_dlg.rejected.connect(self._on_settings_rejected)
        self._settings_dlg.show()

    def _on_theme_preview(self, theme_name: str) -> None:
        self._panel.apply_theme(theme_name)
        self._robot.set_theme(theme_name)

    def _on_settings_rejected(self) -> None:
        saved_theme = config.get_settings().theme
        self._panel.apply_theme(saved_theme)
        self._robot.set_theme(saved_theme)

    def _on_settings_saved(self, new_settings: config.AppSettings) -> None:
        self._panel.apply_theme(new_settings.theme)
        self._robot.set_theme(new_settings.theme)
        self._robot.set_speed(new_settings.robot_speed)
        self._robot.set_status("Ayarlar kaydedildi!")

    # ------------------------------------------------------------------
    # Arka plan tarama & doğrulama & başlatma
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._is_running or self._is_scanning:
            return

        self._is_scanning = True
        self._panel.set_scanning_state(True)
        self._robot.set_status("Masaüstü taranıyor...")

        self._scan_worker = ScanWorkerThread()
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        if hasattr(self._scan_worker, "status_update"):
            self._scan_worker.status_update.connect(self._robot.set_status)
        self._scan_worker.start()

    def _on_scan_finished(self, raw_result: ScanResult) -> None:
        self._is_scanning = False
        self._panel.set_scanning_state(False)
        if self._quitting:
            return

        self._raw_scan = raw_result
        settings = config.get_settings()

        # Kategori kurallarına göre aktif vs. atlananları ayır
        active = []
        pre_skipped: list[FileResult] = []
        for item in raw_result.items:
            rule = settings.category_rules.get(item.category.name, config.ACTION_SKIP)
            if rule == config.ACTION_SKIP or rule not in (
                config.ACTION_MOVE, config.ACTION_TRASH, config.ACTION_DELETE
            ):
                pre_skipped.append(
                    FileResult(
                        item=item,
                        status=FileStatus.SKIPPED,
                        error_msg="Kategori kuralı gereği atlandı",
                    )
                )
            else:
                active.append(item)

        if raw_result.total == 0:
            self._robot.set_idle("Temizlenecek dosya yok.")
            return

        if not active:
            self._robot.set_idle(
                "Tüm dosyalar kategori kuralları gereği atlandı -- işlem yapılmadı."
            )
            return

        # Hedef klasör ön doğrulaması (ACTION_MOVE veya fallback çöp gerekiyorsa)
        needs_target_dir = any(
            settings.category_rules.get(item.category.name, config.ACTION_SKIP) == config.ACTION_MOVE
            or (
                settings.category_rules.get(item.category.name, config.ACTION_SKIP) == config.ACTION_TRASH
                and not HAS_SEND2TRASH
            )
            or (
                settings.category_rules.get(item.category.name, config.ACTION_SKIP) == config.ACTION_DELETE
                and not settings.permanent_delete_enabled
                and not HAS_SEND2TRASH
            )
            for item in active
        )

        try:
            target_root = settings.get_target_root()
        except ValueError as exc:
            if needs_target_dir:
                self._show_critical(
                    "Geçersiz Hedef Klasör",
                    f"Hedef klasör doğrulanamadı:\n{exc}\n\n"
                    "Lütfen Ayarlar'dan geçerli bir hedef klasör seçin.",
                )
                self._robot.set_idle("Hazır -- Başlamak için Süpür butonuna tıklayın.")
                return
            target_root = config.get_organized_root()

        if needs_target_dir and not FileWorkerThread._check_writable(target_root):
            self._show_critical(
                "Yazma İzni Hatası",
                f"Hedef klasöre yazma izni yok:\n{target_root}\n\n"
                "Lütfen Ayarlar'dan yazılabilir bir klasör seçin.",
            )
            self._robot.set_idle("Hazır -- Başlamak için Süpür butonuna tıklayın.")
            return

        self._target_root = target_root

        # Onay diyaloğu için gerçek eylem sayılarını hesapla
        move_count   = 0
        trash_count  = 0
        delete_count = 0
        skip_count   = len(pre_skipped)

        for item in active:
            rule = settings.category_rules.get(item.category.name, config.ACTION_SKIP)
            if rule == config.ACTION_MOVE:
                move_count += 1
            elif rule == config.ACTION_TRASH:
                trash_count += 1
            elif rule == config.ACTION_DELETE:
                if settings.permanent_delete_enabled:
                    delete_count += 1
                else:
                    trash_count += 1

        # Kalıcı silme varsa confirm_before_start False olsa bile onay zorunludur
        if settings.confirm_before_start or delete_count > 0:
            dlg = _ConfirmCleanDialog(
                move_count=move_count,
                trash_count=trash_count,
                delete_count=delete_count,
                skip_count=skip_count,
                target_root=target_root,
                scan_result=raw_result,
                theme=settings.theme,
                parent=None,
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self._robot.set_idle("Hazır -- Başlamak için Süpür butonuna tıklayın.")
                return

        # Temizliği başlat
        self._result = ScanResult(
            items=active,
            skipped_dirs=raw_result.skipped_dirs,
            skipped_names=raw_result.skipped_names,
            desktop_path=raw_result.desktop_path,
            scan_subfolders_note=raw_result.scan_subfolders_note,
            positions_simulated=getattr(raw_result, "positions_simulated", True),
        )
        self._pre_skipped_results = pre_skipped
        self._results_list        = []
        self._remaining_cancelled = []
        self._sent_indices        = set()
        self._animation_done      = False
        self._worker_done         = False
        self._is_cancelling       = False
        self._is_running          = True

        self._panel.set_running_state(True)
        self._robot.set_status(f"{len(active)} dosya bulundu -- başlıyor!")

        # Streaming modda tek FileWorkerThread oluştur
        self._worker = FileWorkerThread(
            items=[],
            settings=settings,
            streaming=True,
            total_hint=len(active),
        )
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_worker_all_done)
        self._worker.status_update.connect(self._robot.set_status)
        self._worker.start()

        positions = [item.screen_pos for item in active]
        labels    = [item.path.name  for item in active]
        self._start_time = time.monotonic()
        self._robot.set_targets(positions, labels)

    # ------------------------------------------------------------------
    # Sinyal işleyiciler & iptal
    # ------------------------------------------------------------------

    def _on_target_reached(self, idx: int) -> None:
        """Robot hedefe ulaştı; o indeksteki dosyayı işleme kuyruğuna ekle."""
        if self._is_cancelling or self._result is None or self._worker is None:
            return
        items = self._result.items
        if 0 <= idx < len(items) and idx not in self._sent_indices:
            self._sent_indices.add(idx)
            self._worker.enqueue_item(items[idx])

    def _on_file_done(self, result: FileResult) -> None:
        """Tek bir dosya işlendi."""
        self._results_list.append(result)

    def _on_worker_all_done(self, results: list[FileResult]) -> None:
        """Worker tüm dosyaları tamamladı."""
        self._worker_done  = True
        self._results_list = list(results)
        self._maybe_show_report()

    def _on_animation_done(self, done_count: int) -> None:
        """Animasyon tüm hedefleri tamamladı."""
        if self._is_cancelling:
            return
        if self._worker is not None:
            self._worker.finish()
        self._animation_done = True
        self._maybe_show_report()

    def _cancel_cleaning(self) -> None:
        """Kullanıcı İptal veya ESC'ye bastı; kalan dosyaları CANCELLED işaretle."""
        if not self._is_running or self._is_cancelling:
            return
        self._is_cancelling = True
        self._panel.btn_cancel.setEnabled(False)

        self._robot.cancel()
        if self._worker is not None:
            self._worker.cancel()

        if self._result is not None:
            self._remaining_cancelled = [
                FileResult(
                    item=item,
                    status=FileStatus.CANCELLED,
                    error_msg="Kullanıcı tarafından iptal edildi",
                )
                for idx, item in enumerate(self._result.items)
                if idx not in self._sent_indices
            ]

        self._animation_done = True
        self._maybe_show_report()

    def _maybe_show_report(self) -> None:
        """Hem animasyon hem worker tamamlandığında raporu göster."""
        if not self._is_running:
            return
        if not (self._animation_done and self._worker_done):
            return

        elapsed          = time.monotonic() - self._start_time
        self._is_running = False
        self._panel.set_running_state(False)

        self._robot.set_idle()
        self._robot.hide()
        self._panel.hide()

        all_results = (
            self._pre_skipped_results
            + self._results_list
            + self._remaining_cancelled
        )

        self._report = ReportDialog(
            all_results,
            elapsed,
            self._target_root,
            scan_result=self._raw_scan,
            theme=config.get_settings().theme,
        )
        self._report.closed.connect(self._quit)
        self._report.show()

    # ------------------------------------------------------------------
    # Yardımcı: opak tema uyumlu hata penceresi
    # ------------------------------------------------------------------

    @staticmethod
    def _show_critical(title: str, message: str) -> None:
        p = config.get_theme_palette()
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setWindowIcon(QIcon(str(config.get_asset_path("robot_supurge.png"))))
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {p['bg']};
                color: {p['text']};
            }}
            QLabel {{
                background-color: {p['bg']};
                color: {p['text']};
            }}
            QPushButton {{
                background-color: {p['hover']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 5px;
                padding: 6px 18px;
                min-width: 70px;
            }}
            QPushButton:hover   {{ background-color: {p['pressed']}; }}
            QPushButton:pressed {{ background-color: {p['surface']}; }}
        """)
        box.exec()

    # ------------------------------------------------------------------
    # Güvenli kapatma & thread temizliği
    # ------------------------------------------------------------------

    def _cleanup_threads(self) -> None:
        """Tüm arka plan iş parçacıklarını güvenli şekilde sonlandır."""
        self._robot.set_idle()

        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()

        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._scan_worker.stop()

    def _on_app_quit(self) -> None:
        self._quitting = True
        self._cleanup_threads()

    def _quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self._cleanup_threads()
        self._app.quit()


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Masaüstü Robot Süpürge")
    app.setWindowIcon(QIcon(str(config.get_asset_path("robot_supurge.png"))))
    app.setQuitOnLastWindowClosed(False)   # rapor kapanınca biz çıkarız

    controller = Controller(app)   # noqa: F841 -- referansı canlı tut

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
