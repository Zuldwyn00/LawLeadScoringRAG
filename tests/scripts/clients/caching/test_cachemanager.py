import json
import logging
from pathlib import Path

import pytest

from scripts.clients.caching.cachemanager import ClientCacheManager
from scripts.clients.caching.cacheschema import SummaryCacheEntry
from scripts.clients.caching.hashing import get_partition_path
# ─── TEST COMMAND ──────────────────────────────────────────────────────────
# Run this test file with: pytest tests/scripts/clients/caching/test_cachemanager.py


@pytest.fixture()
def fake_config(tmp_path: Path) -> dict:
    """
    Build an in-memory config that points cache directories to a temp folder.

    Args:
        tmp_path (Path): Pytest-provided temporary directory.

    Returns:
        dict: Minimal config with caching directories and logger keys.
    """
    summary_dir = tmp_path / "summary_cache"
    summary_dir.mkdir(parents=True, exist_ok=True)

    return {
        "directories": {"logs": "logs"},
        "logger": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "filename": "test.log",
            "max_bytes": 1024,
            "backup_count": 1,
        },
        "caching": {"directories": {"summary": str(summary_dir)}},
    }


@pytest.fixture(autouse=True)
def stub_logger(monkeypatch: pytest.MonkeyPatch):
    """
    Replace logger setup with a simple in-memory logger to avoid file I/O.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patcher fixture.
    """
    def _setup_logger(name, config, level=None, filename=None):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.NullHandler())
        return logger

    monkeypatch.setattr(
        "scripts.clients.caching.cachemanager.setup_logger", _setup_logger, raising=True
    )


@pytest.fixture()
def cache_manager(monkeypatch: pytest.MonkeyPatch, fake_config: dict) -> ClientCacheManager:
    """
    Provide a cache manager instance configured to use temp directories.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patcher fixture.
        fake_config (dict): In-memory configuration dict.

    Returns:
        ClientCacheManager: Instance under test.
    """
    monkeypatch.setattr(
        "scripts.clients.caching.cachemanager.load_config",
        lambda: fake_config,
        raising=True,
    )
    return ClientCacheManager()


@pytest.mark.unit
def test_cache_entry_writes_partition_file(
    cache_manager: ClientCacheManager, tmp_path: Path, fake_config: dict
):
    """
    Ensure cache_entry creates or updates the correct partitioned JSON file
    and writes the entry keyed by "{source_file}#{client}".
    """
    source_file = tmp_path / "docs" / "example.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"dummy")

    entry = SummaryCacheEntry(
        source_file=source_file,
        client="test-client",
        summary="This is a test summary.",
    )

    base_dir = fake_config["caching"]["directories"]["summary"]
    base_name = type(entry).__name__.lower()
    cache_key = f"{entry.source_file}#{entry.client}"
    expected_path = Path(get_partition_path(cache_key, base_dir, base_name))

    cache_manager.cache_entry(entry)

    assert expected_path.exists(), "Partition file should be created by cache_entry()"

    with expected_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert cache_key in data, "Cache data should be stored under the computed key"
    assert (
        data[cache_key]["summary"] == entry.summary
    ), "Stored summary should match the input entry"


@pytest.mark.unit
def test_get_cached_entry_returns_object(
    cache_manager: ClientCacheManager, tmp_path: Path
):
    """
    After writing an entry with cache_entry, get_cached_entry should
    reconstruct and return a SummaryCacheEntry with matching fields.
    """
    source_file = tmp_path / "docs" / "another.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"dummy")

    original = SummaryCacheEntry(
        source_file=source_file,
        client="client-xyz",
        summary="Persist me",
    )
    cache_manager.cache_entry(original)

    restored = cache_manager.get_cached_entry(
        client=original.client,
        source_file=str(original.source_file),
        cache_type=SummaryCacheEntry,
    )

    assert isinstance(restored, SummaryCacheEntry)
    assert restored.summary == original.summary
    assert restored.client == original.client
    assert restored.source_file == original.source_file
    assert restored.tokens is None


@pytest.mark.unit
def test_get_cached_entry_returns_none_when_missing(cache_manager: ClientCacheManager):
    """
    If the partition file or key is absent, get_cached_entry should return None.
    """
    missing = cache_manager.get_cached_entry(
        client="nope",
        source_file="/path/does/not/exist.pdf",
        cache_type=SummaryCacheEntry,
    )
    assert missing is None

