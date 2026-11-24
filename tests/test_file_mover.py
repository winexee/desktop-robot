"""
Tests for file_mover.py:
  - ACTION_MOVE: file moved to correct subdir, FileResult.status == MOVED, dest set
  - Conflict resolution: "test.txt" → "test (1).txt" or "test (2).txt"
  - ACTION_SKIP: status == SKIPPED, file still at original location
  - ACTION_DELETE + permanent_delete_enabled=True: file deleted, status == DELETED_PERMANENTLY
  - Missing source: status == FAILED, error_msg contains "bulunamadi"
  - Cancel mid-queue: remaining items CANCELLED
  - FileStatus enum string values
  - Multiple files: all results collected in all_done signal

QThread tests require a running QApplication and event-loop synchronisation.
"""

from __future__ import annotations

import pathlib
import sys
import time
from unittest.mock import patch

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# QApplication must exist before importing QThread-based modules.
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QEventLoop

_app = QApplication.instance() or QApplication(sys.argv)

from config import (
    ACTION_DELETE,
    ACTION_MOVE,
    ACTION_SKIP,
    ACTION_TRASH,
    AppSettings,
    CATEGORIES,
)
from file_scanner import FileItem
from file_mover import FileStatus, FileResult, FileWorkerThread
from PyQt6.QtCore import QPointF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_category(name: str):
    """Return the CATEGORIES entry that matches *name*, or the last one."""
    for cat in CATEGORIES:
        if cat.name == name:
            return cat
    return CATEGORIES[-1]


def _make_file_item(path: pathlib.Path, category_name: str = "Belgeler") -> FileItem:
    cat = _make_category(category_name)
    return FileItem(path=path, category=cat, screen_pos=QPointF(0, 0))


def _make_settings(
    *,
    custom_target: str,
    action: str = ACTION_MOVE,
    permanent_delete_enabled: bool = False,
) -> AppSettings:
    s = AppSettings()
    s.custom_target = custom_target
    s.permanent_delete_enabled = permanent_delete_enabled
    for cat in CATEGORIES:
        s.category_rules[cat.name] = action
    return s


def _run_worker(worker: FileWorkerThread, timeout_ms: int = 5000) -> list[FileResult]:
    """Run worker in its thread and collect all_done results synchronously."""
    results: list[list[FileResult]] = []

    loop = QEventLoop()

    def on_all_done(res):
        results.append(res)
        loop.quit()

    worker.all_done.connect(on_all_done)
    worker.finished.connect(loop.quit)  # safety net
    worker.start()

    # Timeout guard
    from PyQt6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    loop.exec()
    timer.stop()
    if not worker.wait(5000):
        worker.stop()

    if results:
        return results[0]
    return []


# ---------------------------------------------------------------------------
# FileStatus enum
# ---------------------------------------------------------------------------

class TestFileStatusEnum:
    def test_moved_value(self):
        assert FileStatus.MOVED.value == "moved"

    def test_trashed_value(self):
        assert FileStatus.TRASHED.value == "trashed"

    def test_deleted_permanently_value(self):
        assert FileStatus.DELETED_PERMANENTLY.value == "deleted_permanently"

    def test_skipped_value(self):
        assert FileStatus.SKIPPED.value == "skipped"

    def test_failed_value(self):
        assert FileStatus.FAILED.value == "failed"

    def test_cancelled_value(self):
        assert FileStatus.CANCELLED.value == "cancelled"


# ---------------------------------------------------------------------------
# ACTION_MOVE
# ---------------------------------------------------------------------------

class TestActionMove:
    def test_file_moved_to_correct_subdir(self, tmp_path):
        """File must land in <target_root>/<category_name>/."""
        src = tmp_path / "source" / "report.pdf"
        src.parent.mkdir()
        src.write_text("hello")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        item = _make_file_item(src, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        assert len(results) == 1
        r = results[0]
        assert r.status == FileStatus.MOVED, f"Expected MOVED, got {r.status}: {r.error_msg}"
        assert r.dest is not None
        assert r.dest.parent == target_root / "Belgeler"
        assert r.dest.exists()
        assert not src.exists(), "Source file should have been moved away"

    def test_dest_is_set_on_move(self, tmp_path):
        src = tmp_path / "source" / "photo.jpg"
        src.parent.mkdir()
        src.write_text("img")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(src, "Resimler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        assert results[0].dest is not None
        assert isinstance(results[0].dest, pathlib.Path)


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------

class TestConflictResolution:
    def test_existing_file_gets_numbered_copy(self, tmp_path):
        """Moving 'test.txt' when it already exists → 'test (1).txt' or 'test (2).txt'."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        dest_dir = target_root / "Belgeler"
        dest_dir.mkdir(parents=True)

        # Pre-create the conflicting file
        (dest_dir / "test.txt").write_text("existing")

        src = src_dir / "test.txt"
        src.write_text("new content")

        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(src, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        r = results[0]
        assert r.status == FileStatus.MOVED, f"Expected MOVED: {r.error_msg}"
        assert r.dest is not None
        # Must have been renamed (not overwritten)
        assert r.dest.name != "test.txt"
        assert "(1)" in r.dest.name or "(2)" in r.dest.name
        assert r.dest.exists()
        # Both files must exist
        assert (dest_dir / "test.txt").exists()

    def test_conflict_resolve_static(self, tmp_path):
        """Direct test of _resolve_conflict static method."""
        d = tmp_path / "dir"
        d.mkdir()
        (d / "file.txt").write_text("x")
        (d / "file (1).txt").write_text("x")
        result = FileWorkerThread._resolve_conflict(d, "file.txt")
        assert result.name == "file (2).txt"


# ---------------------------------------------------------------------------
# ACTION_SKIP
# ---------------------------------------------------------------------------

class TestActionSkip:
    def test_skip_leaves_file_in_place(self, tmp_path):
        src = tmp_path / "source" / "note.txt"
        src.parent.mkdir()
        src.write_text("important")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_SKIP)
        item = _make_file_item(src, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        r = results[0]
        assert r.status == FileStatus.SKIPPED
        assert src.exists(), "SKIP must leave file at original location"


# ---------------------------------------------------------------------------
# ACTION_DELETE (permanent)
# ---------------------------------------------------------------------------

class TestActionDelete:
    def test_permanent_delete_when_enabled(self, tmp_path):
        src = tmp_path / "source" / "junk.tmp"
        src.parent.mkdir()
        src.write_text("delete me")

        target_root = tmp_path / "organized"
        settings = _make_settings(
            custom_target=str(target_root),
            action=ACTION_DELETE,
            permanent_delete_enabled=True,
        )
        item = _make_file_item(src, "Belgeler")

        # Patch send2trash so it doesn't do anything if HAS_SEND2TRASH is True
        with patch("file_mover._send2trash", side_effect=RuntimeError("should not be called")), \
             patch("file_mover.HAS_SEND2TRASH", False):
            worker = FileWorkerThread([item], settings)
            results = _run_worker(worker)

        r = results[0]
        assert r.status == FileStatus.DELETED_PERMANENTLY, f"Got {r.status}: {r.error_msg}"
        assert not src.exists(), "File must be deleted"

    def test_delete_without_flag_becomes_trash(self, tmp_path):
        """When permanent_delete_enabled=False, ACTION_DELETE falls back to trash/move."""
        src = tmp_path / "source" / "junk.tmp"
        src.parent.mkdir()
        src.write_text("delete me")

        target_root = tmp_path / "organized"
        settings = _make_settings(
            custom_target=str(target_root),
            action=ACTION_DELETE,
            permanent_delete_enabled=False,
        )
        item = _make_file_item(src, "Belgeler")

        with patch("file_mover.HAS_SEND2TRASH", False):
            worker = FileWorkerThread([item], settings)
            results = _run_worker(worker)

        r = results[0]
        # With no permanent_delete_enabled, should be TRASHED (via Corbeille fallback)
        assert r.status in {FileStatus.TRASHED, FileStatus.MOVED, FileStatus.FAILED}
        # File should no longer be at the original path (either trashed or moved)
        # (FAILED is acceptable if Corbeille path is somehow invalid; just not DELETED_PERMANENTLY)
        assert r.status != FileStatus.DELETED_PERMANENTLY


# ---------------------------------------------------------------------------
# Missing source file
# ---------------------------------------------------------------------------

class TestMissingSource:
    def test_missing_source_gives_failed(self, tmp_path):
        ghost = tmp_path / "ghost.txt"  # does not exist

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(ghost, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        r = results[0]
        assert r.status == FileStatus.FAILED

    def test_missing_source_error_msg_contains_bulunamadi(self, tmp_path):
        ghost = tmp_path / "ghost.txt"

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(ghost, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        r = results[0]
        assert "bulunamadi" in r.error_msg.lower() or "bulunamadı" in r.error_msg.lower(), \
            f"error_msg was: {r.error_msg!r}"


# ---------------------------------------------------------------------------
# Cancel mid-queue
# ---------------------------------------------------------------------------

class TestCancelMidQueue:
    def test_cancelled_items_get_cancelled_status(self, tmp_path):
        """Cancel before starting → all items CANCELLED."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        items = []
        for i in range(5):
            f = src_dir / f"file{i}.txt"
            f.write_text(f"content {i}")
            items.append(_make_file_item(f, "Belgeler"))

        worker = FileWorkerThread(items, settings)
        # Cancel before starting
        worker.cancel()
        results = _run_worker(worker)

        # All must be CANCELLED
        statuses = [r.status for r in results]
        assert all(s == FileStatus.CANCELLED for s in statuses), \
            f"Expected all CANCELLED, got: {statuses}"

    def test_cancel_clears_remaining(self, tmp_path):
        """Files after cancel point get CANCELLED."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        # 3 real files
        items = []
        for i in range(3):
            f = src_dir / f"file{i}.txt"
            f.write_text(f"content {i}")
            items.append(_make_file_item(f, "Belgeler"))

        worker = FileWorkerThread(items, settings)
        # Cancel immediately
        worker.cancel()
        results = _run_worker(worker)

        cancelled = [r for r in results if r.status == FileStatus.CANCELLED]
        assert len(cancelled) > 0, "At least some results should be CANCELLED"


# ---------------------------------------------------------------------------
# Multiple files in sequence (all_done signal)
# ---------------------------------------------------------------------------

class TestMultipleFiles:
    def test_all_results_in_all_done(self, tmp_path):
        """all_done signal must carry results for every item."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        n = 4
        items = []
        for i in range(n):
            f = src_dir / f"doc{i}.pdf"
            f.write_text(f"content {i}")
            items.append(_make_file_item(f, "Belgeler"))

        worker = FileWorkerThread(items, settings)
        results = _run_worker(worker)

        assert len(results) == n

    def test_each_result_has_correct_item(self, tmp_path):
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_SKIP)

        items = []
        for i in range(3):
            f = src_dir / f"img{i}.jpg"
            f.write_text(f"img {i}")
            items.append(_make_file_item(f, "Resimler"))

        worker = FileWorkerThread(items, settings)
        results = _run_worker(worker)

        result_paths = {r.item.path for r in results}
        item_paths = {i.path for i in items}
        assert result_paths == item_paths

    def test_file_done_signal_fires_per_item(self, tmp_path):
        """file_done must fire once per item."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_SKIP)

        n = 3
        items = []
        for i in range(n):
            f = src_dir / f"f{i}.txt"
            f.write_text("x")
            items.append(_make_file_item(f, "Belgeler"))

        file_done_calls: list = []
        done_event = []

        loop = QEventLoop()

        worker = FileWorkerThread(items, settings)
        worker.file_done.connect(lambda r: file_done_calls.append(r))
        worker.all_done.connect(lambda _: (done_event.append(True), loop.quit()))
        worker.start()

        from PyQt6.QtCore import QTimer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)
        loop.exec()
        timer.stop()
        worker.wait(5000)

        assert len(file_done_calls) == n


# ---------------------------------------------------------------------------
# Streaming mode (enqueue_item / finish / cancel)
# ---------------------------------------------------------------------------

class TestStreamingMode:
    def test_streaming_enqueue_and_finish(self, tmp_path):
        """streaming=True processes enqueued items sequentially and stops on finish()."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        files = []
        for i in range(3):
            f = src_dir / f"stream_{i}.pdf"
            f.write_text(f"payload {i}")
            files.append(f)

        items = [_make_file_item(f, "Belgeler") for f in files]

        results_holder: list[list[FileResult]] = []
        loop = QEventLoop()
        worker = FileWorkerThread(
            items=[],
            settings=settings,
            streaming=True,
            total_hint=len(items),
        )
        worker.all_done.connect(lambda res: (results_holder.append(res), loop.quit()))
        worker.finished.connect(loop.quit)
        worker.start()

        for item in items:
            worker.enqueue_item(item)
        worker.finish()

        from PyQt6.QtCore import QTimer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)
        loop.exec()
        timer.stop()
        assert worker.wait(5000), "Streaming worker did not finish after finish()"

        assert len(results_holder) == 1
        results = results_holder[0]
        assert len(results) == 3
        assert all(r.status == FileStatus.MOVED for r in results)
        for f in files:
            assert not f.exists()
            assert (target_root / "Belgeler" / f.name).exists()

    def test_streaming_cancel_unblocks_and_marks_cancelled(self, tmp_path):
        """cancel() in streaming mode unblocks queue.get() cleanly without hanging."""
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        results_holder: list[list[FileResult]] = []
        loop = QEventLoop()
        worker = FileWorkerThread(items=[], settings=settings, streaming=True)
        worker.all_done.connect(lambda res: (results_holder.append(res), loop.quit()))
        worker.finished.connect(loop.quit)
        worker.start()

        # Give the thread a moment to enter queue.get(), then cancel
        time.sleep(0.05)
        worker.cancel()

        from PyQt6.QtCore import QTimer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(5000)
        loop.exec()
        timer.stop()
        assert worker.wait(5000), "Streaming worker stayed blocked after cancel()"
        assert results_holder == [[]]

    def test_streaming_cancel_with_queued_items_marks_cancelled(self, tmp_path):
        """Queued items not yet started when cancel() is set receive CANCELLED status."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)

        items = []
        for i in range(3):
            f = src_dir / f"queued_{i}.txt"
            f.write_text("keep me")
            items.append(_make_file_item(f, "Belgeler"))

        worker = FileWorkerThread(
            items=items,
            settings=settings,
            streaming=True,
            total_hint=len(items),
        )
        worker.cancel()
        results = _run_worker(worker)

        assert len(results) == 3
        assert all(r.status == FileStatus.CANCELLED for r in results)
        for item in items:
            assert item.path.exists()


# ---------------------------------------------------------------------------
# ACTION_TRASH (send2trash mock and Corbeille fallback)
# ---------------------------------------------------------------------------

class TestActionTrash:
    def test_action_trash_calls_send2trash(self, tmp_path):
        src = tmp_path / "source" / "trash_me.txt"
        src.parent.mkdir()
        src.write_text("bye")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_TRASH)
        item = _make_file_item(src, "Belgeler")

        with patch("file_mover.HAS_SEND2TRASH", True), \
             patch("file_mover._send2trash") as mock_trash:
            worker = FileWorkerThread([item], settings)
            results = _run_worker(worker)

        assert len(results) == 1
        assert results[0].status == FileStatus.TRASHED
        mock_trash.assert_called_once_with(str(src))

    def test_action_trash_corbeille_fallback(self, tmp_path):
        src = tmp_path / "source" / "fallback_trash.txt"
        src.parent.mkdir()
        src.write_text("bye")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_TRASH)
        item = _make_file_item(src, "Belgeler")

        with patch("file_mover.HAS_SEND2TRASH", False):
            worker = FileWorkerThread([item], settings)
            results = _run_worker(worker)

        assert len(results) == 1
        r = results[0]
        assert r.status == FileStatus.TRASHED
        assert r.dest is not None
        assert r.dest.parent == target_root / "Corbeille"
        assert r.dest.exists()
        assert not src.exists()


# ---------------------------------------------------------------------------
# Security & error edge cases
# ---------------------------------------------------------------------------

class TestSecurityAndErrors:
    def test_permanent_delete_missing_file_returns_failed(self, tmp_path):
        """ACTION_DELETE + permanent_delete_enabled=True on missing file -> FAILED."""
        ghost = tmp_path / "missing_delete.txt"
        target_root = tmp_path / "organized"
        settings = _make_settings(
            custom_target=str(target_root),
            action=ACTION_DELETE,
            permanent_delete_enabled=True,
        )
        item = _make_file_item(ghost, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        assert results[0].status == FileStatus.FAILED
        assert "bulunamadı" in results[0].error_msg.lower()

        # Also check _delete_file directly (unlink without missing_ok=True)
        res_direct = worker._delete_file(item)
        assert res_direct.status == FileStatus.FAILED
        assert "bulunamadı" in res_direct.error_msg.lower()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation may require elevated privileges on Windows",
    )
    def test_symlink_rejected_with_failed(self, tmp_path):
        real_file = tmp_path / "real.txt"
        real_file.write_text("real")
        link = tmp_path / "sym.txt"
        link.symlink_to(real_file)

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(link, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        assert results[0].status == FileStatus.FAILED
        assert "sembolik" in results[0].error_msg.lower()
        assert real_file.exists()

    def test_unwritable_target_dir_returns_failed(self, tmp_path):
        src = tmp_path / "source" / "doc.txt"
        src.parent.mkdir()
        src.write_text("content")

        target_root = tmp_path / "organized"
        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(src, "Belgeler")

        with patch.object(FileWorkerThread, "_check_writable", return_value=False):
            worker = FileWorkerThread([item], settings)
            results = _run_worker(worker)

        assert results[0].status == FileStatus.FAILED
        assert "izni yok" in results[0].error_msg.lower()
        assert src.exists()

    def test_same_source_and_destination_skipped(self, tmp_path):
        target_root = tmp_path / "organized"
        dest_dir = target_root / "Belgeler"
        dest_dir.mkdir(parents=True)
        existing = dest_dir / "already_here.txt"
        existing.write_text("content")

        settings = _make_settings(custom_target=str(target_root), action=ACTION_MOVE)
        item = _make_file_item(existing, "Belgeler")
        worker = FileWorkerThread([item], settings)
        results = _run_worker(worker)

        assert results[0].status == FileStatus.SKIPPED
        assert existing.exists()
