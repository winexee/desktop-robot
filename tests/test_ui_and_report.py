"""
Offscreen PyQt6 UI & Report tests (never touches real desktop or real user config):
  - SettingsDialog: 4-tab navigation, 4 action chips per category,
    permanent_delete_enabled live toggle sync, dangerous custom_target rejection
  - ReportDialog: mixed statuses + ScanResult summary, per-category QProgressBar
    scaled to category's own total, reject() emits closed signal once
  - RobotOverlay: idle timer off (0% CPU), active during animation, stops on cancel() / hide()
  - _ConfirmCleanDialog: permanent delete checkbox gates Start button
"""

from __future__ import annotations

import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QProgressBar

_app = QApplication.instance() or QApplication(sys.argv)

import config
from config import (
    ACTION_DELETE,
    ACTION_MOVE,
    ACTION_SKIP,
    ACTION_TRASH,
    AppSettings,
    CATEGORIES,
)
from file_mover import FileResult, FileStatus
from file_scanner import FileItem, ScanResult
from main import _ConfirmCleanDialog
from report_dialog import CategoryProgressCard, ReportDialog, SummaryCard
from robot_widget import RobotOverlay
from settings_dialog import SettingsDialog


# ---------------------------------------------------------------------------
# Isolation fixture: never touch real desktop or ~/.config/desktop_robot
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    fake_desktop = tmp_path / "Desktop"
    fake_desktop.mkdir()
    fake_organized = fake_desktop / "Düzenlenmiş"
    fake_settings_path = tmp_path / "config" / "settings.json"

    monkeypatch.setattr(config, "SETTINGS_PATH", fake_settings_path)
    monkeypatch.setattr(config, "_settings_cache", None)
    monkeypatch.setattr(config, "get_desktop_path", lambda: fake_desktop)
    monkeypatch.setattr(config, "get_organized_root", lambda: fake_organized)
    return tmp_path, fake_desktop, fake_organized, fake_settings_path


def _cat(name: str):
    for c in CATEGORIES:
        if c.name == name:
            return c
    raise AssertionError(f"Unknown category: {name}")


def _make_result(tmp_path: pathlib.Path, fname: str, cat_name: str, status: FileStatus) -> FileResult:
    src = tmp_path / fname
    item = FileItem(path=src, category=_cat(cat_name), screen_pos=QPointF(100, 100))
    dest = tmp_path / "Düzenlenmiş" / cat_name / fname if status == FileStatus.MOVED else None
    return FileResult(item=item, status=status, dest=dest)


# ---------------------------------------------------------------------------
# SettingsDialog tests
# ---------------------------------------------------------------------------

class TestSettingsDialog:
    def test_four_tab_navigation(self, qapp):
        dlg = SettingsDialog(AppSettings())
        try:
            assert len(dlg._sb_btns) == 4
            assert dlg._stack.count() == 4
            assert dlg._stack.currentIndex() == 0
            assert dlg._sb_btns[0].isChecked() is True

            for idx in range(4):
                dlg._sb_btns[idx].click()
                assert dlg._stack.currentIndex() == idx
                checked = [b.isChecked() for b in dlg._sb_btns]
                assert checked == [i == idx for i in range(4)]
        finally:
            dlg.close()

    def test_each_category_has_four_action_chips(self, qapp):
        dlg = SettingsDialog(AppSettings())
        try:
            assert len(dlg._page_cats._rows) == len(CATEGORIES)
            for row in dlg._page_cats._rows:
                chips = row._chips._map
                assert set(chips.keys()) == {
                    ACTION_MOVE, ACTION_TRASH, ACTION_DELETE, ACTION_SKIP
                }
                assert chips[ACTION_MOVE].text() == "Taşı"
                assert chips[ACTION_TRASH].text() == "Çöp Kutusu"
                assert chips[ACTION_DELETE].text() == "Kalıcı Sil"
                assert chips[ACTION_SKIP].text() == "Atla"
        finally:
            dlg.close()

    def test_permanent_delete_chip_follows_security_checkbox(self, qapp):
        settings = AppSettings(permanent_delete_enabled=False)
        dlg = SettingsDialog(settings)
        try:
            # Initially disabled
            for row in dlg._page_cats._rows:
                assert row._chips._map[ACTION_DELETE].isEnabled() is False

            # Enable via Security tab checkbox
            dlg._page_security._chk_perm_delete.setChecked(True)
            for row in dlg._page_cats._rows:
                assert row._chips._map[ACTION_DELETE].isEnabled() is True

            # Select ACTION_DELETE on first row, then disable checkbox -> falls back to TRASH
            first_row = dlg._page_cats._rows[0]
            first_row._chips._map[ACTION_DELETE].setChecked(True)
            assert first_row.get_action() == ACTION_DELETE

            dlg._page_security._chk_perm_delete.setChecked(False)
            assert first_row._chips._map[ACTION_DELETE].isEnabled() is False
            assert first_row.get_action() == ACTION_TRASH
        finally:
            dlg.close()

    def test_dangerous_custom_target_rejected_on_save(self, qapp, monkeypatch):
        warnings: list[tuple] = []
        monkeypatch.setattr(
            QMessageBox,
            "warning",
            staticmethod(lambda *args, **kwargs: warnings.append(args) or QMessageBox.StandardButton.Ok),
        )

        dlg = SettingsDialog(AppSettings())
        dlg.show()
        try:
            dangerous_path = str(pathlib.Path.home()) if sys.platform == "win32" else "/etc"
            dlg._page_folder._rb_custom.setChecked(True)
            dlg._page_folder._path_edit.setText(dangerous_path)

            dlg._save()

            assert len(warnings) == 1
            assert dlg._stack.currentIndex() == 1
            assert dlg.result() == 0
            assert dlg.isVisible() is True
        finally:
            dlg.close()

    def test_valid_save_persists_to_patched_settings_path(self, qapp, isolated_env):
        tmp_path, _, _, fake_settings_path = isolated_env
        safe_dir = tmp_path / "CustomSafe"
        safe_dir.mkdir()

        saved_events: list[AppSettings] = []
        dlg = SettingsDialog(AppSettings())
        dlg.settings_saved.connect(saved_events.append)
        try:
            dlg._page_folder._rb_custom.setChecked(True)
            dlg._page_folder._path_edit.setText(str(safe_dir))
            dlg._save()

            assert dlg.result() == SettingsDialog.DialogCode.Accepted
            assert len(saved_events) == 1
            assert saved_events[0].custom_target == str(safe_dir.resolve())
            assert fake_settings_path.exists()
        finally:
            dlg.close()


# ---------------------------------------------------------------------------
# ReportDialog tests
# ---------------------------------------------------------------------------

class TestReportDialog:
    def test_category_progress_bars_use_own_category_total(self, qapp, isolated_env):
        tmp_path, _, fake_organized, _ = isolated_env
        fake_organized.mkdir(parents=True)

        results = [
            # Belgeler: 2/2 succeeded -> 100%
            _make_result(tmp_path, "doc1.pdf", "Belgeler", FileStatus.MOVED),
            _make_result(tmp_path, "doc2.txt", "Belgeler", FileStatus.MOVED),
            # Resimler: 1/2 succeeded -> 50%
            _make_result(tmp_path, "img1.jpg", "Resimler", FileStatus.MOVED),
            _make_result(tmp_path, "img2.png", "Resimler", FileStatus.FAILED),
            # Mixed other statuses
            _make_result(tmp_path, "vid.mp4", "Videolar", FileStatus.TRASHED),
            _make_result(tmp_path, "script.py", "Kod", FileStatus.DELETED_PERMANENTLY),
            _make_result(tmp_path, "song.mp3", "Müzik", FileStatus.SKIPPED),
            _make_result(tmp_path, "arc.zip", "Arşivler", FileStatus.CANCELLED),
        ]

        scan_res = ScanResult(
            items=[],
            skipped_dirs=[tmp_path / "Desktop" / "MyFolder"],
            skipped_names=[".DS_Store", ".hidden"],
            desktop_path=tmp_path / "Desktop",
            positions_simulated=True,
        )

        dlg = ReportDialog(
            results=results,
            elapsed=2.4,
            target_root=fake_organized,
            scan_result=scan_res,
        )
        try:
            # Verify SummaryCards
            summary_cards = dlg.findChildren(SummaryCard)
            summary_map = {}
            for card in summary_cards:
                lbls = [lbl.text() for lbl in card.findChildren(QLabel)]
                assert len(lbls) == 2
                summary_map[lbls[1]] = int(lbls[0])

            assert summary_map == {
                "Taşınan": 3,
                "Çöp Kutusu": 1,
                "Kalıcı Silinen": 1,
                "Atlanan": 1,
                "Başarısız": 2,
            }

            # Verify CategoryProgressCard bars are scaled to each category's own total
            cat_cards = dlg.findChildren(CategoryProgressCard)
            cat_bars: dict[str, tuple[int, int, str]] = {}
            for card in cat_cards:
                texts = [lbl.text() for lbl in card.findChildren(QLabel) if lbl.text()]
                cat_name = texts[0]
                ratio_text = texts[1]
                bar = card.findChild(QProgressBar)
                assert bar is not None
                cat_bars[cat_name] = (bar.value(), bar.maximum(), ratio_text)

            assert cat_bars["Belgeler"] == (2, 2, "2 / 2")
            assert cat_bars["Resimler"] == (1, 2, "1 / 2")
            assert cat_bars["Videolar"] == (1, 1, "1 / 1")
            assert cat_bars["Kod"] == (1, 1, "1 / 1")
            assert cat_bars["Müzik"] == (0, 1, "0 / 1")
            assert cat_bars["Arşivler"] == (0, 1, "0 / 1")
        finally:
            dlg.close()

    def test_reject_emits_closed_signal_once(self, qapp, isolated_env):
        tmp_path, _, fake_organized, _ = isolated_env
        dlg = ReportDialog(
            results=[_make_result(tmp_path, "a.pdf", "Belgeler", FileStatus.MOVED)],
            elapsed=0.5,
            target_root=fake_organized,
        )
        closed_calls: list[bool] = []
        dlg.closed.connect(lambda: closed_calls.append(True))
        dlg.show()

        dlg.reject()
        dlg.close()

        assert len(closed_calls) == 1


# ---------------------------------------------------------------------------
# RobotOverlay tests (idle CPU optimization)
# ---------------------------------------------------------------------------

class TestRobotOverlay:
    def test_idle_timer_inactive_and_starts_only_with_targets(self, qapp):
        overlay = RobotOverlay()
        try:
            # Starts idle -> timer stopped (0% CPU)
            assert overlay._idle is True
            assert overlay._timer.isActive() is False

            # Showing while idle must NOT start timer
            overlay.show()
            qapp.processEvents()
            assert overlay._timer.isActive() is False

            # Setting targets while visible starts timer
            overlay.set_targets([QPointF(200, 200), QPointF(400, 300)], ["a.txt", "b.txt"])
            assert overlay._idle is False
            assert overlay._timer.isActive() is True

            # cancel() stops timer immediately
            overlay.cancel()
            assert overlay._timer.isActive() is False

            # hide() also stops timer when active
            overlay.set_targets([QPointF(250, 250)], ["c.txt"])
            assert overlay._timer.isActive() is True
            overlay.hide()
            qapp.processEvents()
            assert overlay._timer.isActive() is False
        finally:
            overlay.close()


# ---------------------------------------------------------------------------
# _ConfirmCleanDialog tests
# ---------------------------------------------------------------------------

class TestConfirmCleanDialog:
    def test_permanent_delete_checkbox_gates_start_button(self, qapp, isolated_env):
        tmp_path, fake_desktop, fake_organized, _ = isolated_env
        scan_res = ScanResult(desktop_path=fake_desktop, positions_simulated=True)

        dlg = _ConfirmCleanDialog(
            move_count=2,
            trash_count=1,
            delete_count=3,
            skip_count=0,
            target_root=fake_organized,
            scan_result=scan_res,
        )
        try:
            assert dlg._chk_confirm_delete is not None
            assert dlg._chk_confirm_delete.isChecked() is False
            assert dlg._btn_start.isEnabled() is False

            dlg._chk_confirm_delete.setChecked(True)
            assert dlg._btn_start.isEnabled() is True

            dlg._chk_confirm_delete.setChecked(False)
            assert dlg._btn_start.isEnabled() is False
        finally:
            dlg.close()

    def test_zero_delete_count_enables_start_immediately(self, qapp, isolated_env):
        tmp_path, fake_desktop, fake_organized, _ = isolated_env
        scan_res = ScanResult(desktop_path=fake_desktop, positions_simulated=True)

        dlg = _ConfirmCleanDialog(
            move_count=2,
            trash_count=0,
            delete_count=0,
            skip_count=1,
            target_root=fake_organized,
            scan_result=scan_res,
        )
        try:
            assert dlg._chk_confirm_delete is None
            assert dlg._btn_start.isEnabled() is True
        finally:
            dlg.close()
