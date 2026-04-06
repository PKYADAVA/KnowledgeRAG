"""
Pinecone vector store service.
Handles index creation, upsert, similarity search, and deletion.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from django.conf import settings
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document as LCDocument

from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Pinecone upsert batch size
UPSERT_BATCH_SIZE = 100


class VectorStoreService:
    """
    Manages interaction with Pinecone — index lifecycle,
    vector upsert from LangChain documents, and similarity retrieval.
    """

    def __init__(self):
        self._pc: Optional[Pinecone] = None
        self._index = None
        self._embedding_svc = EmbeddingService()

    @property
    def pc(self) -> Pinecone:
        if self._pc is None:
            self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        return self._pc

    def ensure_index(self) -> None:
        """Create Pinecone index if it does not exist."""
        index_name = settings.PINECONE_INDEX_NAME
        existing = [idx.name for idx in self.pc.list_indexes()]

        if index_name not in existing:
            logger.info(f"Creating Pinecone index: {index_name}")
            self.pc.create_index(
                name=index_name,
                dimension=settings.OPENAI_EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=settings.PINECONE_CLOUD,
                    region=settings.PINECONE_REGION,
                ),
            )
            # Wait for index to become ready
            for _ in range(30):
                desc = self.pc.describe_index(index_name)
                if desc.status.ready:
                    break
                time.sleep(2)
            logger.info(f"Pinecone index '{index_name}' is ready.")
        else:
            logger.debug(f"Pinecone index '{index_name}' already exists.")

    def get_vectorstore(self, namespace: str) -> PineconeVectorStore:
        """Return a LangChain PineconeVectorStore bound to a namespace."""
        self.ensure_index()
        index = self.pc.Index(settings.PINECONE_INDEX_NAME)
        return PineconeVectorStore(
            index=index,
            embedding=self._embedding_svc.client,
            namespace=namespace,
        )

    def upsert_documents(
        self,
        documents: List[LCDocument],
        namespace: str,
        batch_size: int = UPSERT_BATCH_SIZE,
    ) -> List[str]:
        """
        Upsert LangChain Document objects into Pinecone.
        Returns list of upserted vector IDs.
        """
        self.ensure_index()
        vectorstore = self.get_vectorstore(namespace)

        all_ids: List[str] = []
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            try:
                ids = vectorstore.add_documents(batch)
                all_ids.extend(ids)
                logger.debug(
                    f"Upserted batch {start // batch_size + 1} "
                    f"({len(batch)} docs) to namespace '{namespace}'"
                )
            except Exception as exc:
                logger.error(f"Upsert failed at batch starting {start}: {exc}")
                raise

        return all_ids

    def similarity_search(
        self,
        query: str,
        namespace: str,
        k: int = 5,
        score_threshold: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Similarity search returning docs with scores.
        Returns list of dicts: {content, score, metadata}.
        """
        vectorstore = self.get_vectorstore(namespace)

        try:
            results = vectorstore.similarity_search_with_relevance_scores(
                query=query,
                k=k,
                filter=filter_metadata,
            )
        except Exception as exc:
            logger.error(f"Similarity search error: {exc}")
            raise

        output = []
        for doc, score in results:
            if score >= score_threshold:
                output.append(
                    {
                        "content": doc.page_content,
                        "score": round(float(score), 4),
                        "metadata": doc.metadata,
                    }
                )

        logger.debug(
            f"Retrieved {len(output)} chunks from namespace '{namespace}' "
            f"(query: '{query[:60]}...')"
        )
        return output

    def multi_namespace_search(
        self,
        query: str,
        namespaces: List[str],
        k: int = 5,
        score_threshold: float = 0.0,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple Pinecone namespaces and merge results,
        re-ranking by score descending.
        """
        all_results: List[Dict[str, Any]] = []
        per_ns_k = max(k, 3)  # fetch a few more per namespace before merging

        for ns in namespaces:
            meta_filter = None
            if document_ids:
                meta_filter = {"document_id": {"$in": document_ids}}

            try:
                results = self.similarity_search(
                    query=query,
                    namespace=ns,
                    k=per_ns_k,
                    score_threshold=score_threshold,
                    filter_metadata=meta_filter,
                )
                all_results.extend(results)
            except Exception as exc:
                logger.warning(f"Search failed for namespace '{ns}': {exc}")

        # Sort by score descending, take top-k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:k]

    def delete_document(self, document_id: str, namespace: str) -> None:
        """Delete all vectors for a given document_id from a namespace."""
        try:
            index = self.pc.Index(settings.PINECONE_INDEX_NAME)
            # Use metadata filter to find and delete
            index.delete(
                filter={"document_id": {"$eq": document_id}},
                namespace=namespace,
            )
            logger.info(f"Deleted vectors for document {document_id} from '{namespace}'")
        except Exception as exc:
            logger.error(f"Failed to delete vectors for {document_id}: {exc}")
            raise

    def get_index_stats(self) -> Dict[str, Any]:
        """Return Pinecone index statistics."""
        self.ensure_index()
        index = self.pc.Index(settings.PINECONE_INDEX_NAME)
        stats = index.describe_index_stats()
        return {
            "total_vector_count": stats.total_vector_count,
            "dimension": stats.dimension,
            "namespaces": {
                ns: {"vector_count": data.vector_count}
                for ns, data in (stats.namespaces or {}).items()
            },
        }
