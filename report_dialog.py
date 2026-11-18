"""
Masaüstü Robot Süpürge — Rapor Ekranı
=======================================
Tüm dosyalar taşındıktan sonra açılan animasyonlu özet penceresi.

Özellikler
----------
- Kategori başına renkli kart (emoji + ad + dosya sayısı + progress bar)
- Üst özet: toplam taşınan, hatalı, geçen süre
- Alt butonlar: "Klasörü Aç" ve "Kapat"
- Fade-in + yukarı kayma animasyonu
- Cross-platform klasör açma (Windows: explorer, Linux: xdg-open, macOS: open)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Optional

from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    QRect, QSize, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont,
    QFontMetrics, QLinearGradient, QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QSizePolicy, QApplication,
)

import config
from file_scanner import ScanResult, FileItem


# ---------------------------------------------------------------------------
# Stil sabitleri
# ---------------------------------------------------------------------------

BG_COLOR        = QColor(18,  20,  30)   # koyu lacivert arkaplan
CARD_BG         = QColor(28,  32,  48)   # kart arkaplanı
CARD_BORDER     = QColor(55,  60,  85)   # kart kenarlığı
TEXT_PRIMARY    = QColor(230, 232, 245)   # başlık metni
TEXT_SECONDARY  = QColor(140, 145, 170)   # açıklama metni
ACCENT_GREEN    = QColor(80,  220, 140)   # başarı rengi
ACCENT_RED      = QColor(255, 90,  90)    # hata rengi
ACCENT_BLUE     = QColor(80,  160, 255)   # buton rengi

DIALOG_W = 540
DIALOG_H = 680


# ---------------------------------------------------------------------------
# Yardımcı: cross-platform klasör açma
# ---------------------------------------------------------------------------

def open_folder(path: str) -> None:
    """İşletim sistemine göre dosya yöneticisinde klasörü aç."""
    system = sys.platform

    try:
        if system == "win32":
            os.startfile(path)                          # Windows Explorer
        elif system == "darwin":
            subprocess.Popen(["open", path])            # macOS Finder
        else:
            subprocess.Popen(["xdg-open", path])        # Linux (Nautilus, Dolphin…)
    except Exception:
        pass   # Sessizce başarısız; kritik değil


# ---------------------------------------------------------------------------
# Kategori kartı widget'ı
# ---------------------------------------------------------------------------

class CategoryCard(QFrame):
    """
    Tek bir kategoriyi gösteren kart.
    Sol: emoji + ad  |  Orta: progress bar  |  Sağ: sayı
    """

    def __init__(
        self,
        emoji:   str,
        name:    str,
        count:   int,
        total:   int,
        color:   str,
        parent:  Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._color  = QColor(color)
        self._count  = count
        self._total  = total
        self._ratio  = count / total if total > 0 else 0.0
        self._bar_w  = 0.0          # animasyonla dolacak

        self.setFixedHeight(52)
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(28, 32, 48, 220);
                border: 1px solid rgba(55, 60, 85, 180);
                border-left: 3px solid {color};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        # Emoji + ad
        lbl_emoji = QLabel(f"{emoji}")
        lbl_emoji.setFont(QFont("Segoe UI Emoji", 16))
        lbl_emoji.setFixedWidth(28)

        lbl_name = QLabel(name)
        lbl_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        lbl_name.setStyleSheet(f"color: {QColor(TEXT_PRIMARY).name()}; border: none;")
        lbl_name.setFixedWidth(90)

        # Boş alan — progress bar paintEvent'te çizilir
        self._bar_placeholder = QWidget()
        self._bar_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # Sayı
        lbl_count = QLabel(f"{count}")
        lbl_count.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_count.setStyleSheet(f"color: {color}; border: none;")
        lbl_count.setFixedWidth(36)
        lbl_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(lbl_emoji)
        layout.addWidget(lbl_name)
        layout.addWidget(self._bar_placeholder, 1)
        layout.addWidget(lbl_count)

        # Progress bar animasyonu (0 → ratio)
        self._anim_step  = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_bar)

    def start_animation(self, delay_ms: int = 0) -> None:
        """delay_ms ms sonra dolum animasyonunu başlat."""
        QTimer.singleShot(delay_ms, lambda: self._anim_timer.start(16))

    def _animate_bar(self) -> None:
        self._anim_step += 0.04
        self._bar_w = min(self._ratio, self._anim_step) * self._get_bar_max()
        self.update()
        if self._anim_step >= self._ratio:
            self._anim_timer.stop()

    def _get_bar_max(self) -> float:
        return float(self._bar_placeholder.width()) if self._bar_placeholder.width() > 0 else 160.0

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        super().paintEvent(_event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Progress bar konumu (placeholder'ın sınırları)
        bx = self._bar_placeholder.x()
        by = self.height() // 2 - 4
        bh = 8
        bw_max = self._bar_placeholder.width()

        # Arka plan izi
        painter.setBrush(QBrush(QColor(45, 50, 70)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bx, by, bw_max, bh, 4, 4)

        # Dolum kısmı
        if self._bar_w > 0:
            grad = QLinearGradient(bx, 0, bx + bw_max, 0)
            grad.setColorAt(0.0, self._color.lighter(130))
            grad.setColorAt(1.0, self._color)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(bx, by, int(self._bar_w), bh, 4, 4)

        painter.end()


# ---------------------------------------------------------------------------
# Ana rapor penceresi
# ---------------------------------------------------------------------------

class ReportDialog(QDialog):
    """
    Tüm dosyalar işlendikten sonra gösterilen özet penceresi.

    Kullanım
    --------
        dialog = ReportDialog(scan_result, elapsed_seconds)
        dialog.exec()
    """

    closed = pyqtSignal()   # Kullanıcı kapattı sinyali

    def __init__(
        self,
        result:  ScanResult,
        elapsed: float = 0.0,
        parent:  Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._result  = result
        self._elapsed = elapsed
        self._cards:  list[CategoryCard] = []

        self._setup_window()
        self._build_ui()
        self._apply_entrance_animation()

    # ------------------------------------------------------------------
    # Pencere ayarları
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setFixedSize(DIALOG_W, DIALOG_H)

        # Ekran ortasına yerleştir
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - DIALOG_W) // 2,
            (screen.height() - DIALOG_H) // 2,
        )

    # ------------------------------------------------------------------
    # UI inşası
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Dış konteyner (gradient arka plan + gölge)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        self._card_widget = QFrame()
        self._card_widget.setObjectName("mainCard")
        self._card_widget.setStyleSheet("""
            QFrame#mainCard {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(22, 25, 40, 245),
                    stop:1 rgba(14, 16, 28, 250)
                );
                border: 1px solid rgba(80, 90, 130, 160);
                border-radius: 20px;
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 160))
        self._card_widget.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self._card_widget)
        inner.setContentsMargins(28, 24, 28, 24)
        inner.setSpacing(14)

        inner.addLayout(self._build_header())
        inner.addLayout(self._build_summary())
        inner.addWidget(self._build_separator())
        inner.addWidget(self._build_category_scroll(), 1)
        inner.addWidget(self._build_separator())
        inner.addLayout(self._build_buttons())

        outer.addWidget(self._card_widget)

    # --- Başlık ---

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        # Robot emoji
        lbl_icon = QLabel("🤖")
        lbl_icon.setFont(QFont("Segoe UI Emoji", 28))
        lbl_icon.setFixedWidth(50)

        # Başlık metni
        v = QVBoxLayout()
        v.setSpacing(2)

        lbl_title = QLabel("Temizlik Tamamlandı!")
        lbl_title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {ACCENT_GREEN.name()};")

        lbl_sub = QLabel("Masaüstün artık pırıl pırıl ✨")
        lbl_sub.setFont(QFont("Segoe UI", 10))
        lbl_sub.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")

        v.addWidget(lbl_title)
        v.addWidget(lbl_sub)

        # Kapat (×) butonu
        btn_close = QPushButton("×")
        btn_close.setFixedSize(32, 32)
        btn_close.setFont(QFont("Segoe UI", 16))
        btn_close.setStyleSheet("""
            QPushButton {
                color: rgba(180,180,200,180);
                background: transparent;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: rgba(255,80,80,80);
                color: white;
            }
        """)
        btn_close.clicked.connect(self._on_close)

        layout.addWidget(lbl_icon)
        layout.addLayout(v, 1)
        layout.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignTop)
        return layout

    # --- Özet istatistikler ---

    def _build_summary(self) -> QHBoxLayout:
        result  = self._result
        moved   = sum(1 for i in result.items if i.moved)
        failed  = sum(1 for i in result.items if not i.moved)
        elapsed = self._elapsed

        def _stat(value: str, label: str, color: QColor) -> QVBoxLayout:
            v = QVBoxLayout()
            v.setSpacing(1)
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_v = QLabel(value)
            lbl_v.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
            lbl_v.setStyleSheet(f"color: {color.name()};")
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_l = QLabel(label)
            lbl_l.setFont(QFont("Segoe UI", 9))
            lbl_l.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")
            lbl_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            v.addWidget(lbl_v)
            v.addWidget(lbl_l)
            return v

        def _divider() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFixedWidth(1)
            line.setStyleSheet("background: rgba(80,90,120,100);")
            return line

        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.addLayout(_stat(str(moved), "Taşındı", ACCENT_GREEN))
        layout.addWidget(_divider())
        layout.addLayout(_stat(str(failed), "Hatalı",  ACCENT_RED if failed else TEXT_SECONDARY))
        layout.addWidget(_divider())
        layout.addLayout(_stat(f"{elapsed:.1f}s", "Süre", ACCENT_BLUE))

        return layout

    # --- Ayraç ---

    @staticmethod
    def _build_separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(70, 80, 115, 120);")
        return line

    # --- Kategori kartları (kaydırılabilir) ---

    def _build_category_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: rgba(30,34,52,180);
                width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(80,100,160,180);
                border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        by_cat    = self._result.by_category
        total_moved = sum(1 for i in self._result.items if i.moved)

        # Yalnızca dosya olan kategorileri göster, sayıya göre sırala
        for cat in config.CATEGORIES:
            items = by_cat.get(cat.name, [])
            if not items:
                continue

            card = CategoryCard(
                emoji=cat.emoji,
                name=cat.name,
                count=len(items),
                total=total_moved or 1,
                color=cat.color,
            )
            layout.addWidget(card)
            self._cards.append(card)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # --- Alt butonlar ---

    def _build_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        btn_open = QPushButton("📁  Klasörü Aç")
        btn_open.setFixedHeight(42)
        btn_open.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        btn_open.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(60,130,220,220), stop:1 rgba(80,180,255,220));
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover  { background: rgba(80,160,255,255); }
            QPushButton:pressed { background: rgba(50,110,200,255); }
        """)
        btn_open.clicked.connect(self._on_open_folder)

        btn_close = QPushButton("✕  Kapat")
        btn_close.setFixedHeight(42)
        btn_close.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(50, 55, 80, 200);
                color: rgba(200,205,225,220);
                border: 1px solid rgba(80,90,120,150);
                border-radius: 10px;
            }
            QPushButton:hover  { background: rgba(70,78,110,220); }
            QPushButton:pressed { background: rgba(40,44,65,255); }
        """)
        btn_close.clicked.connect(self._on_close)

        layout.addWidget(btn_open, 2)
        layout.addWidget(btn_close, 1)
        return layout

    # ------------------------------------------------------------------
    # Giriş animasyonu (fade-in + yukarı kayma)
    # ------------------------------------------------------------------

    def _apply_entrance_animation(self) -> None:
        # Opaklık: 0 → 1
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(380)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Konum: 30px aşağıdan yukarı kayma
        start_pos = self.pos()
        end_pos   = self.pos()
        self.move(start_pos.x(), start_pos.y() + 30)

        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(380)
        self._slide_anim.setStartValue(self.pos())
        self._slide_anim.setEndValue(end_pos)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_anim.start()
        self._slide_anim.start()

        # Animasyon bittikten sonra kartları sırayla canlandır
        QTimer.singleShot(400, self._animate_cards)

    def _animate_cards(self) -> None:
        """Her kartı 80ms arayla canlandır (stagger effect)."""
        for idx, card in enumerate(self._cards):
            card.start_animation(delay_ms=idx * 80)

    # ------------------------------------------------------------------
    # Buton eylemleri
    # ------------------------------------------------------------------

    def _on_open_folder(self) -> None:
        root = config.get_organized_root()
        root.mkdir(parents=True, exist_ok=True)
        open_folder(str(root))

    def _on_close(self) -> None:
        self.closed.emit()
        self.accept()
