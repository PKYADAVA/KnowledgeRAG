# KnowledgeRAG

A production-grade **ChatGPT-like document assistant** built with Django, HTMX, LangChain, OpenAI, and Pinecone.

---

## Architecture Overview

```
Browser ──HTMX──► Django Views ──► RAG Pipeline ──► OpenAI GPT-4o
                      │                  │
                   PostgreSQL        Pinecone
                   (sessions)       (vectors)
                      │
                   Redis ──► Celery Workers (ingestion)
```

### Django Apps

| App | Responsibility |
|-----|---------------|
| `users` | Registration, login, session auth, profiles |
| `documents` | Upload, file validation, processing state |
| `rag` | Pipeline views/status (logic in `services/`) |
| `chat` | Sessions, messages, HTMX chat UI |

### Services Layer

| Service | Description |
|---------|-------------|
| `services/embeddings.py` | OpenAI embeddings with Redis caching + retry |
| `services/vector_store.py` | Pinecone upsert, similarity search, multi-namespace |
| `services/document_processor.py` | PDF/DOCX/TXT loading + chunking via LangChain |
| `services/rag_pipeline.py` | Full RAG flow: retrieve → prompt → LLM → cite |

### Task Queues

| Queue | Workers | Tasks |
|-------|---------|-------|
| `ingestion` | 2 | Document loading, chunking, embedding, Pinecone upsert |
| `chat` | 4 | Reserved for async chat processing |

---

## Quick Start (Docker)

### Prerequisites

- Docker & Docker Compose v2
- OpenAI API key
- Pinecone API key

### 1. Clone & Configure

```bash
git clone <repo-url>
cd KnowledgeRAG

# Create .env from template
make setup-env

# Edit with your API keys
nano backend/.env
```

Required values in `.env`:
```env
SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=knowledge-rag
```

### 2. Start Everything

```bash
make build          # Build Docker images
make up             # Start all services
make migrate        # Apply database migrations
make createsuperuser  # Create admin user
```

### 3. Open the App

| Service | URL |
|---------|-----|
| App | http://localhost:8000 |
| Admin | http://localhost:8000/admin |
| Flower | http://localhost:5555 (admin/password) |

---

## Local Development (without Docker)

### Prerequisites

```bash
python 3.11+
PostgreSQL 14+
Redis 7+
```

### Setup

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Create and edit .env
cp backend/.env.example backend/.env

# Run migrations
cd backend && python manage.py migrate

# Start dev server
python manage.py runserver
```

### Start Celery Workers

```bash
# Terminal 2 — ingestion worker
make worker

# Terminal 3 — beat scheduler
make beat
```

---

## Usage Guide

### 1. Register / Login

Navigate to `http://localhost:8000/users/register/`

### 2. Upload Documents

- Go to `/dashboard/upload/`
- Drag-and-drop or browse for PDF, DOCX, TXT, or Markdown
- Upload triggers async Celery task
- Card shows real-time status updates (HTMX polling every 3s)

### 3. Chat

- From dashboard, click **"Start Chat"** on a ready document
- Or go to `/chat/new/`
- Select documents in the left sidebar
- Type your question → HTMX sends to `/chat/<id>/send/`
- Answer appears with collapsible **source citations**

### 4. Streaming (SSE)

For real-time token streaming, use the SSE endpoint:
```javascript
const es = new EventSource(`/chat/${sessionId}/stream/?q=What+is+this+document+about`);
es.onmessage = e => {
  const data = JSON.parse(e.data);
  if (data.type === 'token') appendToken(data.content);
  if (data.type === 'sources') showSources(data.sources);
  if (data.type === 'done') es.close();
};
```

---

## RAG Pipeline Details

### Ingestion Flow

```
File Upload
    │
    ▼
Celery Task (process_document)
    │
    ├─► DocumentProcessor
    │       ├─ PyPDFLoader / Docx2txtLoader / TextLoader
    │       └─ RecursiveCharacterTextSplitter
    │               chunk_size=1000, overlap=200
    │
    ├─► VectorStoreService.upsert_documents()
    │       ├─ EmbeddingService (OpenAI text-embedding-3-small)
    │       └─ Pinecone upsert (batched, 100/batch)
    │
    └─► DocumentChunk.bulk_create() → PostgreSQL
```

### Query Flow

```
User Query
    │
    ▼
RAGPipeline.query()
    │
    ├─► VectorStoreService.multi_namespace_search()
    │       ├─ Pinecone similarity_search (top-k=5, threshold=0.7)
    │       └─ Multi-namespace merge + re-rank by score
    │
    ├─► Build context string with citations
    │
    ├─► ChatOpenAI.invoke()
    │       └─ System prompt: "Answer ONLY from context. Cite sources."
    │       └─ Last 6 history messages for multi-turn
    │
    └─► Return {answer, sources, model, tokens_used, avg_score}
```

### Prompt Design

```
System: You are a document assistant. Answer ONLY from the context.
        Cite sources as [Source: <title>, Page <n>].
        Context: [retrieved chunks with scores]

History: [last 6 messages]