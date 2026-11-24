"""
Masaüstü Robot Süpürge - Yapılandırma
======================================
Dosya kategorileri, hedef klasör adları ve uygulama sabitleri.
Tüm modüller bu dosyadan import eder; ayar değişikliği için
sadece bu dosya düzenlenir.
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Yardımcı yol fonksiyonları
# ---------------------------------------------------------------------------

def get_asset_path(filename: str) -> pathlib.Path:
    """
    assets/<filename> için mutlak yol döndür.
    PyInstaller (sys._MEIPASS) ve geliştirme ortamı ile uyumludur.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return (pathlib.Path(base) / "assets" / filename).resolve()
    return (pathlib.Path(__file__).resolve().parent / "assets" / filename).resolve()


def open_folder(path: str | pathlib.Path) -> tuple[bool, str]:
    """
    Belirtilen klasörü işletim sisteminin dosya yöneticisinde aç.
    Başarılıysa (True, ""), hata varsa (False, hata_mesajı) döndürür.
    """
    target = pathlib.Path(path)
    if not target.exists():
        return False, f"Klasör bulunamadı: {target}"
    if not target.is_dir():
        return False, f"Belirtilen yol bir klasör değil: {target}"

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(
                ["open", str(target)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", str(target)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True, ""
    except OSError as exc:
        return False, f"Klasör açılamadı: {exc}"
    except Exception as exc:
        return False, f"Beklenmeyen hata: {exc}"


# ---------------------------------------------------------------------------
# Masaüstü yolu (cross-platform + WSL)
# ---------------------------------------------------------------------------

def _desktop_in_user_dir(user_dir: pathlib.Path) -> Optional[pathlib.Path]:
    """Bir Windows kullanıcı klasöründe Masaüstü alt dizinini bul."""
    for d_name in ("Desktop", "Masaüstü"):
        candidate = user_dir / d_name
        if candidate.is_dir():
            return candidate
    onedrive = user_dir / "OneDrive"
    if onedrive.is_dir():
        for d_name in ("Desktop", "Masaüstü"):
            candidate = onedrive / d_name
            if candidate.is_dir():
                return candidate
    return None


def _win_path_to_wsl(win_path: str) -> Optional[pathlib.Path]:
    """Windows yolunu wslpath veya sürücü harfi eşlemesiyle WSL yoluna çevir."""
    try:
        proc = subprocess.run(
            ["wslpath", "-u", win_path],
            capture_output=True,
            text=True,
            timeout=2,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return pathlib.Path(proc.stdout.strip())
    except Exception:
        pass

    if len(win_path) >= 3 and win_path[1] == ":" and win_path[0].isalpha():
        drive = win_path[0].lower()
        rest = win_path[2:].replace("\\", "/").lstrip("/")
        return pathlib.Path("/mnt") / drive / rest
    return None


def _find_wsl_desktop() -> Optional[pathlib.Path]:
    """
    WSL ortamında aktif Windows kullanıcısının masaüstü klasörünü tespit et:
      1. cmd.exe /c "echo %USERPROFILE%" + wslpath ile aktif kullanıcı
      2. Linux $USER adıyla eşleşen /mnt/c/Users/<user> klasörü
      3. Gerçek kullanıcı klasörleri arasından NTUSER.DAT mtime en güncel olan
    """
    # 1. Aktif Windows kullanıcısını cmd.exe üzerinden sorgula
    try:
        proc = subprocess.run(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            capture_output=True,
            text=True,
            timeout=2,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0:
            win_profile = proc.stdout.strip()
            if win_profile and "%USERPROFILE%" not in win_profile:
                user_dir = _win_path_to_wsl(win_profile)
                if user_dir is not None and user_dir.is_dir():
                    desk = _desktop_in_user_dir(user_dir)
                    if desk is not None:
                        return desk
    except Exception:
        pass

    wsl_users = pathlib.Path("/mnt/c/Users")
    if not wsl_users.is_dir():
        return None

    skip_names = {"Public", "Default", "Default User", "All Users"}
    candidates: list[pathlib.Path] = []

    try:
        entries = list(wsl_users.iterdir())
    except OSError:
        return None

    for u in entries:
        if not u.is_dir() or u.name in skip_names:
            continue
        has_desktop = _desktop_in_user_dir(u) is not None
        has_ntuser = (u / "NTUSER.DAT").exists()
        if has_desktop or has_ntuser:
            candidates.append(u)

    if not candidates:
        return None

    # 2. Linux $USER ile eşleşen klasörü önceliklendir
    linux_user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if linux_user:
        for exact in (True, False):
            for u in candidates:
                matched = (u.name == linux_user) if exact else (u.name.lower() == linux_user.lower())
                if matched:
                    desk = _desktop_in_user_dir(u)
                    if desk is not None:
                        return desk

    # 3. NTUSER.DAT son değiştirme zamanına göre en güncelden eskiye sırala
    def _ntuser_mtime(user_dir: pathlib.Path) -> float:
        ntuser = user_dir / "NTUSER.DAT"
        try:
            return ntuser.stat().st_mtime if ntuser.exists() else 0.0
        except OSError:
            return 0.0

    candidates.sort(key=_ntuser_mtime, reverse=True)
    for u in candidates:
        desk = _desktop_in_user_dir(u)
        if desk is not None:
            return desk

    return None


def get_desktop_path() -> pathlib.Path:
    """
    İşletim sistemine göre masaüstü klasörünü döndür (cross-platform).

    Windows  : Registry -> USERPROFILE\\Desktop (sırayla fallback)
    Linux/WSL: WSL tespiti -> $XDG_DESKTOP_DIR -> user-dirs.dirs -> ~/Desktop
    macOS    : ~/Desktop
    """
    system = platform.system()

    if system == "Windows":
        # 1. Tercih: Windows Registry (kullanıcı masaüstünü taşımış olabilir)
        try:
            import winreg  # yalnızca Windows'ta mevcut
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            path = pathlib.Path(desktop)
            if path.is_dir():
                return path
        except Exception:
            pass

        # 2. Fallback: %USERPROFILE%\Desktop
        userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return pathlib.Path(userprofile) / "Desktop"

    # Linux / WSL kontrolü
    if system == "Linux":
        try:
            proc_ver = pathlib.Path("/proc/version").read_text(
                encoding="utf-8", errors="ignore"
            ).lower()
            if "microsoft" in proc_ver:
                wsl_desk = _find_wsl_desktop()
                if wsl_desk is not None:
                    return wsl_desk
        except Exception:
            pass

        # 1. Tercih: XDG standart değişkeni
        xdg = os.environ.get("XDG_DESKTOP_DIR", "")
        if xdg:
            path = pathlib.Path(xdg)
            if path.is_dir():
                return path

        # 2. Fallback: ~/.config/user-dirs.dirs dosyasını oku
        try:
            user_dirs = pathlib.Path.home() / ".config" / "user-dirs.dirs"
            if user_dirs.exists():
                for line in user_dirs.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR="):
                        val = line.split("=", 1)[1].strip().strip('"')
                        val = val.replace("$HOME", str(pathlib.Path.home()))
                        path = pathlib.Path(val)
                        if path.is_dir():
                            return path
        except Exception:
            pass

    # macOS veya son fallback
    return pathlib.Path.home() / "Desktop"


# ---------------------------------------------------------------------------
# Hedef klasör kök dizini
# ---------------------------------------------------------------------------

def get_organized_root() -> pathlib.Path:
    """
    Taşınan dosyaların yerleştirileceği ana klasör.
    Masaüstü altında 'Düzenlenmiş' adıyla oluşturulur.
    """
    return get_desktop_path() / "Düzenlenmiş"


# ---------------------------------------------------------------------------
# Dosya kategorileri
# ---------------------------------------------------------------------------

@dataclass
class Category:
    """Bir dosya kategorisini tanımlar."""
    name: str               # İnsan okunabilir ad (klasör adı da budur)
    extensions: set[str]    # Küçük harf uzantılar, nokta dahil: {'.jpg', ...}
    color: str = "#FFFFFF"  # Rapor ekranında kategori rengi (hex)


CATEGORIES: list[Category] = [
    Category(
        name="Resimler",
        extensions={
            ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".webp", ".svg", ".heic", ".heif", ".tiff",
            ".tif", ".ico", ".raw", ".cr2", ".nef",
        },
        color="#FFD700",
    ),
    Category(
        name="Belgeler",
        extensions={
            ".pdf", ".doc", ".docx", ".txt", ".rtf",
            ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
            ".ods", ".odp", ".csv", ".md", ".pages",
            ".numbers", ".key", ".epub",
        },
        color="#4FC3F7",
    ),
    Category(
        name="Videolar",
        extensions={
            ".mp4", ".avi", ".mkv", ".mov", ".wmv",
            ".flv", ".webm", ".m4v", ".3gp", ".ts",
            ".vob", ".ogv", ".rm", ".rmvb",
        },
        color="#CE93D8",
    ),
    Category(
        name="Müzik",
        extensions={
            ".mp3", ".wav", ".flac", ".aac", ".ogg",
            ".m4a", ".wma", ".opus", ".aif", ".aiff",
            ".mid", ".midi",
        },
        color="#80CBC4",
    ),
    Category(
        name="Arşivler",
        extensions={
            ".zip", ".rar", ".7z", ".tar", ".gz",
            ".bz2", ".xz", ".tgz", ".tar.gz", ".tar.bz2",
            ".cab", ".iso", ".dmg",
        },
        color="#FFAB91",
    ),
    Category(
        name="Kod",
        extensions={
            ".py", ".js", ".ts", ".html", ".htm", ".css",
            ".java", ".cpp", ".c", ".h", ".cs", ".go",
            ".rs", ".rb", ".php", ".sh", ".bash", ".zsh",
            ".sql", ".json", ".xml", ".yaml", ".yml",
            ".toml", ".ini", ".cfg", ".env",
        },
        color="#A5D6A7",
    ),
    Category(
        name="Yürütülebilir",
        extensions={
            ".exe", ".msi", ".deb", ".rpm", ".appimage",
            ".app", ".bat", ".cmd", ".ps1",
        },
        color="#EF9A9A",
    ),
    Category(
        name="Diğerleri",
        extensions=set(),   # Catch-all: uzantı eşleşmeyenler buraya
        color="#B0BEC5",
    ),
]


def get_category(extension: str) -> Category:
    """
    Uzantıya göre kategori döndür.
    Hiçbiri eşleşmezse son kategori (Diğerleri) döner.
    """
    ext = extension.lower()
    for cat in CATEGORIES[:-1]:          # son hariç (Diğerleri)
        if ext in cat.extensions:
            return cat
    return CATEGORIES[-1]                # Diğerleri


# ---------------------------------------------------------------------------
# Robot animasyon sabitleri
# ---------------------------------------------------------------------------

ROBOT_SIZE      = 64      # px
ROBOT_SPEED_MIN = 2.0     # px / frame (en yavaş)
ROBOT_SPEED_MAX = 7.0     # px / frame (en hızlı)
ROBOT_FPS       = 60      # hedef kare hızı
ROBOT_GRID_COLS = 6       # demo modda ızgara sütun sayısı
ROBOT_GRID_ROWS = 4       # demo modda ızgara satır sayısı

# Ekran kenarından bırakılacak boşluk (px)
SCREEN_MARGIN_X = 120
SCREEN_MARGIN_Y = 100

# ---------------------------------------------------------------------------
# Atlanan dosya adları (taşınmamalı)
# ---------------------------------------------------------------------------

SKIP_NAMES: frozenset[str] = frozenset({
    "desktop.ini",
    ".DS_Store",
    "Thumbs.db",
    ".localized",
    ".directory",
})


# ---------------------------------------------------------------------------
# Kullanıcı Ayarları - Kalıcı JSON depolama
# ---------------------------------------------------------------------------

SETTINGS_PATH = pathlib.Path.home() / ".config" / "desktop_robot" / "settings.json"

# Kategori eylemleri
ACTION_MOVE   = "move"    # kategorize klasöre taşı
ACTION_DELETE = "delete"  # kalıcı olarak sil (permanent)
ACTION_TRASH  = "trash"   # geri dönüşüm kutusuna gönder
ACTION_SKIP   = "skip"    # dokunma

# Bilinmeyen eylem için geçerli küme
_VALID_ACTIONS = {ACTION_MOVE, ACTION_DELETE, ACTION_TRASH, ACTION_SKIP}

# Windows sistem dizinleri (küçük harf karşılaştırma için)
_WINDOWS_SYSTEM_DIRS = {
    "windows", "system32", "syswow64",
    "program files", "program files (x86)",
    "programdata", "$recycle.bin", "system volume information",
}
_WINDOWS_ROOT_SYSTEM_DIRS = {"recovery", "boot"}

# Linux sistem dizinleri (tam yol önekleri)
_LINUX_SYSTEM_PREFIXES = (
    "/etc", "/usr", "/bin", "/sbin", "/boot",
    "/proc", "/sys", "/dev", "/run",
    "/var", "/lib", "/lib64", "/lib32", "/root",
)


def validate_target_path(path: str | pathlib.Path) -> None:
    """
    Hedef klasör yolunun güvenli olup olmadığını doğrula.
    Güvensiz veya sistem diziniyse Türkçe ValueError fırlatır.
    """
    if isinstance(path, str) and not path.strip():
        raise ValueError("Hedef klasör yolu boş olamaz.")

    resolved = pathlib.Path(path).resolve()

    # Dosya sistemi kökü kontrolü (/ veya C:\)
    if resolved == resolved.parent:
        raise ValueError(
            "Hedef klasör dosya sistemi kökü olamaz (örn. / veya C:\\)."
        )

    # WSL sürücü kökü kontrolü (/mnt/c vb.)
    parts = resolved.parts
    if (
        len(parts) == 3
        and parts[0] == "/"
        and parts[1].lower() == "mnt"
        and len(parts[2]) == 1
        and parts[2].isalpha()
    ):
        raise ValueError(
            f"Hedef klasör sürücü kökü olamaz: {resolved}"
        )

    # Kullanıcı ana dizini kontrolü
    home = pathlib.Path.home().resolve()
    if resolved == home:
        raise ValueError(
            "Hedef klasör kullanıcı ana dizini olamaz."
        )

    # Masaüstü kontrolü (get_desktop_path hatasını yut ama ValueError'ı dışarıda fırlat!)
    desktop: Optional[pathlib.Path] = None
    try:
        desktop = get_desktop_path().resolve()
    except Exception:
        desktop = None
    if desktop is not None and resolved == desktop:
        raise ValueError(
            "Hedef klasör masaüstünün kendisi olamaz."
        )

    # Linux sistem dizinleri kontrolü
    if platform.system() != "Windows":
        posix_str = resolved.as_posix()
        for prefix in _LINUX_SYSTEM_PREFIXES:
            if posix_str == prefix or posix_str.startswith(prefix + "/"):
                raise ValueError(
                    f"Hedef klasör sistem dizini içinde olamaz: {prefix}"
                )

    # Windows sistem dizinleri kontrolü (Windows ve WSL dahil)
    parts_lower = [p.lower() for p in parts]
    for sysdir in _WINDOWS_SYSTEM_DIRS:
        if sysdir in parts_lower:
            raise ValueError(
                f"Hedef klasör Windows sistem dizini içinde olamaz: {sysdir}"
            )

    # Windows/WSL sürücü kökü altındaki boot/recovery klasörleri
    drive_subdir: Optional[str] = None
    if platform.system() == "Windows" and len(parts_lower) >= 2:
        drive_subdir = parts_lower[1]
    elif (
        len(parts_lower) >= 4
        and parts_lower[0] == "/"
        and parts_lower[1] == "mnt"
        and len(parts_lower[2]) == 1
    ):
        drive_subdir = parts_lower[3]

    if drive_subdir in _WINDOWS_ROOT_SYSTEM_DIRS:
        raise ValueError(
            f"Hedef klasör Windows sistem dizini içinde olamaz: {drive_subdir}"
        )


@dataclass
class AppSettings:
    """
    Tüm kullanıcı tercihlerini tutan veri nesnesi.

    category_rules           : {kategori_adı: "move"|"delete"|"trash"|"skip"}
    custom_target            : None -> get_organized_root() | str -> özel yol
    permanent_delete_enabled : kalıcı silmeye izin ver (False=güvenli)
    skip_hidden_files        : nokta ile başlayan dosyaları atla
    confirm_before_start     : işleme başlamadan önce onay al
    """
    category_rules:           dict[str, str] = field(default_factory=dict)
    custom_target:            Optional[str]  = None
    permanent_delete_enabled: bool = False
    skip_hidden_files:        bool = True
    confirm_before_start:     bool = True

    def __post_init__(self) -> None:
        """Eksik kategorilere varsayılan ACTION_MOVE ata; boş hedefi temizle."""
        if isinstance(self.custom_target, str):
            self.custom_target = self.custom_target.strip() or None
        elif self.custom_target is not None:
            self.custom_target = str(self.custom_target).strip() or None

        for cat in CATEGORIES:
            self.category_rules.setdefault(cat.name, ACTION_MOVE)

        # Bilinmeyen eylem değerlerini ACTION_SKIP ile değiştir
        for key, val in list(self.category_rules.items()):
            if val not in _VALID_ACTIONS:
                self.category_rules[key] = ACTION_SKIP

    # ------------------------------------------------------------------
    # Hedef kök yolu (doğrulama ile)
    # ------------------------------------------------------------------

    def get_target_root(self) -> pathlib.Path:
        """
        Aktif hedef kök klasörünü döndür.
        Tehlikeli dizinler reddedilir; ValueError fırlatılır.
        """
        if self.custom_target:
            path = pathlib.Path(self.custom_target).resolve()
        else:
            return get_organized_root()

        self.validate_target_path(path)
        return path

    @staticmethod
    def validate_target_path(path: str | pathlib.Path) -> None:
        """Hedef yolun güvenli olup olmadığını doğrula (public)."""
        validate_target_path(path)

    @staticmethod
    def _validate_target_path(path: str | pathlib.Path) -> None:
        """Hedef yolun güvenli olup olmadığını doğrula (geriye dönük uyumlu)."""
        validate_target_path(path)

    # ------------------------------------------------------------------
    # JSON serileştirme
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "category_rules":           self.category_rules,
            "custom_target":            self.custom_target,
            "permanent_delete_enabled": self.permanent_delete_enabled,
            "skip_hidden_files":        self.skip_hidden_files,
            "confirm_before_start":     self.confirm_before_start,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        raw_target = data.get("custom_target")
        if isinstance(raw_target, str):
            clean_target: Optional[str] = raw_target.strip() or None
        elif raw_target is not None:
            clean_target = str(raw_target).strip() or None
        else:
            clean_target = None

        s = cls(
            custom_target=clean_target,
            permanent_delete_enabled=bool(data.get("permanent_delete_enabled", False)),
            skip_hidden_files=bool(data.get("skip_hidden_files", True)),
            confirm_before_start=bool(data.get("confirm_before_start", True)),
        )

        # Mevcut kategorileri koru, kaydedilen değerleri dikkatlice birleştir
        saved_rules = data.get("category_rules")
        if isinstance(saved_rules, dict):
            for key, val in saved_rules.items():
                s.category_rules[str(key)] = val if val in _VALID_ACTIONS else ACTION_SKIP

        return s

    # ------------------------------------------------------------------
    # Disk I/O (atomik yazma)
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Ayarları JSON dosyasına atomik olarak yaz."""
        tmp_path = SETTINGS_PATH.with_suffix(".tmp")
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_path, SETTINGS_PATH)
        except OSError as exc:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            print(f"Ayarlar kaydedilemedi: {exc}", file=sys.stderr)
            # GUI ortamında kullanıcıya bildir
            try:
                from PyQt6.QtWidgets import QMessageBox, QApplication
                app = QApplication.instance()
                if app is not None:
                    QMessageBox.warning(
                        None,
                        "Kayıt Hatası",
                        f"Ayarlar diske yazılamadı:\n{exc}",
                    )
            except Exception:
                pass

    @classmethod
    def load(cls) -> "AppSettings":
        """JSON dosyasından ayarları oku; bozuk/eksik -> varsayılanlar."""
        if not SETTINGS_PATH.exists():
            return cls()

        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Ayar dosyası geçerli bir JSON nesnesi değil")
            return cls.from_dict(data)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            # Bozuk dosyayı .bak olarak yedekle
            bak_path = SETTINGS_PATH.with_suffix(".bak")
            try:
                os.replace(SETTINGS_PATH, bak_path)
                print(
                    f"Uyarı: Ayar dosyası bozuk ({exc}). "
                    f"Yedeklendi: {bak_path}. Varsayılanlar kullanılıyor.",
                    file=sys.stderr,
                )
            except OSError as bak_exc:
                print(
                    f"Uyarı: Ayar dosyası bozuk ({exc}) ve yedeklenemedi ({bak_exc}).",
                    file=sys.stderr,
                )
            return cls()
        except Exception as exc:
            print(f"Uyarı: Ayarlar okunamadı ({exc}).", file=sys.stderr)
            return cls()


# ---------------------------------------------------------------------------
# Global ayar önbelleği - tüm modüller buradan erişir
# ---------------------------------------------------------------------------

_settings_cache: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Önbellekten veya diskten ayarları döndür."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = AppSettings.load()
    return _settings_cache


def apply_settings(new_settings: AppSettings) -> None:
    """Yeni ayarları önbelleğe al ve diske kaydet."""
    global _settings_cache
    _settings_cache = new_settings
    new_settings.save()
