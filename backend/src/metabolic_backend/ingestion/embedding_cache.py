"""
Embedding cache system for reducing API costs.

This module provides both in-memory and file-based caching for embeddings,
allowing reuse of embeddings across multiple runs and reducing API calls.
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import pickle

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Persistent embedding cache with file-based storage.

    Uses MD5 hashing of text content as keys and stores embeddings
    in JSON format for easy inspection and portability.
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_memory_size: int = 1000,
        enable_file_cache: bool = True
    ):
        """
        Initialize embedding cache.

        Args:
            cache_dir: Directory for persistent cache files (defaults to .cache/embeddings)
            max_memory_size: Maximum number of embeddings to keep in memory
            enable_file_cache: Whether to use persistent file-based caching

        Example:
            # Default cache
            cache = EmbeddingCache()

            # Custom cache location
            cache = EmbeddingCache(cache_dir="/path/to/cache")

            # Memory-only cache (no persistence)
            cache = EmbeddingCache(enable_file_cache=False)
        """
        self.enable_file_cache = enable_file_cache

        # Set up cache directory
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Default: .cache/embeddings in project root
            project_root = Path(__file__).parent.parent.parent.parent
            self.cache_dir = project_root / ".cache" / "embeddings"

        if self.enable_file_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.index_file = self.cache_dir / "index.json"
            self._load_index()
        else:
            self.file_index = {}

        # In-memory cache for fast access
        self.memory_cache: Dict[str, List[float]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.max_memory_size = max_memory_size

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0
        }

    def _load_index(self):
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    self.file_index = json.load(f)
                logger.info(f"Loaded embedding cache index with {len(self.file_index)} entries")
            except Exception as e:
                logger.warning(f"Failed to load cache index: {e}, starting fresh")
                self.file_index = {}
        else:
            self.file_index = {}

    def _save_index(self):
        """Save cache index to disk."""
        if not self.enable_file_cache:
            return

        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.file_index, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    def _hash_text(self, text: str) -> str:
        """
        Generate MD5 hash for text.

        Args:
            text: Text to hash

        Returns:
            MD5 hash as hexadecimal string
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _get_cache_file(self, text_hash: str) -> Path:
        """
        Get cache file path for a hash.

        Uses subdirectories based on first 2 characters of hash
        to avoid too many files in one directory.

        Args:
            text_hash: MD5 hash of text

        Returns:
            Path to cache file
        """
        # Use first 2 characters as subdirectory
        subdir = self.cache_dir / text_hash[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{text_hash}.json"

    def get(self, text: str) -> Optional[List[float]]:
        """
        Get embedding from cache.

        Checks memory cache first, then file cache if enabled.

        Args:
            text: Text to look up

        Returns:
            Embedding vector if found, None otherwise

        Example:
            embedding = cache.get("대사증후군이란 무엇인가?")
            if embedding:
                print("Cache hit!")
            else:
                print("Cache miss, need to generate embedding")
        """
        text_hash = self._hash_text(text)

        # Check memory cache first
        if text_hash in self.memory_cache:
            self.access_times[text_hash] = datetime.now()
            self.stats["hits"] += 1
            logger.debug(f"Memory cache hit for hash {text_hash[:8]}...")
            return self.memory_cache[text_hash]

        # Check file cache
        if self.enable_file_cache and text_hash in self.file_index:
            try:
                cache_file = self._get_cache_file(text_hash)
                if cache_file.exists():
                    with open(cache_file, 'r') as f:
                        data = json.load(f)

                    embedding = data['embedding']

                    # Load into memory cache
                    self._put_memory(text_hash, embedding)

                    self.stats["hits"] += 1
                    logger.debug(f"File cache hit for hash {text_hash[:8]}...")
                    return embedding
            except Exception as e:
                logger.warning(f"Failed to load from file cache: {e}")
                # Remove invalid entry from index
                if text_hash in self.file_index:
                    del self.file_index[text_hash]
                    self._save_index()

        # Cache miss
        self.stats["misses"] += 1
        return None

    def put(self, text: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None):
        """
        Store embedding in cache.

        Saves to both memory and file cache (if enabled).

        Args:
            text: Original text
            embedding: Embedding vector
            metadata: Optional metadata (model name, timestamp, etc.)

        Example:
            cache.put(
                text="대사증후군의 진단 기준",
                embedding=[0.1, 0.2, ...],
                metadata={"model": "text-embedding-3-small", "dimensions": 1536}
            )
        """
        text_hash = self._hash_text(text)

        # Store in memory cache
        self._put_memory(text_hash, embedding)

        # Store in file cache
        if self.enable_file_cache:
            try:
                cache_file = self._get_cache_file(text_hash)

                # Prepare data
                data = {
                    "hash": text_hash,
                    "text_preview": text[:100] + "..." if len(text) > 100 else text,
                    "text_length": len(text),
                    "embedding": embedding,
                    "embedding_dimension": len(embedding),
                    "cached_at": datetime.now().isoformat(),
                    "metadata": metadata or {}
                }

                # Save to file
                with open(cache_file, 'w') as f:
                    json.dump(data, f)

                # Update index
                self.file_index[text_hash] = {
                    "file": str(cache_file.relative_to(self.cache_dir)),
                    "cached_at": data["cached_at"],
                    "text_length": data["text_length"],
                    "dimension": data["embedding_dimension"]
                }
                self._save_index()

                self.stats["saves"] += 1
                logger.debug(f"Saved embedding to cache (hash: {text_hash[:8]}...)")

            except Exception as e:
                logger.error(f"Failed to save to file cache: {e}")

    def _put_memory(self, text_hash: str, embedding: List[float]):
        """
        Store embedding in memory cache.

        Args:
            text_hash: Hash of text
            embedding: Embedding vector
        """
        # Evict oldest entry if cache is full
        if len(self.memory_cache) >= self.max_memory_size:
            if self.access_times:
                oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
                if oldest_key in self.memory_cache:
                    del self.memory_cache[oldest_key]
                if oldest_key in self.access_times:
                    del self.access_times[oldest_key]

        self.memory_cache[text_hash] = embedding
        self.access_times[text_hash] = datetime.now()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hits, misses, hit rate, memory size, file size

        Example:
            stats = cache.get_stats()
            print(f"Hit rate: {stats['hit_rate']:.1%}")
            print(f"Total entries: {stats['total_file_entries']}")
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "saves": self.stats["saves"],
            "hit_rate": hit_rate,
            "memory_entries": len(self.memory_cache),
            "max_memory_size": self.max_memory_size,
            "total_file_entries": len(self.file_index) if self.enable_file_cache else 0,
            "cache_dir": str(self.cache_dir) if self.enable_file_cache else None
        }

    def clear_memory(self):
        """
        Clear in-memory cache.

        File cache remains intact.

        Example:
            cache.clear_memory()  # Free up memory but keep persistent cache
        """
        self.memory_cache.clear()
        self.access_times.clear()
        logger.info("Cleared memory cache")

    def clear_all(self):
        """
        Clear both memory and file cache.

        **WARNING**: This deletes all cached embeddings permanently.

        Example:
            cache.clear_all()  # Delete everything
        """
        # Clear memory
        self.clear_memory()

        # Clear file cache
        if self.enable_file_cache:
            try:
                # Remove all cache files
                for hash_key in list(self.file_index.keys()):
                    cache_file = self._get_cache_file(hash_key)
                    if cache_file.exists():
                        cache_file.unlink()

                # Clear index
                self.file_index = {}
                self._save_index()

                logger.warning("⚠️  Cleared all cache files")
            except Exception as e:
                logger.error(f"Failed to clear file cache: {e}")

        # Reset stats
        self.stats = {"hits": 0, "misses": 0, "saves": 0}

    def get_size_estimate(self) -> Dict[str, Any]:
        """
        Get estimated size of cache on disk.

        Returns:
            Dict with file count and total size in MB

        Example:
            size_info = cache.get_size_estimate()
            print(f"Cache size: {size_info['size_mb']:.1f} MB")
        """
        if not self.enable_file_cache:
            return {"file_count": 0, "size_mb": 0.0}

        total_size = 0
        file_count = 0

        try:
            for cache_file in self.cache_dir.rglob("*.json"):
                if cache_file != self.index_file:
                    total_size += cache_file.stat().st_size
                    file_count += 1

            return {
                "file_count": file_count,
                "size_bytes": total_size,
                "size_mb": total_size / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Failed to calculate cache size: {e}")
            return {"file_count": 0, "size_mb": 0.0, "error": str(e)}


# Convenience function
def create_cache(
    cache_dir: Optional[str] = None,
    enable: bool = True,
    **kwargs
) -> Optional[EmbeddingCache]:
    """
    Create an embedding cache instance.

    Args:
        cache_dir: Directory for cache files
        enable: Whether to enable caching
        **kwargs: Additional arguments for EmbeddingCache

    Returns:
        EmbeddingCache instance if enabled, None otherwise

    Example:
        # Enable caching
        cache = create_cache()

        # Disable caching
        cache = create_cache(enable=False)

        # Custom cache directory
        cache = create_cache(cache_dir="/tmp/embeddings_cache")
    """
    if not enable:
        return None

    return EmbeddingCache(cache_dir=cache_dir, **kwargs)


# Example usage
if __name__ == "__main__":
    # Create cache
    cache = EmbeddingCache()

    # Simulate some embeddings
    texts = [
        "대사증후군은 당뇨병, 고혈압, 비만이 함께 나타나는 상태입니다.",
        "인슐린 저항성은 대사증후군의 주요 원인 중 하나입니다.",
        "규칙적인 운동과 건강한 식단이 예방에 도움이 됩니다."
    ]

    # Save some embeddings
    for i, text in enumerate(texts):
        fake_embedding = [float(i)] * 1536
        cache.put(text, fake_embedding, metadata={"model": "test"})

    # Try to retrieve
    for text in texts:
        embedding = cache.get(text)
        if embedding:
            print(f"✓ Retrieved embedding for: {text[:50]}...")
        else:
            print(f"✗ No embedding found for: {text[:50]}...")

    # Print stats
    stats = cache.get_stats()
    print(f"\nCache statistics:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit rate: {stats['hit_rate']:.1%}")
    print(f"  File entries: {stats['total_file_entries']}")

    size_info = cache.get_size_estimate()
    print(f"  Cache size: {size_info['size_mb']:.2f} MB")
