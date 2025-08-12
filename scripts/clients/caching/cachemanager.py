
import hashlib
from utils import *
from .cacheschema import *


class ClientCacheManager:
    def __init__(self):
        self.config = load_config()
        self.logger = setup_logger(name = 'CacheManager', config=self.config)
        self.cache_paths = self.config.get('caching', {}).get('directories', {})

    def _get_cache_filepath(self, cache_type: type[CacheEntry]) -> str | None:
        """
        Get the filepath for a given CacheEntry type.
        
        Args:
            cache_type (type[CacheEntry]): The CacheEntry subclass type
            
        Returns:
            str | None: The filepath for the cache type, or None if invalid/unsupported
        """
        # Validate cache_type
        if not (isinstance(cache_type, type) and issubclass(cache_type, CacheEntry)):
            self.logger.error("cache_type must be a subclass of CacheEntry, got: %s", cache_type)
            return None
            
        self.logger.debug("Finding cache filepath for CacheEntry type '%s'", cache_type.__name__)
        
        # Map cache type to filepath
        if cache_type == SummaryCacheEntry:
            filepath = self.cache_paths.get('summary_cache')
            self.logger.debug("Mapped %s to filepath: '%s'", cache_type.__name__, filepath)
            return filepath
        else:
            self.logger.error("Unsupported cache type: %s", cache_type.__name__)
            return None

    def cache_entry(self, data: CacheEntry):
        """
        Cache a data entry to the appropriate JSON file based on its type.
        
        Automatically determines the correct cache file location by inspecting
        the data object's type and mapping it to the corresponding cache path
        in self.cache_paths. Stores entries in a keyed dictionary format where
        keys are content signatures (source_file + client).
        
        Args:
            data (CacheEntry): The cache entry object to store. Must be a subclass
                              of CacheEntry (e.g., SummaryCacheEntry).
        
        Raises:
            TypeError: If the data type is not a recognized cache entry type.
        """
        filepath = self._get_cache_filepath(type(data))
        if not filepath:
            raise TypeError("Invalid cache entry")
        
        # Load existing cache data as a dictionary
        try:
            cache_data = load_from_json(filepath) or {}
        except Exception as e:
            self.logger.warning("Could not load existing cache, starting fresh: %s", e)
            cache_data = {}
        
        # Create cache key from source_file and client
        cache_key = f"{data.source_file}#{data.client}"
        
        # Store the entry data
        data_dict = data.to_dict()
        cache_data[cache_key] = data_dict
        
        # Save back to file
        save_to_json(cache_data, filepath=filepath)
        self.logger.debug("Cached entry with key '%s'", cache_key)

    def get_cached_data(self, filepath: str | type[CacheEntry]) -> dict | None:
        """
        Retrieve (ALL) cached data from JSON file.
        
        Automatically determines the correct cache file location by either:
        1. Using the provided filepath string directly, or
        2. Using the CacheEntry class type to map it to the corresponding
           cache path in self.cache_paths (e.g., SummaryCacheEntry -> 'summary_cache.json').
        
        Args:
            filepath (str | type[CacheEntry]): Either a direct filepath string or a CacheEntry
                                              class type which will be used to determine the
                                              appropriate cache file location.
        
        Returns:
            dict | None: The entire cached data dictionary, or None if loading fails.
        """
        if isinstance(filepath, type) and issubclass(filepath, CacheEntry):
            filepath = self._get_cache_filepath(filepath)
            if not filepath:
                return None

        try:
            cached_data = load_from_json(filepath)
            return cached_data
        except Exception as e:
            self.logger.error("Failed to load cached summary from %s: %s", filepath, str(e))
            return None

    def get_cached_entry(self, client: Optional[str] , source_file: Path,  cache_type: type[CacheEntry]):
