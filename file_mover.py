"""
Masaüstü Robot Süpürge — Dosya Taşıyıcı (QThread)
===================================================
Dosya taşıma/silme işlemini arka plan thread'inde çalıştırır.
UI donmaz; her işlem sonrası sinyal gönderir.

AppSettings entegrasyonu
------------------------
  category_rules["Kategori"] = "move"   → kategorize klasöre taşı
  category_rules["Kategori"] = "delete" → kalıcı sil
  category_rules["Kategori"] = "skip"   → dokunma, atla

Sinyal akışı
------------
    FileMover.start()
        → her dosya için: file_moved(item, success, error_msg)
        → tüm dosyalar sonunda: all_done(moved_count, failed_count)
"""

from __future__ import annotations

import os
import shutil
import pathlib
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

import config
from config import ACTION_MOVE, ACTION_DELETE, ACTION_SKIP, AppSettings
from file_scanner import FileItem, ScanResult


class FileMover(QThread):
    """
    QThread tabanlı arka plan dosya taşıyıcı.

    Parametre olarak ScanResult alır, her dosyayı kategoriye göre
    hedef klasöre taşır. Çakışma durumunda dosya adına numara ekler.
    """

    # Sinyal: (taşınan item, başarılı mı, hata mesajı)
    file_moved = pyqtSignal(object, bool, str)

    # Sinyal: tüm dosyalar tamamlandı (başarılı sayısı, hatalı sayısı)
    all_done = pyqtSignal(int, int)

    # Sinyal: anlık durum metni (status bar için)
    status_update = pyqtSignal(str)

    def __init__(
        self,
        scan_result: ScanResult,
        settings:    Optional[AppSettings] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._result   = scan_result
        self._settings = settings or config.get_settings()
        self._moved    = 0
        self._deleted  = 0
        self._skipped  = 0
        self._failed   = 0
        self._running  = True

    # ------------------------------------------------------------------
    # Thread giriş noktası
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Her dosyayı sırayla işle; ayarlara göre taşı / sil / atla."""
        items = self._result.items

        for idx, item in enumerate(items, start=1):
            if not self._running:
                break

            action = self._settings.category_rules.get(
                item.category.name, ACTION_MOVE
            )

            if action == ACTION_SKIP:
                self._skipped += 1
                self.status_update.emit(f"⏭️  Atlandı: {item.path.name}")
                self.file_moved.emit(item, True, "atlandı")
                continue

            if action == ACTION_DELETE:
                self.status_update.emit(f"🗑️  Siliniyor: {item.path.name}  ({idx}/{len(items)})")
            else:
                self.status_update.emit(f"📂  Taşınıyor: {item.path.name}  ({idx}/{len(items)})")

            success, error_msg = self._process_file(item, action)

            if success:
                if action == ACTION_DELETE:
                    self._deleted += 1
                else:
                    self._moved += 1
                item.moved = True
            else:
                self._failed += 1

            self.file_moved.emit(item, success, error_msg)

        self.all_done.emit(self._moved + self._deleted, self._failed)

    def stop(self) -> None:
        """Dışarıdan durdur (ESC veya pencere kapatma)."""
        self._running = False

    # ------------------------------------------------------------------
    # Tek dosya işleme (taşı veya sil)
    # ------------------------------------------------------------------

    def _process_file(self, item: FileItem, action: str) -> tuple[bool, str]:
        """
        action = "move"   → hedef klasöre taşı
        action = "delete" → kalıcı olarak sil
        """
        try:
            if action == ACTION_DELETE:
                return self._delete_file(item)
            return self._move_file(item)
        except Exception as exc:  # noqa: BLE001
            return False, f"Beklenmeyen hata: {exc}"

    def _delete_file(self, item: FileItem) -> tuple[bool, str]:
        """Dosyayı kalıcı olarak sil."""
        try:
            item.path.unlink(missing_ok=True)
            item.dest = None
            return True, ""
        except PermissionError as exc:
            return False, f"İzin hatası: {exc}"
        except OSError as exc:
            return False, f"OS hatası: {exc}"

    def _move_file(self, item: FileItem) -> tuple[bool, str]:
        """
        Dosyayı hedef kategorize klasörüne taşı.

        Returns
        -------
        (success: bool, error_message: str)
        """
        try:
            # Ayarlardan hedef kökü al (custom veya varsayılan)
            dest_dir = self._settings.get_target_root() / item.category.name
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_path = self._resolve_conflict(dest_dir, item.path.name)
            shutil.move(str(item.path), str(dest_path))

            item.dest = dest_path
            return True, ""

        except PermissionError as exc:
            return False, f"İzin hatası: {exc}"
        except FileNotFoundError as exc:
            return False, f"Dosya bulunamadı: {exc}"
        except OSError as exc:
            return False, f"OS hatası: {exc}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Beklenmeyen hata: {exc}"

    # ------------------------------------------------------------------
    # Çakışma çözümü
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_conflict(dest_dir: pathlib.Path, filename: str) -> pathlib.Path:
        """
        Hedef dizinde aynı isimde dosya varsa numara ekle.

        Örnek: rapor.pdf → rapor (2).pdf → rapor (3).pdf
        """
        dest = dest_dir / filename

        if not dest.exists():
            return dest

        stem   = pathlib.Path(filename).stem
        suffix = pathlib.Path(filename).suffix
        counter = 2

        while True:
            new_name = f"{stem} ({counter}){suffix}"
            dest = dest_dir / new_name
            if not dest.exists():
                return dest
            counter += 1
