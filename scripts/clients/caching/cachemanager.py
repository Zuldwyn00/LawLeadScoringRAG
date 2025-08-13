
from pathlib import Path
from utils import *
from .cacheschema import *
from .hashing import get_partition_path


class ClientCacheManager:
    def __init__(self):
        self.config = load_config()
        self.logger = setup_logger(name = 'CacheManager', config=self.config)
        self.cache_paths = self.config.get('caching', {}).get('directories', {})
        self.partition_count = 50  # Number of partition files to create

        ensure_directories([Path(path) for path in self.cache_paths.values()])
        
    def get_cache_directory(self, cache_type: type[CacheEntry]) -> str | None:
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
            filepath = self.cache_paths.get('summary')
            self.logger.debug("Mapped %s to filepath: '%s'", cache_type.__name__, filepath)
            return filepath
        else:
            self.logger.error("Unsupported cache type: %s", cache_type.__name__)
            return None

    def cache_entry(self, data: CacheEntry):
        cache_key = f"{data.source_file}#{data.client}"
        base_dir = self.get_cache_directory(type(data))
        base_name = type(data).__name__.lower()
        
        cache_path = get_partition_path(cache_key, base_dir, base_name)
        try:
            cache_data = load_from_json(cache_path)
        except Exception as e:
            self.logger.warning("No existing cache found at '%s', initializing new cache file: %s", cache_path, e)
            cache_data = {}

        data_dict = data.to_dict()
        cache_data[cache_key] = data_dict
        
        save_to_json(cache_data, filepath=cache_path)
        self.logger.debug("Cached entry with key '%s' into file '%s'.", cache_key, cache_path)

    
    def get_cached_entry(self, client: str, source_file: str, cache_type: type[CacheEntry]) -> CacheEntry | None:
        """
        Retrieves a cached entry for a specific client and source file combination.

        Constructs a cache key from the source file and client, then attempts to load
        and reconstruct the corresponding cache entry from the partitioned cache storage.
        A None return value indicates the caller should generate fresh data for this entry.

        Args:
            client (str): The client identifier used for cache key generation.
            source_file (str): The source file path used for cache key generation.
            cache_type (type[CacheEntry]): The specific cache entry type to reconstruct.
                Used to determine the cache directory and for object reconstruction.

        Returns:
            CacheEntry | None: The reconstructed cache entry object if found and valid.
                None indicates a cache miss (no existing entry) or reconstruction failure,
                signaling the caller to process new data for this entry since it doesn't
                exist in the cache. This is normal behavior, not an error condition.

        Raises:
            No exceptions are raised directly. All errors are caught and logged,
            with None returned to indicate cache miss or failure.
        """
        cache_key = f"{source_file}#{client}"
        base_dir = self.get_cache_directory(cache_type)
        base_name = cache_type.__name__.lower() 

        cache_path = get_partition_path(cache_key, base_dir, base_name)

        try:
            cache_data = load_from_json(cache_path)
        except Exception as e:
            self.logger.info("Cache file not found at '%s', returning None for cache miss. '%s'", cache_path, e)
            return None  # Cache miss: no existing data found, caller will need to generate fresh content, this is expected behavior and is not indicative of an error

        if cache_key in cache_data:
            entry_dict = cache_data[cache_key]
            self.logger.debug("Cache hit for key '%s', reconstructing %s object", cache_key, cache_type.__name__)

            try:
                cache_entry = cache_type.from_dict(entry_dict) #turn the entry_dict back into a cacheentry object
                return cache_entry
            except Exception as e:
                self.logger.error("Failed to reconstruct '%s' from cached data: '%s'.", cache_type.__name__, e)
                return None
        
        self.logger.debug("Cache miss for key '%s'", cache_key)
        return None 
    