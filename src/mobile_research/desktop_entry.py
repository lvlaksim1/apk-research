from __future__ import annotations

import sys


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

    from mobile_research.desktop.app import (
        main as desktop_main,
    )

    return desktop_main()


if __name__ == "__main__":
    raise SystemExit(main())
