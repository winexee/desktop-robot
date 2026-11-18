"""
Masaüstü Robot Süpürge — Yapılandırma
======================================
Dosya kategorileri, hedef klasör adları ve uygulama sabitleri.
Tüm modüller bu dosyadan import eder; ayar değişikliği için
sadece bu dosya düzenlenir.
"""

from __future__ import annotations

import json
import os
import platform
import pathlib
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Masaüstü yolu (cross-platform)
# ---------------------------------------------------------------------------

def get_desktop_path() -> pathlib.Path:
    """
    İşletim sistemine göre masaüstü klasörünü döndür (cross-platform).

    Windows  : Registry → USERPROFILE\\Desktop (sıraylı fallback)
    Linux    : $XDG_DESKTOP_DIR → ~/Desktop
    macOS    : ~/Desktop
    """
    system = platform.system()

    if system == "Windows":
        # 1. Tercih: Windows Registry (kullanıcı masaüstünü taşımış olabilir)
        try:
            import winreg  # yalnızca Windows'ta mevcut; Linux/macOS'ta import edilmez
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            path = pathlib.Path(desktop)
            if path.is_dir():
                return path
        except Exception:  # winreg bulunamazsa veya key yoksa
            pass

        # 2. Fallback: %USERPROFILE%\Desktop
        userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return pathlib.Path(userprofile) / "Desktop"

    # Linux / WSL kontrolü
    if system == "Linux":
        try:
            if "microsoft" in pathlib.Path("/proc/version").read_text().lower():
                for u in pathlib.Path("/mnt/c/Users").iterdir():
                    if u.name not in ("Public", "Default", "Default User", "All Users"):
                        for d_name in ("Desktop", "Masaüstü"):
                            win_desk = u / d_name
                            if win_desk.is_dir():
                                return win_desk
                        onedrive = u / "OneDrive"
                        if onedrive.is_dir():
                            for d_name in ("Desktop", "Masaüstü"):
                                od_desk = onedrive / d_name
                                if od_desk.is_dir():
                                    return od_desk
        except Exception:
            pass

    if system == "Linux":
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
    emoji: str              # Raporda gösterilecek emoji
    extensions: set[str]    # Küçük harf uzantılar, nokta dahil: {'.jpg', ...}
    color: str = "#FFFFFF"  # Rapor ekranında kategori rengi (hex)


CATEGORIES: list[Category] = [
    Category(
        name="Resimler",
        emoji="📷",
        extensions={
            ".jpg", ".jpeg", ".png", ".gif", ".bmp",
            ".webp", ".svg", ".heic", ".heif", ".tiff",
            ".tif", ".ico", ".raw", ".cr2", ".nef",
        },
        color="#FFD700",
    ),
    Category(
        name="Belgeler",
        emoji="📄",
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
        emoji="🎬",
        extensions={
            ".mp4", ".avi", ".mkv", ".mov", ".wmv",
            ".flv", ".webm", ".m4v", ".3gp", ".ts",
            ".vob", ".ogv", ".rm", ".rmvb",
        },
        color="#CE93D8",
    ),
    Category(
        name="Müzik",
        emoji="🎵",
        extensions={
            ".mp3", ".wav", ".flac", ".aac", ".ogg",
            ".m4a", ".wma", ".opus", ".aif", ".aiff",
            ".mid", ".midi",
        },
        color="#80CBC4",
    ),
    Category(
        name="Arşivler",
        emoji="🗜️",
        extensions={
            ".zip", ".rar", ".7z", ".tar", ".gz",
            ".bz2", ".xz", ".tgz", ".tar.gz", ".tar.bz2",
            ".cab", ".iso", ".dmg",
        },
        color="#FFAB91",
    ),
    Category(
        name="Kod",
        emoji="💻",
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
        emoji="⚙️",
        extensions={
            ".exe", ".msi", ".deb", ".rpm", ".appimage",
            ".app", ".bat", ".cmd", ".ps1",
        },
        color="#EF9A9A",
    ),
    Category(
        name="Diğerleri",
        emoji="📦",
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
    return CATEGORIES[-1]                 # Diğerleri


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
# Kullanıcı Ayarları — Kalıcı JSON depolama
# ---------------------------------------------------------------------------

SETTINGS_PATH = pathlib.Path.home() / ".config" / "desktop_robot" / "settings.json"

# Kategori eylemleri
ACTION_MOVE   = "move"    # kategorize klasöre taşı
ACTION_DELETE = "delete"  # kalıcı olarak sil
ACTION_SKIP   = "skip"    # dokunma


@dataclass
class AppSettings:
    """
    Tüm kullanıcı tercihlerini tutan veri nesnesi.

    category_rules : {kategori_adı: "move"|"delete"|"skip"}
    custom_target  : None → get_organized_root() | str → özel yol
    """
    category_rules:  dict[str, str] = field(default_factory=dict)
    custom_target:   Optional[str]  = None

    def __post_init__(self) -> None:
        """Eksik kategorilere varsayılan "move" ata."""
        for cat in CATEGORIES:
            self.category_rules.setdefault(cat.name, ACTION_MOVE)

    # ------------------------------------------------------------------
    # Hedef kök yolu
    # ------------------------------------------------------------------

    def get_target_root(self) -> pathlib.Path:
        """Aktif hedef kök klasörünü döndür."""
        if self.custom_target:
            return pathlib.Path(self.custom_target)
        return get_organized_root()

    # ------------------------------------------------------------------
    # JSON serileştirme
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "category_rules": self.category_rules,
            "custom_target":  self.custom_target,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        s = cls()
        s.category_rules.update(data.get("category_rules", {}))
        s.custom_target = data.get("custom_target")
        return s

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Ayarları JSON dosyasına yaz."""
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass   # Yazma hatası sessizce geç

    @classmethod
    def load(cls) -> "AppSettings":
        """JSON dosyasından ayarları oku; hata/eksik → varsayılanlar."""
        try:
            if SETTINGS_PATH.exists():
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                return cls.from_dict(data)
        except Exception:
            pass
        return cls()


# ---------------------------------------------------------------------------
# Global ayar önbelleği — tüm modüller buradan erişir
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
