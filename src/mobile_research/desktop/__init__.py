"""Desktop application layer for Mobile Research."""

from mobile_research.desktop import components as _components
from mobile_research.desktop.repository_policy import (
    select_stable_archive as _select_stable_archive,
)

_components.select_archive_from_repository_xml = (
    _select_stable_archive
)
