from __future__ import annotations

import os
import sys


def _gui_smoke_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from apk_research.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    assert window.tabs.count() == 2
    assert window.tabs.tabText(0) == "Исследование"
    assert window.tabs.tabText(1) == "HTTPS • онлайн"
    assert window.https_view is not None
    assert hasattr(window, "install_package_button")
    assert hasattr(window, "stop_button")
    assert hasattr(window, "check_updates_button")
    assert hasattr(window, "install_update_button")
    window.close()
    app.processEvents()
    return 0


def main() -> int:
    if "--https-proxy-worker" in sys.argv:
        from apk_research.https_proxy_worker import (
            main as https_proxy_main,
        )

        index = sys.argv.index("--https-proxy-worker")
        return https_proxy_main(sys.argv[index + 1 :])

    if "--self-test" in sys.argv:
        from apk_research import __version__
        from apk_research.desktop.components import (
            ComponentManager,
        )

        manager = ComponentManager()
        print(f"apk-research {__version__}")
        print(manager.paths.root)
        if getattr(sys, "frozen", False):
            from apk_research.desktop.sidecar import (
                resolve_agent_jar,
            )

            print(resolve_agent_jar())
        return 0

    if "--gui-smoke-test" in sys.argv:
        return _gui_smoke_test()

    if "--runtime-acceptance" in sys.argv:
        from apk_research.desktop.runtime_acceptance import (
            run_runtime_acceptance,
        )

        return run_runtime_acceptance()

    from apk_research.desktop.app import (
        main as desktop_main,
    )

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
