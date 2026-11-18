"""
Masaüstü Robot Süpürge — Ayarlar Penceresi (Modern Dark UI)
===========================================================
Tasarım Dili: Discord / Windows 11 Fluent — koyu tema
  Arka plan : #1e1f22
  Yüzey      : #2b2d31
  Hover      : #35373c
  Accent     : #5865f2 (Discord blurple)
  Metin ana  : #f2f3f5
  Metin soluk: #b5bac1
  Yeşil      : #2d7d4b (taşı — aktif)
  Kırmızı    : #8c2f30 (sil — aktif)
  Gri        : #4e5058 (atla — aktif)

İçerik
------
  Sol kenar çubuğu (sidebar) + QStackedWidget
    Sayfa 0: Kategori Kuralları   – her kategori için Taşı / Sil / Atla çipi
    Sayfa 1: Hedef Klasör         – Otomatik veya özel dizin

Dışa aktarım
------------
  SettingsDialog.settings_saved(AppSettings)   → Controller
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics,
)
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFileDialog,
    QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

import config
from config import AppSettings, CATEGORIES, ACTION_MOVE, ACTION_DELETE, ACTION_SKIP


# ---------------------------------------------------------------------------
# Boyut sabitleri
# ---------------------------------------------------------------------------

_DW, _DH   = 720, 560
_SIDEBAR_W  = 196
_CONTENT_W  = _DW - _SIDEBAR_W

# ---------------------------------------------------------------------------
# Renk sabitleri (hex string — QSS'de kullanılır)
# ---------------------------------------------------------------------------

C_BG        = "#1e1f22"
C_SURFACE   = "#2b2d31"
C_SURFACE2  = "#313338"
C_HOVER     = "#35373c"
C_ACTIVE_BG = "#393c43"
C_ACCENT    = "#5865f2"
C_ACCENT_LO = "rgba(88,101,242,30)"   # accent very low opacity
C_TEXT      = "#f2f3f5"
C_MUTED     = "#b5bac1"
C_DISABLED  = "#4e5058"
C_GREEN_BG  = "#2d7d4b"
C_GREEN_FG  = "#57f287"
C_RED_BG    = "#8c2f30"
C_RED_FG    = "#fe4c43"
C_SKIP_BG   = "#4e5058"
C_SKIP_FG   = "#b5bac1"
C_BORDER    = "rgba(255,255,255,8)"    # ultra-subtle border


# ---------------------------------------------------------------------------
# Paylaşılan QSS parçaları
# ---------------------------------------------------------------------------

_CHIP_QSS = f"""
QPushButton {{
    background: rgba(40,42,52,180);
    color: {C_DISABLED};
    border: 1px solid rgba(255,255,255,8);
    border-radius: 7px;
    font-size: 9pt;
    font-weight: 600;
    padding: 3px 10px;
    min-width: 60px;
}}
QPushButton:hover {{
    background: rgba(55,58,70,210);
    color: {C_MUTED};
    border: 1px solid rgba(255,255,255,15);
}}
QPushButton#chip_move:checked {{
    background: {C_GREEN_BG};
    color: {C_GREEN_FG};
    border: 1px solid rgba(87,242,135,45);
}}
QPushButton#chip_delete:checked {{
    background: {C_RED_BG};
    color: {C_RED_FG};
    border: 1px solid rgba(254,76,67,45);
}}
QPushButton#chip_skip:checked {{
    background: {C_SKIP_BG};
    color: {C_SKIP_FG};
    border: 1px solid rgba(255,255,255,15);
}}
"""

_SIDEBAR_BTN_QSS = f"""
QPushButton {{
    background: transparent;
    color: {C_MUTED};
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 0 14px;
    font-size: 10pt;
    font-weight: 500;
}}
QPushButton:hover:!checked {{
    background: {C_HOVER};
    color: {C_TEXT};
}}
QPushButton:checked {{
    background: {C_ACCENT_LO};
    color: {C_TEXT};
    border-left: 3px solid {C_ACCENT};
    padding-left: 11px;
    font-weight: 700;
}}
"""


# ---------------------------------------------------------------------------
# Yardımcı: ayraç
# ---------------------------------------------------------------------------

def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {C_BORDER}; border: none;")
    return f


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setFixedWidth(1)
    f.setStyleSheet(f"background: {C_BORDER}; border: none;")
    return f


# ---------------------------------------------------------------------------
# Eylem çipleri (Taşı / Sil / Atla) — tek satır için
# ---------------------------------------------------------------------------

class _ActionChips(QWidget):
    """
    Üç özel QPushButton: checkable + exclusive.
    QButtonGroup ile yalnızca biri seçili olabilir.
    """

    def __init__(self, action: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        defs = [
            ("chip_move",   "📦  Taşı",  ACTION_MOVE),
            ("chip_delete", "🗑️  Sil",   ACTION_DELETE),
            ("chip_skip",   "⏭️  Atla",  ACTION_SKIP),
        ]

        self._map: dict[str, QPushButton] = {}
        for obj_name, label, val in defs:
            btn = QPushButton(label)
            btn.setObjectName(obj_name)
            btn.setCheckable(True)
            btn.setChecked(val == action)
            btn.setStyleSheet(_CHIP_QSS)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(btn)
            self._map[val] = btn
            layout.addWidget(btn)

    def get_action(self) -> str:
        for val, btn in self._map.items():
            if btn.isChecked():
                return val
        return ACTION_MOVE


# ---------------------------------------------------------------------------
# Tek kategori satırı
# ---------------------------------------------------------------------------

class _CategoryRow(QFrame):
    """Emoji + ad + üç çip — tek yatay şerit."""

    def __init__(
        self,
        category: config.Category,
        action:   str,
        parent:   Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._cat   = category
        self._chips = _ActionChips(action, self)

        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE2};
                border-radius: 10px;
                border-left: 3px solid {category.color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Emoji
        lbl_e = QLabel(category.emoji)
        lbl_e.setFont(QFont("Segoe UI Emoji", 15))
        lbl_e.setFixedWidth(26)
        lbl_e.setStyleSheet("background: transparent; border: none;")

        # Kategori adı
        lbl_n = QLabel(category.name)
        lbl_n.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        lbl_n.setStyleSheet(f"color: {C_TEXT}; background: transparent; border: none;")
        lbl_n.setFixedWidth(102)

        layout.addWidget(lbl_e)
        layout.addWidget(lbl_n)
        layout.addStretch()
        layout.addWidget(self._chips)

    def get_action(self) -> str:
        return self._chips.get_action()

    @property
    def category(self) -> config.Category:
        return self._cat


# ---------------------------------------------------------------------------
# Sayfa 0 — Kategori Kuralları
# ---------------------------------------------------------------------------

class _PageCategories(QWidget):
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 16, 20)
        root.setSpacing(12)

        # Başlık
        hdr = QLabel("Kategori Kuralları")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_TEXT};")

        sub = QLabel(
            "Her kategori için robotu ne yapması gerektiğini seç."
        )
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C_MUTED};")
        sub.setWordWrap(True)

        root.addWidget(hdr)
        root.addWidget(sub)
        root.addWidget(_hline())

        # Chip renk lejantı
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(14)
        for color, label in [
            (C_GREEN_FG, "📦 Taşı → kategori klasörüne taşı"),
            (C_RED_FG,   "🗑️ Sil → kalıcı olarak sil"),
            (C_SKIP_FG,  "⏭️ Atla → dokunma"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10pt;")
            lbl = QLabel(label)
            lbl.setFont(QFont("Segoe UI", 8))
            lbl.setStyleSheet(f"color: {C_MUTED};")
            legend_layout.addWidget(dot)
            legend_layout.addWidget(lbl)
        legend_layout.addStretch()
        root.addLayout(legend_layout)

        # Kaydırılabilir satır listesi
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea   {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {C_SURFACE};
                width: 5px;
                border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,20);
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 2, 8, 2)
        inner_lay.setSpacing(6)

        self._rows: list[_CategoryRow] = []
        for cat in CATEGORIES:
            action = settings.category_rules.get(cat.name, ACTION_MOVE)
            row = _CategoryRow(cat, action)
            inner_lay.addWidget(row)
            self._rows.append(row)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

    def get_rules(self) -> dict[str, str]:
        return {row.category.name: row.get_action() for row in self._rows}


# ---------------------------------------------------------------------------
# Sayfa 1 — Hedef Klasör
# ---------------------------------------------------------------------------

class _PageTargetFolder(QWidget):
    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Başlık
        hdr = QLabel("Hedef Klasör")
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C_TEXT};")

        sub = QLabel("Taşınan dosyaların yerleştirileceği kök dizini belirle.")
        sub.setFont(QFont("Segoe UI", 9))
        sub.setStyleSheet(f"color: {C_MUTED};")
        sub.setWordWrap(True)

        root.addWidget(hdr)
        root.addWidget(sub)
        root.addWidget(_hline())

        # ── Seçenek: Otomatik ──────────────────────────────────────────
        self._rb_auto = self._make_radio(
            "🏠  Otomatik  (Önerilen)",
            settings.custom_target is None,
        )
        auto_path = str(config.get_desktop_path() / "Düzenlenmiş")
        auto_hint = QLabel(f"Hedef:  {auto_path}")
        auto_hint.setFont(QFont("Courier New", 8))
        auto_hint.setStyleSheet(f"color: {C_DISABLED}; padding-left: 32px;")

        root.addWidget(self._rb_auto)
        root.addWidget(auto_hint)
        root.addWidget(_hline())

        # ── Seçenek: Özel ─────────────────────────────────────────────
        self._rb_custom = self._make_radio(
            "📁  Özel Klasör",
            settings.custom_target is not None,
        )
        root.addWidget(self._rb_custom)

        # Yol + Gözat
        path_row = QHBoxLayout()
        path_row.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Klasör yolunu seçin veya yazın…")
        self._path_edit.setText(settings.custom_target or "")
        self._path_edit.setEnabled(settings.custom_target is not None)
        self._path_edit.setFixedHeight(38)
        self._path_edit.setFont(QFont("Courier New", 9))
        self._path_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {C_SURFACE2};
                color: {C_TEXT};
                border: 1px solid rgba(255,255,255,10);
                border-radius: 8px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(88,101,242,180);
            }}
            QLineEdit:disabled {{
                color: {C_DISABLED};
                background: rgba(30,31,34,200);
                border: 1px solid rgba(255,255,255,5);
            }}
        """)

        self._btn_browse = QPushButton("  Gözat…")
        self._btn_browse.setFixedSize(96, 38)
        self._btn_browse.setEnabled(settings.custom_target is not None)
        self._btn_browse.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self._btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_browse.setStyleSheet(f"""
            QPushButton {{
                background: rgba(88,101,242,200);
                color: white;
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover   {{ background: rgba(100,116,255,220); }}
            QPushButton:pressed {{ background: rgba(72, 85,210,230);  }}
            QPushButton:disabled {{
                background: rgba(50,52,65,180);
                color: {C_DISABLED};
            }}
        """)
        self._btn_browse.clicked.connect(self._browse)

        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._btn_browse)
        root.addLayout(path_row)
        root.addStretch()

        # Radyo grubu & sinyaller
        grp = QButtonGroup(self)
        grp.addButton(self._rb_auto)
        grp.addButton(self._rb_custom)

        def _on_auto_toggled(checked: bool) -> None:
            self._path_edit.setEnabled(not checked)
            self._btn_browse.setEnabled(not checked)

        self._rb_auto.toggled.connect(_on_auto_toggled)

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
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px;
                border-radius: 8px;
                border: 2px solid rgba(255,255,255,30);
                background: {C_SURFACE2};
            }}
            QRadioButton::indicator:checked {{
                background: {C_ACCENT};
                border: 2px solid {C_ACCENT};
            }}
            QRadioButton::indicator:hover {{
                border: 2px solid rgba(88,101,242,160);
            }}
        """)
        return rb

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Hedef Klasör Seç",
            self._path_edit.text() or str(config.get_desktop_path()),
        )
        if path:
            self._path_edit.setText(path)

    def get_custom_target(self) -> Optional[str]:
        if self._rb_custom.isChecked():
            text = self._path_edit.text().strip()
            return text or None
        return None


# ---------------------------------------------------------------------------
# Sidebar öğesi
# ---------------------------------------------------------------------------

class _SidebarItem(QPushButton):
    def __init__(self, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setFont(QFont("Segoe UI", 10))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(_SIDEBAR_BTN_QSS)


# ---------------------------------------------------------------------------
# Ana Ayarlar Diyaloğu
# ---------------------------------------------------------------------------

class SettingsDialog(QDialog):
    """
    Modern koyu temalı ayarlar penceresi.

    Sinyal: settings_saved(AppSettings) → Controller / main.py bağlanır.
    """

    settings_saved = pyqtSignal(object)   # AppSettings

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        parent:   Optional[QWidget]     = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or config.get_settings()

        self._setup_window()
        self._build_ui()
        self._animate_in()

    # ------------------------------------------------------------------
    # Pencere
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(_DW, _DH)

        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - _DW) // 2,
            (screen.height() - _DH) // 2,
        )

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Dış padding (gölge için boşluk)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        # Ana kart
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background: {C_BG};
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,8);
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 180))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card_layout.addWidget(self._build_titlebar())
        card_layout.addLayout(self._build_body(), 1)
        card_layout.addWidget(_hline())
        card_layout.addLayout(self._build_footer())

        outer.addWidget(card)

    # --- Başlık çubuğu ---

    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"""
            QWidget {{
                background: rgba(18,19,22,220);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }}
        """)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 16, 0)

        icon = QLabel("⚙️")
        icon.setFont(QFont("Segoe UI Emoji", 18))
        icon.setStyleSheet("background: transparent;")

        title = QLabel("Ayarlar")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT}; background: transparent;")

        btn_x = QPushButton("×")
        btn_x.setFixedSize(32, 32)
        btn_x.setFont(QFont("Segoe UI", 17))
        btn_x.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_x.setStyleSheet(f"""
            QPushButton {{
                color: rgba(180,180,200,180);
                background: transparent;
                border: none;
                border-radius: 16px;
            }}
            QPushButton:hover   {{ background: rgba(237,66,69,200); color: white; }}
            QPushButton:pressed {{ background: rgba(200,40,40,230); color: white; }}
        """)
        btn_x.clicked.connect(self.reject)

        layout.addWidget(icon)
        layout.addSpacing(10)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(btn_x)
        return bar

    # --- Gövde: sidebar + içerik ---

    def _build_body(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())
        layout.addWidget(_vline())

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {C_SURFACE};")

        self._page_cats   = _PageCategories(self._settings)
        self._page_folder = _PageTargetFolder(self._settings)
        self._stack.addWidget(self._page_cats)
        self._stack.addWidget(self._page_folder)

        layout.addWidget(self._stack, 1)
        return layout

    # --- Sidebar ---

    def _build_sidebar(self) -> QWidget:
        sb = QWidget()
        sb.setFixedWidth(_SIDEBAR_W)
        sb.setStyleSheet(f"""
            QWidget {{
                background: {C_BG};
                border-bottom-left-radius: 0px;
            }}
        """)

        layout = QVBoxLayout(sb)
        layout.setContentsMargins(10, 16, 10, 16)
        layout.setSpacing(4)

        self._sb_items: list[_SidebarItem] = []
        pages = [
            ("📋  Kategori Kuralları", 0),
            ("📁  Hedef Klasör",       1),
        ]

        for label, idx in pages:
            btn = _SidebarItem(label)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda _, i=idx: self._switch(i))
            self._sb_items.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Versiyon / bilgi
        hint = QLabel("Masaüstü Robot Süpürge")
        hint.setFont(QFont("Segoe UI", 7))
        hint.setStyleSheet(f"color: rgba(78,80,88,200); padding-left: 8px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        return sb

    def _switch(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._sb_items):
            btn.setChecked(i == idx)

    # --- Footer ---

    def _build_footer(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setFont(QFont("Segoe UI", 10))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: rgba(44,46,56,200);
                color: {C_MUTED};
                border: 1px solid rgba(255,255,255,8);
                border-radius: 10px;
                padding: 0 20px;
            }}
            QPushButton:hover   {{ background: rgba(58,61,74,220); color: {C_TEXT}; }}
            QPushButton:pressed {{ background: rgba(36,38,48,240); }}
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾  Kaydet")
        btn_save.setFixedHeight(40)
        btn_save.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0 24px;
            }}
            QPushButton:hover   {{ background: rgba(100,115,255,230); }}
            QPushButton:pressed {{ background: rgba(72, 85,215,240);  }}
        """)
        btn_save.clicked.connect(self._save)

        layout.addStretch()
        layout.addWidget(btn_cancel)
        layout.addWidget(btn_save)
        return layout

    # ------------------------------------------------------------------
    # Kaydetme
    # ------------------------------------------------------------------

    def _save(self) -> None:
        new_settings = AppSettings(
            category_rules=self._page_cats.get_rules(),
            custom_target=self._page_folder.get_custom_target(),
        )
        config.apply_settings(new_settings)
        self.settings_saved.emit(new_settings)
        self.accept()

    # ------------------------------------------------------------------
    # Giriş animasyonu (fade-in)
    # ------------------------------------------------------------------

    def _animate_in(self) -> None:
        fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fx)
        fx.setOpacity(0.0)

        anim = QPropertyAnimation(fx, b"opacity", self)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
