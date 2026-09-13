from __future__ import annotations

import os
import sys


def _gui_smoke_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from mobile_research.desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    window.close()
    app.processEvents()
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        from mobile_research import __version__
        from mobile_research.desktop.components import (
            ComponentManager,
        )

        manager = ComponentManager()
        print(f"Mobile Research {__version__}")
        print(manager.paths.root)
        return 0

    if "--gui-smoke-test" in sys.argv:
        return _gui_smoke_test()

    if "--runtime-acceptance" in sys.argv:
        from mobile_research.desktop.runtime_acceptance import (
            run_runtime_acceptance,
        )

        return run_runtime_acceptance()

    from mobile_research.desktop.app import (
        main as desktop_main,
    )

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
