"""Reusable UI widgets."""

from pancomic.ui.widgets.loading_widget import LoadingWidget
from pancomic.ui.widgets.comic_card import ComicCard
from pancomic.ui.widgets.comic_grid import ComicGrid
from pancomic.ui.widgets.anime_card import AnimeCard
from pancomic.ui.widgets.anime_grid import AnimeGrid
from pancomic.ui.widgets.dynamic_tab_bar import DynamicTabBar, SourceSelectorDialog
from pancomic.ui.widgets.source_tab_manager import SourceTabManager
from pancomic.ui.widgets.version_manager import VersionManagerWidget

__all__ = [
    'LoadingWidget',
    'ComicCard',
    'ComicGrid',
    'AnimeCard',
    'AnimeGrid',
    'DynamicTabBar',
    'SourceSelectorDialog',
    'SourceTabManager',
    'VersionManagerWidget',
]
