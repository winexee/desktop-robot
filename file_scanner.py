"""
Masaüstü Robot Süpürge - Dosya Tarayıcı
=======================================
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

import math
import pathlib
import random
import stat
import sys
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QObject, QPointF, QRect, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

import config
from config import Category

if TYPE_CHECKING:
    from file_mover import FileResult


# ---------------------------------------------------------------------------
# Veri modelleri
# ---------------------------------------------------------------------------

@dataclass
class FileItem:
    """Masaüstünde bulunan tek bir dosyayı temsil eder."""
    path:       pathlib.Path                  # tam dosya yolu
    category:   Category                      # hangi kategoriye ait
    screen_pos: QPointF                       # robotun gideceği ekran konumu
    dest:       pathlib.Path | None = None    # taşındıktan sonra hedef yol
    result:     Optional[FileResult] = None   # işlem sonucu


@dataclass
class ScanResult:
    """scan() metodunun döndürdüğü özet."""
    items:                list[FileItem]       = field(default_factory=list)
    skipped_dirs:         list[pathlib.Path]   = field(default_factory=list)
    skipped_names:        list[str]            = field(default_factory=list)
    desktop_path:         pathlib.Path | None  = None
    scan_subfolders_note: str                  = ""
    positions_simulated:  bool                 = True

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
# Gerçek Masaüstü İkon Konumu Sağlayıcısı (Windows Explorer)
# ---------------------------------------------------------------------------

def _get_windows_desktop_icon_positions() -> Optional[dict[str, QPointF]]:
    """
    Windows Explorer masaüstü ikon konumlarını okumayı dener.
    Linux/macOS üzerinde veya erişilemez durumda None döner.
    Dönen koordinatlar fiziksel ekran piksel koordinatlarıdır.
    """
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # 64-bit işaretçi güvenliği için argtypes / restype tanımları
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND

        user32.FindWindowExW.argtypes = [
            wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR
        ]
        user32.FindWindowExW.restype = wintypes.HWND

        user32.SendMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.SendMessageW.restype = ctypes.c_ssize_t

        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        user32.ClientToScreen.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.POINT)
        ]
        user32.ClientToScreen.restype = wintypes.BOOL

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL

        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD, wintypes.BOOL, wintypes.DWORD
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE

        kernel32.VirtualAllocEx.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t,
            wintypes.DWORD, wintypes.DWORD
        ]
        kernel32.VirtualAllocEx.restype = wintypes.LPVOID

        kernel32.VirtualFreeEx.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD
        ]
        kernel32.VirtualFreeEx.restype = wintypes.BOOL

        kernel32.ReadProcessMemory.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
        ]
        kernel32.ReadProcessMemory.restype = wintypes.BOOL

        kernel32.WriteProcessMemory.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCVOID,
            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
        ]
        kernel32.WriteProcessMemory.restype = wintypes.BOOL

        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        # 1. Masaüstü SysListView32 penceresini bul (Progman veya WorkerW içinde)
        defview = None
        progman = user32.FindWindowW("Progman", None)
        if progman:
            defview = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)

        if not defview:
            found_defview: list[Optional[int]] = [None]

            def _enum_cb(hwnd: int, _lparam: int) -> bool:
                child = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
                if child:
                    found_defview[0] = child
                    return False
                return True

            cb = WNDENUMPROC(_enum_cb)
            user32.EnumWindows(cb, 0)
            defview = found_defview[0]

        if not defview:
            return None

        listview = user32.FindWindowExW(defview, None, "SysListView32", "FolderView")
        if not listview:
            listview = user32.FindWindowExW(defview, None, "SysListView32", None)
        if not listview:
            return None

        LVM_GETITEMCOUNT = 0x1004
        LVM_GETITEMPOSITION = 0x1010
        LVM_GETITEMTEXTW = 0x1073
        LVIF_TEXT = 0x0001

        count = int(user32.SendMessageW(listview, LVM_GETITEMCOUNT, 0, 0))
        if count <= 0:
            return None

        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(listview, ctypes.byref(pid))
        if not pid.value:
            return None

        PROCESS_VM_OPERATION = 0x0008
        PROCESS_VM_READ = 0x0010
        PROCESS_VM_WRITE = 0x0020
        MEM_COMMIT = 0x1000
        MEM_RESERVE = 0x2000
        MEM_RELEASE = 0x8000
        PAGE_READWRITE = 0x04

        h_proc = kernel32.OpenProcess(
            PROCESS_VM_OPERATION | PROCESS_VM_READ | PROCESS_VM_WRITE,
            False,
            pid.value,
        )
        if not h_proc:
            return None

        class LVITEMW(ctypes.Structure):
            _fields_ = [
                ("mask", wintypes.UINT),
                ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int),
                ("state", wintypes.UINT),
                ("stateMask", wintypes.UINT),
                ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int),
                ("lParam", ctypes.c_ssize_t),
                ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int),
                ("cColumns", wintypes.UINT),
                ("puColumns", ctypes.c_void_p),
                ("piColFmt", ctypes.c_void_p),
                ("iGroup", ctypes.c_int),
            ]

        MAX_TEXT_CHARS = 260
        text_buf_bytes = MAX_TEXT_CHARS * ctypes.sizeof(ctypes.c_wchar)
        point_size = ctypes.sizeof(wintypes.POINT)
        lvitem_size = ctypes.sizeof(LVITEMW)
        total_alloc = point_size + lvitem_size + text_buf_bytes

        remote_mem = None
        positions: dict[str, QPointF] = {}

        try:
            remote_mem = kernel32.VirtualAllocEx(
                h_proc, None, total_alloc, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
            )
            if not remote_mem:
                return None

            remote_pt = remote_mem
            remote_lv = remote_mem + point_size
            remote_txt = remote_lv + lvitem_size

            pt_local = wintypes.POINT()
            txt_local = ctypes.create_unicode_buffer(MAX_TEXT_CHARS)
            bytes_rw = ctypes.c_size_t(0)

            for idx in range(count):
                ok_pos = user32.SendMessageW(
                    listview, LVM_GETITEMPOSITION, idx, remote_pt
                )
                if not ok_pos:
                    continue

                if not kernel32.ReadProcessMemory(
                    h_proc,
                    remote_pt,
                    ctypes.byref(pt_local),
                    point_size,
                    ctypes.byref(bytes_rw),
                ):
                    continue

                lv = LVITEMW()
                lv.mask = LVIF_TEXT
                lv.iItem = idx
                lv.iSubItem = 0
                lv.pszText = remote_txt
                lv.cchTextMax = MAX_TEXT_CHARS

                if not kernel32.WriteProcessMemory(
                    h_proc,
                    remote_lv,
                    ctypes.byref(lv),
                    lvitem_size,
                    ctypes.byref(bytes_rw),
                ):
                    continue

                length = int(
                    user32.SendMessageW(listview, LVM_GETITEMTEXTW, idx, remote_lv)
                )
                if length <= 0:
                    continue

                ctypes.memset(txt_local, 0, text_buf_bytes)
                if not kernel32.ReadProcessMemory(
                    h_proc,
                    remote_txt,
                    txt_local,
                    text_buf_bytes,
                    ctypes.byref(bytes_rw),
                ):
                    continue

                name = txt_local.value
                if not name:
                    continue

                user32.ClientToScreen(listview, ctypes.byref(pt_local))
                positions[name] = QPointF(
                    float(pt_local.x + 32), float(pt_local.y + 32)
                )

        finally:
            if remote_mem:
                kernel32.VirtualFreeEx(h_proc, remote_mem, 0, MEM_RELEASE)
            kernel32.CloseHandle(h_proc)

        return positions if positions else None

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tarayıcı
# ---------------------------------------------------------------------------

class FileScanner:
    """
    Masaüstü dosya tarayıcısı.

    Sadece üst düzey dosyaları tarar (alt dizinlere inmez).
    Dizinler, sembolik bağlantılar, özel dosyalar ve SKIP_NAMES listesindeki
    isimler atlanır. skip_hidden_files ayarına göre gizli dosyalar atlanabilir.
    """

    def __init__(self) -> None:
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is None and app is not None and QApplication.screens():
            screen = QApplication.screens()[0]
        self._screen_rect = (
            screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        )
        self._dpr = screen.devicePixelRatio() if screen else 1.0

    # ------------------------------------------------------------------
    # Ana tarama metodu
    # ------------------------------------------------------------------

    def scan(
        self,
        scan_subfolders: bool = False,
        cancel_event: Optional[threading.Event] = None,
    ) -> ScanResult:
        """
        Masaüstünü tara ve ScanResult döndür.
        Hata durumunda boş ScanResult döner.
        scan_subfolders parametresi şu an rezerve edilmiştir (ilerisi için).
        """
        result = ScanResult(desktop_path=config.get_desktop_path())
        desktop = result.desktop_path

        if scan_subfolders:
            result.scan_subfolders_note = (
                "Alt klasör tarama henüz desteklenmemektedir; "
                "yalnızca üst düzey dosyalar taranmıştır."
            )
        else:
            result.scan_subfolders_note = (
                "Alt klasörler taranmaz; yalnızca üst düzey dosyalar işlenir."
            )

        if not desktop or not desktop.exists():
            return result

        settings = config.get_settings()

        # Varsayılan hedef klasörü ve aktif özel hedef klasörü tarama dışı bırak
        excluded_roots: set[pathlib.Path] = set()
        try:
            excluded_roots.add(config.get_organized_root().resolve())
        except Exception:
            pass
        try:
            excluded_roots.add(settings.get_target_root().resolve())
        except Exception:
            pass

        raw_files: list[pathlib.Path] = []

        try:
            entries = list(desktop.iterdir())
        except (PermissionError, OSError):
            return result

        for entry in entries:
            if cancel_event is not None and cancel_event.is_set():
                return ScanResult(
                    desktop_path=desktop,
                    scan_subfolders_note=result.scan_subfolders_note,
                )

            try:
                # organized_root ve aktif target_root dizinlerini atla
                if excluded_roots:
                    try:
                        if entry.resolve() in excluded_roots:
                            result.skipped_dirs.append(entry)
                            continue
                    except OSError:
                        pass

                # Sembolik linkleri atla
                if entry.is_symlink():
                    result.skipped_names.append(entry.name)
                    continue

                # Sadece normal dosyalar
                if not entry.is_file():
                    if entry.is_dir():
                        result.skipped_dirs.append(entry)
                    continue

                # Özel sistem dosyalarını atla (FIFO, soket, blok/karakter aygıtı)
                try:
                    mode = entry.stat().st_mode
                    if (
                        stat.S_ISFIFO(mode)
                        or stat.S_ISSOCK(mode)
                        or stat.S_ISBLK(mode)
                        or stat.S_ISCHR(mode)
                    ):
                        result.skipped_names.append(entry.name)
                        continue
                except OSError:
                    result.skipped_names.append(entry.name)
                    continue

                # Gizli dosyaları atla
                if settings.skip_hidden_files and entry.name.startswith("."):
                    result.skipped_names.append(entry.name)
                    continue

                # Özel sistem dosya isimlerini atla
                if entry.name in config.SKIP_NAMES:
                    result.skipped_names.append(entry.name)
                    continue

                raw_files.append(entry)

            except (PermissionError, OSError):
                result.skipped_names.append(entry.name)
                continue

        if not raw_files:
            result.positions_simulated = True
            return result

        # Gerçek masaüstü ikon konumlarını okumayı dene; başarısızsa ızgara fallback
        positions, simulated = self._resolve_positions(raw_files)
        result.positions_simulated = simulated

        for path, pos in zip(raw_files, positions):
            category = config.get_category(path.suffix)
            result.items.append(FileItem(
                path=path,
                category=category,
                screen_pos=pos,
            ))

        return result

    # ------------------------------------------------------------------
    # Konum çözümleme (gerçek masaüstü ikonları veya simüle ızgara)
    # ------------------------------------------------------------------

    def _resolve_positions(
        self, raw_files: list[pathlib.Path]
    ) -> tuple[list[QPointF], bool]:
        """
        Windows masaüstünde gerçek ikon konumlarını eşleştirmeyi dener.
        Tüm dosyalar eşleştirilemezse simüle ızgara konumlarına düşer.
        """
        fallback_positions = self._generate_grid_positions(len(raw_files))
        icon_positions = _get_windows_desktop_icon_positions()
        if not icon_positions:
            return fallback_positions, True

        lower_map = {k.lower(): v for k, v in icon_positions.items()}

        # Benzersiz stem'leri bul (uzantı gizli olduğunda güvenli eşleştirme)
        stem_counts: dict[str, int] = {}
        for p in raw_files:
            sl = p.stem.lower()
            stem_counts[sl] = stem_counts.get(sl, 0) + 1

        dpr = self._dpr if self._dpr > 0 else 1.0
        ox = self._screen_rect.x()
        oy = self._screen_rect.y()

        resolved: list[QPointF] = []
        all_matched = True

        for idx, path in enumerate(raw_files):
            pos = icon_positions.get(path.name) or lower_map.get(path.name.lower())
            if pos is None and stem_counts.get(path.stem.lower(), 0) == 1:
                pos = lower_map.get(path.stem.lower())

            if pos is not None:
                resolved.append(QPointF(pos.x() / dpr - ox, pos.y() / dpr - oy))
            else:
                all_matched = False
                resolved.append(fallback_positions[idx])

        return resolved, (not all_matched)

    # ------------------------------------------------------------------
    # Izgara koordinat üreteci
    # ------------------------------------------------------------------

    def _generate_grid_positions(self, count: int) -> list[QPointF]:
        """
        Ekranı ızgaraya bölerek dosya başına bir koordinat üret.
        Robotun gerçekçi gezinmesi için hafifçe rastgele kaydırılır.

        count > kapasite durumunda satır sayısı dinamik olarak artırılır;
        hiçbir pozisyon tekrar edilmez.
        """
        if count == 0:
            return []

        sw = self._screen_rect.width()
        sh = self._screen_rect.height()
        mx = config.SCREEN_MARGIN_X
        my = config.SCREEN_MARGIN_Y

        usable_w = sw - 2 * mx

        ICON_W = 90
        ICON_H = 90

        cols = max(1, usable_w // ICON_W)

        # Dinamik satır hesabı: tüm dosyalar için benzersiz hücreler
        _rows = max(1, math.ceil(count / cols))

        JITTER = 8  # piksel

        positions: list[QPointF] = []
        for i in range(count):
            col = i % cols
            row = i // cols

            cx = mx + col * ICON_W + ICON_W / 2
            cy = my + row * ICON_H + ICON_H / 2

            jx = random.uniform(-JITTER, JITTER)
            jy = random.uniform(-JITTER, JITTER)

            positions.append(QPointF(cx + jx, cy + jy))

        random.shuffle(positions)
        return positions


# ---------------------------------------------------------------------------
# Arka plan tarama iş parçacığı (QThread)
# ---------------------------------------------------------------------------

class ScanWorkerThread(QThread):
    """
    Masaüstü taramasını arka plan thread'inde çalıştırır.
    Tamamlandığında scan_finished(ScanResult) sinyali yayınlar.
    """

    scan_finished: pyqtSignal = pyqtSignal(object)  # ScanResult
    status_update: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        scanner: Optional[FileScanner] = None,
        scan_subfolders: bool = False,
        parent: Optional[QObject] = None,
    ) -> None:
        if scanner is not None and not isinstance(scanner, FileScanner):
            if isinstance(scanner, QObject) and parent is None:
                parent = scanner
                scanner = None
        super().__init__(parent)
        self._scanner = scanner if scanner is not None else FileScanner()
        self._scan_subfolders = scan_subfolders
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Taramayı iptal etmek için işaret koy."""
        self._cancel_event.set()

    def stop(self, timeout_ms: int = 5000) -> None:
        """Tarama thread'ini durdur ve bitmesini bekle."""
        self._cancel_event.set()
        self.wait(timeout_ms)

    def run(self) -> None:
        self.status_update.emit("Masaüstü taranıyor...")
        try:
            result = self._scanner.scan(
                scan_subfolders=self._scan_subfolders,
                cancel_event=self._cancel_event,
            )
        except Exception:
            result = ScanResult(desktop_path=config.get_desktop_path())

        self.status_update.emit(f"Tarama tamamlandı: {result.total} dosya bulundu.")
        self.scan_finished.emit(result)
