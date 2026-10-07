from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


_ROW_PREFIX_RE = re.compile(r"^Row:\s+\d+\s+")
_FIELD_RE = {
    "_id": re.compile(r"(?:^|,\s)_id=(-?\d+)"),
    "container": re.compile(r"(?:^|,\s)container=(-?\d+)"),
    "screen": re.compile(r"(?:^|,\s)screen=(-?\d+)"),
    "cellX": re.compile(r"(?:^|,\s)cellX=(-?\d+)"),
    "cellY": re.compile(r"(?:^|,\s)cellY=(-?\d+)"),
    "spanX": re.compile(r"(?:^|,\s)spanX=(-?\d+)"),
    "spanY": re.compile(r"(?:^|,\s)spanY=(-?\d+)"),
}
_INTENT_RE = re.compile(r"(?:^|,\s)intent=(.*?),\scontainer=")
_GRID_DB_RE = re.compile(r"^(launcher_(\d+)_by_(\d+)\.db)$")


@dataclass(frozen=True)
class LauncherFavorite:
    item_id: int
    intent: str
    container: int
    screen: int
    cell_x: int
    cell_y: int
    span_x: int
    span_y: int


def parse_launcher_favorites(output: str) -> tuple[LauncherFavorite, ...]:
    rows: list[LauncherFavorite] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not _ROW_PREFIX_RE.match(line):
            continue
        line = _ROW_PREFIX_RE.sub(
            "",
            line,
            count=1,
        )

        values: dict[str, int] = {}
        valid = True
        for name, pattern in _FIELD_RE.items():
            match = pattern.search(line)
            if not match:
                valid = False
                break
            values[name] = int(match.group(1))
        if not valid:
            continue

        intent_match = _INTENT_RE.search(line)
        intent = intent_match.group(1) if intent_match else ""
        rows.append(
            LauncherFavorite(
                item_id=values["_id"],
                intent=intent,
                container=values["container"],
                screen=values["screen"],
                cell_x=values["cellX"],
                cell_y=values["cellY"],
                span_x=max(1, values["spanX"]),
                span_y=max(1, values["spanY"]),
            )
        )
    return tuple(rows)


def launcher_database_from_listing(
    output: str,
    *,
    default: tuple[str, int, int] = (
        "launcher_4_by_4.db",
        4,
        4,
    ),
) -> tuple[str, int, int]:
    candidates: list[tuple[str, int, int]] = []
    for raw in output.splitlines():
        name = raw.strip().split("/")[-1]
        match = _GRID_DB_RE.match(name)
        if match:
            candidates.append(
                (
                    match.group(1),
                    int(match.group(2)),
                    int(match.group(3)),
                )
            )
    if not candidates:
        return default
    return max(candidates)


def launcher_grid_from_listing(
    output: str,
    *,
    default: tuple[int, int] = (4, 4),
) -> tuple[int, int]:
    _, columns, rows = launcher_database_from_listing(
        output,
        default=(
            f"launcher_{default[0]}_by_{default[1]}.db",
            default[0],
            default[1],
        ),
    )
    return columns, rows


def has_package_shortcut(
    favorites: tuple[LauncherFavorite, ...],
    package_name: str,
) -> bool:
    package_token = f"package={package_name};"
    component_token = f"component={package_name}/"
    return any(
        package_token in item.intent
        or component_token in item.intent
        for item in favorites
    )


def choose_home_cell(
    favorites: tuple[LauncherFavorite, ...],
    *,
    columns: int,
    rows: int,
) -> tuple[int, int, int]:
    if columns <= 0 or rows <= 0:
        raise ValueError("Launcher grid must be positive")

    occupied: dict[int, set[tuple[int, int]]] = {}
    for item in favorites:
        if item.container != -100:
            continue
        cells = occupied.setdefault(item.screen, set())
        for dx in range(item.span_x):
            for dy in range(item.span_y):
                x = item.cell_x + dx
                y = item.cell_y + dy
                if x >= 0 and y >= 0:
                    cells.add((x, y))

    screens = sorted(occupied) or [0]
    for screen in screens:
        cells = occupied.get(screen, set())
        for y in range(rows):
            for x in range(columns):
                if (x, y) not in cells:
                    return screen, x, y

    screen = max(screens) + 1
    return screen, 0, 0


def next_favorite_id(
    favorites: tuple[LauncherFavorite, ...],
) -> int:
    return max(
        (item.item_id for item in favorites),
        default=0,
    ) + 1


def build_launch_intent(
    package_name: str,
    component: str,
) -> str:
    return (
        "#Intent;"
        "action=android.intent.action.MAIN;"
        "category=android.intent.category.LAUNCHER;"
        "launchFlags=0x10200000;"
        f"package={package_name};"
        f"component={component};"
        "end"
    )


def _database_favorites(
    connection: sqlite3.Connection,
) -> tuple[LauncherFavorite, ...]:
    rows = connection.execute(
        "SELECT _id, intent, container, screen, "
        "cellX, cellY, spanX, spanY FROM favorites"
    ).fetchall()
    return tuple(
        LauncherFavorite(
            item_id=int(row[0]),
            intent=str(row[1] or ""),
            container=int(row[2] or 0),
            screen=int(row[3] or 0),
            cell_x=int(row[4] or 0),
            cell_y=int(row[5] or 0),
            span_x=max(1, int(row[6] or 1)),
            span_y=max(1, int(row[7] or 1)),
        )
        for row in rows
    )


def ensure_shortcut_in_database(
    database: Path,
    *,
    package_name: str,
    label: str,
    component: str,
    columns: int,
    rows: int,
) -> str:
    connection = sqlite3.connect(str(database))
    try:
        columns_info = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(favorites)"
            ).fetchall()
        }
        required = {
            "_id",
            "title",
            "intent",
            "container",
            "screen",
            "cellX",
            "cellY",
            "spanX",
            "spanY",
            "itemType",
        }
        missing = sorted(required - columns_info)
        if missing:
            raise ValueError(
                "Launcher favorites schema is missing: "
                + ", ".join(missing)
            )

        favorites = _database_favorites(connection)
        if has_package_shortcut(
            favorites,
            package_name,
        ):
            return "existing"

        screen, cell_x, cell_y = choose_home_cell(
            favorites,
            columns=columns,
            rows=rows,
        )
        values: dict[str, object] = {
            "_id": next_favorite_id(favorites),
            "title": label.strip() or package_name,
            "intent": build_launch_intent(
                package_name,
                component,
            ),
            "container": -100,
            "screen": screen,
            "cellX": cell_x,
            "cellY": cell_y,
            "spanX": 1,
            "spanY": 1,
            "itemType": 0,
        }
        optional: dict[str, object] = {
            "appWidgetId": -1,
            "modified": int(time.time() * 1000),
            "restored": 0,
            "profileId": 0,
            "rank": 0,
            "options": 0,
            "appWidgetSource": -1,
        }
        for name, value in optional.items():
            if name in columns_info:
                values[name] = value

        names = list(values)
        placeholders = ", ".join("?" for _ in names)
        connection.execute(
            "INSERT INTO favorites ("
            + ", ".join(names)
            + ") VALUES ("
            + placeholders
            + ")",
            [values[name] for name in names],
        )
        connection.commit()

        # Launcher3 keeps this database in WAL mode. Force every
        # committed page back into the main .db before the caller
        # copies that file to Android; otherwise the new shortcut may
        # exist only in a local -wal sidecar and be lost on transfer.
        connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()

        check = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise ValueError(
                "Launcher database integrity check failed"
            )

        verified = _database_favorites(connection)
        if not has_package_shortcut(
            verified,
            package_name,
        ):
            raise ValueError(
                "Shortcut insert was not persisted"
            )
        return "created"
    finally:
        connection.close()
