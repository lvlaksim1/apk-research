from __future__ import annotations

from apk_research.desktop.home_shortcut import (
    build_launch_intent,
    choose_home_cell,
    has_package_shortcut,
    launcher_grid_from_listing,
    next_favorite_id,
    parse_launcher_favorites,
)


SAMPLE = """Row: 0 _id=1, title=Phone, intent=#Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;package=com.android.dialer;component=com.android.dialer/.MainActivity;end, container=-101, screen=0, cellX=0, cellY=0, spanX=1, spanY=1, itemType=0, appWidgetId=-1, modified=0, restored=0, profileId=0, rank=0, options=0, appWidgetSource=-1
Row: 1 _id=5, title=Gallery, intent=#Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;package=com.android.gallery3d;component=com.android.gallery3d/.GalleryActivity;end, container=-100, screen=0, cellX=1, cellY=3, spanX=1, spanY=1, itemType=0, appWidgetId=-1, modified=0, restored=0, profileId=0, rank=0, options=0, appWidgetSource=-1
"""


def test_parse_launcher_rows_and_choose_free_home_cell() -> None:
    rows = parse_launcher_favorites(SAMPLE)

    assert len(rows) == 2
    assert next_favorite_id(rows) == 6
    assert choose_home_cell(
        rows,
        columns=4,
        rows=4,
    ) == (0, 0, 0)


def test_detect_existing_package_shortcut() -> None:
    rows = parse_launcher_favorites(SAMPLE)

    assert has_package_shortcut(
        rows,
        "com.android.gallery3d",
    )
    assert not has_package_shortcut(
        rows,
        "com.example.missing",
    )


def test_launcher_grid_is_read_from_database_name() -> None:
    assert launcher_grid_from_listing(
        "app_icons.db\nlauncher_4_by_4.db\n"
    ) == (4, 4)


def test_build_launch_intent_is_launcher_intent() -> None:
    value = build_launch_intent(
        "com.example.app",
        "com.example.app/.MainActivity",
    )

    assert "category=android.intent.category.LAUNCHER;" in value
    assert "package=com.example.app;" in value
    assert "component=com.example.app/.MainActivity;" in value
