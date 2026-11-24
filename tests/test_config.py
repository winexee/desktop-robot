"""
Tests for config.py:
  - get_category()
  - AppSettings save/load round-trip
  - Corrupt / missing settings file
  - category_rules merge and unknown-action handling
  - get_target_root() dangerous-path rejection
  - get_desktop_path() return type
  - Atomic save (smoke-test)
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

# Ensure project root is on sys.path so we can import config
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from config import (
    ACTION_DELETE,
    ACTION_MOVE,
    ACTION_SKIP,
    ACTION_TRASH,
    CATEGORIES,
    AppSettings,
    get_category,
    get_desktop_path,
)


# ---------------------------------------------------------------------------
# get_category()
# ---------------------------------------------------------------------------

class TestGetCategory:
    def test_jpg_is_resimler(self):
        cat = get_category(".jpg")
        assert cat.name == "Resimler"

    def test_jpeg_is_resimler(self):
        cat = get_category(".jpeg")
        assert cat.name == "Resimler"

    def test_png_is_resimler(self):
        cat = get_category(".png")
        assert cat.name == "Resimler"

    def test_pdf_is_belgeler(self):
        cat = get_category(".pdf")
        assert cat.name == "Belgeler"

    def test_docx_is_belgeler(self):
        cat = get_category(".docx")
        assert cat.name == "Belgeler"

    def test_mp4_is_videolar(self):
        cat = get_category(".mp4")
        assert cat.name == "Videolar"

    def test_mp3_is_muzik(self):
        cat = get_category(".mp3")
        assert cat.name == "Müzik"

    def test_zip_is_arsivler(self):
        cat = get_category(".zip")
        assert cat.name == "Arşivler"

    def test_py_is_kod(self):
        cat = get_category(".py")
        assert cat.name == "Kod"

    def test_exe_is_yurutülebilir(self):
        cat = get_category(".exe")
        assert cat.name == "Yürütülebilir"

    def test_unknown_extension_is_diger(self):
        cat = get_category(".zzz_unknown_ext_xyz")
        # Last category is the catch-all
        assert cat is CATEGORIES[-1]

    def test_unknown_extension_name_contains_diger(self):
        cat = get_category(".zzz_unknown_ext_xyz")
        assert cat.name == "Diğerleri"

    def test_uppercase_extension_normalised(self):
        cat = get_category(".JPG")
        assert cat.name == "Resimler"

    def test_empty_extension_is_diger(self):
        cat = get_category("")
        assert cat is CATEGORIES[-1]

    def test_category_has_no_emoji_field(self):
        """Category dataclass must NOT have an emoji field."""
        cat = get_category(".jpg")
        assert not hasattr(cat, "emoji"), "Category must not have an emoji field"

    def test_category_has_color_field(self):
        cat = get_category(".jpg")
        assert hasattr(cat, "color")
        assert cat.color.startswith("#")


# ---------------------------------------------------------------------------
# AppSettings defaults
# ---------------------------------------------------------------------------

class TestAppSettingsDefaults:
    def test_defaults_permanent_delete_disabled(self):
        s = AppSettings()
        assert s.permanent_delete_enabled is False

    def test_defaults_skip_hidden_files(self):
        s = AppSettings()
        assert s.skip_hidden_files is True

    def test_defaults_confirm_before_start(self):
        s = AppSettings()
        assert s.confirm_before_start is True

    def test_defaults_all_categories_have_move_rule(self):
        s = AppSettings()
        for cat in CATEGORIES:
            assert cat.name in s.category_rules
            assert s.category_rules[cat.name] == ACTION_MOVE


# ---------------------------------------------------------------------------
# AppSettings save / load round-trip
# ---------------------------------------------------------------------------

class TestAppSettingsSaveLoad:
    def _patch_settings_path(self, monkeypatch, tmp_path):
        """Point SETTINGS_PATH to a temp file."""
        fake_path = tmp_path / "settings.json"
        monkeypatch.setattr(config, "SETTINGS_PATH", fake_path)
        return fake_path

    def test_roundtrip_category_rules(self, monkeypatch, tmp_path):
        fake_path = self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        s.category_rules["Resimler"] = ACTION_SKIP
        s.save()
        assert fake_path.exists()
        loaded = AppSettings.load()
        assert loaded.category_rules["Resimler"] == ACTION_SKIP

    def test_roundtrip_permanent_delete_enabled(self, monkeypatch, tmp_path):
        self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        s.permanent_delete_enabled = True
        s.save()
        loaded = AppSettings.load()
        assert loaded.permanent_delete_enabled is True

    def test_roundtrip_skip_hidden_files_false(self, monkeypatch, tmp_path):
        self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        s.skip_hidden_files = False
        s.save()
        loaded = AppSettings.load()
        assert loaded.skip_hidden_files is False

    def test_roundtrip_confirm_before_start_false(self, monkeypatch, tmp_path):
        self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        s.confirm_before_start = False
        s.save()
        loaded = AppSettings.load()
        assert loaded.confirm_before_start is False

    def test_roundtrip_custom_target(self, monkeypatch, tmp_path):
        self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        custom = str(tmp_path / "my_organized")
        s.custom_target = custom
        s.save()
        loaded = AppSettings.load()
        assert loaded.custom_target == custom

    def test_missing_file_returns_defaults(self, monkeypatch, tmp_path):
        self._patch_settings_path(monkeypatch, tmp_path)
        # File does not exist → defaults
        loaded = AppSettings.load()
        assert loaded.permanent_delete_enabled is False
        assert loaded.skip_hidden_files is True

    def test_corrupt_json_returns_defaults(self, monkeypatch, tmp_path):
        fake_path = self._patch_settings_path(monkeypatch, tmp_path)
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text("{ CORRUPT JSON !!!!", encoding="utf-8")
        loaded = AppSettings.load()
        assert loaded.permanent_delete_enabled is False

    def test_corrupt_json_creates_bak_file(self, monkeypatch, tmp_path):
        fake_path = self._patch_settings_path(monkeypatch, tmp_path)
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text("not valid json", encoding="utf-8")
        AppSettings.load()
        bak = fake_path.with_suffix(".bak")
        assert bak.exists(), "Corrupt settings must be renamed to .bak"

    def test_save_does_not_crash(self, monkeypatch, tmp_path):
        """Smoke test: save() should not raise on a valid writable path."""
        self._patch_settings_path(monkeypatch, tmp_path)
        s = AppSettings()
        s.save()  # must not raise


# ---------------------------------------------------------------------------
# category_rules merge and unknown-action handling
# ---------------------------------------------------------------------------

class TestCategoryRulesMerge:
    def test_new_categories_get_action_move_on_load(self, monkeypatch, tmp_path):
        """When saved file is missing a category, load() must fill it with ACTION_MOVE."""
        fake_path = tmp_path / "settings.json"
        monkeypatch.setattr(config, "SETTINGS_PATH", fake_path)

        # Save only partial rules (pretend a category wasn't there at save time)
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        partial_data = {"category_rules": {"Resimler": "skip"}}
        fake_path.write_text(json.dumps(partial_data), encoding="utf-8")

        loaded = AppSettings.load()
        # All categories present in CATEGORIES should have a rule
        for cat in CATEGORIES:
            assert cat.name in loaded.category_rules

        # Resimler keeps the saved value
        assert loaded.category_rules["Resimler"] == ACTION_SKIP

        # Other categories get default ACTION_MOVE (or any valid action)
        for cat in CATEGORIES:
            if cat.name != "Resimler":
                assert loaded.category_rules[cat.name] in {
                    ACTION_MOVE, ACTION_DELETE, ACTION_TRASH, ACTION_SKIP
                }

    def test_unknown_action_becomes_skip(self, monkeypatch, tmp_path):
        fake_path = tmp_path / "settings.json"
        monkeypatch.setattr(config, "SETTINGS_PATH", fake_path)
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        bad_data = {"category_rules": {"Resimler": "fly_to_moon"}}
        fake_path.write_text(json.dumps(bad_data), encoding="utf-8")
        loaded = AppSettings.load()
        assert loaded.category_rules["Resimler"] == ACTION_SKIP

    def test_unknown_action_in_post_init_becomes_skip(self):
        s = AppSettings(category_rules={"Resimler": "bogus_action"})
        assert s.category_rules["Resimler"] == ACTION_SKIP


# ---------------------------------------------------------------------------
# ACTION constants
# ---------------------------------------------------------------------------

class TestActionConstants:
    def test_action_move_value(self):
        assert ACTION_MOVE == "move"

    def test_action_delete_value(self):
        assert ACTION_DELETE == "delete"

    def test_action_trash_value(self):
        assert ACTION_TRASH == "trash"

    def test_action_skip_value(self):
        assert ACTION_SKIP == "skip"


# ---------------------------------------------------------------------------
# get_target_root() dangerous-path rejection
# ---------------------------------------------------------------------------

class TestGetTargetRootValidation:
    def _settings_with_target(self, path: str) -> AppSettings:
        s = AppSettings()
        s.custom_target = path
        return s

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_root_slash_raises(self):
        s = self._settings_with_target("/")
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_home_dir_raises(self):
        s = self._settings_with_target(str(pathlib.Path.home()))
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_etc_raises(self):
        s = self._settings_with_target("/etc")
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_usr_raises(self):
        s = self._settings_with_target("/usr")
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_bin_raises(self):
        s = self._settings_with_target("/bin")
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    def test_etc_subdir_raises(self):
        s = self._settings_with_target("/etc/ssh")
        with pytest.raises(ValueError):
            s.get_target_root()

    def test_valid_tmp_does_not_raise(self, tmp_path):
        """A safe custom path under tmp_path should not raise."""
        safe = tmp_path / "my_organized"
        safe.mkdir()
        s = self._settings_with_target(str(safe))
        # Should return a Path without raising
        result = s.get_target_root()
        assert isinstance(result, pathlib.Path)

    def test_desktop_path_rejected(self, monkeypatch, tmp_path):
        """get_target_root() must raise ValueError when custom_target equals desktop."""
        fake_desktop = tmp_path / "Desktop"
        fake_desktop.mkdir()
        monkeypatch.setattr(config, "get_desktop_path", lambda: fake_desktop)
        s = self._settings_with_target(str(fake_desktop))
        with pytest.raises(ValueError):
            s.get_target_root()

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only test")
    @pytest.mark.parametrize("bad_dir", ["/var", "/lib", "/root"])
    def test_extra_linux_system_dirs_raise(self, bad_dir):
        s = self._settings_with_target(bad_dir)
        with pytest.raises(ValueError):
            s.get_target_root()

    def test_whitespace_custom_target_becomes_none(self):
        s1 = AppSettings(custom_target="   \t\n  ")
        assert s1.custom_target is None
        s2 = AppSettings.from_dict({"custom_target": "   "})
        assert s2.custom_target is None

    def test_validate_target_path_public(self, monkeypatch, tmp_path):
        fake_desktop = tmp_path / "Desktop"
        fake_desktop.mkdir()
        monkeypatch.setattr(config, "get_desktop_path", lambda: fake_desktop)
        with pytest.raises(ValueError):
            config.validate_target_path(fake_desktop)
        with pytest.raises(ValueError):
            AppSettings.validate_target_path(fake_desktop)

    def test_non_dict_json_creates_bak(self, monkeypatch, tmp_path):
        fake_path = tmp_path / "settings.json"
        monkeypatch.setattr(config, "SETTINGS_PATH", fake_path)
        fake_path.write_text("[1, 2, 3]", encoding="utf-8")
        loaded = AppSettings.load()
        assert loaded.permanent_delete_enabled is False
        assert fake_path.with_suffix(".bak").exists()


# ---------------------------------------------------------------------------
# get_desktop_path() / get_asset_path() / open_folder()
# ---------------------------------------------------------------------------

class TestGetDesktopPath:
    def test_returns_path_object(self):
        result = get_desktop_path()
        assert isinstance(result, pathlib.Path)

    def test_get_asset_path_finds_robot_png(self):
        asset = config.get_asset_path("robot_supurge.png")
        assert isinstance(asset, pathlib.Path)
        assert asset.exists(), f"Missing asset: {asset}"

    def test_open_folder_missing_path_returns_false(self, tmp_path):
        ok, err = config.open_folder(tmp_path / "missing_dir")
        assert ok is False
        assert isinstance(err, str) and len(err) > 0
