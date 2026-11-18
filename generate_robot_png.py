"""
generate_robot_png.py — Tek seferlik çalıştır, assets/robot_supurge.png üretir.

Kullanım:
    python generate_robot_png.py

Kendi görselinizi kullanmak isterseniz:
    assets/robot_supurge.png yoluna 128×128 veya daha büyük bir PNG koyun.
"""

import sys
import pathlib
import math

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QBrush, QPen,
    QRadialGradient, QLinearGradient,
)

SIZE = 256   # px × px çıktı boyutu

def render_robot(size: int) -> QPixmap:
    """Roomba tarzı robot vacuum'u QPixmap üzerine çiz."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(size / 2, size / 2)

    s = size / 2 * 0.88   # yarıçap

    # --- Gölge ---
    shadow_grad = QRadialGradient(QPointF(5, 8), s)
    shadow_grad.setColorAt(0.6, QColor(0, 0, 0, 60))
    shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(shadow_grad))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QRectF(-s + 5, -s + 8, s * 2, s * 2))

    # --- Dış gövde ---
    body = QRadialGradient(QPointF(-s * 0.3, -s * 0.3), s * 1.5)
    body.setColorAt(0.0, QColor(105, 108, 125))
    body.setColorAt(0.5, QColor(65,  68,  82))
    body.setColorAt(1.0, QColor(35,  37,  48))
    p.setBrush(QBrush(body))
    p.setPen(QPen(QColor(80, 83, 100), 3))
    p.drawEllipse(QRectF(-s, -s, s * 2, s * 2))

    # --- Üst panel ---
    panel = QRadialGradient(QPointF(-s * 0.2, -s * 0.25), s * 0.9)
    panel.setColorAt(0.0, QColor(130, 133, 152))
    panel.setColorAt(1.0, QColor(75,  78,  95))
    p.setBrush(QBrush(panel))
    p.setPen(Qt.PenStyle.NoPen)
    ps = s * 0.76
    p.drawEllipse(QRectF(-ps, -ps, ps * 2, ps * 2))

    # --- Ön bump-sensörü (ince çizgi) ---
    p.setPen(QPen(QColor(50, 210, 255, 160), max(2, int(s * 0.04))))
    p.drawArc(QRectF(-s * 0.5, -s * 0.78, s, s * 0.42), 0, 180 * 16)

    # --- Gözler ---
    eye_y   = -s * 0.26
    eye_off =  s * 0.30
    eye_r   =  s * 0.165

    for sign in (-1, 1):
        ex = sign * eye_off

        # Parlama hâlesi
        glow = QRadialGradient(QPointF(ex, eye_y), eye_r * 2.2)
        glow.setColorAt(0.0, QColor(55, 220, 255, 100))
        glow.setColorAt(1.0, QColor(55, 220, 255, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(ex - eye_r * 2.2, eye_y - eye_r * 2.2,
                             eye_r * 4.4, eye_r * 4.4))

        # Göz beyazı (cyan)
        p.setBrush(QBrush(QColor(55, 220, 255)))
        p.setPen(QPen(QColor(20, 155, 200), 1.5))
        p.drawEllipse(QRectF(ex - eye_r, eye_y - eye_r, eye_r * 2, eye_r * 2))

        # Göz bebeği
        pr = eye_r * 0.52
        p.setBrush(QBrush(QColor(8, 10, 22)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(ex - pr, eye_y - pr, pr * 2, pr * 2))

        # Parlaklık noktası
        hr = eye_r * 0.24
        p.setBrush(QBrush(QColor(255, 255, 255, 190)))
        p.drawEllipse(QRectF(ex - eye_r * 0.28 - hr,
                             eye_y - eye_r * 0.28 - hr,
                             hr * 2, hr * 2))

    # --- Ön fırça şeridi ---
    brush_grad = QLinearGradient(QPointF(-s * 0.56, 0), QPointF(s * 0.56, 0))
    brush_grad.setColorAt(0.0, QColor(255, 120, 20))
    brush_grad.setColorAt(0.5, QColor(255, 170, 50))
    brush_grad.setColorAt(1.0, QColor(255, 120, 20))
    bw, bh = s * 1.12, s * 0.21
    p.setBrush(QBrush(brush_grad))
    p.setPen(QPen(QColor(190, 90, 10), 1))
    p.drawRoundedRect(QRectF(-bw / 2, s * 0.60, bw, bh), 5, 5)

    # Fırça tüyleri
    p.setPen(QPen(QColor(220, 90, 10, 160), 1.2))
    for i in range(9):
        fx = -bw / 2 + (i + 0.5) * bw / 9
        p.drawLine(QPointF(fx, s * 0.60), QPointF(fx, s * 0.60 + bh * 1.6))

    # --- Merkez güç butonu ---
    btn_r = s * 0.175
    btn_g = QRadialGradient(QPointF(-btn_r * 0.3, -btn_r * 0.3), btn_r * 1.6)
    btn_g.setColorAt(0.0, QColor(255, 115, 115))
    btn_g.setColorAt(1.0, QColor(170,  25,  25))
    p.setBrush(QBrush(btn_g))
    p.setPen(QPen(QColor(220, 55, 55), 2))
    p.drawEllipse(QRectF(-btn_r, -btn_r, btn_r * 2, btn_r * 2))

    # Güç sembolü
    pw = max(1.5, s * 0.03)
    p.setPen(QPen(QColor(255, 255, 255, 215), pw, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(0, -btn_r * 0.72), QPointF(0, -btn_r * 0.28))
    arc_r = btn_r * 0.52
    p.drawArc(QRectF(-arc_r, -arc_r, arc_r * 2, arc_r * 2), 50 * 16, 260 * 16)

    # --- Tekerlek / alt kısım vurgusu ---
    wheel_grad = QLinearGradient(QPointF(0, s * 0.7), QPointF(0, s))
    wheel_grad.setColorAt(0.0, QColor(50, 52, 65, 180))
    wheel_grad.setColorAt(1.0, QColor(25, 26, 35, 220))
    p.setBrush(QBrush(wheel_grad))
    p.setPen(Qt.PenStyle.NoPen)
    # Alt yarı yay
    p.drawChord(QRectF(-s * 0.65, s * 0.55, s * 1.3, s * 0.55), 180 * 16, 180 * 16)

    p.end()
    return px


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    out_dir = pathlib.Path(__file__).parent / "assets"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "robot_supurge.png"

    px = render_robot(SIZE)

    if px.save(str(out_path), "PNG"):
        print(f"✅  Görsel kaydedildi: {out_path}")
        print(f"   Boyut: {SIZE}×{SIZE} px")
        print()
        print("İpucu: Kendi görselinizi kullanmak için")
        print(f"       {out_path} yoluna PNG koyun.")
    else:
        print("❌  Görsel kaydedilemedi!")
        sys.exit(1)


if __name__ == "__main__":
    main()
