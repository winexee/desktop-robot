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

from PyQt6.QtCore import Qt, QTimer, QObject, QRect, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
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
# Sabitler (opak tema renkleri)
# ---------------------------------------------------------------------------

_BG_DARK        = "#1e1f22"
_BG_CARD        = "#2b2d31"
_BORDER_COLOR   = "#3f4147"
_TEXT_PRIMARY   = "#dcddde"
_TEXT_SECONDARY = "#b5bac1"
_TEXT_MUTED     = "#949ba4"
_ACCENT_BLUE    = "#5865f2"
_ACCENT_GREEN   = "#57f287"
_WARN_BG        = "#3b1f23"
_WARN_BORDER    = "#fe4c43"
_WARN_TEXT      = "#ffb3b0"


# ---------------------------------------------------------------------------
# Yüzen Kontrol Paneli (> Süpür | İptal | Ayarlar | Kapat)
# ---------------------------------------------------------------------------

class ControlPanel(QWidget):
    """Ekranın sağ üst köşesinde yüzen kontrol şeridi."""

    start_clicked    = pyqtSignal()
    cancel_clicked   = pyqtSignal()
    settings_clicked = pyqtSignal()
    quit_clicked     = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # WA_TranslucentBackground yalnızca bu yüzen kontrol şeridinde kullanılır
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # -- > Süpür -----------------------------------------------------
        self.btn_start = QPushButton("> Süpür")
        self.btn_start.setFixedHeight(42)
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background: #28b464;
                color: #ffffff;
                border: 1px solid #50dc8c;
                border-radius: 21px;
                padding: 0 18px;
            }
            QPushButton:hover   { background: #37cd78; }
            QPushButton:pressed { background: #1e9655; }
            QPushButton:disabled {
                background: #3c4155;
                color: #969baf;
                border: 1px solid #50556e;
            }
        """)

        # -- İptal (yalnızca çalışma sırasında görünür/aktif) ------------
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setFixedHeight(42)
        self.btn_cancel.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #d83c3e;
                color: #ffffff;
                border: 1px solid #f06e6e;
                border-radius: 21px;
                padding: 0 16px;
            }
            QPushButton:hover   { background: #e84e50; }
            QPushButton:pressed { background: #b52e30; }
            QPushButton:disabled {
                background: #3c4155;
                color: #969baf;
                border: 1px solid #50556e;
            }
        """)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.hide()

        # -- Ayarlar -----------------------------------------------------
        self.btn_settings = QPushButton("Ayarlar")
        self.btn_settings.setFixedHeight(42)
        self.btn_settings.setFont(QFont("Segoe UI", 10))
        self.btn_settings.setToolTip("Ayarları Aç")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background: #161a2a;
                color: #b4c3eb;
                border: 1px solid #465078;
                border-radius: 21px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #3778d7;
                color: #ffffff;
            }
            QPushButton:pressed { background: #2b5ea8; }
            QPushButton:disabled {
                background: #2b2d31;
                color: #72767d;
                border: 1px solid #3f4147;
            }
        """)

        # -- Kapat -------------------------------------------------------
        self.btn_quit = QPushButton("Kapat")
        self.btn_quit.setFixedHeight(42)
        self.btn_quit.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_quit.setToolTip("Uygulamayı Kapat")
        self.btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quit.setStyleSheet("""
            QPushButton {
                background: #161a2a;
                color: #f06e6e;
                border: 1px solid #5a323c;
                border-radius: 21px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #dc3c3c;
                color: #ffffff;
            }
            QPushButton:pressed { background: #b02828; }
        """)

        for btn in (self.btn_start, self.btn_cancel, self.btn_settings, self.btn_quit):
            layout.addWidget(btn)

        self.btn_start.clicked.connect(self.start_clicked)
        self.btn_cancel.clicked.connect(self.cancel_clicked)
        self.btn_settings.clicked.connect(self.settings_clicked)
        self.btn_quit.clicked.connect(self.quit_clicked)

        self._reposition()

    def _reposition(self) -> None:
        """Boyutu güncelleyip sağ üst köşeye güvenli şekilde yerleştir."""
        self.adjustSize()
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
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("> Süpür")
            self.btn_settings.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.hide()
        self._reposition()

    def set_running_state(self, running: bool) -> None:
        """Temizlik çalışması sırasında buton durumlarını güncelle."""
        if running:
            self.btn_start.setEnabled(False)
            self.btn_start.setText("Süpürülüyor...")
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.show()
            self.btn_settings.setEnabled(False)
        else:
            self.btn_start.setEnabled(True)
            self.btn_start.setText("> Süpür")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.hide()
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
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._delete_count = delete_count
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
        self.setWindowTitle("Temizlik Onayı")
        self.setMinimumWidth(500)
        self.setWindowIcon(QIcon(str(config.get_asset_path("robot_supurge.png"))))
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_BG_DARK};
                color: {_TEXT_PRIMARY};
            }}
            QLabel {{
                background-color: {_BG_DARK};
                color: {_TEXT_PRIMARY};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Başlık
        title = QLabel("Temizlik İşlemi Özeti")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"background-color: {_BG_DARK}; color: {_TEXT_PRIMARY};")
        root.addWidget(title)

        subtitle = QLabel(
            f"Hedef klasör: {target_root}"
        )
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"background-color: {_BG_DARK}; color: {_TEXT_SECONDARY};")
        root.addWidget(subtitle)

        # Özet kartı
        summary_card = QFrame()
        summary_card.setStyleSheet(f"""
            QFrame {{
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER_COLOR};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(summary_card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        rows = [
            ("Taşınacak dosya", f"{move_count}", _ACCENT_GREEN),
            ("Çöp kutusuna gönderilecek", f"{trash_count}", "#7289da"),
            ("Kalıcı olarak silinecek", f"{delete_count}", _WARN_BORDER if delete_count > 0 else _TEXT_SECONDARY),
            ("Atlanacak (kategori kuralı)", f"{skip_count}", _TEXT_SECONDARY),
            ("Tarama dışı bırakılan klasör", f"{len(scan_result.skipped_dirs)}", _TEXT_MUTED),
            ("Tarama dışı gizli / sistem dosyası", f"{len(scan_result.skipped_names)}", _TEXT_MUTED),
        ]

        for label_text, val_text, val_color in rows:
            row_w = QWidget()
            row_w.setStyleSheet(f"background-color: {_BG_CARD};")
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)

            lbl_k = QLabel(label_text)
            lbl_k.setFont(QFont("Segoe UI", 10))
            lbl_k.setStyleSheet(f"background-color: {_BG_CARD}; color: {_TEXT_PRIMARY}; border: none;")

            lbl_v = QLabel(val_text)
            lbl_v.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_v.setStyleSheet(f"background-color: {_BG_CARD}; color: {val_color}; border: none;")

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
                background-color: {_BG_CARD};
                border: 1px solid {_BORDER_COLOR};
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
                f"background-color: {_BG_CARD}; color: {_TEXT_SECONDARY}; border: none;"
            )
            notes_layout.addWidget(lbl_note)
        root.addWidget(notes_frame)

        # Kalıcı silme uyarısı (yalnızca delete_count > 0 ise)
        self._chk_confirm_delete: Optional[QCheckBox] = None
        if delete_count > 0:
            warn_frame = QFrame()
            warn_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {_WARN_BG};
                    border: 1px solid {_WARN_BORDER};
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
                f"background-color: {_WARN_BG}; color: {_WARN_TEXT}; border: none;"
            )
            warn_layout.addWidget(lbl_warn)

            self._chk_confirm_delete = QCheckBox("Kalıcı silme işlemini onaylıyorum")
            self._chk_confirm_delete.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._chk_confirm_delete.setStyleSheet(f"""
                QCheckBox {{
                    background-color: {_WARN_BG};
                    color: {_TEXT_PRIMARY};
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid {_WARN_BORDER};
                    border-radius: 3px;
                    background-color: {_BG_DARK};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {_WARN_BORDER};
                    border: 1px solid {_WARN_BORDER};
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
                background-color: #35373c;
                color: {_TEXT_PRIMARY};
                border: 1px solid {_BORDER_COLOR};
                border-radius: 6px;
                padding: 0 16px;
            }}
            QPushButton:hover   {{ background-color: #40444b; }}
            QPushButton:pressed {{ background-color: #2b2d31; }}
        """)
        btn_cancel.clicked.connect(self.reject)

        self._btn_start = QPushButton("Başlat")
        self._btn_start.setFixedHeight(36)
        self._btn_start.setMinimumWidth(120)
        self._btn_start.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: #28b464;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 0 18px;
            }}
            QPushButton:hover   {{ background-color: #37cd78; }}
            QPushButton:pressed {{ background-color: #1e9655; }}
            QPushButton:disabled {{
                background-color: #35373c;
                color: #72767d;
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
        self._panel = ControlPanel()
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
        dlg.finished.connect(self._on_startup_settings_closed)
        self._settings_dlg = dlg
        dlg.show()

    def _on_startup_settings_closed(self) -> None:
        """Ayarlar penceresi kapandı -> robot (boşta, %0 CPU) + kontrol panelini göster."""
        self._robot.set_idle("Hazır -- Başlamak için Süpür butonuna tıklayın.")
        self._robot.show()
        self._panel.show()

    # ------------------------------------------------------------------
    # Çalışma sırasında ayarlar
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
        self._settings_dlg.show()

    def _on_settings_saved(self, new_settings: config.AppSettings) -> None:
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
        )
        self._report.closed.connect(self._quit)
        self._report.show()

    # ------------------------------------------------------------------
    # Yardımcı: opak koyu hata penceresi
    # ------------------------------------------------------------------

    @staticmethod
    def _show_critical(title: str, message: str) -> None:
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setWindowIcon(QIcon(str(config.get_asset_path("robot_supurge.png"))))
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {_BG_DARK};
                color: {_TEXT_PRIMARY};
            }}
            QLabel {{
                background-color: {_BG_DARK};
                color: {_TEXT_PRIMARY};
            }}
            QPushButton {{
                background-color: #35373c;
                color: {_TEXT_PRIMARY};
                border: 1px solid {_BORDER_COLOR};
                border-radius: 5px;
                padding: 6px 18px;
                min-width: 70px;
            }}
            QPushButton:hover   {{ background-color: #40444b; }}
            QPushButton:pressed {{ background-color: #2b2d31; }}
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
