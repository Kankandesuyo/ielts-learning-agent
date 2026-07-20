from pathlib import Path
from re import findall

from app.config import get_settings


class RagService:
    """Small RAG scaffold for MVP.

    Production upgrade path:
    1. Replace simple token overlap with embeddings.
    2. Store chunks in FAISS, Chroma, or PostgreSQL pgvector.
    3. Pass retrieved context into LLM prompts.
    """

    def __init__(self, docs_path: str | None = None) -> None:
        settings = get_settings()
        self.docs_path = Path(docs_path or settings.rag_docs_path)

    def load_documents(self) -> list[dict]:
        docs = []
        if not self.docs_path.exists():
            return docs
        for path in self.docs_path.glob("*.md"):
            docs.append({"source": str(path), "text": path.read_text(encoding="utf-8")})
        return docs

    def split_text(self, text: str, chunk_size: int = 700) -> list[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) > chunk_size and current:
                chunks.append(current)
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}".strip()
        if current:
            chunks.append(current)
        return chunks

    def index(self) -> list[dict]:
        chunks = []
        for doc in self.load_documents():
            for chunk in self.split_text(doc["text"]):
                chunks.append({"source": doc["source"], "text": chunk, "tokens": self._tokens(chunk)})
        return chunks

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        query_tokens = self._tokens(query)
        scored = []
        for chunk in self.index():
            score = len(query_tokens.intersection(chunk["tokens"]))
            if score:
                scored.append({"source": chunk["source"], "text": chunk["text"], "score": score})
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

    def _tokens(self, text: str) -> set[str]:
        return {t.lower() for t in findall(r"[A-Za-z]{3,}", text)}

