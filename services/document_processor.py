"""
Document loading, chunking, and metadata enrichment.
Supports PDF, DOCX, TXT, and Markdown.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document as LCDocument

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    chunks: List[LCDocument] = field(default_factory=list)
    page_count: int = 0
    chunk_count: int = 0
    error: str = ""


class DocumentProcessor:
    """Loads documents from disk and splits them into LangChain Document chunks."""

    LOADER_MAP = {
        "pdf": PyPDFLoader,
        "docx": Docx2txtLoader,
        "txt": TextLoader,
        "md": UnstructuredMarkdownLoader,
    }

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def process(
        self,
        file_path: str,
        file_type: str,
        document_id: str,
        owner_id: str,
        extra_metadata: Dict[str, Any] = None,
    ) -> ProcessingResult:
        """
        Full processing pipeline:
        1. Load document from path.
        2. Split into chunks.
        3. Enrich each chunk's metadata.
        Returns ProcessingResult.
        """
        result = ProcessingResult()
        extra_metadata = extra_metadata or {}

        # ── Step 1: Load ───────────────────────────────────────────────────────
        raw_docs = self._load(file_path, file_type)
        if not raw_docs:
            result.error = f"No content extracted from file: {file_path}"
            return result

        result.page_count = self._count_pages(raw_docs, file_type)
        logger.info(
            f"Loaded {len(raw_docs)} raw pages from {os.path.basename(file_path)}"
        )

        # ── Step 2: Split ──────────────────────────────────────────────────────
        chunks = self.splitter.split_documents(raw_docs)
        if not chunks:
            result.error = "Document produced no text chunks."
            return result

        # ── Step 3: Enrich metadata ────────────────────────────────────────────
        for i, chunk in enumerate(chunks):
            chunk.metadata.update(
                {
                    "document_id": document_id,
                    "owner_id": owner_id,
                    "chunk_index": i,
                    "file_type": file_type,
                    "source": os.path.basename(file_path),
                    **extra_metadata,
                }
            )

        result.chunks = chunks
        result.chunk_count = len(chunks)
        logger.info(
            f"Produced {len(chunks)} chunks from document {document_id}"
        )
        return result

    def _load(self, file_path: str, file_type: str) -> List[LCDocument]:
        loader_cls = self.LOADER_MAP.get(file_type.lower())
        if loader_cls is None:
            raise ValueError(f"Unsupported file type: {file_type}")

        try:
            loader = loader_cls(file_path)
            return loader.load()
        except Exception as exc:
            logger.error(f"Failed to load {file_path} as {file_type}: {exc}")
            raise

    def _count_pages(self, docs: List[LCDocument], file_type: str) -> int:
        if file_type == "pdf":
            # PyPDFLoader gives one document per page
            return len(docs)
        # For other types, estimate based on content length
        total_chars = sum(len(d.page_content) for d in docs)
        return max(1, total_chars // 3000)
