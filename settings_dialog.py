"""
Masaüstü Robot Süpürge - Ayarlar Penceresi
==========================================
Modern çok temalı arayüz: 5 sayfa sidebar + QStackedWidget

Pencere: 820 x 600 (tamamen opak)
Sidebar: 200px
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config
from config import (
    ACTION_DELETE,
    ACTION_MOVE,
    ACTION_SKIP,
    ACTION_TRASH,
    AppSettings,
    CATEGORIES,
    SPEED_FAST,
    SPEED_NORMAL,
    SPEED_SLOW,
    THEME_DARK,
    THEME_LIGHT,
    THEME_MIDNIGHT,
)


# ---------------------------------------------------------------------------
# Boyut sabitleri
# ---------------------------------------------------------------------------

_DW = 820
_DH = 600
_SIDEBAR_W = 200

_PERM_DELETE_DISABLED_TOOLTIP = (
    "Güvenlik sekmesinden Kalıcı Silme seçeneğini etkinleştirin"
)


# ---------------------------------------------------------------------------
# Asset ve klasör açma yardımcıları
# ---------------------------------------------------------------------------

def _get_asset_path(filename: str) -> Path:
    if hasattr(config, "get_asset_path"):
        return Path(config.get_asset_path(filename))
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / filename


def _open_folder(path: Path) -> tuple[bool, str]:
    if hasattr(config, "open_folder"):
        return config.open_folder(path)
    try:
        target = str(path)
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return True, ""
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Dinamik Opak QSS Üreteçleri (sıfır transparent / sıfır rgba)
# ---------------------------------------------------------------------------

def _sidebar_btn_qss(p: dict[str, str]) -> str:
    return f"""
QPushButton {{
    background-color: {p['surface']};
    color: {p['muted']};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 16px;
    font-size: 10pt;
}}
QPushButton:hover:!checked {{
    background-color: {p['hover']};
    color: {p['text']};
}}
QPushButton:pressed {{
    background-color: {p['pressed']};
    color: {p['text']};
}}
QPushButton:checked {{
    background-color: {p['sidebar_active']};
    color: {p['text']};
    border-left: 3px solid {p['accent']};
    padding-left: 13px;
    font-weight: bold;
}}
QPushButton:checked:hover {{
    background-color: {p['sidebar_active_hover']};
    color: {p['text']};
}}
QPushButton:disabled {{
    background-color: {p['surface']};
    color: {p['disabled_fg']};
}}
"""


def _chip_qss(p: dict[str, str]) -> str:
    return f"""
QPushButton {{
    background-color: {p['chip_off_bg']};
    color: {p['chip_off_fg']};
    border: none;
    border-radius: 5px;
    font-size: 9pt;
    font-weight: 600;
    padding: 4px 10px;
    min-width: 60px;
}}
QPushButton:hover:!checked:!disabled {{
    background-color: {p['chip_off_hv']};
    color: {p['text']};
}}
QPushButton:pressed:!disabled {{
    background-color: {p['chip_off_pr']};
    color: {p['text']};
}}
QPushButton:disabled {{
    background-color: {p['disabled_bg']};
    color: {p['disabled_fg']};
}}
QPushButton#chip_move:checked {{
    background-color: {p['green_bg']};
    color: {p['green_fg']};
}}
QPushButton#chip_move:checked:hover {{
    background-color: {p['green_hv']};
    color: {p['green_fg']};
}}
QPushButton#chip_move:checked:pressed {{
    background-color: {p['green_pr']};
    color: {p['green_fg']};
}}
QPushButton#chip_trash:checked {{
    background-color: {p['blue_bg']};
    color: {p['blue_fg']};
}}
QPushButton#chip_trash:checked:hover {{
    background-color: {p['blue_hv']};
    color: {p['blue_fg']};
}}
QPushButton#chip_trash:checked:pressed {{
    background-color: {p['blue_pr']};
    color: {p['blue_fg']};
}}
QPushButton#chip_delete:checked {{
    background-color: {p['red_bg']};
    color: {p['red_fg']};
}}
QPushButton#chip_delete:checked:hover {{
    background-color: {p['red_hv']};
    color: {p['red_fg']};
}}
QPushButton#chip_delete:checked:pressed {{
    background-color: {p['red_pr']};
    color: {p['red_fg']};
}}
QPushButton#chip_delete:disabled {{
    background-color: {p['disabled_bg']};
    color: {p['disabled_fg']};
}}
QPushButton#chip_skip:checked {{
    background-color: {p['skip_bg']};
    color: {p['skip_fg']};
}}
QPushButton#chip_skip:checked:hover {{
    background-color: {p['skip_hv']};
    color: {p['skip_fg']};
}}
QPushButton#chip_skip:checked:pressed {{
    background-color: {p['skip_pr']};
    color: {p['skip_fg']};
}}
QPushButton#chip_accent:checked {{
    background-color: {p['accent']};
    color: {p['accent_fg']};
}}
QPushButton#chip_accent:checked:hover {{
    background-color: {p['accent_hover']};
    color: {p['accent_fg']};
}}
QPushButton#chip_accent:checked:pressed {{
    background-color: {p['accent_pressed']};
    color: {p['accent_fg']};
}}
"""


def _card_qss(p: dict[str, str], obj_name: str = "sec_card") -> str:
    return f"""
QFrame#{obj_name} {{
    background-color: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 8px;
}}
"""


def _scroll_qss(p: dict[str, str]) -> str:
    return f"""
QScrollArea {{
    background-color: {p['bg']};
    border: none;
}}
QScrollBar:vertical {{
    background-color: {p['surface']};
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: {p['chip_off_bg']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {p['chip_off_hv']};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background-color: {p['surface']};
    height: 0px;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background-color: {p['surface']};
}}
"""


def _radio_qss(p: dict[str, str]) -> str:
    return f"""
QRadioButton {{
    color: {p['text']};
    spacing: 10px;
    background-color: {p['bg']};
}}
QRadioButton:hover {{
    color: {p['accent']};
}}
QRadioButton:disabled {{
    color: {p['disabled_fg']};
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid {p['border']};
    background-color: {p['surface']};
}}
QRadioButton::indicator:hover {{
    border: 2px solid {p['accent']};
}}
QRadioButton::indicator:checked {{
    background-color: {p['accent']};
    border: 2px solid {p['accent']};
}}
"""


def _checkbox_qss(p: dict[str, str]) -> str:
    return f"""
QCheckBox {{
    color: {p['text']};
    spacing: 10px;
    background-color: {p['surface']};
    border: none;
}}
QCheckBox:hover {{
    color: {p['accent']};
}}
QCheckBox:disabled {{
    color: {p['disabled_fg']};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid {p['border']};
    background-color: {p['surface2']};
}}
QCheckBox::indicator:hover {{
    border: 2px solid {p['accent']};
}}
QCheckBox::indicator:checked {{
    background-color: {p['accent']};
    border: 2px solid {p['accent']};
}}
QCheckBox::indicator:disabled {{
    background-color: {p['disabled_bg']};
    border: 2px solid {p['border']};
}}
"""


def _action_btn_qss(p: dict[str, str]) -> str:
    return f"""
QPushButton {{
    background-color: {p['accent']};
    color: {p['accent_fg']};
    border: none;
    border-radius: 6px;
    padding: 0 14px;
}}
QPushButton:hover {{
    background-color: {p['accent_hover']};
    color: {p['accent_fg']};
}}
QPushButton:pressed {{
    background-color: {p['accent_pressed']};
    color: {p['accent_fg']};
}}
QPushButton:disabled {{
    background-color: {p['disabled_bg']};
    color: {p['disabled_fg']};
    border: 1px solid {p['border']};
}}
"""


def _line_edit_qss(p: dict[str, str]) -> str:
    return f"""
QLineEdit {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 0 10px;
}}
QLineEdit:focus {{
    border: 1px solid {p['accent']};
}}
QLineEdit:disabled {{
    color: {p['disabled_fg']};
    background-color: {p['input_disabled_bg']};
    border: 1px solid {p['surface']};
}}
"""


def _make_hline(p: dict[str, str]) -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background-color: {p['border']}; border: none;")
    return f


# ---------------------------------------------------------------------------
# Eylem chip grubu (Taşı / Çöp Kutusu / Kalıcı Sil / Atla)
# ---------------------------------------------------------------------------

class _ActionChips(QWidget):
    """
    Dört checkable QPushButton; QButtonGroup ile exclusive.
    action: ACTION_MOVE | ACTION_TRASH | ACTION_DELETE | ACTION_SKIP
    """

    def __init__(
        self,
        action: str,
        permanent_delete_enabled: bool,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {pal['surface']};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        defs = [
            ("chip_move",   "Taşı",       ACTION_MOVE),
            ("chip_trash",  "Çöp Kutusu", ACTION_TRASH),
            ("chip_delete", "Kalıcı Sil", ACTION_DELETE),
            ("chip_skip",   "Atla",       ACTION_SKIP),
        ]

        selected = action if action in {ACTION_MOVE, ACTION_TRASH, ACTION_DELETE, ACTION_SKIP} else ACTION_SKIP
        if not permanent_delete_enabled and selected == ACTION_DELETE:
            selected = ACTION_TRASH

        chip_style = _chip_qss(pal)
        self._map: dict[str, QPushButton] = {}
        for obj_name, label, val in defs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setCheckable(True)
            btn.setChecked(val == selected)
            btn.setStyleSheet(chip_style)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn)
            self._map[val] = btn
            layout.addWidget(btn)

        self.set_permanent_delete_enabled(permanent_delete_enabled)

    def apply_theme(self, pal: dict[str, str]) -> None:
        self.setStyleSheet(f"background-color: {pal['surface']};")
        chip_style = _chip_qss(pal)
        for btn in self._map.values():
            btn.setStyleSheet(chip_style)

    def set_permanent_delete_enabled(self, enabled: bool) -> None:
        btn_del = self._map[ACTION_DELETE]
        btn_del.setEnabled(enabled)
        if enabled:
            btn_del.setToolTip("")
        else:
            btn_del.setToolTip(_PERM_DELETE_DISABLED_TOOLTIP)
            if btn_del.isChecked():
                self._map[ACTION_TRASH].setChecked(True)

    def get_action(self) -> str:
        for val, btn in self._map.items():
            if btn.isChecked():
                return val
        return ACTION_MOVE


# ---------------------------------------------------------------------------
# Tek kategori satırı (kart)
# ---------------------------------------------------------------------------

class _CategoryRow(QFrame):
    """Renkli durum noktası + kategori adı + dört eylem chip."""

    def __init__(
        self,
        category: config.Category,
        action: str,
        permanent_delete_enabled: bool,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("category_row")
        self._cat = category
        self._chips = _ActionChips(action, permanent_delete_enabled, pal, self)

        self.setFixedHeight(56)
        self.setStyleSheet(_card_qss(pal, "category_row"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {category.color}; border-radius: 5px; border: none;"
        )

        self._lbl = QLabel(category.name)
        self._lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._lbl.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )
        self._lbl.setMinimumWidth(105)

        layout.addWidget(dot)
        layout.addWidget(self._lbl)
        layout.addStretch()
        layout.addWidget(self._chips)

    def apply_theme(self, pal: dict[str, str]) -> None:
        self.setStyleSheet(_card_qss(pal, "category_row"))
        self._lbl.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )
        self._chips.apply_theme(pal)

    def set_permanent_delete_enabled(self, enabled: bool) -> None:
        self._chips.set_permanent_delete_enabled(enabled)

    def get_action(self) -> str:
        return self._chips.get_action()

    @property
    def category(self) -> config.Category:
        return self._cat


# ---------------------------------------------------------------------------
# Sayfa 0 — Kategori Kuralları
# ---------------------------------------------------------------------------

class _PageCategories(QWidget):
    def __init__(
        self,
        settings: AppSettings,
        permanent_delete_enabled: bool,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {pal['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 16, 20)
        root.setSpacing(12)

        self._hdr = QLabel("Kategori Kuralları")
        self._hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")

        self._sub = QLabel(
            "Her kategori için robotun ne yapması gerektiğini seçin.\n"
            "Taşı: kategori klasörüne taşı  |  "
            "Çöp Kutusu: geri dönüşüm kutusuna at  |  "
            "Kalıcı Sil: geri döndürülemez sil  |  "
            "Atla: dokunma"
        )
        self._sub.setFont(QFont("Segoe UI", 9))
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._sub.setWordWrap(True)

        self._hline = _make_hline(pal)

        root.addWidget(self._hdr)
        root.addWidget(self._sub)
        root.addWidget(self._hline)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(_scroll_qss(pal))
        self._scroll.viewport().setStyleSheet(f"background-color: {pal['bg']};")

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {pal['bg']};")
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(0, 2, 10, 2)
        inner_lay.setSpacing(6)

        self._rows: list[_CategoryRow] = []
        for cat in CATEGORIES:
            action = settings.category_rules.get(cat.name, ACTION_MOVE)
            row = _CategoryRow(cat, action, permanent_delete_enabled, pal)
            inner_lay.addWidget(row)
            self._rows.append(row)

        inner_lay.addStretch()
        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

    def apply_theme(self, pal: dict[str, str]) -> None:
        self.setStyleSheet(f"background-color: {pal['bg']};")
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._hline.setStyleSheet(f"background-color: {pal['border']}; border: none;")
        self._scroll.setStyleSheet(_scroll_qss(pal))
        self._scroll.viewport().setStyleSheet(f"background-color: {pal['bg']};")
        self._inner.setStyleSheet(f"background-color: {pal['bg']};")
        for row in self._rows:
            row.apply_theme(pal)

    def set_permanent_delete_enabled(self, enabled: bool) -> None:
        for row in self._rows:
            row.set_permanent_delete_enabled(enabled)

    def get_rules(self) -> dict[str, str]:
        return {row.category.name: row.get_action() for row in self._rows}


# ---------------------------------------------------------------------------
# Sayfa 1 — Hedef Klasör
# ---------------------------------------------------------------------------

class _PageTargetFolder(QWidget):
    def __init__(
        self,
        settings: AppSettings,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = pal
        self.setStyleSheet(f"background-color: {pal['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        self._hdr = QLabel("Hedef Klasör")
        self._hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")

        self._sub = QLabel("Taşınan dosyaların yerleştirileceği kök dizini belirleyin.")
        self._sub.setFont(QFont("Segoe UI", 9))
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._sub.setWordWrap(True)

        self._hline1 = _make_hline(pal)
        root.addWidget(self._hdr)
        root.addWidget(self._sub)
        root.addWidget(self._hline1)

        self._rb_auto = self._make_radio(
            "Otomatik (Masaüstü/Düzenlenmiş)",
            settings.custom_target is None,
            pal,
        )

        try:
            auto_path = str(config.get_organized_root())
        except Exception:
            auto_path = str(Path.home() / "Desktop" / "Düzenlenmiş")

        self._auto_hint = QLabel(f"Hedef: {auto_path}")
        self._auto_hint.setFont(QFont("Courier New", 8))
        self._auto_hint.setStyleSheet(
            f"color: {pal['muted']}; padding-left: 28px; background-color: {pal['bg']};"
        )
        self._auto_hint.setWordWrap(True)

        self._hline2 = _make_hline(pal)
        root.addWidget(self._rb_auto)
        root.addWidget(self._auto_hint)
        root.addWidget(self._hline2)

        self._rb_custom = self._make_radio(
            "Özel Klasör",
            settings.custom_target is not None,
            pal,
        )
        root.addWidget(self._rb_custom)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Klasör yolunu seçin veya yazın...")
        self._path_edit.setText(settings.custom_target or "")
        self._path_edit.setEnabled(settings.custom_target is not None)
        self._path_edit.setFixedHeight(36)
        self._path_edit.setFont(QFont("Courier New", 9))
        self._path_edit.setStyleSheet(_line_edit_qss(pal))

        self._btn_browse = self._make_action_btn("Gözat", pal)
        self._btn_browse.setEnabled(settings.custom_target is not None)
        self._btn_browse.clicked.connect(self._browse)

        self._btn_open = self._make_action_btn("Klasörü Aç", pal)
        self._btn_open.setEnabled(settings.custom_target is not None)
        self._btn_open.clicked.connect(self._open_folder)

        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._btn_browse)
        path_row.addWidget(self._btn_open)
        root.addLayout(path_row)

        self._status_lbl = QLabel()
        self._status_lbl.setFont(QFont("Segoe UI", 9))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        root.addWidget(self._status_lbl)

        root.addStretch()

        grp = QButtonGroup(self)
        grp.addButton(self._rb_auto)
        grp.addButton(self._rb_custom)

        self._rb_auto.toggled.connect(self._on_auto_toggled)
        self._path_edit.textChanged.connect(self._validate_path)

        self._validate_path(self._path_edit.text())

    def apply_theme(self, pal: dict[str, str]) -> None:
        self._pal = pal
        self.setStyleSheet(f"background-color: {pal['bg']};")
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._hline1.setStyleSheet(f"background-color: {pal['border']}; border: none;")
        self._hline2.setStyleSheet(f"background-color: {pal['border']}; border: none;")
        self._rb_auto.setStyleSheet(_radio_qss(pal))
        self._rb_custom.setStyleSheet(_radio_qss(pal))
        self._auto_hint.setStyleSheet(
            f"color: {pal['muted']}; padding-left: 28px; background-color: {pal['bg']};"
        )
        self._path_edit.setStyleSheet(_line_edit_qss(pal))
        self._btn_browse.setStyleSheet(_action_btn_qss(pal))
        self._btn_open.setStyleSheet(_action_btn_qss(pal))
        self._validate_path(self._path_edit.text())

    @staticmethod
    def _make_radio(label: str, checked: bool, pal: dict[str, str]) -> QRadioButton:
        rb = QRadioButton(label)
        rb.setChecked(checked)
        rb.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        rb.setStyleSheet(_radio_qss(pal))
        return rb

    @staticmethod
    def _make_action_btn(label: str, pal: dict[str, str]) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(36)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(_action_btn_qss(pal))
        return btn

    def _on_auto_toggled(self, checked: bool) -> None:
        custom = not checked
        self._path_edit.setEnabled(custom)
        self._btn_browse.setEnabled(custom)
        self._btn_open.setEnabled(custom)
        if checked:
            self._status_lbl.setText("")
            self._status_lbl.setStyleSheet(
                f"color: {self._pal['muted']}; background-color: {self._pal['bg']};"
            )
        else:
            self._validate_path(self._path_edit.text())

    def _browse(self) -> None:
        try:
            start = self._path_edit.text().strip() or str(config.get_desktop_path())
        except Exception:
            start = str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Hedef Klasör Seç", start)
        if path:
            self._path_edit.setText(path)

    def _open_folder(self) -> None:
        raw = self._path_edit.text().strip()
        if not raw:
            QMessageBox.warning(
                self,
                "Klasör Bulunamadı",
                "Açılacak geçerli bir klasör yolu giriniz.",
            )
            return
        try:
            p = Path(raw).expanduser().resolve()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Geçersiz Yol",
                f"Klasör yolu çözümlenemedi:\n{exc}",
            )
            return

        if not p.is_dir():
            QMessageBox.warning(
                self,
                "Klasör Bulunamadı",
                f"Belirtilen klasör henüz mevcut değil:\n{p}",
            )
            return

        ok, err = _open_folder(p)
        if not ok:
            QMessageBox.warning(
                self,
                "Klasör Açılamadı",
                f"Klasör dosya yöneticisinde açılamadı:\n{err}",
            )

    @staticmethod
    def _evaluate_path(raw_text: str) -> tuple[bool, str, Optional[Path], bool]:
        """Döner: (gecerli_mi, mesaj, cozumlenmis_path, klasor_mevcut_mu)"""
        cleaned = raw_text.strip()
        if not cleaned:
            return False, "Klasör yolu boş olamaz.", None, False

        if sys.platform != "win32" and len(cleaned) >= 2 and cleaned[1] == ":" and cleaned[0].isalpha():
            return False, "Bu işletim sisteminde sürücü harfi içeren yol geçersizdir.", None, False

        try:
            p_abs = Path(cleaned).expanduser().resolve()
        except Exception as exc:
            return False, f"Geçersiz yol ({exc}).", None, False

        try:
            AppSettings._validate_target_path(p_abs)
            try:
                desktop = config.get_desktop_path().resolve()
            except Exception:
                desktop = None
            if desktop is not None and p_abs == desktop:
                raise ValueError("Hedef klasör masaüstünün kendisi olamaz.")
        except ValueError as exc:
            return False, str(exc), None, False

        if p_abs.exists():
            if not p_abs.is_dir():
                return False, "Seçilen yol bir dosya; klasör olmalı.", None, False
            writable = os.access(p_abs, os.W_OK)
            if sys.platform != "win32":
                writable = writable and os.access(p_abs, os.X_OK)
            if writable:
                return True, "Yazılabilir", p_abs, True
            return False, "Bu klasöre yazma izni yok.", None, True

        ancestor = p_abs.parent
        while ancestor != ancestor.parent and not ancestor.exists():
            ancestor = ancestor.parent

        if not ancestor.exists() or not ancestor.is_dir():
            return False, "Üst dizin geçersiz veya mevcut değil.", None, False

        parent_writable = os.access(ancestor, os.W_OK)
        if sys.platform != "win32":
            parent_writable = parent_writable and os.access(ancestor, os.X_OK)

        if parent_writable:
            return True, "Yazılabilir (klasör otomatik oluşturulacak)", p_abs, False
        return False, "Klasör oluşturulamıyor: üst dizine yazma izni yok.", None, False

    def _validate_path(self, text: str) -> None:
        pal = self._pal
        if not self._rb_custom.isChecked():
            self._status_lbl.setText("")
            self._status_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
            return

        if not text.strip():
            self._status_lbl.setText("Yazılamaz / Geçersiz: Bir klasör yolu seçin veya yazın.")
            self._status_lbl.setStyleSheet(
                f"color: {pal['status_failed']}; background-color: {pal['bg']};"
            )
            return

        ok, msg, _, _ = self._evaluate_path(text)
        if ok:
            self._status_lbl.setText(msg)
            self._status_lbl.setStyleSheet(
                f"color: {pal['status_moved']}; background-color: {pal['bg']};"
            )
        else:
            self._status_lbl.setText(f"Yazılamaz / Geçersiz: {msg}")
            self._status_lbl.setStyleSheet(
                f"color: {pal['status_failed']}; background-color: {pal['bg']};"
            )

    def is_custom_selected(self) -> bool:
        return self._rb_custom.isChecked()

    def validate_for_save(self) -> tuple[bool, str, Optional[str]]:
        if not self._rb_custom.isChecked():
            return True, "", None
        ok, msg, resolved, _ = self._evaluate_path(self._path_edit.text())
        if not ok or resolved is None:
            return False, msg, None
        return True, "", str(resolved)

    def get_custom_target(self) -> Optional[str]:
        if self._rb_custom.isChecked():
            ok, _, resolved, _ = self._evaluate_path(self._path_edit.text())
            if ok and resolved is not None:
                return str(resolved)
            text = self._path_edit.text().strip()
            return text or None
        return None


# ---------------------------------------------------------------------------
# Sayfa 2 — Görünüm (Tema ve Robot Hızı)
# ---------------------------------------------------------------------------

class _PageAppearance(QWidget):
    theme_changed = pyqtSignal(str)

    def __init__(
        self,
        settings: AppSettings,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pal = pal
        self.setStyleSheet(f"background-color: {pal['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        self._hdr = QLabel("Görünüm ve Animasyon")
        self._hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")

        self._sub = QLabel(
            "Arayüz renk temasını ve robot süpürgenin masaüstündeki hareket hızını özelleştirin."
        )
        self._sub.setFont(QFont("Segoe UI", 9))
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._sub.setWordWrap(True)

        self._hline = _make_hline(pal)
        root.addWidget(self._hdr)
        root.addWidget(self._sub)
        root.addWidget(self._hline)

        # Kart 1: Tema Seçimi
        self._card_theme = QFrame()
        self._card_theme.setObjectName("app_card")
        self._card_theme.setStyleSheet(_card_qss(pal, "app_card"))
        ct_lay = QVBoxLayout(self._card_theme)
        ct_lay.setContentsMargins(16, 14, 16, 14)
        ct_lay.setSpacing(10)

        self._t_title = QLabel("Tema Seçimi")
        self._t_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._t_title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        self._t_desc = QLabel(
            "Seçtiğiniz tema ayarlar penceresi, kontrol çubuğu, durum çubuğu ve rapor ekranına anında uygulanır."
        )
        self._t_desc.setFont(QFont("Segoe UI", 9))
        self._t_desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )
        self._t_desc.setWordWrap(True)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)

        current_theme = getattr(settings, "theme", THEME_DARK)
        if current_theme not in config.VALID_THEMES:
            current_theme = THEME_DARK

        theme_defs = [
            (THEME_DARK,     "Koyu (Dark)"),
            (THEME_LIGHT,    "Açık (Light)"),
            (THEME_MIDNIGHT, "Gece Mavisi (Midnight)"),
        ]
        self._theme_btns: dict[str, QPushButton] = {}
        chip_style = _chip_qss(pal)
        for key, label in theme_defs:
            btn = QPushButton(label)
            btn.setObjectName("chip_accent")
            btn.setCheckable(True)
            btn.setChecked(key == current_theme)
            btn.setFixedHeight(36)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(chip_style)
            btn.clicked.connect(lambda _, k=key: self.theme_changed.emit(k))
            self._theme_group.addButton(btn)
            self._theme_btns[key] = btn
            theme_row.addWidget(btn)

        ct_lay.addWidget(self._t_title)
        ct_lay.addWidget(self._t_desc)
        ct_lay.addLayout(theme_row)
        root.addWidget(self._card_theme)

        # Kart 2: Robot Hızı
        self._card_speed = QFrame()
        self._card_speed.setObjectName("speed_card")
        self._card_speed.setStyleSheet(_card_qss(pal, "speed_card"))
        cs_lay = QVBoxLayout(self._card_speed)
        cs_lay.setContentsMargins(16, 14, 16, 14)
        cs_lay.setSpacing(10)

        self._s_title = QLabel("Robot Hızı")
        self._s_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._s_title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        self._s_desc = QLabel(
            "Yavaş: sakin ve takip etmesi kolay  |  "
            "Normal: dengeli ve akıcı  |  "
            "Hızlı: seri temizlik"
        )
        self._s_desc.setFont(QFont("Segoe UI", 9))
        self._s_desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )
        self._s_desc.setWordWrap(True)

        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)
        self._speed_group = QButtonGroup(self)
        self._speed_group.setExclusive(True)

        current_speed = getattr(settings, "robot_speed", SPEED_NORMAL)
        if current_speed not in config.VALID_SPEEDS:
            current_speed = SPEED_NORMAL

        speed_defs = [
            (SPEED_SLOW,   "Yavaş"),
            (SPEED_NORMAL, "Normal"),
            (SPEED_FAST,   "Hızlı"),
        ]
        self._speed_btns: dict[str, QPushButton] = {}
        for key, label in speed_defs:
            btn = QPushButton(label)
            btn.setObjectName("chip_accent")
            btn.setCheckable(True)
            btn.setChecked(key == current_speed)
            btn.setFixedHeight(36)
            btn.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(chip_style)
            self._speed_group.addButton(btn)
            self._speed_btns[key] = btn
            speed_row.addWidget(btn)

        cs_lay.addWidget(self._s_title)
        cs_lay.addWidget(self._s_desc)
        cs_lay.addLayout(speed_row)
        root.addWidget(self._card_speed)

        root.addStretch()

    def apply_theme(self, pal: dict[str, str]) -> None:
        self._pal = pal
        self.setStyleSheet(f"background-color: {pal['bg']};")
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._sub.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._hline.setStyleSheet(f"background-color: {pal['border']}; border: none;")

        self._card_theme.setStyleSheet(_card_qss(pal, "app_card"))
        self._t_title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )
        self._t_desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )

        self._card_speed.setStyleSheet(_card_qss(pal, "speed_card"))
        self._s_title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )
        self._s_desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )

        chip_style = _chip_qss(pal)
        for btn in self._theme_btns.values():
            btn.setStyleSheet(chip_style)
        for btn in self._speed_btns.values():
            btn.setStyleSheet(chip_style)

    def get_theme(self) -> str:
        for key, btn in self._theme_btns.items():
            if btn.isChecked():
                return key
        return THEME_DARK

    def get_speed(self) -> str:
        for key, btn in self._speed_btns.items():
            if btn.isChecked():
                return key
        return SPEED_NORMAL


# ---------------------------------------------------------------------------
# Sayfa 3 — Güvenlik ve Gelişmiş
# ---------------------------------------------------------------------------

class _PageSecurity(QWidget):
    permanent_delete_toggled = pyqtSignal(bool)

    def __init__(
        self,
        settings: AppSettings,
        pal: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {pal['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 16, 20)
        root.setSpacing(12)

        self._hdr = QLabel("Güvenlik ve Gelişmiş")
        self._hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._hline = _make_hline(pal)
        root.addWidget(self._hdr)
        root.addWidget(self._hline)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(_scroll_qss(pal))
        self._scroll.viewport().setStyleSheet(f"background-color: {pal['bg']};")

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {pal['bg']};")
        inner_lay = QVBoxLayout(self._inner)
        inner_lay.setContentsMargins(0, 2, 10, 2)
        inner_lay.setSpacing(12)

        self._cards: list[QFrame] = []
        self._card_titles: list[QLabel] = []
        self._card_descs: list[QLabel] = []

        # Kart 1: Silme Davranışı
        card1 = self._make_card(pal)
        c1lay = QVBoxLayout(card1)
        c1lay.setContentsMargins(16, 12, 16, 12)
        c1lay.setSpacing(8)

        c1title = QLabel("Silme Davranışı")
        c1title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c1title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        c1desc = QLabel(
            "Varsayılan silme işlemi dosyaları güvenle Geri Dönüşüm Kutusuna (Çöp Kutusu) "
            "gönderir. Gelişmiş kalıcı silme yalnızca aşağıdaki seçenek işaretliyken kullanılabilir."
        )
        c1desc.setFont(QFont("Segoe UI", 9))
        c1desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )
        c1desc.setWordWrap(True)

        perm_delete_enabled = bool(getattr(settings, "permanent_delete_enabled", False))
        self._chk_perm_delete = self._make_checkbox(
            "Kalıcı silmeyi etkinleştir", perm_delete_enabled, pal
        )

        self._warn_lbl = QLabel(
            "Dikkat: Bu seçenek dosyaları geri dönüştürülemez şekilde siler."
        )
        self._warn_lbl.setFont(QFont("Segoe UI", 9))
        self._warn_lbl.setStyleSheet(
            f"color: {pal['status_failed']}; background-color: {pal['surface']}; border: none;"
        )
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setVisible(perm_delete_enabled)

        c1lay.addWidget(c1title)
        c1lay.addWidget(c1desc)
        c1lay.addWidget(self._chk_perm_delete)
        c1lay.addWidget(self._warn_lbl)
        inner_lay.addWidget(card1)
        self._cards.append(card1)
        self._card_titles.append(c1title)
        self._card_descs.append(c1desc)

        self._chk_perm_delete.toggled.connect(self._on_perm_toggled)

        # Kart 2: Gizli Dosyalar
        card2 = self._make_card(pal)
        c2lay = QVBoxLayout(card2)
        c2lay.setContentsMargins(16, 12, 16, 12)
        c2lay.setSpacing(8)

        c2title = QLabel("Gizli Dosyalar")
        c2title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c2title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        skip_hidden = bool(getattr(settings, "skip_hidden_files", True))
        self._chk_hidden = self._make_checkbox(
            "Gizli dosyaları atla (. ile başlayan)", skip_hidden, pal
        )

        c2lay.addWidget(c2title)
        c2lay.addWidget(self._chk_hidden)
        inner_lay.addWidget(card2)
        self._cards.append(card2)
        self._card_titles.append(c2title)

        # Kart 3: İşlem Onay Özeti
        card3 = self._make_card(pal)
        c3lay = QVBoxLayout(card3)
        c3lay.setContentsMargins(16, 12, 16, 12)
        c3lay.setSpacing(8)

        c3title = QLabel("İşlem Onay Özeti")
        c3title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c3title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        confirm = bool(getattr(settings, "confirm_before_start", True))
        self._chk_confirm = self._make_checkbox(
            "İşlem başlamadan önce özet göster", confirm, pal
        )

        c3lay.addWidget(c3title)
        c3lay.addWidget(self._chk_confirm)
        inner_lay.addWidget(card3)
        self._cards.append(card3)
        self._card_titles.append(c3title)

        # Kart 4: Alt Klasör Taraması Bilgisi
        card4 = self._make_card(pal)
        c4lay = QVBoxLayout(card4)
        c4lay.setContentsMargins(16, 12, 16, 12)
        c4lay.setSpacing(6)

        c4title = QLabel("Alt Klasör Taraması Bilgisi")
        c4title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c4title.setStyleSheet(
            f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
        )

        c4desc = QLabel(
            "Alt klasörler taranmaz ve taşınmaz; yalnızca masaüstünün üst düzeyindeki "
            "dosyalar güvenli şekilde işlenir."
        )
        c4desc.setFont(QFont("Segoe UI", 9))
        c4desc.setStyleSheet(
            f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
        )
        c4desc.setWordWrap(True)

        c4lay.addWidget(c4title)
        c4lay.addWidget(c4desc)
        inner_lay.addWidget(card4)
        self._cards.append(card4)
        self._card_titles.append(c4title)
        self._card_descs.append(c4desc)

        inner_lay.addStretch()
        self._scroll.setWidget(self._inner)
        root.addWidget(self._scroll, 1)

    def apply_theme(self, pal: dict[str, str]) -> None:
        self.setStyleSheet(f"background-color: {pal['bg']};")
        self._hdr.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._hline.setStyleSheet(f"background-color: {pal['border']}; border: none;")
        self._scroll.setStyleSheet(_scroll_qss(pal))
        self._scroll.viewport().setStyleSheet(f"background-color: {pal['bg']};")
        self._inner.setStyleSheet(f"background-color: {pal['bg']};")

        card_qss = _card_qss(pal)
        for card in self._cards:
            card.setStyleSheet(card_qss)
        for t in self._card_titles:
            t.setStyleSheet(
                f"color: {pal['text']}; background-color: {pal['surface']}; border: none;"
            )
        for d in self._card_descs:
            d.setStyleSheet(
                f"color: {pal['muted']}; background-color: {pal['surface']}; border: none;"
            )
        self._warn_lbl.setStyleSheet(
            f"color: {pal['status_failed']}; background-color: {pal['surface']}; border: none;"
        )
        cb_qss = _checkbox_qss(pal)
        self._chk_perm_delete.setStyleSheet(cb_qss)
        self._chk_hidden.setStyleSheet(cb_qss)
        self._chk_confirm.setStyleSheet(cb_qss)

    def _on_perm_toggled(self, checked: bool) -> None:
        self._warn_lbl.setVisible(checked)
        self.permanent_delete_toggled.emit(checked)

    @staticmethod
    def _make_card(pal: dict[str, str]) -> QFrame:
        f = QFrame()
        f.setObjectName("sec_card")
        f.setStyleSheet(_card_qss(pal))
        return f

    @staticmethod
    def _make_checkbox(label: str, checked: bool, pal: dict[str, str]) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setFont(QFont("Segoe UI", 10))
        cb.setStyleSheet(_checkbox_qss(pal))
        return cb

    def get_permanent_delete(self) -> bool:
        return self._chk_perm_delete.isChecked()

    def get_skip_hidden(self) -> bool:
        return self._chk_hidden.isChecked()

    def get_confirm_before_start(self) -> bool:
        return self._chk_confirm.isChecked()


# ---------------------------------------------------------------------------
# Sayfa 4 — Hakkında
# ---------------------------------------------------------------------------

class _PageAbout(QWidget):
    def __init__(self, pal: dict[str, str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {pal['bg']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(12)
        root.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._logo_lbl = QLabel()
        self._logo_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._logo_lbl.setStyleSheet(f"background-color: {pal['bg']};")
        px = QPixmap(str(_get_asset_path("robot_supurge.png")))
        if not px.isNull():
            self._logo_lbl.setPixmap(
                px.scaled(
                    120, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._logo_lbl.setText("[logo]")
            self._logo_lbl.setStyleSheet(
                f"color: {pal['muted']}; font-size: 14pt; background-color: {pal['bg']};"
            )

        self._name_lbl = QLabel("Masaüstü Robot Süpürge")
        self._name_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._name_lbl.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._ver_lbl = QLabel("v1.0.0")
        self._ver_lbl.setFont(QFont("Segoe UI", 10))
        self._ver_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._ver_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._hline = _make_hline(pal)

        self._desc_lbl = QLabel(
            "Masaüstünüzü otomatik olarak düzenleyen akıllı dosya organizasyon robotu.\n"
            "Dosyaları kategorilere ayırır, taşır, çöp kutusuna gönderir veya atlar. "
            "Tamamen yönetimde sizsiniz."
        )
        self._desc_lbl.setFont(QFont("Segoe UI", 10))
        self._desc_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._desc_lbl.setWordWrap(True)

        self._gh_lbl = QLabel(
            f'<a href="https://github.com/winexee/desktop-robot" '
            f'style="color:{pal["accent"]}; text-decoration:underline;">'
            "GitHub: winexee/desktop-robot</a>"
        )
        self._gh_lbl.setFont(QFont("Segoe UI", 10))
        self._gh_lbl.setStyleSheet(f"background-color: {pal['bg']};")
        self._gh_lbl.setOpenExternalLinks(True)
        self._gh_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(self._logo_lbl)
        root.addWidget(self._name_lbl)
        root.addWidget(self._ver_lbl)
        root.addWidget(self._hline)
        root.addWidget(self._desc_lbl)
        root.addSpacing(8)
        root.addWidget(self._gh_lbl)
        root.addStretch()

    def apply_theme(self, pal: dict[str, str]) -> None:
        self.setStyleSheet(f"background-color: {pal['bg']};")
        self._logo_lbl.setStyleSheet(
            f"color: {pal['muted']}; font-size: 14pt; background-color: {pal['bg']};"
        )
        self._name_lbl.setStyleSheet(f"color: {pal['text']}; background-color: {pal['bg']};")
        self._ver_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._hline.setStyleSheet(f"background-color: {pal['border']}; border: none;")
        self._desc_lbl.setStyleSheet(f"color: {pal['muted']}; background-color: {pal['bg']};")
        self._gh_lbl.setStyleSheet(f"background-color: {pal['bg']};")
        self._gh_lbl.setText(
            f'<a href="https://github.com/winexee/desktop-robot" '
            f'style="color:{pal["accent"]}; text-decoration:underline;">'
            "GitHub: winexee/desktop-robot</a>"
        )


# ---------------------------------------------------------------------------
# Ana Ayarlar Diyaloğu
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """
    Modern çok temalı ayarlar penceresi.
    Sinyaller:
      settings_saved(AppSettings)  -> Controller
      theme_preview_requested(str) -> Controller (anlık tema önizleme)
    """

    settings_saved = pyqtSignal(object)         # AppSettings
    theme_preview_requested = pyqtSignal(str)   # theme_name

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or config.get_settings()
        self._pal = config.get_theme_palette(getattr(self._settings, "theme", THEME_DARK))

        self._setup_window()
        self._build_ui()

    def _setup_window(self) -> None:
        self.setObjectName("settings_dialog")
        self.setWindowTitle("Ayarlar")
        self.setWindowIcon(QIcon(str(_get_asset_path("robot_supurge.png"))))
        self.setFixedSize(_DW, _DH)

        self.setStyleSheet(self._dialog_qss(self._pal))

        screens = QApplication.screens()
        screen = QApplication.primaryScreen() or (screens[0] if screens else None)
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - _DW) // 2,
                geo.y() + (geo.height() - _DH) // 2,
            )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_content(), 1)

        self._footer_hline = _make_hline(self._pal)

        outer.addLayout(body, 1)
        outer.addWidget(self._footer_hline)
        outer.addWidget(self._build_footer())

    def _build_sidebar(self) -> QWidget:
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(_SIDEBAR_W)
        self._sidebar.setStyleSheet(
            f"QWidget#sidebar {{ background-color: {self._pal['surface']}; }}"
        )

        layout = QVBoxLayout(self._sidebar)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        pages = [
            ("Kategori Kuralları",    0),
            ("Hedef Klasör",          1),
            ("Görünüm",               2),
            ("Güvenlik ve Gelişmiş",  3),
            ("Hakkında",              4),
        ]

        sb_qss = _sidebar_btn_qss(self._pal)
        self._sb_btns: list[QPushButton] = []
        for label, idx in pages:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setFixedHeight(42)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(sb_qss)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            self._sb_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        return self._sidebar

    def _build_content(self) -> QWidget:
        self._content_wrapper = QWidget()
        self._content_wrapper.setObjectName("content_wrapper")
        self._content_wrapper.setStyleSheet(
            f"QWidget#content_wrapper {{ background-color: {self._pal['bg']}; }}"
        )

        lay = QVBoxLayout(self._content_wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(
            f"QStackedWidget {{ background-color: {self._pal['bg']}; }}"
        )

        perm_enabled = bool(getattr(self._settings, "permanent_delete_enabled", False))
        self._page_cats       = _PageCategories(self._settings, perm_enabled, self._pal)
        self._page_folder     = _PageTargetFolder(self._settings, self._pal)
        self._page_appearance = _PageAppearance(self._settings, self._pal)
        self._page_security   = _PageSecurity(self._settings, self._pal)
        self._page_about      = _PageAbout(self._pal)

        self._page_security.permanent_delete_toggled.connect(
            self._page_cats.set_permanent_delete_enabled
        )
        self._page_appearance.theme_changed.connect(self._on_theme_preview)

        self._stack.addWidget(self._page_cats)        # 0
        self._stack.addWidget(self._page_folder)      # 1
        self._stack.addWidget(self._page_appearance)  # 2
        self._stack.addWidget(self._page_security)    # 3
        self._stack.addWidget(self._page_about)       # 4

        lay.addWidget(self._stack, 1)
        return self._content_wrapper

    def _switch_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._sb_btns):
            btn.setChecked(i == idx)

    def _build_footer(self) -> QWidget:
        self._footer = QWidget()
        self._footer.setObjectName("footer")
        self._footer.setStyleSheet(
            f"QWidget#footer {{ background-color: {self._pal['bg']}; }}"
        )

        layout = QHBoxLayout(self._footer)
        layout.setContentsMargins(20, 10, 20, 14)
        layout.setSpacing(10)

        self._btn_cancel = QPushButton("İptal")
        self._btn_cancel.setFixedHeight(38)
        self._btn_cancel.setFont(QFont("Segoe UI", 10))
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self.reject)

        self._btn_save = QPushButton("Kaydet")
        self._btn_save.setFixedHeight(38)
        self._btn_save.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.clicked.connect(self._save)

        self._apply_footer_styles(self._pal)

        layout.addStretch()
        layout.addWidget(self._btn_cancel)
        layout.addWidget(self._btn_save)
        return self._footer

    def _apply_footer_styles(self, pal: dict[str, str]) -> None:
        self._btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {pal['surface']};
                color: {pal['muted']};
                border: 1px solid {pal['border']};
                border-radius: 8px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: {pal['hover']};
                color: {pal['text']};
            }}
            QPushButton:pressed {{
                background-color: {pal['pressed']};
                color: {pal['text']};
            }}
            QPushButton:disabled {{
                background-color: {pal['disabled_bg']};
                color: {pal['disabled_fg']};
            }}
        """)
        self._btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {pal['accent']};
                color: {pal['accent_fg']};
                border: none;
                border-radius: 8px;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {pal['accent_hover']};
                color: {pal['accent_fg']};
            }}
            QPushButton:pressed {{
                background-color: {pal['accent_pressed']};
                color: {pal['accent_fg']};
            }}
            QPushButton:disabled {{
                background-color: {pal['surface']};
                color: {pal['disabled_fg']};
            }}
        """)

    # ------------------------------------------------------------------
    # Tema önizleme & dinamik yeniden boyama
    # ------------------------------------------------------------------

    def _on_theme_preview(self, theme_name: str) -> None:
        self.apply_theme(theme_name)
        self.theme_preview_requested.emit(theme_name)

    @staticmethod
    def _dialog_qss(pal: dict[str, str]) -> str:
        return f"""
QDialog#settings_dialog {{
    background-color: {pal['bg']};
}}
QMessageBox {{
    background-color: {pal['bg']};
    color: {pal['text']};
}}
QMessageBox QLabel {{
    background-color: {pal['bg']};
    color: {pal['text']};
}}
QMessageBox QPushButton {{
    background-color: {pal['hover']};
    color: {pal['text']};
    border: 1px solid {pal['border']};
    border-radius: 5px;
    padding: 5px 16px;
    min-width: 68px;
}}
QMessageBox QPushButton:hover {{ background-color: {pal['pressed']}; }}
QMessageBox QPushButton:pressed {{ background-color: {pal['surface']}; }}
"""

    def apply_theme(self, theme_name: str) -> None:
        """Ayarlar penceresinin tüm bileşenlerini seçili opak temaya geçir."""
        pal = config.get_theme_palette(theme_name)
        self._pal = pal

        self.setStyleSheet(self._dialog_qss(pal))
        self._sidebar.setStyleSheet(
            f"QWidget#sidebar {{ background-color: {pal['surface']}; }}"
        )
        sb_qss = _sidebar_btn_qss(pal)
        for btn in self._sb_btns:
            btn.setStyleSheet(sb_qss)

        self._content_wrapper.setStyleSheet(
            f"QWidget#content_wrapper {{ background-color: {pal['bg']}; }}"
        )
        self._stack.setStyleSheet(
            f"QStackedWidget {{ background-color: {pal['bg']}; }}"
        )
        self._footer_hline.setStyleSheet(
            f"background-color: {pal['border']}; border: none;"
        )
        self._footer.setStyleSheet(
            f"QWidget#footer {{ background-color: {pal['bg']}; }}"
        )
        self._apply_footer_styles(pal)

        self._page_cats.apply_theme(pal)
        self._page_folder.apply_theme(pal)
        self._page_appearance.apply_theme(pal)
        self._page_security.apply_theme(pal)
        self._page_about.apply_theme(pal)

    # ------------------------------------------------------------------
    # Kaydetme
    # ------------------------------------------------------------------

    def _save(self) -> None:
        ok, err_msg, resolved_target = self._page_folder.validate_for_save()
        if not ok:
            self._switch_page(1)
            QMessageBox.warning(
                self,
                "Geçersiz Hedef Klasör",
                err_msg,
            )
            return

        new_settings = AppSettings(
            category_rules=self._page_cats.get_rules(),
            custom_target=resolved_target,
            permanent_delete_enabled=self._page_security.get_permanent_delete(),
            skip_hidden_files=self._page_security.get_skip_hidden(),
            confirm_before_start=self._page_security.get_confirm_before_start(),
            theme=self._page_appearance.get_theme(),
            robot_speed=self._page_appearance.get_speed(),
        )

        config.apply_settings(new_settings)
        self.settings_saved.emit(new_settings)
        self.accept()
