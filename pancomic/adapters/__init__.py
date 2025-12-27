"""Adapter layer for comic source integration."""

from .base_adapter import BaseSourceAdapter
from .jmcomic_adapter import JMComicAdapter
from .ehentai_adapter import EHentaiAdapter
from .picacg_adapter import PicACGAdapter
from .bangumi_adapter import BangumiAdapter

__all__ = [
    'BaseSourceAdapter',
    'JMComicAdapter',
    'EHentaiAdapter',
    'PicACGAdapter',
    'BangumiAdapter',
]
