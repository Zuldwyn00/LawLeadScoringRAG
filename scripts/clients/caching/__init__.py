"""
Caching functionality for AI clients.

This module provides caching capabilities for AI client operations,
including summary caching and other result storage.
"""

from .cachemanager import ClientCacheManager
from .cacheschema import CacheEntry, SummaryCacheEntry

__all__ = [
    "ClientCacheManager",
    "CacheEntry",
    "SummaryCacheEntry",
]
