"""
OpenAI embeddings service with caching and retry logic.
"""
import hashlib
import logging
import time
from typing import List, Optional

from django.conf import settings
from django.core.cache import cache
from langchain_openai import OpenAIEmbeddings
from openai import RateLimitError, APIError

logger = logging.getLogger(__name__)

# Cache TTL for embeddings (7 days — they're deterministic)
EMBEDDING_CACHE_TTL = 7 * 24 * 3600


class EmbeddingService:
    """Wraps OpenAI embeddings with Redis caching and exponential backoff."""

    def __init__(self):
        self._client: Optional[OpenAIEmbeddings] = None

    @property
    def client(self) -> OpenAIEmbeddings:
        if self._client is None:
            self._client = OpenAIEmbeddings(
                model=settings.OPENAI_EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                dimensions=settings.OPENAI_EMBEDDING_DIMENSION,
                show_progress_bar=False,
            )
        return self._client

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(
            f"{settings.OPENAI_EMBEDDING_MODEL}:{text}".encode()
        ).hexdigest()
        return f"emb:{digest}"

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string, with Redis cache."""
        key = self._cache_key(text)
        cached = cache.get(key)
        if cached is not None:
            return cached

        vector = self._embed_with_retry([text])[0]
        cache.set(key, vector, timeout=EMBEDDING_CACHE_TTL)
        return vector

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed texts.
        - Checks cache for each text.
        - Batches cache misses into OpenAI call.
        - Fills results back in original order.
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        miss_indices: List[int] = []
        miss_texts: List[str] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            cached = cache.get(key)
            if cached is not None:
                results[i] = cached
            else:
                miss_indices.append(i)
                miss_texts.append(text)

        if miss_texts:
            logger.debug(f"Embedding {len(miss_texts)} texts (cache misses)")
            # Batch into chunks of 100 (OpenAI limit)
            batch_size = 100
            embeddings: List[List[float]] = []
            for start in range(0, len(miss_texts), batch_size):
                batch = miss_texts[start : start + batch_size]
                embeddings.extend(self._embed_with_retry(batch))

            for idx, (orig_i, vector) in enumerate(zip(miss_indices, embeddings)):
                results[orig_i] = vector
                cache.set(self._cache_key(miss_texts[idx]), vector, timeout=EMBEDDING_CACHE_TTL)

        return results  # type: ignore[return-value]

    def _embed_with_retry(
        self, texts: List[str], max_retries: int = 3
    ) -> List[List[float]]:
        """Call OpenAI with exponential backoff on rate limits."""
        for attempt in range(max_retries):
            try:
                return self.client.embed_documents(texts)
            except RateLimitError:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning(f"OpenAI rate limit. Waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            except APIError as exc:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt
                logger.warning(f"OpenAI API error: {exc}. Retrying in {wait}s")
                time.sleep(wait)
        raise RuntimeError("OpenAI embedding failed after all retries")

    def embed_query(self, query: str) -> List[float]:
        """Embed a query string (query-optimised model call)."""
        key = self._cache_key(f"__query__{query}")
        cached = cache.get(key)
        if cached is not None:
            return cached

        for attempt in range(3):
            try:
                vector = self.client.embed_query(query)
                cache.set(key, vector, timeout=3600)  # shorter TTL for queries
                return vector
            except RateLimitError:
                time.sleep(2 ** attempt * 5)
            except APIError as exc:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("Query embedding failed after all retries")
