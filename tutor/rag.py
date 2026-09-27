"""Hybrid RAG over NCERT textbooks: ChromaDB (semantic) + BM25 (keyword), fused with RRF.

Embeddings: OpenAI text-embedding-3-small (multilingual, no local model / torch needed).
"""
import os
import re
from pathlib import Path

import chromadb
import pymupdf
from dotenv import load_dotenv
from openai import OpenAI
from rank_bm25 import BM25Okapi

load_dotenv(override=True)
ROOT = Path(__file__).resolve().parent.parent / "knowledge_base"
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
_tok = lambda s: re.findall(r"\w+", s.lower())


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Paragraph/sentence-aware chunking: pack whole sentences up to `size` chars, carry an overlap."""
    sentences = re.split(r"(?<=[.?!।])\s+", re.sub(r"\s+", " ", text).strip())
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) > size:
            chunks.append(cur.strip())
            cur = cur[-overlap:]  # overlap keeps context across chunk borders
        cur += " " + s
    if len(cur.strip()) > 80:
        chunks.append(cur.strip())
    return chunks


class KnowledgeBase:
    def __init__(self):
        self.col = None
        self.bm25 = None
        self._client = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._client = self._client or OpenAI()
        out = []
        for i in range(0, len(texts), 256):  # stay well under per-request token limits
            resp = self._client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + 256])
            out += [d.embedding for d in resp.data]
        return out

    # ---------- setup ----------
    def load(self):
        if self.col is not None:
            return self
        client = chromadb.PersistentClient(path=str(ROOT / "chroma"))
        self.col = client.get_or_create_collection("ncert_openai", metadata={"hnsw:space": "cosine"})
        data = self.col.get(include=["documents", "metadatas"])
        self.ids, self.docs, self.metas = data["ids"], data["documents"], data["metadatas"]
        if self.docs:
            self.bm25 = BM25Okapi([_tok(d) for d in self.docs])
        return self

    def ingest(self, pdf_dir: Path = ROOT / "pdfs"):
        """PDF -> pages -> chunks -> embeddings -> Chroma. Metadata: subject, class, chapter, page."""
        self.load()
        ids, docs, metas = [], [], []
        for pdf in sorted(pdf_dir.glob("*/*.pdf")):
            subject, chapter = pdf.parent.name, pdf.stem[3:].replace("_", " ")
            for pno, page in enumerate(pymupdf.open(pdf), 1):
                for ci, chunk in enumerate(chunk_text(page.get_text())):
                    ids.append(f"{pdf.stem}-p{pno}-c{ci}")
                    docs.append(chunk)
                    metas.append({"subject": subject, "class": 10, "chapter": chapter, "page": pno})
            print(f"  {subject}/{pdf.name}")
        print(f"Embedding {len(docs)} chunks with {EMBED_MODEL} ...")
        embs = self.embed(docs)
        for i in range(0, len(ids), 2000):  # chroma batch limit
            self.col.upsert(ids=ids[i:i + 2000], documents=docs[i:i + 2000],
                            metadatas=metas[i:i + 2000], embeddings=embs[i:i + 2000])
        self.col = None
        return self.load()

    # ---------- search ----------
    def search(self, query: str, subject: str | None = None, k: int = 3, pool: int = 20) -> list[dict]:
        """Hybrid search: semantic top-N + BM25 top-N, merged with Reciprocal Rank Fusion."""
        self.load()
        if not self.docs:
            return []
        subject = subject if subject in ("science", "maths") else None
        where = {"subject": subject} if subject else None

        sem = self.col.query(query_embeddings=self.embed([query]), n_results=pool, where=where)["ids"][0]

        scores = self.bm25.get_scores(_tok(query))
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        kw = [self.ids[i] for i in order if not subject or self.metas[i]["subject"] == subject][:pool]

        rrf: dict[str, float] = {}
        for ranked in (sem, kw):
            for rank, _id in enumerate(ranked):
                rrf[_id] = rrf.get(_id, 0) + 1 / (60 + rank)
        idx = {_id: i for i, _id in enumerate(self.ids)}
        top = sorted(rrf, key=rrf.get, reverse=True)[:k]
        return [{"text": self.docs[idx[t]], **self.metas[idx[t]], "score": round(rrf[t], 4)} for t in top]


kb = KnowledgeBase()
