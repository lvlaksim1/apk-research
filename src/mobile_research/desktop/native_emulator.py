from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

from PySide6.QtCore import QPoint, QObject, QTimer, Signal


WINDOWS = os.name == "nt"

if WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

    TH32CS_SNAPPROCESS = 0x00000002
    MAX_PATH = 260
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    SW_HIDE = 0
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010

    SM_XVIRTUALSCREEN = 76

    DWM_TNP_RECTDESTINATION = 0x00000001
    DWM_TNP_RECTSOURCE = 0x00000002
    DWM_TNP_OPACITY = 0x00000004
    DWM_TNP_VISIBLE = 0x00000008
    DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010

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

    class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
        _fields_ = [
            ("dwFlags", wintypes.DWORD),
            ("rcDestination", RECT),
            ("rcSource", RECT),
            ("opacity", ctypes.c_ubyte),
            ("fVisible", wintypes.BOOL),
            ("fSourceClientAreaOnly", wintypes.BOOL),
        ]

    HTHUMBNAIL = wintypes.HANDLE

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

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.EnumWindows.argtypes = [
        WNDENUMPROC,
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
    user32.GetClientRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(RECT),
    ]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
    ]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int

    dwmapi.DwmIsCompositionEnabled.argtypes = [
        ctypes.POINTER(wintypes.BOOL),
    ]
    dwmapi.DwmIsCompositionEnabled.restype = ctypes.c_long
    dwmapi.DwmRegisterThumbnail.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.POINTER(HTHUMBNAIL),
    ]
    dwmapi.DwmRegisterThumbnail.restype = ctypes.c_long
    dwmapi.DwmUnregisterThumbnail.argtypes = [HTHUMBNAIL]
    dwmapi.DwmUnregisterThumbnail.restype = ctypes.c_long
    dwmapi.DwmUpdateThumbnailProperties.argtypes = [
        HTHUMBNAIL,
        ctypes.POINTER(DWM_THUMBNAIL_PROPERTIES),
    ]
    dwmapi.DwmUpdateThumbnailProperties.restype = ctypes.c_long


def windows_native_embedding_available() -> bool:
    return WINDOWS


def _succeeded(hr: int) -> bool:
    return int(hr) >= 0


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
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
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
            if parent in result and pid not in result:
                result.add(pid)
                changed = True
    return result


def _window_text(hwnd: int) -> str:
    if not WINDOWS:
        return ""
    length = int(user32.GetWindowTextLengthW(hwnd))
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_class(hwnd: int) -> str:
    if not WINDOWS:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_size(hwnd: int) -> tuple[int, int]:
    if not WINDOWS:
        return 0, 0
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return 0, 0
    return (
        max(0, int(rect.right - rect.left)),
        max(0, int(rect.bottom - rect.top)),
    )


def _client_size(hwnd: int) -> tuple[int, int]:
    if not WINDOWS:
        return 0, 0
    rect = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return 0, 0
    return (
        max(0, int(rect.right - rect.left)),
        max(0, int(rect.bottom - rect.top)),
    )


def _phone_content_size(
    client_width: int,
    client_height: int,
) -> tuple[int, int]:
    """Crop the Emulator side toolbar from its client area when present."""

    width = max(1, int(client_width))
    height = max(1, int(client_height))
    expected_width = round(
        height * (
            9 / 16
            if height >= width
            else 16 / 9
        )
    )
    if (
        expected_width > 0
        and width > expected_width * 1.04
    ):
        width = min(width, expected_width)
    return width, height


def _fit_rect(
    width: int,
    height: int,
    source_width: int,
    source_height: int,
) -> tuple[int, int, int, int]:
    width = max(1, int(width))
    height = max(1, int(height))
    source_width = max(1, int(source_width))
    source_height = max(1, int(source_height))
    scale = min(
        width / source_width,
        height / source_height,
    )
    target_width = max(1, round(source_width * scale))
    target_height = max(1, round(source_height * scale))
    return (
        (width - target_width) // 2,
        (height - target_height) // 2,
        target_width,
        target_height,
    )


def find_emulator_window(
    root_pid: int,
    avd_name: str,
    *,
    require_visible: bool = False,
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

    @WNDENUMPROC
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

        visible = bool(user32.IsWindowVisible(hwnd))
        if require_visible and not visible:
            return True

        width, height = _window_size(hwnd)
        area = width * height
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
        if visible:
            score += 10_000_000

        candidates.append(
            (
                score,
                int(hwnd),
                {
                    "pid": window_pid,
                    "title": title,
                    "class_name": class_name,
                    "visible_before_attach": visible,
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
    """Render the real standalone Emulator through a live DWM thumbnail."""

    attached = Signal(dict)
    failed = Signal(str)

    def __init__(self, host) -> None:
        super().__init__(host)
        self.host = host
        self.hwnd = 0
        self.thumbnail = 0
        self._root_pid = 0
        self._avd_name = ""
        self._deadline = 0.0
        self._source_width = 0
        self._source_height = 0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)

    @property
    def active(self) -> bool:
        return bool(
            WINDOWS
            and self.thumbnail
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
                "DWM live display is only available on Windows"
            )
            return
        self.detach()
        self._root_pid = int(root_pid or 0)
        self._avd_name = str(avd_name or "")
        self._deadline = (
            time.monotonic()
            + max(1.0, float(timeout))
        )
        self.host.window().winId()
        self._timer.start()
        self._poll()

    def detach(self, *, restore: bool = False) -> None:
        self._timer.stop()
        if WINDOWS and self.thumbnail:
            try:
                dwmapi.DwmUnregisterThumbnail(
                    HTHUMBNAIL(self.thumbnail)
                )
            except Exception:
                pass
        self.thumbnail = 0
        self.hwnd = 0
        self._source_width = 0
        self._source_height = 0

    def resize_embedded(self) -> None:
        if not self.active:
            return
        try:
            self._update_thumbnail()
        except Exception as exc:
            self._fail(
                "DWM live display update failed: "
                + (str(exc) or exc.__class__.__name__)
            )

    def focus_embedded(self) -> None:
        # Input is intentionally delivered through Emulator gRPC.
        return

    def _poll(self) -> None:
        if self.active:
            self._timer.stop()
            return

        found = find_emulator_window(
            self._root_pid,
            self._avd_name,
            require_visible=True,
        )
        if found is not None:
            hwnd, details = found
            try:
                self._register_thumbnail(hwnd)
            except Exception as exc:
                try:
                    if user32.IsWindow(hwnd):
                        user32.ShowWindow(hwnd, SW_HIDE)
                except Exception:
                    pass
                self._fail(
                    "Не удалось подключить DWM live display: "
                    + (
                        str(exc)
                        or exc.__class__.__name__
                    )
                    + "; используется framebuffer fallback"
                )
                return

            details = {
                **details,
                "hwnd": int(hwnd),
                "mode": "dwm-thumbnail",
                "source_width": self._source_width,
                "source_height": self._source_height,
                "input_width": (
                    1080
                    if self._source_height >= self._source_width
                    else 1920
                ),
                "input_height": (
                    1920
                    if self._source_height >= self._source_width
                    else 1080
                ),
            }
            self._timer.stop()
            self.attached.emit(details)
            return

        if time.monotonic() >= self._deadline:
            self._fail(
                "Окно Android Emulator не найдено для DWM live; "
                "используется framebuffer fallback"
            )

    def _register_thumbnail(self, hwnd: int) -> None:
        enabled = wintypes.BOOL()
        hr = dwmapi.DwmIsCompositionEnabled(
            ctypes.byref(enabled)
        )
        if not _succeeded(hr) or not enabled.value:
            raise RuntimeError(
                "Windows Desktop Window Manager composition is unavailable"
            )

        destination = self.host.window()
        destination_hwnd = int(destination.winId())
        if destination_hwnd <= 0:
            raise RuntimeError(
                "Top-level Mobile Research HWND is unavailable"
            )

        client_width, client_height = _client_size(hwnd)
        if client_width <= 0 or client_height <= 0:
            raise RuntimeError(
                "Android Emulator client area is empty"
            )

        self._source_width, self._source_height = (
            _phone_content_size(
                client_width,
                client_height,
            )
        )

        thumbnail = HTHUMBNAIL()
        hr = dwmapi.DwmRegisterThumbnail(
            destination_hwnd,
            hwnd,
            ctypes.byref(thumbnail),
        )
        if not _succeeded(hr) or not thumbnail:
            raise RuntimeError(
                f"DwmRegisterThumbnail failed: 0x{int(hr) & 0xffffffff:08x}"
            )

        self.hwnd = int(hwnd)
        self.thumbnail = int(thumbnail.value or 0)
        try:
            self._update_thumbnail()
            self._move_source_offscreen()
        except Exception:
            try:
                dwmapi.DwmUnregisterThumbnail(thumbnail)
            except Exception:
                pass
            self.thumbnail = 0
            self.hwnd = 0
            raise

    def _update_thumbnail(self) -> None:
        if not self.active:
            return

        top_level = self.host.window()
        available = self.host.contentsRect()
        local_x, local_y, width, height = _fit_rect(
            available.width(),
            available.height(),
            self._source_width,
            self._source_height,
        )
        origin = self.host.mapTo(
            top_level,
            QPoint(
                available.x() + local_x,
                available.y() + local_y,
            ),
        )
        destination_rect = RECT(
            int(origin.x()),
            int(origin.y()),
            int(origin.x() + width),
            int(origin.y() + height),
        )
        source_rect = RECT(
            0,
            0,
            int(self._source_width),
            int(self._source_height),
        )
        properties = DWM_THUMBNAIL_PROPERTIES()
        properties.dwFlags = (
            DWM_TNP_RECTDESTINATION
            | DWM_TNP_RECTSOURCE
            | DWM_TNP_OPACITY
            | DWM_TNP_VISIBLE
            | DWM_TNP_SOURCECLIENTAREAONLY
        )
        properties.rcDestination = destination_rect
        properties.rcSource = source_rect
        properties.opacity = 255
        properties.fVisible = True
        properties.fSourceClientAreaOnly = True

        hr = dwmapi.DwmUpdateThumbnailProperties(
            HTHUMBNAIL(self.thumbnail),
            ctypes.byref(properties),
        )
        if not _succeeded(hr):
            raise RuntimeError(
                f"DwmUpdateThumbnailProperties failed: "
                f"0x{int(hr) & 0xffffffff:08x}"
            )

    def _move_source_offscreen(self) -> None:
        if not self.hwnd:
            return
        width, _height = _window_size(self.hwnd)
        virtual_left = int(
            user32.GetSystemMetrics(
                SM_XVIRTUALSCREEN
            )
        )
        offscreen_x = virtual_left - max(200, width) - 200
        user32.SetWindowPos(
            self.hwnd,
            0,
            offscreen_x,
            0,
            0,
            0,
            SWP_NOSIZE
            | SWP_NOZORDER
            | SWP_NOACTIVATE,
        )

    def _fail(self, message: str) -> None:
        self.detach()
        self.failed.emit(message)
