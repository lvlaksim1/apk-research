from __future__ import annotations

import sqlite3
from pathlib import Path

from apk_research.desktop.home_shortcut import (
    ensure_shortcut_in_database,
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


def test_database_shortcut_insert_and_duplicate_prevention(
    tmp_path: Path,
) -> None:
    database = tmp_path / "launcher_4_by_4.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE favorites (
                _id INTEGER PRIMARY KEY,
                title TEXT,
                intent TEXT,
                container INTEGER,
                screen INTEGER,
                cellX INTEGER,
                cellY INTEGER,
                spanX INTEGER,
                spanY INTEGER,
                itemType INTEGER,
                appWidgetId INTEGER DEFAULT -1,
                modified INTEGER DEFAULT 0,
                restored INTEGER DEFAULT 0,
                profileId INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 0,
                options INTEGER DEFAULT 0,
                appWidgetSource INTEGER DEFAULT -1
            )
            """
        )
        connection.execute(
            """
            INSERT INTO favorites (
                _id, title, intent, container, screen,
                cellX, cellY, spanX, spanY, itemType
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "Gallery",
                "#Intent;package=com.android.gallery3d;"
                "component=com.android.gallery3d/.GalleryActivity;end",
                -100,
                0,
                1,
                3,
                1,
                1,
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    created = ensure_shortcut_in_database(
        database,
        package_name="com.example.app",
        label="Example App",
        component="com.example.app/.MainActivity",
        columns=4,
        rows=4,
    )
    duplicate = ensure_shortcut_in_database(
        database,
        package_name="com.example.app",
        label="Example App",
        component="com.example.app/.MainActivity",
        columns=4,
        rows=4,
    )

    assert created == "created"
    assert duplicate == "existing"

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT title, intent, container, screen, cellX, cellY "
            "FROM favorites WHERE _id = 2"
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (
            "Example App",
            "#Intent;action=android.intent.action.MAIN;"
            "category=android.intent.category.LAUNCHER;"
            "launchFlags=0x10200000;"
            "package=com.example.app;"
            "component=com.example.app/.MainActivity;end",
            -100,
            0,
            0,
            0,
        )
    ]

    copied_database = tmp_path / "copied-main-only.db"
    copied_database.write_bytes(database.read_bytes())
    copied = sqlite3.connect(copied_database)
    try:
        copied_rows = copied.execute(
            "SELECT title FROM favorites "
            "WHERE intent LIKE '%package=com.example.app;%'"
        ).fetchall()
    finally:
        copied.close()

    assert copied_rows == [("Example App",)]
