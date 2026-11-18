"""
Masaüstü Robot Süpürge — Dosya Tarayıcı
=========================================
Masaüstündeki dosyaları tarar, kategorilere ayırır ve
robot animasyonu için ekran koordinatları üretir.

Kullanım
--------
    scanner = FileScanner()
    result  = scanner.scan()          # ScanResult döner
    for item in result.items:
        print(item.path, item.category.name, item.screen_pos)
"""

from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRect
from PyQt6.QtWidgets import QApplication

import config
from config import Category, get_category, get_desktop_path


# ---------------------------------------------------------------------------
# Veri modelleri
# ---------------------------------------------------------------------------

@dataclass
class FileItem:
    """Masaüstünde bulunan tek bir dosyayı temsil eder."""
    path:       pathlib.Path   # tam dosya yolu
    category:   Category       # hangi kategoriye ait
    screen_pos: QPointF        # robotun gideceği simüle ekran konumu
    moved:      bool = False   # taşındı mı?
    dest:       pathlib.Path | None = None  # taşındıktan sonra hedef yol


@dataclass
class ScanResult:
    """scan() metodunun döndürdüğü özet."""
    items:         list[FileItem]       = field(default_factory=list)
    skipped_dirs:  list[pathlib.Path]   = field(default_factory=list)
    skipped_names: list[str]            = field(default_factory=list)
    desktop_path:  pathlib.Path | None  = None

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def by_category(self) -> dict[str, list[FileItem]]:
        """Kategori adına göre gruplanmış sözlük."""
        groups: dict[str, list[FileItem]] = {}
        for item in self.items:
            groups.setdefault(item.category.name, []).append(item)
        return groups


# ---------------------------------------------------------------------------
# Tarayıcı
# ---------------------------------------------------------------------------

class FileScanner:
    """
    Masaüstü dosya tarayıcısı.

    Sadece üst düzey dosyaları tarar (alt dizinlere inmez).
    Dizinler, gizli dosyalar ve SKIP_NAMES listesindeki isimler atlanır.
    """

    def __init__(self) -> None:
        self._screen_rect: QRect = QApplication.primaryScreen().geometry()

    # ------------------------------------------------------------------
    # Ana tarama metodu
    # ------------------------------------------------------------------

    def scan(self) -> ScanResult:
        """
        Masaüstünü tara ve ScanResult döndür.
        Hata durumunda boş ScanResult döner.
        """
        result = ScanResult(desktop_path=get_desktop_path())
        desktop = result.desktop_path

        if not desktop or not desktop.exists():
            return result

        # Hedef klasörünü tara dışı bırak
        organized_root = config.get_organized_root()

        raw_files: list[pathlib.Path] = []

        try:
            for entry in desktop.iterdir():
                # Dizinleri atla (organize root dahil)
                if entry.is_dir():
                    result.skipped_dirs.append(entry)
                    continue

                # Gizli dosyaları atla (Linux: nokta ile başlar)
                if entry.name.startswith("."):
                    result.skipped_names.append(entry.name)
                    continue

                # Özel sistem dosyalarını atla
                if entry.name in config.SKIP_NAMES:
                    result.skipped_names.append(entry.name)
                    continue

                raw_files.append(entry)

        except PermissionError:
            return result

        # Ekran konumlarını ızgara üzerinde dağıt
        positions = self._generate_grid_positions(len(raw_files))

        for path, pos in zip(raw_files, positions):
            suffix = path.suffix
            category = get_category(suffix)
            result.items.append(FileItem(
                path=path,
                category=category,
                screen_pos=pos,
            ))

        return result

    # ------------------------------------------------------------------
    # Izgara koordinat üreteci
    # ------------------------------------------------------------------

    def _generate_grid_positions(self, count: int) -> list[QPointF]:
        """
        Ekranı ızgaraya bölerek dosya başına bir koordinat üret.
        Robotun gerçekçi gezinmesi için hafifçe rastgele kaydırılır.

        Masaüstü ikonlarının gerçek piksel konumunu okumak OS-spesifik
        API gerektirir (Windows: SHGetFileInfo, Linux: Nautilus DBus),
        bu yüzden simüle ızgara kullanılır.
        """
        if count == 0:
            return []

        sw = self._screen_rect.width()
        sh = self._screen_rect.height()
        mx = config.SCREEN_MARGIN_X
        my = config.SCREEN_MARGIN_Y

        usable_w = sw - 2 * mx
        usable_h = sh - 2 * my

        # İkon boyutu (~80px) + boşluk
        ICON_W = 90
        ICON_H = 90

        cols = max(1, usable_w // ICON_W)
        rows = max(1, usable_h // ICON_H)
        capacity = cols * rows

        positions: list[QPointF] = []

        for i in range(count):
            cell = i % capacity
            col  = cell % cols
            row  = cell // cols

            # Merkez koordinatı
            cx = mx + col * ICON_W + ICON_W / 2
            cy = my + row * ICON_H + ICON_H / 2

            # ±10px jitter (piksel mükemmelliğinden kaçın)
            jx = random.uniform(-10, 10)
            jy = random.uniform(-10, 10)

            positions.append(QPointF(cx + jx, cy + jy))

        # Karıştır: robot rastgele sırayla gezmeli
        random.shuffle(positions)
        return positions
