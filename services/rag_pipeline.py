"""
Core RAG pipeline — retrieval, prompt construction, LLM call,
and source citation assembly.
"""
import logging
from typing import Any, Dict, Generator, List, Optional

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from .vector_store import VectorStoreService

logger = logging.getLogger(__name__)

# ── Prompt templates ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a knowledgeable assistant that answers questions based on the provided document context.

Rules:
1. Answer ONLY from the context below. Do NOT use external knowledge.
2. If the question asks about something that is clearly NOT mentioned in the context, say so directly (e.g. "No, Spring Boot is not mentioned in the document.") and suggest what related information IS available.
3. Only use "I don't have enough information" if the context is genuinely ambiguous or incomplete — not when the answer is simply "no" or "not mentioned".
4. Always cite your sources using the format [Source: <document_title>, Page <page>].
5. Be concise but thorough. Use bullet points for lists.
6. If multiple documents are relevant, synthesize their information clearly.

Context:
{context}
"""

HUMAN_PROMPT = """{question}"""


class RAGPipeline:
    """
    Orchestrates the full RAG flow:
    retrieve → format → prompt → LLM → parse → cite.
    """

    def __init__(self):
        self._llm: Optional[ChatOpenAI] = None
        self._vs = VectorStoreService()

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.OPENAI_LLM_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0.1,
                max_tokens=2048,
                request_timeout=60,
            )
        return self._llm

    def query(
        self,
        question: str,
        namespaces: List[str],
        document_ids: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Run RAG query and return:
        {answer, sources, model, tokens_used, avg_score}
        """
        # ── Retrieve ───────────────────────────────────────────────────────────
        if not namespaces:
            return {
                "answer": "Please select at least one document to chat with.",
                "sources": [],
                "model": settings.OPENAI_LLM_MODEL,
                "tokens_used": 0,
                "avg_score": None,
            }

        chunks = self._vs.multi_namespace_search(
            query=question,
            namespaces=namespaces,
            k=settings.RAG_TOP_K,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
            document_ids=document_ids,
        )

        if not chunks:
            return {
                "answer": (
                    "I couldn't find relevant information in the selected documents "
                    "for your question. Try rephrasing or selecting different documents."
                ),
                "sources": [],
                "model": settings.OPENAI_LLM_MODEL,
                "tokens_used": 0,
                "avg_score": None,
            }

        # ── Format context ─────────────────────────────────────────────────────
        context, sources = self._build_context(chunks)
        avg_score = sum(c["score"] for c in chunks) / len(chunks)

        # ── Build messages ─────────────────────────────────────────────────────
        messages = []
        messages.append(SystemMessage(content=SYSTEM_PROMPT.format(context=context)))

        # Inject recent chat history for multi-turn coherence
        if chat_history:
            for turn in chat_history[-6:]:  # last 3 turns (user+assistant)
                if turn["role"] == "user":
                    messages.append(HumanMessage(content=turn["content"]))
                elif turn["role"] == "assistant":
                    messages.append(AIMessage(content=turn["content"]))

        messages.append(HumanMessage(content=question))

        # ── LLM call ──────────────────────────────────────────────────────────
        logger.info(
            f"RAG query: '{question[:80]}' | {len(chunks)} chunks | "
            f"{len(namespaces)} namespaces | avg_score={avg_score:.3f}"
        )
        response = self.llm.invoke(messages)
        answer = response.content
        tokens_used = getattr(response, "usage_metadata", {})
        total_tokens = (
            tokens_used.get("total_tokens", 0) if isinstance(tokens_used, dict) else 0
        )

        return {
            "answer": answer,
            "sources": sources,
            "model": settings.OPENAI_LLM_MODEL,
            "tokens_used": total_tokens,
            "avg_score": round(avg_score, 4),
        }

    def stream(
        self,
        question: str,
        namespaces: List[str],
        document_ids: Optional[List[str]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming version — yields token dicts, then a final sources dict.
        Used by the SSE endpoint.
        """
        if not namespaces:
            yield {"type": "token", "content": "Please select at least one document."}
            yield {"type": "done"}
            return

        chunks = self._vs.multi_namespace_search(
            query=question,
            namespaces=namespaces,
            k=settings.RAG_TOP_K,
            score_threshold=settings.RAG_SCORE_THRESHOLD,
            document_ids=document_ids,
        )

        if not chunks:
            yield {
                "type": "token",
                "content": "No relevant information found in the selected documents.",
            }
            yield {"type": "done"}
            return

        context, sources = self._build_context(chunks)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(context=context)),
            HumanMessage(content=question),
        ]

        # Stream tokens
        for token_chunk in self.llm.stream(messages):
            if token_chunk.content:
                yield {"type": "token", "content": token_chunk.content}

        # Emit sources after stream completes
        yield {"type": "sources", "sources": sources}

    def _build_context(
        self, chunks: List[Dict[str, Any]]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Build the context string and source list from retrieved chunks.
        Returns (context_string, sources_list).
        """
        context_parts: List[str] = []
        sources: List[Dict[str, Any]] = []

        for i, chunk in enumerate(chunks, 1):
            meta = chunk["metadata"]
            doc_title = meta.get("title", meta.get("source", "Unknown Document"))
            page = meta.get("page", meta.get("page_number", "?"))

            context_parts.append(
                f"[{i}] Source: {doc_title} | Page: {page} | Score: {chunk['score']}\n"
                f"{chunk['content']}\n"
            )
            sources.append(
                {
                    "index": i,
                    "document_id": meta.get("document_id", ""),
                    "document_title": doc_title,
                    "page_number": page,
                    "score": chunk["score"],
                    "excerpt": chunk["content"][:200] + "..."
                    if len(chunk["content"]) > 200
                    else chunk["content"],
                }
            )

        return "\n\n".join(context_parts), sources
