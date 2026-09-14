from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication, QWidget

from mobile_research.desktop.native_emulator import (
    NativeEmulatorEmbedder,
    find_emulator_window,
    windows_native_embedding_available,
)


@pytest.mark.skipif(
    os.name != "nt",
    reason="Win32 HWND embedding is Windows-only",
)
def test_native_emulator_window_can_be_found_and_reparented() -> None:
    app = QApplication.instance() or QApplication([])

    host = QWidget()
    host.resize(640, 720)
    host.show()

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
    assert int(hwnd) == int(
        fake_emulator.winId()
    )
    assert details["pid"] == os.getpid()

    embedder = NativeEmulatorEmbedder(host)
    embedder._embed(hwnd)
    app.processEvents()

    assert windows_native_embedding_available()
    assert embedder.active

    embedder.detach()
    fake_emulator.close()
    host.close()
    app.processEvents()



@pytest.mark.skipif(
    os.name != "nt",
    reason="Win32 HWND embedding is Windows-only",
)
def test_hidden_qt_window_is_not_a_native_candidate() -> None:
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
