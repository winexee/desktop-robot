"""
Masaüstü Robot Süpürge - Dosya Taşıyıcı (QThread)
===================================================
Dosya taşıma/silme işlemini arka plan thread'inde çalıştırır.
UI donmaz; her işlem sonrası sinyal gönderir.

AppSettings entegrasyonu
------------------------
  category_rules["Kategori"] = "move"   -> kategorize klasöre taşı
  category_rules["Kategori"] = "trash"  -> geri dönüşüm kutusuna gönder
  category_rules["Kategori"] = "delete" -> kalıcı sil (permanent_delete_enabled gerektirir)
  category_rules["Kategori"] = "skip"   -> dokunma, atla

Çalışma modları
---------------
  1. Toplu (batch) mod (`streaming=False`):
     `items` listesini işler ve tamamlanınca `all_done` yayınlar.
  2. Akış (streaming) mod (`streaming=True`):
     Robot hedefe ulaştıkça `enqueue_item(item)` ile beslenir,
     `finish()` veya `cancel()` çağrılınca sonlanır.
"""

from __future__ import annotations

import os
import pathlib
import queue
import shutil
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

import config
from config import (
    ACTION_DELETE,
    ACTION_MOVE,
    ACTION_SKIP,
    ACTION_TRASH,
    AppSettings,
)
from file_scanner import FileItem

# send2trash: zorunlu değil, yoksa Corbeille klasörüne taşınır
try:
    from send2trash import send2trash as _send2trash
    HAS_SEND2TRASH = True
except ImportError:
    _send2trash = None  # type: ignore[assignment]
    HAS_SEND2TRASH = False

# Kuyruk sonu işaretçisi
_END = object()


# ---------------------------------------------------------------------------
# Dosya işlemi sonuç türleri
# ---------------------------------------------------------------------------

class FileStatus(Enum):
    MOVED                = "moved"
    TRASHED              = "trashed"
    DELETED_PERMANENTLY  = "deleted_permanently"
    SKIPPED              = "skipped"
    FAILED               = "failed"
    CANCELLED            = "cancelled"


@dataclass
class FileResult:
    """Tek bir dosya işleminin sonucunu tanımlar."""
    item:      FileItem
    status:    FileStatus
    error_msg: str                    = ""
    dest:      Optional[pathlib.Path] = None


# ---------------------------------------------------------------------------
# Arka plan iş parçacığı
# ---------------------------------------------------------------------------

class FileWorkerThread(QThread):
    """
    QThread tabanlı arka plan dosya taşıyıcı.

    Her dosya için `file_done(FileResult)` sinyali gönderir.
    Tamamlandığında `all_done(list[FileResult])` sinyali gönderir.
    """

    # Sinyal: tek dosya tamamlandı
    file_done: pyqtSignal = pyqtSignal(object)      # FileResult

    # Sinyal: tüm dosyalar tamamlandı
    all_done: pyqtSignal = pyqtSignal(object)       # list[FileResult]

    # Sinyal: anlık durum metni (durum çubuğu için)
    status_update: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        items:      Optional[list[FileItem]] = None,
        settings:   Optional[AppSettings]    = None,
        streaming:  bool                     = False,
        total_hint: Optional[int]            = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._items         = list(items) if items is not None else []
        self._settings      = settings or config.get_settings()
        self._streaming     = streaming
        self._total_hint    = total_hint
        self._cancel_event  = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self._worker_ident: Optional[int] = None

        for item in self._items:
            self._queue.put(item)
        if not self._streaming:
            self._queue.put(_END)

    def __del__(self) -> None:
        """C++ nesnesi yok edilmeden once calisan thread'in bitmesini bekle."""
        try:
            if (
                self.isRunning()
                and QThread.currentThread() != self
                and threading.get_ident() != self._worker_ident
            ):
                self.cancel()
                self.wait(5000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Kuyruk yönetimi (streaming modu)
    # ------------------------------------------------------------------

    def enqueue_item(self, item: FileItem) -> None:
        """Akış modunda işlenmek üzere kuyruğa bir dosya ekle."""
        if not self._cancel_event.is_set():
            self._queue.put(item)

    def finish(self) -> None:
        """Akış modunda yeni dosya eklenmeyeceğini bildir."""
        self._queue.put(_END)

    # ------------------------------------------------------------------
    # Thread girişi
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Kuyruktaki dosyaları sırayla işle; iptal edilirse kalanlar CANCELLED olur."""
        self._worker_ident = threading.get_ident()
        results: list[FileResult] = []
        idx = 0

        while True:
            raw = self._queue.get()
            if raw is _END:
                break

            idx += 1
            item: FileItem = raw  # type: ignore[assignment]

            if self._cancel_event.is_set():
                result = FileResult(
                    item=item,
                    status=FileStatus.CANCELLED,
                    error_msg="Kullanıcı tarafından iptal edildi",
                )
                item.result = result
                results.append(result)
                self.file_done.emit(result)
                continue

            total = self._total_hint or len(self._items) or idx
            action = self._settings.category_rules.get(
                item.category.name, ACTION_SKIP
            )

            result = self._process_item(item, action, idx, total)
            item.result = result
            results.append(result)
            self.file_done.emit(result)

        self.all_done.emit(results)

    # ------------------------------------------------------------------
    # İptal / durdurma
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Thread'i iptal et; bekleyen kuyruk bloklanmasını çözer."""
        self._cancel_event.set()
        self._queue.put(_END)

    def stop(self, timeout_ms: int = 10000) -> None:
        """Thread'i durdur ve bitmesini bekle."""
        self.cancel()
        self.wait(timeout_ms)

    # ------------------------------------------------------------------
    # Tek dosya işleme
    # ------------------------------------------------------------------

    def _process_item(
        self,
        item:   FileItem,
        action: str,
        idx:    int,
        total:  int,
    ) -> FileResult:
        """
        Dosyayı belirtilen eyleme göre işle.
        Sembolik bağlantılar reddedilir; kaynak dosya yoksa FAILED döner.
        """
        # Sembolik bağlantı kontrolü (kırık symlink dahil)
        if item.path.is_symlink():
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Sembolik bağlantılar işlenmez",
            )

        # Kaynak dosya varlığı kontrolü
        if not item.path.exists():
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Kaynak dosya bulunamadı",
            )

        if action == ACTION_MOVE:
            self.status_update.emit(
                f"Taşınıyor: {item.path.name} ({idx}/{total})"
            )
            return self._move_file(item)

        if action == ACTION_TRASH:
            self.status_update.emit(
                f"Geri dönüşüme gönderiliyor: {item.path.name} ({idx}/{total})"
            )
            return self._trash_file(item)

        if action == ACTION_DELETE:
            self.status_update.emit(
                f"Siliniyor: {item.path.name} ({idx}/{total})"
            )
            return self._delete_file(item)

        # ACTION_SKIP veya bilinmeyen eylem -> dokunma
        self.status_update.emit(f"Atlandı: {item.path.name}")
        return FileResult(item=item, status=FileStatus.SKIPPED)

    # ------------------------------------------------------------------
    # Çöp Kutusu
    # ------------------------------------------------------------------

    def _trash_file(self, item: FileItem) -> FileResult:
        """
        Dosyayı geri dönüşüm kutusuna gönder.
        send2trash yoksa hedef kök altındaki 'Corbeille' klasörüne taşı.
        """
        if item.path.is_symlink():
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Sembolik bağlantılar işlenmez",
            )

        try:
            if HAS_SEND2TRASH and _send2trash is not None:
                _send2trash(str(item.path))
                return FileResult(item=item, status=FileStatus.TRASHED)

            # Fallback: Corbeille klasörüne taşı
            try:
                target_root = self._settings.get_target_root()
            except ValueError as exc:
                return FileResult(
                    item=item,
                    status=FileStatus.FAILED,
                    error_msg=str(exc),
                )

            corbeille = target_root / "Corbeille"
            if not self._check_writable(corbeille):
                return FileResult(
                    item=item,
                    status=FileStatus.FAILED,
                    error_msg=f"Dizine yazma izni yok: {corbeille}",
                )

            corbeille.mkdir(parents=True, exist_ok=True)
            dest = self._resolve_conflict(corbeille, item.path.name)

            if item.path.resolve() == dest.resolve():
                return FileResult(
                    item=item,
                    status=FileStatus.SKIPPED,
                    dest=dest,
                    error_msg="Kaynak ve hedef aynı konum",
                )

            shutil.move(str(item.path), str(dest))
            if not dest.exists():
                return FileResult(
                    item=item,
                    status=FileStatus.FAILED,
                    error_msg="Dosya çöp klasöründe doğrulanamadı",
                )

            item.dest = dest
            return FileResult(item=item, status=FileStatus.TRASHED, dest=dest)

        except FileNotFoundError:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Kaynak dosya bulunamadı",
            )
        except PermissionError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"İzin hatası: {exc}",
            )
        except OSError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"OS hatası: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"Beklenmeyen hata: {exc}",
            )

    # ------------------------------------------------------------------
    # Kalıcı silme
    # ------------------------------------------------------------------

    def _delete_file(self, item: FileItem) -> FileResult:
        """
        Dosyayı kalıcı olarak sil.
        permanent_delete_enabled False ise TRASHED olarak işle.
        """
        if not self._settings.permanent_delete_enabled:
            # Güvenli mod: kalıcı silme yerine geri dönüşüme gönder
            return self._trash_file(item)

        if item.path.is_symlink():
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Sembolik bağlantılar işlenmez",
            )

        try:
            item.path.unlink()
            item.dest = None
            return FileResult(item=item, status=FileStatus.DELETED_PERMANENTLY)
        except FileNotFoundError:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Kaynak dosya bulunamadı",
            )
        except PermissionError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"İzin hatası: {exc}",
            )
        except OSError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"OS hatası: {exc}",
            )

    # ------------------------------------------------------------------
    # Dosya taşıma
    # ------------------------------------------------------------------

    def _move_file(self, item: FileItem) -> FileResult:
        """
        Dosyayı hedef kategorize klasörüne taşı.
        Çakışma durumunda 'dosya (1).ext' şeklinde numara ekler.
        """
        if item.path.is_symlink():
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Sembolik bağlantılar işlenmez",
            )

        try:
            target_root = self._settings.get_target_root()
        except ValueError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=str(exc),
            )

        try:
            dest_dir = target_root / item.category.name

            # Hedef dizin yazılabilirlik kontrolü
            if not self._check_writable(dest_dir):
                return FileResult(
                    item=item,
                    status=FileStatus.FAILED,
                    error_msg=f"Dizine yazma izni yok: {dest_dir}",
                )

            dest_dir.mkdir(parents=True, exist_ok=True)

            # Kaynak dosya zaten aynı hedef dizindeyse üzerine yazma/yeniden adlandırma yapma
            candidate = dest_dir / item.path.name
            if candidate.exists() and item.path.resolve() == candidate.resolve():
                return FileResult(
                    item=item,
                    status=FileStatus.SKIPPED,
                    dest=candidate,
                    error_msg="Kaynak ve hedef aynı konum",
                )

            dest_path = self._resolve_conflict(dest_dir, item.path.name)
            if item.path.resolve() == dest_path.resolve():
                return FileResult(
                    item=item,
                    status=FileStatus.SKIPPED,
                    dest=dest_path,
                    error_msg="Kaynak ve hedef aynı konum",
                )

            shutil.move(str(item.path), str(dest_path))
            if not dest_path.exists():
                return FileResult(
                    item=item,
                    status=FileStatus.FAILED,
                    error_msg="Dosya taşındıktan sonra hedefte doğrulanamadı",
                )

            item.dest = dest_path
            return FileResult(item=item, status=FileStatus.MOVED, dest=dest_path)

        except FileNotFoundError:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg="Kaynak dosya bulunamadı",
            )
        except PermissionError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"İzin hatası: {exc}",
            )
        except OSError as exc:
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"OS hatası: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return FileResult(
                item=item,
                status=FileStatus.FAILED,
                error_msg=f"Beklenmeyen hata: {exc}",
            )

    # ------------------------------------------------------------------
    # Yardımcı metotlar
    # ------------------------------------------------------------------

    @staticmethod
    def _check_writable(directory: pathlib.Path) -> bool:
        """
        Dizin yazılabilir mi kontrol et.
        Dizin henüz mevcut değilse var olan en yakın üst dizini kontrol eder.
        """
        check = pathlib.Path(directory).resolve()
        while not check.exists():
            parent = check.parent
            if parent == check:
                return False
            check = parent
        if not check.is_dir():
            return False
        return os.access(check, os.W_OK)

    @staticmethod
    def _resolve_conflict(dest_dir: pathlib.Path, filename: str) -> pathlib.Path:
        """
        Hedef dizinde aynı isimde dosya varsa numara ekle.

        Örnek: rapor.pdf -> rapor (1).pdf -> rapor (2).pdf
        """
        dest = dest_dir / filename
        if not dest.exists():
            return dest

        stem    = pathlib.Path(filename).stem
        suffix  = pathlib.Path(filename).suffix
        counter = 1

        while True:
            new_name = f"{stem} ({counter}){suffix}"
            dest = dest_dir / new_name
            if not dest.exists():
                return dest
            counter += 1


# ---------------------------------------------------------------------------
# Geriye dönük uyumluluk takma adı
# ---------------------------------------------------------------------------

FileMover = FileWorkerThread
