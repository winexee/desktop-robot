"""
Masaüstü Robot Süpürge - Temizlik Raporu
========================================
Tüm dosyalar işlendikten sonra gösterilen özet penceresi.

Özellikler
----------
- Özet kartlar (Taşınan, Çöp Kutusu, Kalıcı Silinen, Atlanan, Başarısız)
- Geçen süre ve tarama özeti bilgi satırı
- Üç sekmeli rapor görünümü (Başarılı / Kategoriler / Atlanan ve Hatalar)
- Klasörü Aç ve Kapat butonları (cross-platform)
- Tamamen opak koyu tema arayüzü
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont, QIcon, QShowEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
from file_mover import FileResult, FileStatus
from file_scanner import ScanResult


# ---------------------------------------------------------------------------
# Stil sabitleri (tamamen opak hex renkler)
# ---------------------------------------------------------------------------

BG_COLOR       = "#1e1f22"
CARD_BG        = "#2b2d31"
CARD_BORDER    = "#3f4147"
ROW_ALT_BG     = "#313338"
SECTION_BG     = "#232428"

COLOR_MOVED    = "#57f287"   # yesil
COLOR_TRASHED  = "#5865f2"   # mor/mavi
COLOR_DELETED  = "#ff9d4d"   # turuncu
COLOR_SKIPPED  = "#b5bac1"   # gri
COLOR_FAILED   = "#fe4c43"   # kirmizi

TEXT_PRIMARY   = "#f2f3f5"
TEXT_BODY      = "#dcddde"
TEXT_SECONDARY = "#b5bac1"
TEXT_DIM       = "#949ba4"

DIALOG_W = 640
DIALOG_H = 720

SUCCESS_STATUSES = frozenset({
    FileStatus.MOVED,
    FileStatus.TRASHED,
    FileStatus.DELETED_PERMANENTLY,
})

PROBLEM_STATUSES = frozenset({
    FileStatus.FAILED,
    FileStatus.CANCELLED,
    FileStatus.SKIPPED,
})


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _get_asset_icon(filename: str) -> QIcon:
    """Varlık dosyasının mutlak yolundan QIcon oluştur."""
    if hasattr(config, "get_asset_path"):
        return QIcon(str(config.get_asset_path(filename)))
    return QIcon(str(Path(__file__).resolve().parent / "assets" / filename))


def open_folder(path: str | Path) -> tuple[bool, str]:
    """
    İşletim sistemine göre dosya yöneticisinde klasörü aç.
    config.open_folder varsa onu kullanır.
    """
    if hasattr(config, "open_folder"):
        return config.open_folder(path)

    target = str(path)
    try:
        if sys.platform == "win32":
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _status_display(
    result: FileResult,
    pal: Optional[dict[str, str]] = None,
) -> tuple[str, str]:
    """FileResult için (gösterim metni, hex renk) döndürür."""
    p = pal or config.get_theme_palette()
    s = result.status
    if s == FileStatus.MOVED:
        return "Taşındı", p["status_moved"]
    if s == FileStatus.TRASHED:
        return "Çöp Kutusu", p["status_trashed"]
    if s == FileStatus.DELETED_PERMANENTLY:
        return "Kalıcı Silindi", p["status_deleted"]
    if s == FileStatus.SKIPPED:
        return "Atlandı", p["status_skipped"]
    if s == FileStatus.FAILED:
        return "Başarısız", p["status_failed"]
    if s == FileStatus.CANCELLED:
        return "İptal Edildi", p["status_failed"]
    return "Bilinmiyor", p["dim"]


def _create_scroll_area(
    pal: Optional[dict[str, str]] = None,
) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    """Opak tema uyumlu standart bir QScrollArea ve içerik yerleşimi oluşturur."""
    p = pal or config.get_theme_palette()
    bg = p["bg"]
    card_bg = p["surface"]
    handle_bg = p["chip_off_bg"]
    handle_hv = p["chip_off_hv"]

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet(f"""
        QScrollArea {{
            background-color: {card_bg};
            border: none;
        }}
        QScrollBar:vertical {{
            background-color: {bg};
            width: 8px;
            border-radius: 4px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {handle_bg};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {handle_hv};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            background-color: {bg};
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background-color: {bg};
        }}
    """)

    container = QWidget()
    container.setObjectName("scrollContainer")
    container.setStyleSheet(f"QWidget#scrollContainer {{ background-color: {card_bg}; }}")

    vbox = QVBoxLayout(container)
    vbox.setContentsMargins(0, 0, 0, 0)
    vbox.setSpacing(0)

    scroll.setWidget(container)
    if scroll.viewport():
        scroll.viewport().setStyleSheet(f"background-color: {card_bg};")

    return scroll, container, vbox


# ---------------------------------------------------------------------------
# Özet kart widget'ı
# ---------------------------------------------------------------------------

class SummaryCard(QFrame):
    """
    Tek bir özet metriği gösteren kart.
    Üst kısımda büyük kalın sayı, alt kısımda küçük etiket.
    """

    def __init__(
        self,
        label: str,
        count: int,
        color: str,
        pal: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        p = pal or config.get_theme_palette()
        card_bg = p["surface"]
        border = p["border"]
        sec_txt = p["muted"]

        self.setObjectName("summaryCard")
        self.setStyleSheet(f"""
            QFrame#summaryCard {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(78)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_count = QLabel(str(count))
        lbl_count.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl_count.setStyleSheet(
            f"color: {color}; background-color: {card_bg}; border: none;"
        )
        lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_name = QLabel(label)
        lbl_name.setFont(QFont("Segoe UI", 9))
        lbl_name.setStyleSheet(
            f"color: {sec_txt}; background-color: {card_bg}; border: none;"
        )
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(lbl_count)
        layout.addWidget(lbl_name)


# ---------------------------------------------------------------------------
# Kategori ilerleme kartı widget'ı
# ---------------------------------------------------------------------------

class CategoryProgressCard(QFrame):
    """
    Kategoriler sekmesi için tek kategori kartı.
    Renkli nokta + kategori adı + 'başarılı / toplam' + QProgressBar.
    """

    def __init__(
        self,
        name: str,
        color: str,
        success_count: int,
        total_count: int,
        pal: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        p = pal or config.get_theme_palette()
        row_bg = p["surface2"]
        border = p["border"]
        bg = p["bg"]

        self.setObjectName("categoryCard")
        self.setStyleSheet(f"""
            QFrame#categoryCard {{
                background-color: {row_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        # QSS ile çizilmiş 10x10 renkli durum noktası
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {color}; border-radius: 5px; border: none;"
        )

        lbl_name = QLabel(name)
        lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_name.setStyleSheet(
            f"color: {p['text']}; background-color: {row_bg}; border: none;"
        )

        lbl_ratio = QLabel(f"{success_count} / {total_count}")
        lbl_ratio.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        lbl_ratio.setStyleSheet(
            f"color: {p['muted']}; background-color: {row_bg}; border: none;"
        )
        lbl_ratio.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top_row.addWidget(dot)
        top_row.addWidget(lbl_name, 1)
        top_row.addWidget(lbl_ratio)

        # İlerleme çubuğu: oran her zaman kendi kategorisinin toplamına göre
        bar = QProgressBar()
        bar.setFixedHeight(10)
        bar.setTextVisible(False)
        bar.setRange(0, max(1, total_count))
        bar.setValue(min(success_count, max(1, total_count)) if total_count > 0 else 0)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

        outer.addLayout(top_row)
        outer.addWidget(bar)


# ---------------------------------------------------------------------------
# Dosya satırı ve bilgi satırı widget'ları
# ---------------------------------------------------------------------------

class FileRow(QWidget):
    """
    Tek bir FileResult sonucunu gösteren satır.
    Sol: dosya adı ve varsa hedef yol/hata mesajı | Sağ: durum etiketi
    """

    def __init__(
        self,
        result: FileResult,
        alt_row: bool = False,
        pal: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        p = pal or config.get_theme_palette()

        bg = p["surface2"] if alt_row else p["surface"]
        self.setObjectName("fileRow")
        self.setStyleSheet(f"QWidget#fileRow {{ background-color: {bg}; }}")
        self.setMinimumHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(2)

        filename = result.item.path.name if result.item and result.item.path else "?"
        lbl_name = QLabel(filename)
        lbl_name.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        lbl_name.setStyleSheet(f"color: {p['text']}; background-color: {bg};")
        lbl_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lbl_name.setWordWrap(False)

        source_tip = str(result.item.path) if result.item and result.item.path else ""
        if result.dest:
            lbl_name.setToolTip(f"{source_tip}\n-> {result.dest}")
        else:
            lbl_name.setToolTip(source_tip)

        left_col.addWidget(lbl_name)

        # Alt satır: hata mesajı veya hedef yolu
        sub_text = ""
        sub_color = p["dim"]
        if result.error_msg:
            sub_text = result.error_msg
            if result.status in (FileStatus.FAILED, FileStatus.CANCELLED):
                sub_color = p["status_failed"]
        elif result.dest is not None:
            sub_text = f"Hedef: {result.dest}"

        if sub_text:
            lbl_sub = QLabel(sub_text)
            lbl_sub.setFont(QFont("Segoe UI", 8))
            lbl_sub.setStyleSheet(f"color: {sub_color}; background-color: {bg};")
            lbl_sub.setWordWrap(True)
            lbl_sub.setToolTip(sub_text)
            left_col.addWidget(lbl_sub)

        status_text, status_color = _status_display(result, p)
        lbl_status = QLabel(status_text)
        lbl_status.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_status.setStyleSheet(f"color: {status_color}; background-color: {bg};")
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_status.setMinimumWidth(90)

        layout.addLayout(left_col, 1)
        layout.addWidget(lbl_status, 0, Qt.AlignmentFlag.AlignTop)


class _SimpleInfoRow(QWidget):
    """Atlanan klasör veya gizli/sistem dosyası satırı."""

    def __init__(
        self,
        title: str,
        badge: str,
        tooltip: str = "",
        alt_row: bool = False,
        pal: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        p = pal or config.get_theme_palette()

        bg = p["surface2"] if alt_row else p["surface"]
        self.setObjectName("infoRow")
        self.setStyleSheet(f"QWidget#infoRow {{ background-color: {bg}; }}")
        self.setMinimumHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Segoe UI", 9))
        lbl_title.setStyleSheet(f"color: {p['text_body']}; background-color: {bg};")
        lbl_title.setWordWrap(False)
        if tooltip:
            lbl_title.setToolTip(tooltip)

        lbl_badge = QLabel(badge)
        lbl_badge.setFont(QFont("Segoe UI", 8))
        lbl_badge.setStyleSheet(f"color: {p['dim']}; background-color: {bg};")
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(lbl_title, 1)
        layout.addWidget(lbl_badge)


class _SectionHeader(QWidget):
    """Liste içi bölüm başlığı."""

    def __init__(
        self,
        text: str,
        pal: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        p = pal or config.get_theme_palette()
        sec_bg = p["section"]
        border = p["border"]

        self.setObjectName("sectionHeader")
        self.setStyleSheet(
            f"QWidget#sectionHeader {{ background-color: {sec_bg}; "
            f"border-top: 1px solid {border}; border-bottom: 1px solid {border}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {p['muted']}; background-color: {sec_bg};")
        layout.addWidget(lbl)


# ---------------------------------------------------------------------------
# Ana rapor penceresi
# ---------------------------------------------------------------------------

class ReportDialog(QDialog):
    """
    Tüm dosyalar işlendikten sonra gösterilen özet penceresi.

    Kullanım
    --------
        dialog = ReportDialog(results, elapsed_seconds, target_root, scan_result=scan)
        dialog.exec()
    """

    closed = pyqtSignal()

    def __init__(
        self,
        results: list[FileResult],
        elapsed: float,
        target_root: Path,
        scan_result: Optional[ScanResult] = None,
        theme: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._results = list(results)
        self._elapsed = elapsed
        self._target_root = (
            Path(target_root)
            if target_root is not None
            else config.get_organized_root()
        )
        self._scan_result = scan_result
        self._pal = config.get_theme_palette(theme)
        self._closed_emitted = False

        self._setup_window()
        self._build_ui()

    # ------------------------------------------------------------------
    # Pencere ayarları ve kapatma sinyali koruması
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        p = self._pal
        self.setWindowTitle("Temizlik Raporu")
        self.setMinimumSize(600, 660)
        self.resize(DIALOG_W, DIALOG_H)
        self.setWindowIcon(_get_asset_icon("robot_supurge.png"))

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p['bg']};
                color: {p['text_body']};
            }}
            QMessageBox {{
                background-color: {p['bg']};
                color: {p['text']};
            }}
            QMessageBox QLabel {{
                background-color: {p['bg']};
                color: {p['text']};
            }}
            QMessageBox QPushButton {{
                background-color: {p['hover']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 5px;
                padding: 5px 16px;
                min-width: 68px;
            }}
            QMessageBox QPushButton:hover {{ background-color: {p['pressed']}; }}
            QMessageBox QPushButton:pressed {{ background-color: {p['surface']}; }}
        """)

    def _emit_closed_once(self) -> None:
        if not self._closed_emitted:
            self._closed_emitted = True
            self.closed.emit()

    def showEvent(self, event: QShowEvent) -> None:
        self._closed_emitted = False
        super().showEvent(event)

    def accept(self) -> None:
        self._emit_closed_once()
        super().accept()

    def reject(self) -> None:
        self._emit_closed_once()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._emit_closed_once()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        p = self._pal
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(10)

        lbl_title = QLabel("Temizlik Raporu")
        lbl_title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {p['text']}; background-color: {p['bg']};")
        root_layout.addWidget(lbl_title)

        # Üst özet kartları
        root_layout.addLayout(self._build_summary_cards())

        # Süre ve tarama özeti bilgi satırı
        root_layout.addLayout(self._build_info_section())

        # 3 sekmeli detay görünümü
        root_layout.addWidget(self._build_tab_widget(), 1)

        # Alt butonlar
        root_layout.addLayout(self._build_buttons())

    def _build_summary_cards(self) -> QHBoxLayout:
        p = self._pal
        layout = QHBoxLayout()
        layout.setSpacing(8)

        moved_count   = sum(1 for r in self._results if r.status == FileStatus.MOVED)
        trashed_count = sum(1 for r in self._results if r.status == FileStatus.TRASHED)
        deleted_count = sum(1 for r in self._results if r.status == FileStatus.DELETED_PERMANENTLY)
        skipped_count = sum(1 for r in self._results if r.status == FileStatus.SKIPPED)
        failed_count  = sum(
            1 for r in self._results
            if r.status in (FileStatus.FAILED, FileStatus.CANCELLED)
        )

        cards: list[tuple[str, int, str]] = [
            ("Taşınan",      moved_count,   p["status_moved"]),
            ("Çöp Kutusu",   trashed_count, p["status_trashed"]),
        ]
        if deleted_count > 0:
            cards.append(("Kalıcı Silinen", deleted_count, p["status_deleted"]))
        cards.extend([
            ("Atlanan",      skipped_count, p["status_skipped"]),
            ("Başarısız",    failed_count,  p["status_failed"]),
        ])

        for label, count, color in cards:
            layout.addWidget(SummaryCard(label, count, color, pal=p))

        return layout

    def _build_info_section(self) -> QVBoxLayout:
        p = self._pal
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 2, 0, 2)
        vbox.setSpacing(2)

        skipped_dirs_count = (
            len(self._scan_result.skipped_dirs) if self._scan_result else 0
        )
        skipped_names_count = (
            len(self._scan_result.skipped_names) if self._scan_result else 0
        )

        info_text = (
            f"Geçen süre: {self._elapsed:.1f} sn  |  "
            f"Atlanan klasörler: {skipped_dirs_count}  |  "
            f"Atlanan gizli/sistem dosyaları: {skipped_names_count}"
        )
        lbl_info = QLabel(info_text)
        lbl_info.setFont(QFont("Segoe UI", 9))
        lbl_info.setStyleSheet(f"color: {p['muted']}; background-color: {p['bg']};")
        lbl_info.setWordWrap(True)
        vbox.addWidget(lbl_info)

        notes: list[str] = []
        if self._scan_result is not None:
            sub_note = getattr(self._scan_result, "scan_subfolders_note", "")
            if sub_note:
                notes.append(sub_note)
            else:
                notes.append("Alt klasörler taranmaz; yalnızca masaüstü üst düzeyi işlenir.")
            if getattr(self._scan_result, "positions_simulated", False):
                notes.append("Dosya konumları masaüstü ızgarası üzerinden simüle edilmiştir.")

        if notes:
            lbl_notes = QLabel(" | ".join(notes))
            lbl_notes.setFont(QFont("Segoe UI", 8))
            lbl_notes.setStyleSheet(f"color: {p['dim']}; background-color: {p['bg']};")
            lbl_notes.setWordWrap(True)
            vbox.addWidget(lbl_notes)

        return vbox

    # ------------------------------------------------------------------
    # 3 Sekmeli dosya / kategori görünümü
    # ------------------------------------------------------------------

    def _build_tab_widget(self) -> QTabWidget:
        p = self._pal
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget {{
                background-color: {p['bg']};
            }}
            QTabWidget::pane {{
                background-color: {p['surface']};
                border: 1px solid {p['border']};
                border-radius: 6px;
            }}
            QTabBar {{
                background-color: {p['bg']};
            }}
            QTabBar::tab {{
                background-color: {p['section']};
                color: {p['muted']};
                padding: 8px 16px;
                border: 1px solid {p['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }}
            QTabBar::tab:selected {{
                background-color: {p['surface']};
                color: {p['text']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {p['hover']};
                color: {p['text_body']};
            }}
        """)

        success_results = [r for r in self._results if r.status in SUCCESS_STATUSES]
        problem_results = [r for r in self._results if r.status in PROBLEM_STATUSES]

        skipped_dirs = (
            list(self._scan_result.skipped_dirs) if self._scan_result else []
        )
        skipped_names = (
            list(self._scan_result.skipped_names) if self._scan_result else []
        )
        problem_total = len(problem_results) + len(skipped_dirs) + len(skipped_names)

        tab_success = self._build_success_tab(success_results)
        tab_cats, active_cat_count = self._build_categories_tab()
        tab_problem = self._build_problems_tab(
            problem_results, skipped_dirs, skipped_names
        )

        tabs.addTab(tab_success, f"Başarılı ({len(success_results)})")
        tabs.addTab(tab_cats, f"Kategoriler ({active_cat_count})")
        tabs.addTab(tab_problem, f"Atlanan ve Hatalar ({problem_total})")

        return tabs

    def _build_success_tab(self, results: list[FileResult]) -> QScrollArea:
        p = self._pal
        scroll, _container, vbox = _create_scroll_area(p)
        if not results:
            lbl_empty = QLabel("Başarılı işlem yok.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setFont(QFont("Segoe UI", 10))
            lbl_empty.setStyleSheet(
                f"color: {p['dim']}; background-color: {p['surface']}; padding: 24px;"
            )
            vbox.addWidget(lbl_empty)
        else:
            for idx, res in enumerate(results):
                vbox.addWidget(FileRow(res, alt_row=(idx % 2 == 1), pal=p))
        vbox.addStretch()
        return scroll

    def _build_categories_tab(self) -> tuple[QScrollArea, int]:
        p = self._pal
        scroll, _container, vbox = _create_scroll_area(p)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(8)

        by_cat: dict[str, list[FileResult]] = {}
        cat_colors: dict[str, str] = {c.name: c.color for c in config.CATEGORIES}

        for res in self._results:
            if res.item and res.item.category:
                cname = res.item.category.name
                cat_colors.setdefault(cname, res.item.category.color)
                by_cat.setdefault(cname, []).append(res)

        ordered_names = [c.name for c in config.CATEGORIES if c.name in by_cat]
        for cname in by_cat:
            if cname not in ordered_names:
                ordered_names.append(cname)

        if not ordered_names:
            lbl_empty = QLabel("Kategori verisi yok.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setFont(QFont("Segoe UI", 10))
            lbl_empty.setStyleSheet(
                f"color: {p['dim']}; background-color: {p['surface']}; padding: 24px;"
            )
            vbox.addWidget(lbl_empty)
        else:
            for cname in ordered_names:
                items = by_cat[cname]
                cat_total = len(items)
                cat_success = sum(1 for r in items if r.status in SUCCESS_STATUSES)
                color = cat_colors.get(cname, p["muted"])
                vbox.addWidget(
                    CategoryProgressCard(
                        name=cname,
                        color=color,
                        success_count=cat_success,
                        total_count=cat_total,
                        pal=p,
                    )
                )

        vbox.addStretch()
        return scroll, len(ordered_names)

    def _build_problems_tab(
        self,
        problem_results: list[FileResult],
        skipped_dirs: list[Path],
        skipped_names: list[str],
    ) -> QScrollArea:
        p = self._pal
        scroll, _container, vbox = _create_scroll_area(p)

        has_any = bool(problem_results or skipped_dirs or skipped_names)
        if not has_any:
            lbl_empty = QLabel("Atlanan dosya veya hata yok.")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setFont(QFont("Segoe UI", 10))
            lbl_empty.setStyleSheet(
                f"color: {p['dim']}; background-color: {p['surface']}; padding: 24px;"
            )
            vbox.addWidget(lbl_empty)
            vbox.addStretch()
            return scroll

        if problem_results:
            ordered = sorted(
                problem_results,
                key=lambda r: (
                    0 if r.status == FileStatus.FAILED else (
                        1 if r.status == FileStatus.CANCELLED else 2
                    )
                ),
            )
            vbox.addWidget(
                _SectionHeader(f"İşlem Hataları ve Atlanan Dosyalar ({len(ordered)})", pal=p)
            )
            for idx, res in enumerate(ordered):
                vbox.addWidget(FileRow(res, alt_row=(idx % 2 == 1), pal=p))

        if skipped_dirs:
            vbox.addWidget(
                _SectionHeader(f"Atlanan Klasörler ({len(skipped_dirs)})", pal=p)
            )
            for idx, d in enumerate(skipped_dirs):
                vbox.addWidget(
                    _SimpleInfoRow(
                        title=d.name or str(d),
                        badge="Klasör (taranmadı)",
                        tooltip=str(d),
                        alt_row=(idx % 2 == 1),
                        pal=p,
                    )
                )

        if skipped_names:
            vbox.addWidget(
                _SectionHeader(f"Atlanan Gizli / Sistem Dosyaları ({len(skipped_names)})", pal=p)
            )
            for idx, name in enumerate(skipped_names):
                vbox.addWidget(
                    _SimpleInfoRow(
                        title=name,
                        badge="Gizli / sistem dosyası",
                        tooltip=name,
                        alt_row=(idx % 2 == 1),
                        pal=p,
                    )
                )

        vbox.addStretch()
        return scroll

    # ------------------------------------------------------------------
    # Alt butonlar
    # ------------------------------------------------------------------

    def _build_buttons(self) -> QHBoxLayout:
        p = self._pal
        layout = QHBoxLayout()
        layout.setSpacing(10)

        moved_count = sum(1 for r in self._results if r.status == FileStatus.MOVED)
        can_open = moved_count > 0 or self._target_root.exists()

        btn_open = QPushButton("Klasörü Aç")
        btn_open.setFixedHeight(38)
        btn_open.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        btn_open.setEnabled(can_open)
        if not can_open:
            btn_open.setToolTip("Taşınan dosya veya mevcut hedef klasör yok.")
        else:
            btn_open.setToolTip(str(self._target_root))
        btn_open.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['chip_off_bg']};
                color: {p['text']};
                border: 1px solid {p['border']};
                border-radius: 6px;
                padding: 0px 18px;
            }}
            QPushButton:hover {{
                background-color: {p['chip_off_hv']};
                color: {p['text']};
            }}
            QPushButton:pressed {{
                background-color: {p['chip_off_pr']};
            }}
            QPushButton:disabled {{
                background-color: {p['disabled_bg']};
                color: {p['disabled_fg']};
                border: 1px solid {p['border']};
            }}
        """)
        btn_open.clicked.connect(self._on_open_folder)

        btn_close = QPushButton("Kapat")
        btn_close.setFixedHeight(38)
        btn_close.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {p['accent']};
                color: {p['accent_fg']};
                border: 1px solid {p['accent']};
                border-radius: 6px;
                padding: 0px 24px;
            }}
            QPushButton:hover {{
                background-color: {p['accent_hover']};
                border-color: {p['accent_hover']};
            }}
            QPushButton:pressed {{
                background-color: {p['accent_pressed']};
                border-color: {p['accent_pressed']};
            }}
            QPushButton:disabled {{
                background-color: {p['disabled_bg']};
                color: {p['disabled_fg']};
                border-color: {p['border']};
            }}
        """)
        btn_close.clicked.connect(self._on_close)

        layout.addWidget(btn_open)
        layout.addStretch()
        layout.addWidget(btn_close)

        return layout

    # ------------------------------------------------------------------
    # Buton eylemleri
    # ------------------------------------------------------------------

    def _on_open_folder(self) -> None:
        if not self._target_root.exists():
            QMessageBox.warning(
                self,
                "Klasör Bulunamadı",
                f"Hedef klasör mevcut değil:\n{self._target_root}",
            )
            return

        ok, err = open_folder(self._target_root)
        if not ok:
            QMessageBox.warning(
                self,
                "Klasör Açılamadı",
                f"Hedef klasör açılamadı:\n{err}",
            )

    def _on_close(self) -> None:
        self.accept()
