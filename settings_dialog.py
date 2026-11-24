"""
Masaustu Robot Supurge - Ayarlar Penceresi
==========================================
Modern koyu tema: 4 sayfa sidebar + QStackedWidget

Pencere: 820 x 600 (tamamen opak)
Sidebar: 200px, #2b2d31
Icerik: kalan, #1e1f22
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
from config import AppSettings, CATEGORIES, ACTION_MOVE, ACTION_DELETE, ACTION_SKIP

try:
    from config import ACTION_TRASH
except ImportError:
    ACTION_TRASH = "trash"


# ---------------------------------------------------------------------------
# Boyut ve renk sabitleri (tamamen opak hex degerler)
# ---------------------------------------------------------------------------

_DW = 820
_DH = 600
_SIDEBAR_W = 200

C_BG             = "#1e1f22"
C_SURFACE        = "#2b2d31"
C_SURFACE2       = "#313338"
C_HOVER          = "#35373c"
C_PRESSED        = "#3f4147"
C_SIDEBAR_ACTIVE = "#383c54"
C_SIDEBAR_ACT_HV = "#414663"
C_ACCENT         = "#5865f2"
C_ACCENT_HOVER   = "#6475ff"
C_ACCENT_PRESS   = "#4855d4"
C_TEXT           = "#f2f3f5"
C_MUTED          = "#b5bac1"
C_DISABLED_BG    = "#23252a"
C_DISABLED_FG    = "#5c6068"
C_BORDER         = "#3f4147"

C_GREEN_BG       = "#2d7d4b"
C_GREEN_HV       = "#348f56"
C_GREEN_PR       = "#25683e"
C_GREEN_FG       = "#57f287"

C_BLUE_BG        = "#5865f2"
C_BLUE_HV        = "#6475ff"
C_BLUE_PR        = "#4855d4"
C_BLUE_FG        = "#ffffff"

C_RED_BG         = "#8c2f30"
C_RED_HV         = "#9e3536"
C_RED_PR         = "#772728"
C_RED_FG         = "#fe4c43"

C_SKIP_BG        = "#5c606b"
C_SKIP_HV        = "#696d7a"
C_SKIP_PR        = "#4e5058"
C_SKIP_FG        = "#ffffff"

C_CHIP_OFF_BG    = "#40444b"
C_CHIP_OFF_HV    = "#4e5058"
C_CHIP_OFF_PR    = "#35373c"
C_CHIP_OFF_FG    = "#b5bac1"


# ---------------------------------------------------------------------------
# Asset ve klasor acma yardimcilari
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
# QSS Sablonlari (tamamen opak hex renkler)
# ---------------------------------------------------------------------------

_SIDEBAR_BTN_QSS = f"""
QPushButton {{
    background-color: {C_SURFACE};
    color: {C_MUTED};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 16px;
    font-size: 10pt;
}}
QPushButton:hover:!checked {{
    background-color: {C_HOVER};
    color: {C_TEXT};
}}
QPushButton:pressed {{
    background-color: {C_PRESSED};
    color: {C_BLUE_FG};
}}
QPushButton:checked {{
    background-color: {C_SIDEBAR_ACTIVE};
    color: {C_TEXT};
    border-left: 3px solid {C_ACCENT};
    padding-left: 13px;
    font-weight: bold;
}}
QPushButton:checked:hover {{
    background-color: {C_SIDEBAR_ACT_HV};
    color: {C_BLUE_FG};
}}
QPushButton:disabled {{
    background-color: {C_SURFACE};
    color: {C_DISABLED_FG};
}}
"""

_CHIP_QSS = f"""
QPushButton {{
    background-color: {C_CHIP_OFF_BG};
    color: {C_CHIP_OFF_FG};
    border: none;
    border-radius: 5px;
    font-size: 9pt;
    font-weight: 600;
    padding: 4px 10px;
    min-width: 60px;
}}
QPushButton:hover:!checked:!disabled {{
    background-color: {C_CHIP_OFF_HV};
    color: {C_TEXT};
}}
QPushButton:pressed:!disabled {{
    background-color: {C_CHIP_OFF_PR};
    color: {C_BLUE_FG};
}}
QPushButton:disabled {{
    background-color: {C_DISABLED_BG};
    color: {C_DISABLED_FG};
}}
QPushButton#chip_move:checked {{
    background-color: {C_GREEN_BG};
    color: {C_GREEN_FG};
}}
QPushButton#chip_move:checked:hover {{
    background-color: {C_GREEN_HV};
    color: {C_GREEN_FG};
}}
QPushButton#chip_move:checked:pressed {{
    background-color: {C_GREEN_PR};
    color: {C_GREEN_FG};
}}
QPushButton#chip_trash:checked {{
    background-color: {C_BLUE_BG};
    color: {C_BLUE_FG};
}}
QPushButton#chip_trash:checked:hover {{
    background-color: {C_BLUE_HV};
    color: {C_BLUE_FG};
}}
QPushButton#chip_trash:checked:pressed {{
    background-color: {C_BLUE_PR};
    color: {C_BLUE_FG};
}}
QPushButton#chip_delete:checked {{
    background-color: {C_RED_BG};
    color: {C_RED_FG};
}}
QPushButton#chip_delete:checked:hover {{
    background-color: {C_RED_HV};
    color: {C_RED_FG};
}}
QPushButton#chip_delete:checked:pressed {{
    background-color: {C_RED_PR};
    color: {C_RED_FG};
}}
QPushButton#chip_delete:disabled {{
    background-color: {C_DISABLED_BG};
    color: {C_DISABLED_FG};
}}
QPushButton#chip_skip:checked {{
    background-color: {C_SKIP_BG};
    color: {C_SKIP_FG};
}}
QPushButton#chip_skip:checked:hover {{
    background-color: {C_SKIP_HV};
    color: {C_SKIP_FG};
}}
QPushButton#chip_skip:checked:pressed {{
    background-color: {C_SKIP_PR};
    color: {C_SKIP_FG};
}}
"""

_CARD_QSS = f"""
QFrame#sec_card {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}}
"""

_SCROLL_QSS = f"""
QScrollArea {{
    background-color: {C_BG};
    border: none;
}}
QScrollBar:vertical {{
    background-color: {C_SURFACE};
    width: 8px;
    border-radius: 4px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background-color: #4e5058;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #6d717a;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    background-color: {C_SURFACE};
    height: 0px;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background-color: {C_SURFACE};
}}
"""

_PERM_DELETE_DISABLED_TOOLTIP = (
    "Güvenlik sekmesinden Kalıcı Silme seçeneğini etkinleştirin"
)


# ---------------------------------------------------------------------------
# Yardimci: yatay ayrac
# ---------------------------------------------------------------------------

def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
    return f


# ---------------------------------------------------------------------------
# Eylem chip grubu (Tasi / Cop Kutusu / Kalici Sil / Atla)
# ---------------------------------------------------------------------------

class _ActionChips(QWidget):
    """
    Dort checkable QPushButton; QButtonGroup ile exclusive.
    action: ACTION_MOVE | ACTION_TRASH | ACTION_DELETE | ACTION_SKIP
    """

    def __init__(
        self,
        action: str,
        permanent_delete_enabled: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {C_SURFACE};")

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

        self._map: dict[str, QPushButton] = {}
        for obj_name, label, val in defs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setCheckable(True)
            btn.setChecked(val == selected)
            btn.setStyleSheet(_CHIP_QSS)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn)
            self._map[val] = btn
            layout.addWidget(btn)

        self.set_permanent_delete_enabled(permanent_delete_enabled)

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
# Tek kategori satiri (kart)
# ---------------------------------------------------------------------------

class _CategoryRow(QFrame):
    """Renkli durum noktasi + kategori adi + dort eylem chip."""

    def __init__(
        self,
        category: config.Category,
        action: str,
        permanent_delete_enabled: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("category_row")
        self._cat = category
        self._chips = _ActionChips(action, permanent_delete_enabled, self)

        self.setFixedHeight(56)
        self.setStyleSheet(f"""
            QFrame#category_row {{
                background-color: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Renkli durum noktasi (10x10 daire)
        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {category.color}; border-radius: 5px; border: none;"
        )

        # Kategori adi
        lbl = QLabel(category.name)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {C_TEXT}; background-color: {C_SURFACE}; border: none;"
        )
        lbl.setMinimumWidth(105)

        layout.addWidget(dot)
        layout.addWidget(lbl)
        layout.addStretch()
        layout.addWidget(self._chips)

    def set_permanent_delete_enabled(self, enabled: bool) -> None:
        self._chips.set_permanent_delete_enabled(enabled)

    def get_action(self) -> str:
        return self._chips.get_action()

    @property
    def category(self) -> config.Category:
        return self._cat


# ---------------------------------------------------------------------------
# Sayfa 0 — Kategori Kurallari
# ---------------------------------------------------------------------------

class _PageCategories(QWidget):
    def __init__(
        self,
        settings: AppSettings,
        permanent_delete_enabled: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 16, 20)
        root.setSpacing(12)

        hdr = QLabel("Kategori Kuralları")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_TEXT}; background-color: {C_BG};")

        sub = QLabel(
            "Her kategori için robotun ne yapması gerektiğini seçin.\n"
            "Taşı: kategori klasörüne taşı  |  "
            "Çöp Kutusu: geri dönüşüm kutusuna at  |  "
            "Kalıcı Sil: geri döndürülemez sil  |  "
            "Atla: dokunma"
        )
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
        sub.setWordWrap(True)

        root.addWidget(hdr)
        root.addWidget(sub)
        root.addWidget(_hline())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(_SCROLL_QSS)
        scroll.viewport().setStyleSheet(f"background-color: {C_BG};")

        inner = QWidget()
        inner.setStyleSheet(f"background-color: {C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 2, 10, 2)
        inner_lay.setSpacing(6)

        self._rows: list[_CategoryRow] = []
        for cat in CATEGORIES:
            action = settings.category_rules.get(cat.name, ACTION_MOVE)
            row = _CategoryRow(cat, action, permanent_delete_enabled)
            inner_lay.addWidget(row)
            self._rows.append(row)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def set_permanent_delete_enabled(self, enabled: bool) -> None:
        for row in self._rows:
            row.set_permanent_delete_enabled(enabled)

    def get_rules(self) -> dict[str, str]:
        return {row.category.name: row.get_action() for row in self._rows}


# ---------------------------------------------------------------------------
# Sayfa 1 — Hedef Klasor
# ---------------------------------------------------------------------------

class _PageTargetFolder(QWidget):
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        hdr = QLabel("Hedef Klasör")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_TEXT}; background-color: {C_BG};")

        sub = QLabel("Taşınan dosyaların yerleştirileceği kök dizini belirleyin.")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
        sub.setWordWrap(True)

        root.addWidget(hdr)
        root.addWidget(sub)
        root.addWidget(_hline())

        # Otomatik secenegi
        self._rb_auto = self._make_radio(
            "Otomatik (Masaüstü/Düzenlenmiş)",
            settings.custom_target is None,
        )

        try:
            auto_path = str(config.get_organized_root())
        except Exception:
            auto_path = str(Path.home() / "Desktop" / "Düzenlenmiş")

        auto_hint = QLabel(f"Hedef: {auto_path}")
        auto_hint.setFont(QFont("Courier New", 8))
        auto_hint.setStyleSheet(
            f"color: {C_MUTED}; padding-left: 28px; background-color: {C_BG};"
        )
        auto_hint.setWordWrap(True)

        root.addWidget(self._rb_auto)
        root.addWidget(auto_hint)
        root.addWidget(_hline())

        # Ozel Klasor secenegi
        self._rb_custom = self._make_radio(
            "Özel Klasör",
            settings.custom_target is not None,
        )
        root.addWidget(self._rb_custom)

        # Yol + Gozat + Klasoru Ac
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Klasör yolunu seçin veya yazın...")
        self._path_edit.setText(settings.custom_target or "")
        self._path_edit.setEnabled(settings.custom_target is not None)
        self._path_edit.setFixedHeight(36)
        self._path_edit.setFont(QFont("Courier New", 9))
        self._path_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {C_ACCENT};
            }}
            QLineEdit:disabled {{
                color: {C_DISABLED_FG};
                background-color: {C_DISABLED_BG};
                border: 1px solid {C_SURFACE};
            }}
        """)

        self._btn_browse = self._make_action_btn("Gözat")
        self._btn_browse.setEnabled(settings.custom_target is not None)
        self._btn_browse.clicked.connect(self._browse)

        self._btn_open = self._make_action_btn("Klasörü Aç")
        self._btn_open.setEnabled(settings.custom_target is not None)
        self._btn_open.clicked.connect(self._open_folder)

        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._btn_browse)
        path_row.addWidget(self._btn_open)
        root.addLayout(path_row)

        # Durum etiketi
        self._status_lbl = QLabel()
        self._status_lbl.setFont(QFont("Segoe UI", 9))
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
        root.addWidget(self._status_lbl)

        root.addStretch()

        # Radyo grubu
        grp = QButtonGroup(self)
        grp.addButton(self._rb_auto)
        grp.addButton(self._rb_custom)

        self._rb_auto.toggled.connect(self._on_auto_toggled)
        self._path_edit.textChanged.connect(self._validate_path)

        # Baslangic dogrulama
        self._validate_path(self._path_edit.text())

    # ------------------------------------------------------------------

    @staticmethod
    def _make_radio(label: str, checked: bool) -> QRadioButton:
        rb = QRadioButton(label)
        rb.setChecked(checked)
        rb.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        rb.setStyleSheet(f"""
            QRadioButton {{
                color: {C_TEXT};
                spacing: 10px;
                background-color: {C_BG};
            }}
            QRadioButton:hover {{
                color: {C_BLUE_FG};
            }}
            QRadioButton:disabled {{
                color: {C_DISABLED_FG};
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #4e5058;
                background-color: {C_SURFACE};
            }}
            QRadioButton::indicator:hover {{
                border: 2px solid {C_ACCENT};
            }}
            QRadioButton::indicator:checked {{
                background-color: {C_ACCENT};
                border: 2px solid {C_ACCENT};
            }}
        """)
        return rb

    @staticmethod
    def _make_action_btn(label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(36)
        btn.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT};
                color: {C_BLUE_FG};
                border: none;
                border-radius: 6px;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background-color: {C_ACCENT_HOVER};
                color: {C_BLUE_FG};
            }}
            QPushButton:pressed {{
                background-color: {C_ACCENT_PRESS};
                color: {C_BLUE_FG};
            }}
            QPushButton:disabled {{
                background-color: {C_SURFACE};
                color: {C_DISABLED_FG};
                border: 1px solid {C_BORDER};
            }}
        """)
        return btn

    def _on_auto_toggled(self, checked: bool) -> None:
        custom = not checked
        self._path_edit.setEnabled(custom)
        self._btn_browse.setEnabled(custom)
        self._btn_open.setEnabled(custom)
        if checked:
            self._status_lbl.setText("")
            self._status_lbl.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
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
        """
        Doner: (gecerli_mi, mesaj, cozumlenmis_path, klasor_mevcut_mu)
        """
        cleaned = raw_text.strip()
        if not cleaned:
            return False, "Klasör yolu boş olamaz.", None, False

        if sys.platform != "win32" and len(cleaned) >= 2 and cleaned[1] == ":" and cleaned[0].isalpha():
            return False, "Bu işletim sisteminde sürücü harfi içeren yol geçersizdir.", None, False

        try:
            p_abs = Path(cleaned).expanduser().resolve()
        except Exception as exc:
            return False, f"Geçersiz yol ({exc}).", None, False

        # Tehlikeli yollar kontrolu (AppSettings._validate_target_path + masaustu)
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

        # Klasor henuz yoksa, olusturulabilir/yazilabilir ust dizini bul
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
        if not self._rb_custom.isChecked():
            self._status_lbl.setText("")
            self._status_lbl.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
            return

        if not text.strip():
            self._status_lbl.setText("Yazılamaz / Geçersiz: Bir klasör yolu seçin veya yazın.")
            self._status_lbl.setStyleSheet(f"color: {C_RED_FG}; background-color: {C_BG};")
            return

        ok, msg, _, _ = self._evaluate_path(text)
        if ok:
            self._status_lbl.setText(msg)
            self._status_lbl.setStyleSheet(f"color: {C_GREEN_FG}; background-color: {C_BG};")
        else:
            self._status_lbl.setText(f"Yazılamaz / Geçersiz: {msg}")
            self._status_lbl.setStyleSheet(f"color: {C_RED_FG}; background-color: {C_BG};")

    def is_custom_selected(self) -> bool:
        return self._rb_custom.isChecked()

    def validate_for_save(self) -> tuple[bool, str, Optional[str]]:
        """
        Kaydetme oncesi dogrulama.
        Doner: (basarili_mi, hata_mesaji, cozumlenmis_yol_veya_None)
        """
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
# Sayfa 2 — Guvenlik ve Gelismis
# ---------------------------------------------------------------------------

class _PageSecurity(QWidget):
    permanent_delete_toggled = pyqtSignal(bool)

    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 16, 20)
        root.setSpacing(12)

        hdr = QLabel("Güvenlik ve Gelişmiş")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_TEXT}; background-color: {C_BG};")
        root.addWidget(hdr)
        root.addWidget(_hline())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(_SCROLL_QSS)
        scroll.viewport().setStyleSheet(f"background-color: {C_BG};")

        inner = QWidget()
        inner.setStyleSheet(f"background-color: {C_BG};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 2, 10, 2)
        inner_lay.setSpacing(12)

        # Kart 1: Silme Davranisi & Kalici Silme
        card1 = self._make_card()
        c1lay = QVBoxLayout(card1)
        c1lay.setContentsMargins(16, 12, 16, 12)
        c1lay.setSpacing(8)

        c1title = QLabel("Silme Davranışı")
        c1title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c1title.setStyleSheet(
            f"color: {C_TEXT}; background-color: {C_SURFACE}; border: none;"
        )

        c1desc = QLabel(
            "Varsayılan silme işlemi dosyaları güvenle Geri Dönüşüm Kutusuna (Çöp Kutusu) "
            "gönderir. Gelişmiş kalıcı silme yalnızca aşağıdaki seçenek işaretliyken kullanılabilir."
        )
        c1desc.setFont(QFont("Segoe UI", 9))
        c1desc.setStyleSheet(
            f"color: {C_MUTED}; background-color: {C_SURFACE}; border: none;"
        )
        c1desc.setWordWrap(True)

        perm_delete_enabled = bool(getattr(settings, "permanent_delete_enabled", False))
        self._chk_perm_delete = self._make_checkbox(
            "Kalıcı silmeyi etkinleştir", perm_delete_enabled
        )

        self._warn_lbl = QLabel(
            "Dikkat: Bu seçenek dosyaları geri dönüştürülemez şekilde siler."
        )
        self._warn_lbl.setFont(QFont("Segoe UI", 9))
        self._warn_lbl.setStyleSheet(
            f"color: {C_RED_FG}; background-color: {C_SURFACE}; border: none;"
        )
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setVisible(perm_delete_enabled)

        c1lay.addWidget(c1title)
        c1lay.addWidget(c1desc)
        c1lay.addWidget(self._chk_perm_delete)
        c1lay.addWidget(self._warn_lbl)
        inner_lay.addWidget(card1)

        self._chk_perm_delete.toggled.connect(self._on_perm_toggled)

        # Kart 2: Gizli Dosyalar
        card2 = self._make_card()
        c2lay = QVBoxLayout(card2)
        c2lay.setContentsMargins(16, 12, 16, 12)
        c2lay.setSpacing(8)

        c2title = QLabel("Gizli Dosyalar")
        c2title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c2title.setStyleSheet(
            f"color: {C_TEXT}; background-color: {C_SURFACE}; border: none;"
        )

        skip_hidden = bool(getattr(settings, "skip_hidden_files", True))
        self._chk_hidden = self._make_checkbox(
            "Gizli dosyaları atla (. ile başlayan)", skip_hidden
        )

        c2lay.addWidget(c2title)
        c2lay.addWidget(self._chk_hidden)
        inner_lay.addWidget(card2)

        # Kart 3: Islem Onay Ozeti
        card3 = self._make_card()
        c3lay = QVBoxLayout(card3)
        c3lay.setContentsMargins(16, 12, 16, 12)
        c3lay.setSpacing(8)

        c3title = QLabel("İşlem Onay Özeti")
        c3title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c3title.setStyleSheet(
            f"color: {C_TEXT}; background-color: {C_SURFACE}; border: none;"
        )

        confirm = bool(getattr(settings, "confirm_before_start", True))
        self._chk_confirm = self._make_checkbox(
            "İşlem başlamadan önce özet göster", confirm
        )

        c3lay.addWidget(c3title)
        c3lay.addWidget(self._chk_confirm)
        inner_lay.addWidget(card3)

        # Kart 4: Alt Klasor Taramasi Bilgisi
        card4 = self._make_card()
        c4lay = QVBoxLayout(card4)
        c4lay.setContentsMargins(16, 12, 16, 12)
        c4lay.setSpacing(6)

        c4title = QLabel("Alt Klasör Taraması Bilgisi")
        c4title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c4title.setStyleSheet(
            f"color: {C_TEXT}; background-color: {C_SURFACE}; border: none;"
        )

        c4desc = QLabel(
            "Alt klasörler taranmaz ve taşınmaz; yalnızca masaüstünün üst düzeyindeki "
            "dosyalar güvenli şekilde işlenir."
        )
        c4desc.setFont(QFont("Segoe UI", 9))
        c4desc.setStyleSheet(
            f"color: {C_MUTED}; background-color: {C_SURFACE}; border: none;"
        )
        c4desc.setWordWrap(True)

        c4lay.addWidget(c4title)
        c4lay.addWidget(c4desc)
        inner_lay.addWidget(card4)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def _on_perm_toggled(self, checked: bool) -> None:
        self._warn_lbl.setVisible(checked)
        self.permanent_delete_toggled.emit(checked)

    @staticmethod
    def _make_card() -> QFrame:
        f = QFrame()
        f.setObjectName("sec_card")
        f.setStyleSheet(_CARD_QSS)
        return f

    @staticmethod
    def _make_checkbox(label: str, checked: bool) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setFont(QFont("Segoe UI", 10))
        cb.setStyleSheet(f"""
            QCheckBox {{
                color: {C_TEXT};
                spacing: 10px;
                background-color: {C_SURFACE};
                border: none;
            }}
            QCheckBox:hover {{
                color: {C_BLUE_FG};
            }}
            QCheckBox:disabled {{
                color: {C_DISABLED_FG};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 2px solid #4e5058;
                background-color: {C_SURFACE2};
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid {C_ACCENT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {C_ACCENT};
                border: 2px solid {C_ACCENT};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {C_DISABLED_BG};
                border: 2px solid {C_BORDER};
            }}
        """)
        return cb

    def get_permanent_delete(self) -> bool:
        return self._chk_perm_delete.isChecked()

    def get_skip_hidden(self) -> bool:
        return self._chk_hidden.isChecked()

    def get_confirm_before_start(self) -> bool:
        return self._chk_confirm.isChecked()


# ---------------------------------------------------------------------------
# Sayfa 3 — Hakkinda
# ---------------------------------------------------------------------------

class _PageAbout(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(12)
        root.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_lbl.setStyleSheet(f"background-color: {C_BG};")
        px = QPixmap(str(_get_asset_path("robot_supurge.png")))
        if not px.isNull():
            logo_lbl.setPixmap(
                px.scaled(
                    120, 120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo_lbl.setText("[logo]")
            logo_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 14pt; background-color: {C_BG};"
            )

        # Uygulama adi
        name_lbl = QLabel("Masaüstü Robot Süpürge")
        name_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {C_TEXT}; background-color: {C_BG};")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Versiyon
        ver_lbl = QLabel("v1.0.0")
        ver_lbl.setFont(QFont("Segoe UI", 10))
        ver_lbl.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Aciklama
        desc_lbl = QLabel(
            "Masaüstünüzü otomatik olarak düzenleyen akıllı dosya organizasyon robotu.\n"
            "Dosyaları kategorilere ayırır, taşır, çöp kutusuna gönderir veya atlar. "
            "Tamamen yönetimde sizsiniz."
        )
        desc_lbl.setFont(QFont("Segoe UI", 10))
        desc_lbl.setStyleSheet(f"color: {C_MUTED}; background-color: {C_BG};")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        desc_lbl.setWordWrap(True)

        # GitHub baglantisi
        gh_lbl = QLabel(
            '<a href="https://github.com/winexee/desktop-robot" '
            'style="color:#5865f2; text-decoration:underline;">'
            "GitHub: winexee/desktop-robot</a>"
        )
        gh_lbl.setFont(QFont("Segoe UI", 10))
        gh_lbl.setStyleSheet(f"background-color: {C_BG};")
        gh_lbl.setOpenExternalLinks(True)
        gh_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(logo_lbl)
        root.addWidget(name_lbl)
        root.addWidget(ver_lbl)
        root.addWidget(_hline())
        root.addWidget(desc_lbl)
        root.addSpacing(8)
        root.addWidget(gh_lbl)
        root.addStretch()


# ---------------------------------------------------------------------------
# Ana Ayarlar Diyalogu
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """
    Modern koyu temali ayarlar penceresi.
    Sinyal: settings_saved(AppSettings) -> Controller / main.py baglanir.
    """

    settings_saved = pyqtSignal(object)  # AppSettings

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or config.get_settings()

        self._setup_window()
        self._build_ui()

    # ------------------------------------------------------------------
    # Pencere kurulumu
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setObjectName("settings_dialog")
        self.setWindowTitle("Ayarlar")
        self.setWindowIcon(QIcon(str(_get_asset_path("robot_supurge.png"))))
        self.setFixedSize(_DW, _DH)

        # Tamamen opak standart pencere
        self.setStyleSheet(
            f"QDialog#settings_dialog {{ background-color: {C_BG}; }}"
        )

        screens = QApplication.screens()
        screen = QApplication.primaryScreen() or (screens[0] if screens else None)
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - _DW) // 2,
                geo.y() + (geo.height() - _DH) // 2,
            )

    # ------------------------------------------------------------------
    # UI insasi
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Govde: sidebar + icerik
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_content(), 1)

        outer.addLayout(body, 1)
        outer.addWidget(_hline())
        outer.addWidget(self._build_footer())

    # --- Sidebar ---

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(_SIDEBAR_W)
        sb.setStyleSheet(f"QWidget#sidebar {{ background-color: {C_SURFACE}; }}")

        layout = QVBoxLayout(sb)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        pages = [
            ("Kategori Kuralları",    0),
            ("Hedef Klasör",          1),
            ("Güvenlik ve Gelişmiş",  2),
            ("Hakkında",              3),
        ]

        self._sb_btns: list[QPushButton] = []
        for label, idx in pages:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setFixedHeight(42)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_SIDEBAR_BTN_QSS)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            self._sb_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        return sb

    # --- Icerik alani ---

    def _build_content(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("content_wrapper")
        wrapper.setStyleSheet(f"QWidget#content_wrapper {{ background-color: {C_BG}; }}")

        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"QStackedWidget {{ background-color: {C_BG}; }}")

        perm_enabled = bool(getattr(self._settings, "permanent_delete_enabled", False))
        self._page_cats     = _PageCategories(self._settings, perm_enabled)
        self._page_folder   = _PageTargetFolder(self._settings)
        self._page_security = _PageSecurity(self._settings)
        self._page_about    = _PageAbout()

        self._page_security.permanent_delete_toggled.connect(
            self._page_cats.set_permanent_delete_enabled
        )

        self._stack.addWidget(self._page_cats)      # 0
        self._stack.addWidget(self._page_folder)    # 1
        self._stack.addWidget(self._page_security)  # 2
        self._stack.addWidget(self._page_about)     # 3

        lay.addWidget(self._stack, 1)
        return wrapper

    def _switch_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._sb_btns):
            btn.setChecked(i == idx)

    # --- Alt bar ---

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("footer")
        footer.setStyleSheet(f"QWidget#footer {{ background-color: {C_BG}; }}")

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(20, 10, 20, 14)
        layout.setSpacing(10)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setFont(QFont("Segoe UI", 10))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_SURFACE};
                color: {C_MUTED};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: {C_HOVER};
                color: {C_TEXT};
            }}
            QPushButton:pressed {{
                background-color: {C_DISABLED_BG};
                color: {C_BLUE_FG};
            }}
            QPushButton:disabled {{
                background-color: {C_DISABLED_BG};
                color: {C_DISABLED_FG};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Kaydet")
        btn_save.setFixedHeight(38)
        btn_save.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {C_ACCENT};
                color: {C_BLUE_FG};
                border: none;
                border-radius: 8px;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background-color: {C_ACCENT_HOVER};
                color: {C_BLUE_FG};
            }}
            QPushButton:pressed {{
                background-color: {C_ACCENT_PRESS};
                color: {C_BLUE_FG};
            }}
            QPushButton:disabled {{
                background-color: {C_SURFACE};
                color: {C_DISABLED_FG};
            }}
        """)
        btn_save.clicked.connect(self._save)

        layout.addStretch()
        layout.addWidget(btn_cancel)
        layout.addWidget(btn_save)
        return footer

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
        )

        if hasattr(new_settings, "permanent_delete_enabled"):
            new_settings.permanent_delete_enabled = (
                self._page_security.get_permanent_delete()
            )
        if hasattr(new_settings, "skip_hidden_files"):
            new_settings.skip_hidden_files = self._page_security.get_skip_hidden()
        if hasattr(new_settings, "confirm_before_start"):
            new_settings.confirm_before_start = (
                self._page_security.get_confirm_before_start()
            )

        config.apply_settings(new_settings)
        self.settings_saved.emit(new_settings)
        self.accept()
