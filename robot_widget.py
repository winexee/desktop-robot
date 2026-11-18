"""
Masaüstü Robot Süpürge — Şeffaf Overlay & Robot Animasyonu
===========================================================

QPainter Kuralları (hata önleme)
---------------------------------
  • QPainter YALNIZCA paintEvent içinde, TEK seferlik oluşturulur.
  • Her alt çizim metodu var olan painter'ı argüman olarak alır —
    kendi painter'ını yaratmaz.
  • Transform/opacity değiştiren her blok kendi save()/restore() çiftine
    sahiptir. setOpacity() kullanılmaz; alpha manuel hesaplanır.
  • Scaled pixmap her frame yeniden ölçeklenmez; boyut değişince cache güncellenir.
  • Konuşma balonunun QPainterPath'i _tick() içinde (paintEvent dışında)
    hesaplanır, paintEvent sadece çizer.

Sinyaller
----------
  settings_requested  → Controller ayarlar penceresini açar
  target_reached(int) → Controller o indeksteki dosyayı taşır
  all_targets_done(int) → Controller raporu gösterir
"""

from __future__ import annotations

import math
import pathlib
import random
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPainterPath,
    QColor, QBrush, QPen, QFont, QFontMetrics,
    QRadialGradient, QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

_BUBBLE_LIFETIME   = 150   # frame (~2.5 sn @ 60fps)
_BUBBLE_FADE_FRAME = 20    # fade-in / fade-out süresi

BUBBLE_PHRASES: list[str] = [
    "Nom nom! 😋",
    "Hapur hupur!",
    "Ne kadar çok dosya...",
    "Burası çok dağılmış!",
    "Temizlik zamanı!",
    "Ben süpürüyorum! 🧹",
    "Bu da gitti~",
    "Çöp mü? Çöp!",
    "Hızlıyım ben!",
    "Bir tane daha!",
    "Masaüstü tertemiz olacak.",
    "Yum yum yum...",
    "Vızzz vızzz~",
    "Duramam, durmam!",
    "İşte bu kadar sıranlı olmaz.",
]


# ---------------------------------------------------------------------------
# Yardımcı: Particle
# ---------------------------------------------------------------------------

class Particle:
    """Yutma efektinde fırlayan renkli parçacık."""

    __slots__ = ("x", "y", "vx", "vy", "life", "color", "size")

    COLORS = [
        QColor(255, 215,  50),
        QColor( 50, 200, 255),
        QColor(255, 100, 100),
        QColor(100, 255, 130),
        QColor(255, 160,  50),
        QColor(200, 100, 255),
    ]

    def __init__(self, x: float, y: float) -> None:
        angle      = random.uniform(0.0, 2 * math.pi)
        speed      = random.uniform(3.0, 8.0)
        self.x     = x
        self.y     = y
        self.vx    = math.cos(angle) * speed
        self.vy    = math.sin(angle) * speed
        self.life  = 1.0
        self.color = random.choice(Particle.COLORS)
        self.size  = random.uniform(4.0, 10.0)

    def update(self) -> None:
        self.x   += self.vx
        self.y   += self.vy
        self.vy  += 0.25
        self.vx  *= 0.97
        self.life -= 0.045

    @property
    def alive(self) -> bool:
        return self.life > 0.0


# ---------------------------------------------------------------------------
# Yardımcı: DustDot
# ---------------------------------------------------------------------------

class DustDot:
    """Robotun geçtiği yerde bıraktığı toz izi noktası."""

    __slots__ = ("x", "y", "life")

    def __init__(self, x: float, y: float) -> None:
        self.x    = x
        self.y    = y
        self.life = 1.0

    def update(self) -> None:
        self.life -= 0.03

    @property
    def alive(self) -> bool:
        return self.life > 0.0


# ---------------------------------------------------------------------------
# Ana Overlay Widget
# ---------------------------------------------------------------------------

class RobotOverlay(QWidget):
    """
    Tüm ekranı kaplayan şeffaf pencere.
    Tüm çizim işlemleri TEK bir QPainter örneği ile paintEvent içinde yapılır.
    """

    settings_requested = pyqtSignal()
    target_reached     = pyqtSignal(int)   # indeks
    all_targets_done   = pyqtSignal(int)   # toplam sayı

    # -------------------------------------------------------------------
    # Başlangıç
    # -------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_window()
        self._init_robot()
        self._init_animation()

    # -------------------------------------------------------------------
    # Pencere
    # -------------------------------------------------------------------

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        geo = QApplication.primaryScreen().geometry()
        self.setGeometry(geo)
        self._screen_w = geo.width()
        self._screen_h = geo.height()

    # -------------------------------------------------------------------
    # Robot iç durumu
    # -------------------------------------------------------------------

    def _init_robot(self) -> None:
        # Pozisyon & yön
        self._rx: float    = self._screen_w / 2.0
        self._ry: float    = self._screen_h - 120.0
        self._robot_size   = 64
        self._angle: float = 0.0

        # Hedef kuyruğu
        self._targets:    list[QPointF] = []
        self._target_idx: int           = 0
        self._labels:     list[str]     = []
        self._done_count: int           = 0
        self._demo_mode:  bool          = True
        self._finished:   bool          = False

        # Yutma animasyonu
        self._eating:    bool  = False
        self._eat_phase: int   = 0
        self._eat_scale: float = 1.0

        # Efektler
        self._particles:  list[Particle] = []
        self._dust:       list[DustDot]  = []
        self._dust_timer: int            = 0

        # Durum metni
        self._status: str = "🤖  Hazırlanıyor..."

        # Demo konumları
        self._generate_demo_targets()

        # PNG pixmap (yoksa None → geometrik çizim)
        self._robot_pixmap: Optional[QPixmap] = self._load_robot_pixmap()
        self._cached_px:    Optional[QPixmap] = None   # ölçeklenmiş önbellek
        self._cached_px_sz: int               = 0

        # Konuşma balonu (paintEvent dışında hesaplanır)
        self._bubble_text:    str              = ""
        self._bubble_life:    int              = 0
        self._bubble_alpha:   float            = 0.0   # 0.0–1.0
        self._bubble_path:    Optional[QPainterPath] = None
        self._bubble_txt_rect: QRectF          = QRectF()
        self._bubble_font:    QFont            = QFont("Segoe UI", 11, QFont.Weight.Bold)

    # -------------------------------------------------------------------
    # Demo hedefleri
    # -------------------------------------------------------------------

    def _generate_demo_targets(self) -> None:
        mx = int(self._screen_w * 0.12)
        my = int(self._screen_h * 0.12)
        pts: list[QPointF] = []
        for row in range(4):
            for col in range(5):
                x = mx + col * (self._screen_w - 2 * mx) / 4
                y = my + row * (self._screen_h - 2 * my) / 3
                pts.append(QPointF(x, y))
        random.shuffle(pts)
        self._targets = pts

    # -------------------------------------------------------------------
    # PNG yükleme
    # -------------------------------------------------------------------

    @staticmethod
    def _load_robot_pixmap() -> Optional[QPixmap]:
        png = pathlib.Path(__file__).parent / "assets" / "robot_supurge.png"
        if png.exists():
            px = QPixmap(str(png))
            if not px.isNull():
                return px
        return None

    def _get_scaled_pixmap(self, size: int) -> Optional[QPixmap]:
        """Ölçeklenmiş pixmap'i önbellekten al; boyut değiştiyse yenile."""
        if self._robot_pixmap is None:
            return None
        if self._cached_px is None or self._cached_px_sz != size:
            self._cached_px = self._robot_pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._cached_px_sz = size
        return self._cached_px

    # -------------------------------------------------------------------
    # Dışarıdan enjeksiyon
    # -------------------------------------------------------------------

    def set_targets(self, positions: list[QPointF], labels: list[str]) -> None:
        self._demo_mode   = False
        self._targets     = list(positions)
        self._labels      = list(labels)
        self._target_idx  = 0
        self._done_count  = 0
        self._finished    = False
        self._status      = f"📂  {len(positions)} dosya bulundu — temizlik başlıyor!"

    def set_status(self, text: str) -> None:
        self._status = text

    # -------------------------------------------------------------------
    # Animasyon kurulumu
    # -------------------------------------------------------------------

    def _init_animation(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(16)   # ~60 fps
        self._timer.start()

    # -------------------------------------------------------------------
    # Ana döngü  (paintEvent DIŞINDA — sadece veri günceller)
    # -------------------------------------------------------------------

    def _tick(self) -> None:
        """Tüm durum güncellemeleri burada. Çizim yok."""
        if self._eating:
            self._update_eat_anim()
        else:
            self._move_robot()

        self._update_bubble()      # QPainterPath hesapla (paintEvent değil)
        self._update_particles()
        self._update_dust()
        self.update()              # Qt'ya "yeniden çiz" sinyali gönder

    # -------------------------------------------------------------------
    # Hareket mantığı
    # -------------------------------------------------------------------

    def _move_robot(self) -> None:
        if self._target_idx >= len(self._targets):
            if not self._finished:
                self._finished = True
                if self._demo_mode:
                    random.shuffle(self._targets)
                    self._target_idx = 0
                    self._finished   = False
                else:
                    self._status = f"✅  {self._done_count} dosya temizlendi!"
                    self.all_targets_done.emit(self._done_count)
            return

        target = self._targets[self._target_idx]
        dx   = target.x() - self._rx
        dy   = target.y() - self._ry
        dist = math.hypot(dx, dy)

        if dist > 1.0:
            self._angle = math.degrees(math.atan2(dy, dx))

        # Toz izi
        self._dust_timer += 1
        if self._dust_timer >= 4:
            self._dust.append(DustDot(self._rx, self._ry))
            self._dust_timer = 0

        if dist < 6.0:
            reached_idx      = self._target_idx
            self._rx         = target.x()
            self._ry         = target.y()
            self._target_idx += 1
            self._done_count += 1
            self._start_eat()
            self._show_bubble(random.choice(BUBBLE_PHRASES))

            if not self._demo_mode:
                label = (self._labels[reached_idx]
                         if reached_idx < len(self._labels) else "")
                self._status = f"🍽️  Yutuldu: {label}"
                self.target_reached.emit(reached_idx)
        else:
            speed     = max(2.0, min(6.0, dist * 0.08))
            self._rx += (dx / dist) * speed
            self._ry += (dy / dist) * speed
            # Hareket esnasında %0.3 ihtimalle balon
            if self._bubble_life == 0 and random.random() < 0.003:
                self._show_bubble(random.choice(BUBBLE_PHRASES))

    # -------------------------------------------------------------------
    # Yutma animasyonu
    # -------------------------------------------------------------------

    def _start_eat(self) -> None:
        self._eating    = True
        self._eat_phase = 0
        self._spawn_particles(self._rx, self._ry)

    def _update_eat_anim(self) -> None:
        self._eat_phase += 1
        t = self._eat_phase / 30.0
        self._eat_scale = 1.0 + 0.35 * math.sin(t * math.pi)
        if self._eat_phase >= 30:
            self._eating    = False
            self._eat_scale = 1.0

    # -------------------------------------------------------------------
    # Konuşma balonu — HESAPLAMA (_tick içinde çağrılır)
    # -------------------------------------------------------------------

    def _show_bubble(self, text: str) -> None:
        """Yeni balon başlat."""
        self._bubble_text  = text
        self._bubble_life  = _BUBBLE_LIFETIME
        self._bubble_alpha = 0.0
        self._rebuild_bubble_path()

    def _update_bubble(self) -> None:
        """Her frame: alpha güncelle, path'i robot konumuna göre yenile."""
        if self._bubble_life <= 0:
            self._bubble_alpha = 0.0
            self._bubble_path  = None
            return

        self._bubble_life -= 1
        self._rebuild_bubble_path()   # robot hareket ettiği için path güncelle

        if self._bubble_life > _BUBBLE_LIFETIME - _BUBBLE_FADE_FRAME:
            # Fade-in
            self._bubble_alpha = (
                (_BUBBLE_LIFETIME - self._bubble_life) / _BUBBLE_FADE_FRAME
            )
        elif self._bubble_life < _BUBBLE_FADE_FRAME:
            # Fade-out
            self._bubble_alpha = self._bubble_life / _BUBBLE_FADE_FRAME
        else:
            self._bubble_alpha = 1.0

    def _rebuild_bubble_path(self) -> None:
        """
        Ekran koordinatlarında QPainterPath oluştur.
        paintEvent dışında çağrılır — QPainter gerektirmez.
        """
        if not self._bubble_text:
            self._bubble_path = None
            return

        font = self._bubble_font
        fm   = QFontMetrics(font)
        tw   = fm.horizontalAdvance(self._bubble_text)
        th   = fm.height()

        pad_x  = 16
        pad_y  = 10
        bw     = tw + pad_x * 2
        bh     = th + pad_y * 2
        radius = 14.0
        tail_h = 16
        tail_w = 10
        margin = 12
        half   = self._robot_size / 2

        # Balon üst-sol köşesi (robota göre ortalanmış)
        bx = self._rx - bw / 2
        by = self._ry - half - tail_h - bh - 6

        # Ekran sınır kontrolü
        bx = max(margin, min(bx, self._screen_w - bw - margin))
        by = max(margin, by)

        # Kuyruk ucu → robotun tam üstü
        tip_x  = self._rx
        tail_top_y = by + bh

        # Kuyruk tabanı (balonun alt kenarında)
        tc = max(bx + radius + tail_w, min(tip_x, bx + bw - radius - tail_w))

        # Yuvarlak dikdörtgen + kuyruk üçgeni birleştir
        body = QPainterPath()
        body.addRoundedRect(QRectF(bx, by, bw, bh), radius, radius)

        tail = QPainterPath()
        tail.moveTo(tc - tail_w / 2, tail_top_y)
        tail.lineTo(tip_x, tail_top_y + tail_h)
        tail.lineTo(tc + tail_w / 2, tail_top_y)
        tail.closeSubpath()

        self._bubble_path     = body.united(tail)
        self._bubble_txt_rect = QRectF(bx + pad_x, by + pad_y, tw, th)

    # -------------------------------------------------------------------
    # Parçacık sistemi
    # -------------------------------------------------------------------

    def _spawn_particles(self, x: float, y: float, count: int = 10) -> None:
        self._particles.extend(Particle(x, y) for _ in range(count))

    def _update_particles(self) -> None:
        for p in self._particles:
            p.update()
        self._particles = [p for p in self._particles if p.alive]

    def _update_dust(self) -> None:
        for d in self._dust:
            d.update()
        self._dust = [d for d in self._dust if d.alive]

    # ===================================================================
    # paintEvent — TEK QPainter, TÜM ÇİZİM BURADA
    # ===================================================================

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            self._paint_dust(painter)
            self._paint_particles(painter)
            self._paint_robot(painter)
            self._paint_bubble(painter)
            self._paint_status(painter)
        finally:
            painter.end()   # hata olsa bile her zaman sonlandır

    # -------------------------------------------------------------------
    # Çizim — toz izi
    # -------------------------------------------------------------------

    def _paint_dust(self, p: QPainter) -> None:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for d in self._dust:
            alpha = int(d.life * 60)
            p.setBrush(QBrush(QColor(180, 180, 180, alpha)))
            r = d.life * 5
            p.drawEllipse(QRectF(d.x - r, d.y - r, r * 2, r * 2))
        p.restore()

    # -------------------------------------------------------------------
    # Çizim — parçacıklar
    # -------------------------------------------------------------------

    def _paint_particles(self, p: QPainter) -> None:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for pt in self._particles:
            c = QColor(pt.color)
            c.setAlpha(int(pt.life * 240))
            p.setBrush(QBrush(c))
            r = pt.size * pt.life
            p.drawEllipse(QRectF(pt.x - r / 2, pt.y - r / 2, r, r))
        p.restore()

    # -------------------------------------------------------------------
    # Çizim — robot
    # -------------------------------------------------------------------

    def _paint_robot(self, p: QPainter) -> None:
        p.save()
        p.translate(self._rx, self._ry)
        p.rotate(self._angle + 90)
        p.scale(self._eat_scale, self._eat_scale)

        s = self._robot_size / 2.0

        px = self._get_scaled_pixmap(int(self._robot_size * 1.1))
        if px is not None:
            half = px.width() // 2
            p.drawPixmap(-half, -half, px)
        else:
            self._paint_robot_geometric(p, s)

        p.restore()

    def _paint_robot_geometric(self, p: QPainter, s: float) -> None:
        """Roomba tarzı geometrik robot çizimi (PNG yoksa fallback)."""
        # Gölge
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 50)))
        p.drawEllipse(QRectF(-s + 5, -s + 5, s * 2, s * 2))
        p.restore()

        # Dış gövde
        p.save()
        body = QRadialGradient(QPointF(-s * .3, -s * .3), s * 1.4)
        body.setColorAt(0.0, QColor(90,  90, 100))
        body.setColorAt(1.0, QColor(40,  40,  50))
        p.setBrush(QBrush(body))
        p.setPen(QPen(QColor(70, 70, 80), 2))
        p.drawEllipse(QRectF(-s, -s, s * 2, s * 2))
        p.restore()

        # Üst panel
        p.save()
        panel = QRadialGradient(QPointF(-s * .2, -s * .2), s)
        panel.setColorAt(0.0, QColor(110, 110, 125))
        panel.setColorAt(1.0, QColor(70,  70,  85))
        p.setBrush(QBrush(panel))
        p.setPen(Qt.PenStyle.NoPen)
        ps = s * 0.78
        p.drawEllipse(QRectF(-ps, -ps, ps * 2, ps * 2))
        p.restore()

        # Sensör çizgisi
        p.save()
        p.setPen(QPen(QColor(50, 210, 255, 180), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(-s * .5, -s * .75, s, s * .4), 0, 180 * 16)
        p.restore()

        # Gözler
        self._paint_eyes(p, s)

        # Ön fırça
        p.save()
        p.setBrush(QBrush(QColor(255, 150, 40)))
        p.setPen(QPen(QColor(200, 100, 10), 1))
        bw, bh = s * 1.1, s * 0.22
        p.drawRoundedRect(QRectF(-bw / 2, s * .62, bw, bh), 4, 4)
        p.restore()

        # Güç butonu
        p.save()
        btn = QRadialGradient(QPointF(-2, -2), 10)
        btn.setColorAt(0.0, QColor(255, 100, 100))
        btn.setColorAt(1.0, QColor(180,  30,  30))
        p.setBrush(QBrush(btn))
        p.setPen(QPen(QColor(220, 60, 60), 1.5))
        p.drawEllipse(QRectF(-9, -9, 18, 18))
        p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
        p.drawLine(QPointF(0, -6), QPointF(0, -2))
        p.drawArc(QRectF(-4, -5, 8, 8), 50 * 16, 260 * 16)
        p.restore()

    def _paint_eyes(self, p: QPainter, s: float) -> None:
        eye_y, eye_off, eye_r = -s * .28, s * .32, s * .18
        for sign in (-1, 1):
            ex = sign * eye_off
            # Parlama
            p.save()
            glow = QRadialGradient(QPointF(ex, eye_y), eye_r * 2)
            glow.setColorAt(0.0, QColor(50, 220, 255, 120))
            glow.setColorAt(1.0, QColor(50, 220, 255,   0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(ex - eye_r*2, eye_y - eye_r*2, eye_r*4, eye_r*4))
            p.restore()
            # Iris
            p.save()
            p.setBrush(QBrush(QColor(50, 220, 255)))
            p.setPen(QPen(QColor(20, 160, 200), 1))
            p.drawEllipse(QRectF(ex - eye_r, eye_y - eye_r, eye_r*2, eye_r*2))
            p.restore()
            # Pupil + highlight
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            pr = eye_r * .5
            p.setBrush(QBrush(QColor(10, 10, 20)))
            p.drawEllipse(QRectF(ex - pr, eye_y - pr, pr*2, pr*2))
            hr = eye_r * .22
            p.setBrush(QBrush(QColor(255, 255, 255, 180)))
            p.drawEllipse(QRectF(ex - eye_r*.3 - hr, eye_y - eye_r*.3 - hr, hr*2, hr*2))
            p.restore()

    # -------------------------------------------------------------------
    # Çizim — konuşma balonu
    # -------------------------------------------------------------------

    def _paint_bubble(self, p: QPainter) -> None:
        """
        Önceden hesaplanmış _bubble_path'i çizer.
        setOpacity() KULLANILMAZ — renkler manuel alpha ile oluşturulur.
        """
        if self._bubble_path is None or self._bubble_alpha <= 0.0:
            return

        a    = self._bubble_alpha       # 0.0–1.0
        path = self._bubble_path

        # ── Gölge (kendi save/restore bloğunda translate) ──
        p.save()
        p.translate(2.0, 3.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, int(55 * a))))
        p.drawPath(path)
        p.restore()

        # ── Balon gövdesi ──
        p.save()
        p.setBrush(QBrush(QColor(255, 255, 255, int(242 * a))))
        p.setPen(QPen(QColor(90, 110, 180, int(160 * a)), 1.5))
        p.drawPath(path)
        p.restore()

        # ── Metin ──
        p.save()
        p.setFont(self._bubble_font)
        p.setPen(QPen(QColor(28, 32, 58, int(255 * a))))
        p.drawText(
            self._bubble_txt_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._bubble_text,
        )
        p.restore()

    # -------------------------------------------------------------------
    # Çizim — alt durum metni
    # -------------------------------------------------------------------

    def _paint_status(self, p: QPainter) -> None:
        font = QFont("Segoe UI", 11) if self._screen_w > 1920 else QFont("Sans", 10)
        font.setBold(True)
        p.setFont(font)
        fm = QFontMetrics(font)

        text   = self._status
        pad_x  = 20
        pad_y  = 10
        tw     = fm.horizontalAdvance(text)
        th     = fm.height()
        pill_w = tw + pad_x * 2
        pill_h = th + pad_y * 2
        pill_x = (self._screen_w - pill_w) / 2
        pill_y = self._screen_h - pill_h - 24

        p.save()
        p.setBrush(QBrush(QColor(10, 10, 20, 200)))
        p.setPen(QPen(QColor(80, 80, 100, 160), 1))
        p.drawRoundedRect(QRectF(pill_x, pill_y, pill_w, pill_h),
                          pill_h / 2, pill_h / 2)
        p.setPen(QPen(QColor(230, 230, 240)))
        p.drawText(QRectF(pill_x, pill_y, pill_w, pill_h),
                   Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    # -------------------------------------------------------------------
    # Klavye kısayolları
    # -------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            self._timer.stop()
            self.close()
