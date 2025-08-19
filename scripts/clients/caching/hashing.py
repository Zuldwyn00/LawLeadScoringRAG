import hashlib
from pathlib import Path


def compute_partition_index(cache_key: str, partition_count: int = 50) -> int:
    """
    Compute the deterministic partition index for a given cache key.

    Args:
        cache_key (str): Key used to select a partition (e.g., "{source_file}#{client}").
        partition_count (int): Total number of partitions. Must be > 0.

    Returns:
        int: Partition index in [0, partition_count - 1].
    """
    if partition_count <= 0:
        raise ValueError("partition_count must be greater than 0")

    hash_number = int(hashlib.md5(cache_key.encode()).hexdigest(), 16)
    return hash_number % partition_count


def build_partition_filename(base_name: str, partition_index: int) -> str:
    """
    Build a partitioned filename following "{base_name}.part_XX.json".

    Args:
        base_name (str): Logical group name (e.g., "summary").
        partition_index (int): Precomputed partition index.

    Returns:
        str: Filename like "summary.part_03.json".
    """
    return f"{base_name}.part_{partition_index:02d}.json"


def _validate_get_partition_path_args(
    cache_key: str,
    base_dir: str | Path,
    base_name: str,
    partition_count: int = 50,
) -> None:
    """
    Validate arguments provided to get_partition_path.

    Args:
        cache_key (str): Key used to select a partition (e.g., "{source_file}#{client}").
        base_dir (str | Path): Directory where partition files live.
        base_name (str): Logical group name (e.g., "summary").
        partition_count (int): Total number of partitions. Must be > 0.

    Raises:
        TypeError: If any argument has an invalid type.
        ValueError: If any argument value is missing/invalid.
    """
    if not isinstance(cache_key, str):
        raise TypeError(f"cache_key must be str, got {type(cache_key).__name__}")
    if cache_key.strip() == "":
        raise ValueError("cache_key must be a non-empty string")

    if base_dir is None or (isinstance(base_dir, str) and not base_dir.strip()):
        raise ValueError("base_dir must be a non-empty path")
    if not isinstance(base_dir, (str, Path)):
        raise TypeError(f"base_dir must be str or Path, got {type(base_dir).__name__}")

    if not isinstance(base_name, str):
        raise TypeError(f"base_name must be str, got {type(base_name).__name__}")
    if base_name.strip() == "":
        raise ValueError("base_name must be a non-empty string")

    if not isinstance(partition_count, int):
        raise TypeError(
            f"partition_count must be int, got {type(partition_count).__name__}"
        )
    if partition_count <= 0:
        raise ValueError("partition_count must be greater than 0")


def get_partition_path(
    cache_key: str,
    base_dir: str | Path,
    base_name: str,
    partition_count: int = 50,
) -> str:
    """
    Build full path for a partitioned cache file using a directory and base name.

    Args:
        cache_key (str): Key used to select a partition.
        base_dir (Union[str, Path]): Directory where partition files live.
        base_name (str): Logical group name (e.g., "summary").
        partition_count (int): Total number of partitions.

    Returns:
        str: Full path like ".../summary_cache/summary.part_03.json".
    """
    _validate_get_partition_path_args(cache_key, base_dir, base_name, partition_count)
    partition_index = compute_partition_index(cache_key, partition_count)
    filename = build_partition_filename(base_name, partition_index)
    return str(Path(base_dir) / filename)
