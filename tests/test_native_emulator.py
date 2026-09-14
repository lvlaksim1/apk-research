from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication, QWidget

from mobile_research.desktop.native_emulator import (
    _fit_rect,
    _phone_content_size,
    find_emulator_window,
    windows_native_embedding_available,
)


def test_phone_content_size_crops_emulator_toolbar() -> None:
    assert _phone_content_size(500, 800) == (450, 800)
    assert _phone_content_size(450, 800) == (450, 800)


def test_fit_rect_preserves_source_aspect() -> None:
    assert _fit_rect(
        1000,
        800,
        450,
        800,
    ) == (275, 0, 450, 800)


@pytest.mark.skipif(
    os.name != "nt",
    reason="Win32 window discovery is Windows-only",
)
def test_visible_emulator_window_can_be_found() -> None:
    app = QApplication.instance() or QApplication([])
    fake_emulator = QWidget()
    fake_emulator.setWindowTitle(
        "Android Emulator - AVD_RESEARCH:5554"
    )
    fake_emulator.resize(420, 760)
    fake_emulator.show()
    app.processEvents()

    found = find_emulator_window(
        os.getpid(),
        "AVD_RESEARCH",
        require_visible=True,
    )
    assert found is not None
    hwnd, details = found
    assert int(hwnd) == int(fake_emulator.winId())
    assert details["pid"] == os.getpid()
    assert windows_native_embedding_available()

    fake_emulator.close()
    app.processEvents()


@pytest.mark.skipif(
    os.name != "nt",
    reason="Win32 window discovery is Windows-only",
)
def test_hidden_qt_window_is_not_a_dwm_candidate() -> None:
    app = QApplication.instance() or QApplication([])
    fake_emulator = QWidget()
    fake_emulator.setWindowTitle(
        "Android Emulator - AVD_RESEARCH:5554"
    )
    fake_emulator.resize(420, 760)
    fake_emulator.show()
    app.processEvents()
    fake_emulator.hide()
    app.processEvents()

    found = find_emulator_window(
        os.getpid(),
        "AVD_RESEARCH",
        require_visible=True,
    )
    assert found is None

    fake_emulator.close()
    app.processEvents()
