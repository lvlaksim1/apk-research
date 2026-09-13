from __future__ import annotations

import json
import urllib.parse

from mobile_research.desktop.components import ComponentManager


def main() -> int:
    archives = ComponentManager().resolve_required_archives()
    if len(archives) != 4:
        raise SystemExit(
            f"Expected 4 Android packages, resolved {len(archives)}"
        )

    payload = []
    for archive in archives:
        parsed = urllib.parse.urlparse(archive.url)
        if parsed.scheme != "https":
            raise SystemExit(
                f"Android package URL is not HTTPS: {archive.url}"
            )
        if parsed.hostname not in {
            "dl.google.com",
            "redirector.gvt1.com",
        }:
            raise SystemExit(
                f"Unexpected Android package host: {parsed.hostname}"
            )
        if archive.size is not None and archive.size <= 0:
            raise SystemExit(
                f"Invalid archive size for {archive.package_path}"
            )
        if not archive.checksum:
            raise SystemExit(
                f"Repository checksum is missing for {archive.package_path}"
            )
        payload.append(
            {
                "package": archive.package_path,
                "url": archive.url,
                "size": archive.size,
                "checksum_type": archive.checksum_type,
                "checksum": archive.checksum,
            }
        )

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
