
from utils import *
from .cacheschema import *


class ClientCacheManager:
    def __init__(self):
        self.logger = setup_logger(name = 'CacheManager')
        self.config = load_config()
        self.cache_paths = {
            'summary_cache': 'summary_cache.json',
        }

    def cache_entry(self, data: CacheEntry):
        """
        Cache a data entry to the appropriate JSON file based on its type.
        
        Automatically determines the correct cache file location by inspecting
        the data object's type and mapping it to the corresponding cache path
        in self.cache_paths. 
        
        Args:
            data (CacheEntry): The cache entry object to store. Must be a subclass
                              of CacheEntry (e.g., SummaryCacheEntry).
        
        Raises:
            TypeError: If the data type is not a recognized cache entry type.
        """
        def _validate_type_filepath(self, data) -> str:
            if isinstance(data, SummaryCacheEntry):
                filepath = self.cache_paths.get('summary_cache')
                self.logger.debug("Caching as type '%s' to '%s'.", type(data).__name__, filepath)
                return filepath
            
            self.logger.error("Invalid type for cache entry, undefined cache entry type: '%s'", type(data).__name__)
            raise TypeError("Invalid cache entry")
        
        filepath = _validate_type_filepath(self, data)
        data_dict = data.to_dict()
        save_to_json(data_dict, filepath=filepath)

    def get_cached_data(self, filepath: str | CacheEntry):
        """
        Retrieve cached data from JSON file.
        
        Automatically determines the correct cache file location by either:
        1. Using the provided filepath string directly, or
        2. Inspecting the CacheEntry object's type and mapping it to the corresponding
           cache path in self.cache_paths (e.g., SummaryCacheEntry -> 'summary_cache.json').
        
        Args:
            filepath (str | CacheEntry): Either a direct filepath string or a CacheEntry
                                        object whose type will be used to determine the
                                        appropriate cache file location.
        
        Returns:
            dict | None: The cached data as a dictionary, or None if loading fails.
        """
        if isinstance(filepath, CacheEntry):
            self.logger.debug("filepath given as a CacheEntry object, finding correct json filepath based on object type '%s'", type(filepath).__name__)
            if isinstance(filepath, SummaryCacheEntry):
                filepath = self.cache_paths.get('summary_cache')
                self.logger.debug("Getting cache data from '%s'.", filepath)

        try:
            cached_data = load_from_json(filepath)
            return cached_data
        except Exception as e:
            self.logger.error("Failed to load cached summary from %s: %s", filepath, str(e))
            return None