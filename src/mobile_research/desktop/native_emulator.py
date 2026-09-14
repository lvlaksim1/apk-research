from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer, Signal


WINDOWS = os.name == "nt"

if WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    TH32CS_SNAPPROCESS = 0x00000002
    MAX_PATH = 260
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    GWL_STYLE = -16
    GWL_EXSTYLE = -20

    WS_CHILD = 0x40000000
    WS_VISIBLE = 0x10000000
    WS_CLIPCHILDREN = 0x02000000
    WS_CLIPSIBLINGS = 0x04000000
    WS_POPUP = 0x80000000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_SYSMENU = 0x00080000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000

    WS_EX_APPWINDOW = 0x00040000

    SW_SHOW = 5
    SW_HIDE = 0

    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * MAX_PATH),
        ]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    user32.EnumWindows.argtypes = [
        ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        ),
        wintypes.LPARAM,
    ]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(RECT),
    ]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetParent.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
    ]
    user32.SetParent.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
    ]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.MoveWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.BOOL,
    ]
    user32.MoveWindow.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND

    _get_window_long = getattr(
        user32,
        "GetWindowLongPtrW",
        user32.GetWindowLongW,
    )
    _set_window_long = getattr(
        user32,
        "SetWindowLongPtrW",
        user32.SetWindowLongW,
    )
    _get_window_long.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
    ]
    _get_window_long.restype = ctypes.c_ssize_t
    _set_window_long.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_ssize_t,
    ]
    _set_window_long.restype = ctypes.c_ssize_t


def windows_native_embedding_available() -> bool:
    return WINDOWS


def _process_descendants(root_pid: int) -> set[int]:
    if not WINDOWS or root_pid <= 0:
        return set()

    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPPROCESS,
        0,
    )
    if (
        snapshot in {0, None}
        or snapshot == INVALID_HANDLE_VALUE
    ):
        return {root_pid}

    parents: dict[int, int] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(
            PROCESSENTRY32W
        )
        ok = bool(
            kernel32.Process32FirstW(
                snapshot,
                ctypes.byref(entry),
            )
        )
        while ok:
            parents[int(entry.th32ProcessID)] = int(
                entry.th32ParentProcessID
            )
            ok = bool(
                kernel32.Process32NextW(
                    snapshot,
                    ctypes.byref(entry),
                )
            )
    finally:
        kernel32.CloseHandle(snapshot)

    result = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if (
                parent in result
                and pid not in result
            ):
                result.add(pid)
                changed = True
    return result


def _window_text(hwnd: int) -> str:
    if not WINDOWS:
        return ""
    length = int(
        user32.GetWindowTextLengthW(hwnd)
    )
    buffer = ctypes.create_unicode_buffer(
        max(1, length + 1)
    )
    user32.GetWindowTextW(
        hwnd,
        buffer,
        len(buffer),
    )
    return buffer.value


def _window_class(hwnd: int) -> str:
    if not WINDOWS:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(
        hwnd,
        buffer,
        len(buffer),
    )
    return buffer.value


def _window_area(hwnd: int) -> int:
    if not WINDOWS:
        return 0
    rect = RECT()
    if not user32.GetWindowRect(
        hwnd,
        ctypes.byref(rect),
    ):
        return 0
    return max(
        0,
        int(rect.right - rect.left),
    ) * max(
        0,
        int(rect.bottom - rect.top),
    )


def find_emulator_window(
    root_pid: int,
    avd_name: str,
) -> tuple[int, dict] | None:
    if not WINDOWS:
        return None

    pids = _process_descendants(root_pid)
    avd_tokens = {
        avd_name.lower(),
        avd_name.lower().replace("_", "-"),
        avd_name.lower().replace("-", "_"),
    }
    candidates: list[tuple[int, int, dict]] = []

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    @callback_type
    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(
            hwnd,
            ctypes.byref(pid),
        )
        window_pid = int(pid.value)
        title = _window_text(hwnd)
        class_name = _window_class(hwnd)
        title_lower = title.lower()

        pid_match = bool(
            root_pid > 0
            and window_pid in pids
        )
        title_match = (
            "android emulator" in title_lower
            or any(
                token and token in title_lower
                for token in avd_tokens
            )
        )
        if not pid_match and not title_match:
            return True

        area = _window_area(hwnd)
        if area <= 0:
            return True

        score = area
        if pid_match:
            score += 2_000_000_000
        if "android emulator" in title_lower:
            score += 1_000_000_000
        if any(
            token and token in title_lower
            for token in avd_tokens
        ):
            score += 500_000_000
        if class_name.lower().startswith("qt"):
            score += 100_000_000
        if user32.IsWindowVisible(hwnd):
            score += 10_000_000

        candidates.append(
            (
                score,
                int(hwnd),
                {
                    "pid": window_pid,
                    "title": title,
                    "class_name": class_name,
                    "visible_before_attach": bool(
                        user32.IsWindowVisible(hwnd)
                    ),
                    "area": area,
                },
            )
        )
        return True

    user32.EnumWindows(callback, 0)
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )
    _score, hwnd, details = candidates[0]
    return hwnd, details


class NativeEmulatorEmbedder(QObject):
    """Re-parent the real Emulator Qt window into a Qt host widget."""

    attached = Signal(dict)
    failed = Signal(str)

    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host
        self.hwnd = 0
        self._root_pid = 0
        self._avd_name = ""
        self._deadline = 0.0
        self._old_parent = 0
        self._old_style = 0
        self._old_exstyle = 0

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(
            self._poll
        )

    @property
    def active(self) -> bool:
        return bool(
            WINDOWS
            and self.hwnd
            and user32.IsWindow(self.hwnd)
        )

    def attach(
        self,
        root_pid: int,
        avd_name: str,
        *,
        timeout: float = 12.0,
    ) -> None:
        if not WINDOWS:
            self.failed.emit(
                "Native Emulator embedding is only available on Windows"
            )
            return
        self.detach(restore=False)
        self._root_pid = int(root_pid or 0)
        self._avd_name = str(avd_name or "")
        self._deadline = (
            time.monotonic()
            + max(1.0, float(timeout))
        )
        self.host.winId()
        self._timer.start()
        self._poll()

    def detach(self, *, restore: bool = True) -> None:
        self._timer.stop()
        if not self.active:
            self.hwnd = 0
            return
        hwnd = self.hwnd
        self.hwnd = 0
        if restore:
            try:
                user32.ShowWindow(hwnd, SW_HIDE)
                user32.SetParent(
                    hwnd,
                    self._old_parent,
                )
                _set_window_long(
                    hwnd,
                    GWL_STYLE,
                    self._old_style,
                )
                _set_window_long(
                    hwnd,
                    GWL_EXSTYLE,
                    self._old_exstyle,
                )
            except Exception:
                pass

    def resize_embedded(self) -> None:
        if not self.active:
            return
        rect = self.host.contentsRect()
        user32.MoveWindow(
            self.hwnd,
            0,
            0,
            max(1, rect.width()),
            max(1, rect.height()),
            True,
        )

    def focus_embedded(self) -> None:
        if self.active:
            user32.SetFocus(self.hwnd)

    def _poll(self) -> None:
        if self.active:
            self._timer.stop()
            return
        found = find_emulator_window(
            self._root_pid,
            self._avd_name,
        )
        if found is not None:
            hwnd, details = found
            try:
                self._embed(hwnd)
            except Exception as exc:
                self._timer.stop()
                self.failed.emit(
                    "Не удалось встроить нативное окно "
                    "Android Emulator: "
                    + (
                        str(exc)
                        or exc.__class__.__name__
                    )
                )
                return
            details = {
                **details,
                "hwnd": int(hwnd),
                "mode": "native-hwnd",
            }
            self._timer.stop()
            self.attached.emit(details)
            return

        if time.monotonic() >= self._deadline:
            self._timer.stop()
            self.failed.emit(
                "Нативное окно Android Emulator не найдено; "
                "используется framebuffer fallback"
            )

    def _embed(self, hwnd: int) -> None:
        parent_hwnd = int(self.host.winId())
        if parent_hwnd <= 0:
            raise RuntimeError(
                "Qt host window handle is unavailable"
            )

        self._old_parent = int(
            user32.GetParent(hwnd) or 0
        )
        self._old_style = int(
            _get_window_long(
                hwnd,
                GWL_STYLE,
            )
        )
        self._old_exstyle = int(
            _get_window_long(
                hwnd,
                GWL_EXSTYLE,
            )
        )

        user32.ShowWindow(hwnd, SW_HIDE)

        style = self._old_style
        style &= ~(
            WS_POPUP
            | WS_CAPTION
            | WS_THICKFRAME
            | WS_SYSMENU
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
        )
        style |= (
            WS_CHILD
            | WS_VISIBLE
            | WS_CLIPCHILDREN
            | WS_CLIPSIBLINGS
        )
        exstyle = (
            self._old_exstyle
            & ~WS_EX_APPWINDOW
        )

        _set_window_long(
            hwnd,
            GWL_STYLE,
            style,
        )
        _set_window_long(
            hwnd,
            GWL_EXSTYLE,
            exstyle,
        )
        user32.SetParent(
            hwnd,
            parent_hwnd,
        )

        self.hwnd = int(hwnd)
        self.resize_embedded()
        user32.ShowWindow(
            hwnd,
            SW_SHOW,
        )
        self.focus_embedded()
