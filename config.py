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
ROBOT_SPEED_MIN = 1.3     # px / frame (varsayılan normal alt sınır)
ROBOT_SPEED_MAX = 4.5     # px / frame (varsayılan normal üst sınır)
ROBOT_FPS       = 60      # hedef kare hızı
ROBOT_GRID_COLS = 6       # demo modda ızgara sütun sayısı
ROBOT_GRID_ROWS = 4       # demo modda ızgara satır sayısı

# Ekran kenarından bırakılacak boşluk (px)
SCREEN_MARGIN_X = 120
SCREEN_MARGIN_Y = 100

# ---------------------------------------------------------------------------
# Tema ve robot hızı seçenekleri
# ---------------------------------------------------------------------------

THEME_DARK     = "dark"
THEME_LIGHT    = "light"
THEME_MIDNIGHT = "midnight"
VALID_THEMES   = (THEME_DARK, THEME_LIGHT, THEME_MIDNIGHT)

SPEED_SLOW   = "slow"
SPEED_NORMAL = "normal"
SPEED_FAST   = "fast"
VALID_SPEEDS = (SPEED_SLOW, SPEED_NORMAL, SPEED_FAST)

# (min_px_per_frame, max_px_per_frame, distance_factor)
ROBOT_SPEED_PARAMS: dict[str, tuple[float, float, float]] = {
    SPEED_SLOW:   (0.8, 2.6, 0.032),
    SPEED_NORMAL: (1.3, 4.5, 0.052),
    SPEED_FAST:   (2.4, 7.5, 0.090),
}


def get_robot_speed_params(speed: Optional[str] = None) -> tuple[float, float, float]:
    """Seçili hız profili için (min_hız, max_hız, mesafe_katsayısı) döndür."""
    key = speed if speed in ROBOT_SPEED_PARAMS else SPEED_NORMAL
    return ROBOT_SPEED_PARAMS[key]


THEMES: dict[str, dict[str, str]] = {
    THEME_DARK: {
        "name":                 "Koyu",
        "bg":                   "#1e1f22",
        "surface":              "#2b2d31",
        "surface2":             "#313338",
        "section":              "#232428",
        "hover":                "#35373c",
        "pressed":              "#3f4147",
        "sidebar_active":       "#383c54",
        "sidebar_active_hover": "#414663",
        "border":               "#3f4147",
        "accent":               "#5865f2",
        "accent_hover":         "#6475ff",
        "accent_pressed":       "#4855d4",
        "accent_fg":            "#ffffff",
        "text":                 "#f2f3f5",
        "text_body":            "#dcddde",
        "muted":                "#b5bac1",
        "dim":                  "#949ba4",
        "disabled_bg":          "#23252a",
        "disabled_fg":          "#5c6068",
        "input_bg":             "#2b2d31",
        "input_disabled_bg":    "#1a1b1e",
        "chip_off_bg":          "#40444b",
        "chip_off_hv":          "#4e5058",
        "chip_off_pr":          "#35373c",
        "chip_off_fg":          "#b5bac1",
        "green_bg":             "#2d7d4b",
        "green_hv":             "#348f56",
        "green_pr":             "#25683e",
        "green_fg":             "#57f287",
        "blue_bg":              "#5865f2",
        "blue_hv":              "#6475ff",
        "blue_pr":              "#4855d4",
        "blue_fg":              "#ffffff",
        "red_bg":               "#8c2f30",
        "red_hv":               "#9e3536",
        "red_pr":               "#772728",
        "red_fg":               "#fe4c43",
        "skip_bg":              "#5c606b",
        "skip_hv":              "#696d7a",
        "skip_pr":              "#4e5058",
        "skip_fg":              "#ffffff",
        "warn_bg":              "#3b1f23",
        "warn_border":          "#fe4c43",
        "warn_text":            "#ffb3b0",
        "toolbar_start_bg":     "#237a4b",
        "toolbar_start_hv":     "#2c925b",
        "toolbar_start_pr":     "#1c623c",
        "toolbar_start_fg":     "#ffffff",
        "toolbar_cancel_bg":    "#8c2f30",
        "toolbar_cancel_hv":    "#a63738",
        "toolbar_cancel_pr":    "#732526",
        "toolbar_cancel_fg":    "#ffffff",
        "toolbar_quit_hv":      "#8c2f30",
        "toolbar_quit_pr":      "#732526",
        "toolbar_quit_fg":      "#fe4c43",
        "status_moved":         "#57f287",
        "status_trashed":       "#5865f2",
        "status_deleted":       "#ff9d4d",
        "status_skipped":       "#b5bac1",
        "status_failed":        "#fe4c43",
    },
    THEME_LIGHT: {
        "name":                 "Açık",
        "bg":                   "#f3f4f6",
        "surface":              "#ffffff",
        "surface2":             "#e5e7eb",
        "section":              "#e8eaed",
        "hover":                "#e5e7eb",
        "pressed":              "#d1d5db",
        "sidebar_active":       "#e0e7ff",
        "sidebar_active_hover": "#c7d2fe",
        "border":               "#d1d5db",
        "accent":               "#4f46e5",
        "accent_hover":         "#4338ca",
        "accent_pressed":       "#3730a3",
        "accent_fg":            "#ffffff",
        "text":                 "#111827",
        "text_body":            "#1f2937",
        "muted":                "#4b5563",
        "dim":                  "#6b7280",
        "disabled_bg":          "#e5e7eb",
        "disabled_fg":          "#9ca3af",
        "input_bg":             "#ffffff",
        "input_disabled_bg":    "#f3f4f6",
        "chip_off_bg":          "#e5e7eb",
        "chip_off_hv":          "#d1d5db",
        "chip_off_pr":          "#cbd5e1",
        "chip_off_fg":          "#374151",
        "green_bg":             "#15803d",
        "green_hv":             "#166534",
        "green_pr":             "#14532d",
        "green_fg":             "#ffffff",
        "blue_bg":              "#4f46e5",
        "blue_hv":              "#4338ca",
        "blue_pr":              "#3730a3",
        "blue_fg":              "#ffffff",
        "red_bg":               "#b91c1c",
        "red_hv":               "#991b1b",
        "red_pr":               "#7f1d1d",
        "red_fg":               "#ffffff",
        "skip_bg":              "#4b5563",
        "skip_hv":              "#374151",
        "skip_pr":              "#1f2937",
        "skip_fg":              "#ffffff",
        "warn_bg":              "#fee2e2",
        "warn_border":          "#dc2626",
        "warn_text":            "#991b1b",
        "toolbar_start_bg":     "#15803d",
        "toolbar_start_hv":     "#166534",
        "toolbar_start_pr":     "#14532d",
        "toolbar_start_fg":     "#ffffff",
        "toolbar_cancel_bg":    "#b91c1c",
        "toolbar_cancel_hv":    "#991b1b",
        "toolbar_cancel_pr":    "#7f1d1d",
        "toolbar_cancel_fg":    "#ffffff",
        "toolbar_quit_hv":      "#fee2e2",
        "toolbar_quit_pr":      "#fecaca",
        "toolbar_quit_fg":      "#b91c1c",
        "status_moved":         "#15803d",
        "status_trashed":       "#4f46e5",
        "status_deleted":       "#c2410c",
        "status_skipped":       "#4b5563",
        "status_failed":        "#dc2626",
    },
    THEME_MIDNIGHT: {
        "name":                 "Gece Mavisi",
        "bg":                   "#0f172a",
        "surface":              "#1e293b",
        "surface2":             "#273549",
        "section":              "#162032",
        "hover":                "#2d3c54",
        "pressed":              "#364763",
        "sidebar_active":       "#1e3a5f",
        "sidebar_active_hover": "#254773",
        "border":               "#334155",
        "accent":               "#38bdf8",
        "accent_hover":         "#56ccf9",
        "accent_pressed":       "#0ea5e9",
        "accent_fg":            "#0f172a",
        "text":                 "#f1f5f9",
        "text_body":            "#e2e8f0",
        "muted":                "#94a3b8",
        "dim":                  "#64748b",
        "disabled_bg":          "#162032",
        "disabled_fg":          "#475569",
        "input_bg":             "#1e293b",
        "input_disabled_bg":    "#0f172a",
        "chip_off_bg":          "#273549",
        "chip_off_hv":          "#334155",
        "chip_off_pr":          "#1e293b",
        "chip_off_fg":          "#94a3b8",
        "green_bg":             "#0f766e",
        "green_hv":             "#115e59",
        "green_pr":             "#134e4a",
        "green_fg":             "#5eead4",
        "blue_bg":              "#0284c7",
        "blue_hv":              "#0369a1",
        "blue_pr":              "#075985",
        "blue_fg":              "#ffffff",
        "red_bg":               "#9f1239",
        "red_hv":               "#be123c",
        "red_pr":               "#881337",
        "red_fg":               "#fda4af",
        "skip_bg":              "#475569",
        "skip_hv":              "#64748b",
        "skip_pr":              "#334155",
        "skip_fg":              "#ffffff",
        "warn_bg":              "#3b1222",
        "warn_border":          "#f43f5e",
        "warn_text":            "#fda4af",
        "toolbar_start_bg":     "#0f766e",
        "toolbar_start_hv":     "#0d9488",
        "toolbar_start_pr":     "#115e59",
        "toolbar_start_fg":     "#ffffff",
        "toolbar_cancel_bg":    "#9f1239",
        "toolbar_cancel_hv":    "#be123c",
        "toolbar_cancel_pr":    "#881337",
        "toolbar_cancel_fg":    "#ffffff",
        "toolbar_quit_hv":      "#4c1428",
        "toolbar_quit_pr":      "#6b1a36",
        "toolbar_quit_fg":      "#fb7185",
        "status_moved":         "#5eead4",
        "status_trashed":       "#38bdf8",
        "status_deleted":       "#fb923c",
        "status_skipped":       "#94a3b8",
        "status_failed":        "#fb7185",
    },
}


def get_theme_palette(theme_name: Optional[str] = None) -> dict[str, str]:
    """Belirtilen tema için opak renk paletini döndür."""
    name = theme_name if theme_name is not None else get_settings().theme
    if name not in THEMES:
        name = THEME_DARK
    return dict(THEMES[name])

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
    theme                    : "dark" | "light" | "midnight"
    robot_speed              : "slow" | "normal" | "fast"
    """
    category_rules:           dict[str, str] = field(default_factory=dict)
    custom_target:            Optional[str]  = None
    permanent_delete_enabled: bool = False
    skip_hidden_files:        bool = True
    confirm_before_start:     bool = True
    theme:                    str  = THEME_DARK
    robot_speed:              str  = SPEED_NORMAL

    def __post_init__(self) -> None:
        """Eksik kategorilere varsayılan ACTION_MOVE ata; alanları doğrula."""
        if isinstance(self.custom_target, str):
            self.custom_target = self.custom_target.strip() or None
        elif self.custom_target is not None:
            self.custom_target = str(self.custom_target).strip() or None

        if self.theme not in VALID_THEMES:
            self.theme = THEME_DARK

        if self.robot_speed not in VALID_SPEEDS:
            self.robot_speed = SPEED_NORMAL

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
            "theme":                    self.theme,
            "robot_speed":              self.robot_speed,
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

        raw_theme = str(data.get("theme", THEME_DARK)).strip().lower()
        raw_speed = str(data.get("robot_speed", SPEED_NORMAL)).strip().lower()

        s = cls(
            custom_target=clean_target,
            permanent_delete_enabled=bool(data.get("permanent_delete_enabled", False)),
            skip_hidden_files=bool(data.get("skip_hidden_files", True)),
            confirm_before_start=bool(data.get("confirm_before_start", True)),
            theme=raw_theme if raw_theme in VALID_THEMES else THEME_DARK,
            robot_speed=raw_speed if raw_speed in VALID_SPEEDS else SPEED_NORMAL,
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
