"""Data models."""

from .comic import Comic
from .chapter import Chapter
from .download_task import DownloadTask
from .app_config import AppConfig
from .anime import Anime

__all__ = [
    'Comic',
    'Chapter',
    'DownloadTask',
    'AppConfig',
    'Anime',
]
