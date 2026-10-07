from __future__ import annotations

import re
from dataclasses import dataclass


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
_GRID_DB_RE = re.compile(r"launcher_(\d+)_by_(\d+)\.db$")


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


def launcher_grid_from_listing(
    output: str,
    *,
    default: tuple[int, int] = (4, 4),
) -> tuple[int, int]:
    candidates: list[tuple[int, int]] = []
    for raw in output.splitlines():
        name = raw.strip().split("/")[-1]
        match = _GRID_DB_RE.search(name)
        if match:
            candidates.append(
                (int(match.group(1)), int(match.group(2)))
            )
    if not candidates:
        return default
    return max(candidates)


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

    max_screen = max(occupied, default=0)
    for screen in range(max_screen + 2):
        cells = occupied.get(screen, set())
        for y in range(rows):
            for x in range(columns):
                if (x, y) not in cells:
                    return screen, x, y

    raise ValueError("No launcher cell available")


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
