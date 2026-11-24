"""
Tests for file_scanner.py:
  - scan() on empty dir: 0 items
  - scan() finds .jpg, categorizes as "Resimler"
  - scan() skips hidden files (starting with ".")
  - scan() skips directories
  - scan() skips symlinks
  - scan() skips files in SKIP_NAMES
  - _generate_grid_positions(count > capacity): unique positions
  - _generate_grid_positions(0): []
  - scan() skips organized_root directory contents
"""

from __future__ import annotations

import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# QApplication must exist before FileScanner is imported.
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import config
from config import SKIP_NAMES, AppSettings
from file_scanner import FileScanner, ScanResult, ScanWorkerThread


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def scanner(monkeypatch, tmp_path):
    """
    Return a FileScanner whose get_desktop_path() points to tmp_path/desktop
    and whose get_organized_root() points to tmp_path/organized.
    """
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    organized = tmp_path / "organized"
    organized.mkdir()

    monkeypatch.setattr(config, "get_desktop_path", lambda: desktop)
    monkeypatch.setattr(config, "get_organized_root", lambda: organized)

    # Also patch get_settings to avoid touching real settings file
    monkeypatch.setattr(config, "_settings_cache", AppSettings())

    fs = FileScanner()
    return fs, desktop, organized


# ---------------------------------------------------------------------------
# Empty directory
# ---------------------------------------------------------------------------

class TestScanEmpty:
    def test_empty_dir_returns_zero_items(self, scanner):
        fs, desktop, _ = scanner
        result = fs.scan()
        assert result.total == 0
        assert result.items == []

    def test_empty_dir_scan_result_type(self, scanner):
        fs, desktop, _ = scanner
        result = fs.scan()
        assert isinstance(result, ScanResult)


# ---------------------------------------------------------------------------
# File discovery and categorisation
# ---------------------------------------------------------------------------

class TestScanFileDiscovery:
    def test_jpg_found_and_categorised_resimler(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "photo.jpg").write_text("img data")
        result = fs.scan()
        assert result.total == 1
        assert result.items[0].category.name == "Resimler"

    def test_pdf_found_and_categorised_belgeler(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "report.pdf").write_text("pdf data")
        result = fs.scan()
        assert result.total == 1
        assert result.items[0].category.name == "Belgeler"

    def test_multiple_files_all_found(self, scanner):
        fs, desktop, _ = scanner
        for name in ["a.jpg", "b.pdf", "c.mp4"]:
            (desktop / name).write_text("x")
        result = fs.scan()
        assert result.total == 3

    def test_file_item_has_path(self, scanner):
        fs, desktop, _ = scanner
        f = desktop / "test.txt"
        f.write_text("hello")
        result = fs.scan()
        assert result.total == 1
        assert isinstance(result.items[0].path, pathlib.Path)

    def test_file_item_has_no_moved_field(self, scanner):
        """FileItem must not have a 'moved' field (removed in new API)."""
        fs, desktop, _ = scanner
        (desktop / "x.pdf").write_text("x")
        result = fs.scan()
        assert not hasattr(result.items[0], "moved"), \
            "FileItem.moved field should have been removed"


# ---------------------------------------------------------------------------
# Hidden files
# ---------------------------------------------------------------------------

class TestScanHiddenFiles:
    def test_hidden_file_skipped_by_default(self, scanner):
        fs, desktop, _ = scanner
        (desktop / ".hidden_file").write_text("secret")
        (desktop / "visible.txt").write_text("visible")
        result = fs.scan()
        names = [item.path.name for item in result.items]
        assert ".hidden_file" not in names

    def test_visible_file_not_skipped(self, scanner):
        fs, desktop, _ = scanner
        (desktop / ".hidden").write_text("h")
        (desktop / "visible.txt").write_text("v")
        result = fs.scan()
        names = [item.path.name for item in result.items]
        assert "visible.txt" in names

    def test_hidden_file_in_skipped_names(self, scanner):
        fs, desktop, _ = scanner
        (desktop / ".hidden").write_text("h")
        result = fs.scan()
        assert result.total == 0


# ---------------------------------------------------------------------------
# Directories
# ---------------------------------------------------------------------------

class TestScanDirectories:
    def test_directory_is_skipped(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "subdir").mkdir()
        result = fs.scan()
        assert result.total == 0

    def test_directory_is_in_skipped_dirs(self, scanner):
        fs, desktop, _ = scanner
        subdir = desktop / "subdir"
        subdir.mkdir()
        result = fs.scan()
        assert subdir in result.skipped_dirs

    def test_file_alongside_dir_found(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "subdir").mkdir()
        (desktop / "file.pdf").write_text("x")
        result = fs.scan()
        assert result.total == 1


# ---------------------------------------------------------------------------
# Symlinks
# ---------------------------------------------------------------------------

class TestScanSymlinks:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation may require elevated privileges on Windows",
    )
    def test_symlink_is_skipped(self, scanner, tmp_path):
        fs, desktop, _ = scanner
        real_file = tmp_path / "real_file.txt"
        real_file.write_text("real")
        link = desktop / "link_to_file.txt"
        link.symlink_to(real_file)
        result = fs.scan()
        names = [item.path.name for item in result.items]
        assert "link_to_file.txt" not in names

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation may require elevated privileges on Windows",
    )
    def test_symlink_in_skipped_names(self, scanner, tmp_path):
        fs, desktop, _ = scanner
        real_file = tmp_path / "real.txt"
        real_file.write_text("real")
        link = desktop / "my_link.txt"
        link.symlink_to(real_file)
        result = fs.scan()
        assert "my_link.txt" in result.skipped_names


# ---------------------------------------------------------------------------
# SKIP_NAMES
# ---------------------------------------------------------------------------

class TestScanSkipNames:
    def test_desktop_ini_skipped(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "desktop.ini").write_text("Windows metadata")
        result = fs.scan()
        assert result.total == 0

    def test_DS_Store_skipped(self, scanner):
        fs, desktop, _ = scanner
        (desktop / ".DS_Store").write_text("macOS metadata")
        result = fs.scan()
        assert result.total == 0

    def test_thumbs_db_skipped(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "Thumbs.db").write_text("Windows thumbnail cache")
        result = fs.scan()
        assert result.total == 0

    def test_all_skip_names_are_skipped(self, scanner):
        fs, desktop, _ = scanner
        for name in SKIP_NAMES:
            # Write something for each skip name (some start with ".", handle both)
            try:
                (desktop / name).write_text("skip me")
            except (OSError, ValueError):
                pass  # Some names might be OS-restricted
        result = fs.scan()
        assert result.total == 0


# ---------------------------------------------------------------------------
# organized_root exclusion
# ---------------------------------------------------------------------------

class TestScanOrganizedRoot:
    def test_organized_root_itself_excluded(self, scanner):
        fs, desktop, organized = scanner
        # Create some files inside organized root
        (organized / "Resimler").mkdir(parents=True, exist_ok=True)
        (organized / "Resimler" / "photo.jpg").write_text("img")
        # Put organized root ON the desktop
        link_or_dir = desktop / organized.name
        # Symlink organized onto desktop to simulate it being there
        try:
            link_or_dir.symlink_to(organized)
        except (OSError, NotImplementedError):
            # Can't create symlink; create actual dir instead
            if not link_or_dir.exists():
                link_or_dir.mkdir()

        result = fs.scan()
        # Files inside organized should not appear
        names = [item.path.name for item in result.items]
        assert "photo.jpg" not in names

    def test_regular_file_next_to_organized_found(self, scanner):
        fs, desktop, organized = scanner
        # Regular file on desktop (not inside organized)
        (desktop / "myfile.pdf").write_text("x")
        result = fs.scan()
        names = [item.path.name for item in result.items]
        assert "myfile.pdf" in names


# ---------------------------------------------------------------------------
# _generate_grid_positions
# ---------------------------------------------------------------------------

class TestGenerateGridPositions:
    def test_zero_count_returns_empty(self, scanner):
        fs, _, _ = scanner
        positions = fs._generate_grid_positions(0)
        assert positions == []

    def test_returns_correct_count(self, scanner):
        fs, _, _ = scanner
        for n in [1, 5, 10, 25]:
            positions = fs._generate_grid_positions(n)
            assert len(positions) == n, f"Expected {n} positions, got {len(positions)}"

    def test_large_count_no_duplicates(self, scanner):
        """count > grid capacity: all positions must be unique (within 1px)."""
        fs, _, _ = scanner
        # Use a very large count to exceed natural grid capacity
        count = 500
        positions = fs._generate_grid_positions(count)
        assert len(positions) == count
        # Check uniqueness: no two positions are closer than 1px in both axes
        for i, p1 in enumerate(positions):
            for j, p2 in enumerate(positions):
                if i == j:
                    continue
                dx = abs(p1.x() - p2.x())
                dy = abs(p1.y() - p2.y())
                assert not (dx < 1.0 and dy < 1.0), \
                    f"Duplicate positions at index {i} and {j}: ({p1.x()},{p1.y()}) vs ({p2.x()},{p2.y()})"

    def test_positions_are_qpointf(self, scanner):
        from PyQt6.QtCore import QPointF
        fs, _, _ = scanner
        positions = fs._generate_grid_positions(3)
        for p in positions:
            assert isinstance(p, QPointF)


# ---------------------------------------------------------------------------
# Custom target exclusion, simulated positions & ScanWorkerThread
# ---------------------------------------------------------------------------

class TestScanCustomTargetAndWorker:
    def test_custom_target_inside_desktop_excluded(self, scanner, monkeypatch):
        fs, desktop, _ = scanner
        custom_dir = desktop / "CustomOrganized"
        custom_dir.mkdir()
        (custom_dir / "inside.jpg").write_text("img")
        (desktop / "outside.jpg").write_text("img2")

        monkeypatch.setattr(
            config,
            "_settings_cache",
            AppSettings(custom_target=str(custom_dir)),
        )

        result = fs.scan()
        names = [item.path.name for item in result.items]
        assert "outside.jpg" in names
        assert "inside.jpg" not in names
        assert custom_dir in result.skipped_dirs

    @pytest.mark.skipif(sys.platform == "win32", reason="Linux-only simulated fallback check")
    def test_positions_simulated_true_on_linux(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "sample.txt").write_text("hello")
        result = fs.scan()
        assert result.positions_simulated is True

    def test_scan_worker_thread_emits_scan_finished(self, scanner):
        fs, desktop, _ = scanner
        (desktop / "doc1.pdf").write_text("a")
        (desktop / "pic1.png").write_text("b")

        results_holder: list[ScanResult] = []
        loop = QEventLoop()
        worker = ScanWorkerThread(scanner=fs)
        worker.scan_finished.connect(lambda res: (results_holder.append(res), loop.quit()))
        worker.finished.connect(loop.quit)
        worker.start()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)
        loop.exec()
        timer.stop()
        assert worker.wait(5000), "ScanWorkerThread did not finish in time"

        assert len(results_holder) == 1
        scan_res = results_holder[0]
        assert isinstance(scan_res, ScanResult)
        assert scan_res.total == 2
        found_names = {item.path.name for item in scan_res.items}
        assert found_names == {"doc1.pdf", "pic1.png"}
