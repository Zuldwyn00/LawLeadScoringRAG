import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

# Import the modules we need to test
from scripts.clients.caching.cachemanager import ClientCacheManager
from scripts.clients.caching.cacheschema import SummaryCacheEntry


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_cache_entry():
    """Create a sample SummaryCacheEntry for testing."""
    return SummaryCacheEntry(
        source_file=Path("test_document.pdf"),
        client="gpt-4o",
        tokens=150,
        summary="This is a test summary of the document."
    )


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for cache manager."""
    with patch('scripts.clients.caching.cachemanager.setup_logger') as mock_logger, \
         patch('scripts.clients.caching.cachemanager.load_config') as mock_config, \
         patch('scripts.clients.caching.cachemanager.save_to_json') as mock_save, \
         patch('scripts.clients.caching.cachemanager.load_from_json') as mock_load:
        
        # Setup mocks
        mock_logger.return_value = MagicMock()
        mock_config.return_value = {}
        
        yield {
            'logger': mock_logger,
            'config': mock_config,
            'save': mock_save,
            'load': mock_load
        }


@pytest.fixture
def cache_manager(temp_cache_dir, mock_dependencies):
    """Create a ClientCacheManager instance with mocked dependencies."""
    cache_manager = ClientCacheManager()
    cache_manager.cache_paths['summary_cache'] = os.path.join(temp_cache_dir, 'summary_cache.json')
    return cache_manager


class TestClientCacheManager:
    """Test cases for ClientCacheManager class using pytest."""
    
    def test_cache_and_retrieve_summary_cache_entry(self, cache_manager, sample_cache_entry, mock_dependencies):
        """
        Test caching a SummaryCacheEntry object and then retrieving it successfully.
        
        Creates a SummaryCacheEntry, saves it using cache_entry method,
        then retrieves it using get_cached_data method and verifies the data matches.
        """
        # Test caching the entry
        cache_manager.cache_entry(sample_cache_entry)
        
        # Verify save_to_json was called with correct data
        mock_dependencies['save'].assert_called_once()
        saved_data = mock_dependencies['save'].call_args[0][0]  # First argument is the data dict
        saved_filepath = mock_dependencies['save'].call_args[1]['filepath']  # filepath keyword argument
        
        # Verify the saved data contains the expected fields
        assert saved_data['summary'] == sample_cache_entry.summary
        assert saved_data['source_file'] == sample_cache_entry.source_file
        assert saved_data['client'] == sample_cache_entry.client
        assert saved_data['tokens'] == sample_cache_entry.tokens
        assert 'created_at' in saved_data
        assert saved_filepath == cache_manager.cache_paths['summary_cache']
        
        # Mock the load_from_json to return our saved data
        mock_dependencies['load'].return_value = saved_data
        
        # Test retrieving the cached data using the cache entry object
        retrieved_data = cache_manager.get_cached_data(sample_cache_entry)
        
        # Verify load_from_json was called with correct filepath
        mock_dependencies['load'].assert_called_with(cache_manager.cache_paths['summary_cache'])
        
        # Verify the retrieved data matches the original
        assert retrieved_data is not None
        assert retrieved_data['summary'] == sample_cache_entry.summary
        assert retrieved_data['source_file'] == sample_cache_entry.source_file
        assert retrieved_data['client'] == sample_cache_entry.client
        assert retrieved_data['tokens'] == sample_cache_entry.tokens
        assert 'created_at' in retrieved_data

    @pytest.mark.parametrize("client,tokens", [
        ("gpt-4o", 150),
        ("gpt-3.5-turbo", 100),
        ("claude-3", 200),
    ])
    def test_cache_with_different_clients(self, cache_manager, mock_dependencies, client, tokens):
        """Test caching with different client configurations."""
        cache_entry = SummaryCacheEntry(
            source_file=Path("test_document.pdf"),
            client=client,
            tokens=tokens,
            summary=f"Summary for {client}"
        )
        
        cache_manager.cache_entry(cache_entry)
        
        # Verify save was called
        mock_dependencies['save'].assert_called_once()
        saved_data = mock_dependencies['save'].call_args[0][0]
        
        assert saved_data['client'] == client
        assert saved_data['tokens'] == tokens
        assert saved_data['summary'] == f"Summary for {client}"

    def test_cache_entry_with_none_data(self, cache_manager, mock_dependencies):
        """Test that caching None data raises appropriate error."""
        with pytest.raises(TypeError, match="Invalid cache entry"):
            cache_manager.cache_entry(None)

    def test_get_cached_data_with_none_entry(self, cache_manager, mock_dependencies):
        """Test that getting cached data with None entry returns None."""
        # Configure the mock to raise an exception when called with None
        mock_dependencies['load'].side_effect = Exception("Invalid filepath")
        
        result = cache_manager.get_cached_data(None)
        assert result is None

    def test_summary_cache_entry_invalid_summary(self):
        """Test that SummaryCacheEntry raises ValueError for invalid summary."""
        with pytest.raises(ValueError, match="summary must be a str object"):
            SummaryCacheEntry(
                source_file=Path("test.pdf"),
                client="gpt-4o",
                summary=123  # Invalid: should be string
            )

    def test_summary_cache_entry_empty_summary(self):
        """Test that SummaryCacheEntry raises ValueError for empty summary."""
        with pytest.raises(ValueError, match="summary cannot be empty or just whitespace"):
            SummaryCacheEntry(
                source_file=Path("test.pdf"),
                client="gpt-4o",
                summary=""  # Invalid: empty string
            )

    def test_cache_entry_invalid_field_types(self):
        """Test that CacheEntry raises TypeError for invalid field types."""
        with pytest.raises(TypeError, match="source_file must be a Path object"):
            SummaryCacheEntry(
                source_file="not_a_path",  # Invalid: should be Path
                client="gpt-4o",
                summary="test summary"
            )
