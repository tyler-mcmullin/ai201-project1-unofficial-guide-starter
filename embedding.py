"""
TAMU RAG — Embedding and Storage
Reads chunks.jsonl, embeds with all-MiniLM-L6-v2, stores in ChromaDB.

Usage:
    python embed_and_store.py
"""

import json
from dataclasses import dataclass

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError("Run: pip install sentence-transformers")

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    raise ImportError("Run: pip install chromadb")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNKS_FILE     = "chunks.jsonl"
CHROMA_DIR      = "./chroma_db"
COLLECTION_NAME = "tamu_rag"
MODEL_NAME      = "all-MiniLM-L6-v2"
BATCH_SIZE      = 64


# ---------------------------------------------------------------------------
# Load chunks
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text:        str
    source_url:  str
    source_type: str
    chunk_index: int
    metadata:    dict


def load_chunks(path: str) -> list[Chunk]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            chunks.append(Chunk(
                text        = d["text"],
                source_url  = d["source_url"],
                source_type = d["source_type"],
                chunk_index = d["chunk_index"],
                metadata    = d.get("metadata", {}),
            ))
    return chunks


# ---------------------------------------------------------------------------
# Build Chroma metadata
# ---------------------------------------------------------------------------

def build_metadata(chunk: Chunk) -> dict:
    """
    Flatten chunk into a Chroma-safe metadata dict.
    Chroma only accepts str, int, float, bool values.
    """
    meta = {
        "source_url":  chunk.source_url,
        "source_type": chunk.source_type,
        "text":        chunk.text,
    }
    for k, v in chunk.metadata.items():
        meta[k] = v if isinstance(v, (str, int, float, bool)) else str(v)
    return meta


def make_id(chunk: Chunk, global_index: int) -> str:
    import re
    clean = re.sub(r'https?://', '', chunk.source_url)
    clean = re.sub(r'[^a-zA-Z0-9]', '_', clean)
    return f"{clean}__{global_index}"


# ---------------------------------------------------------------------------
# Embed and store
# ---------------------------------------------------------------------------

def embed_and_store(chunks: list[Chunk]) -> None:
    # Load model
    print(f"Loading model: {MODEL_NAME}…")
    model = SentenceTransformer(MODEL_NAME)
    print("Model ready.\n")

    # Connect to Chroma
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Embed and upsert in batches
    total = len(chunks)
    for i in range(0, total, BATCH_SIZE):
        batch  = chunks[i : i + BATCH_SIZE]
        texts  = [c.text for c in batch]

        print(f"  Embedding batch {i // BATCH_SIZE + 1} "
              f"({i}–{min(i + BATCH_SIZE, total)} of {total})…")

        vectors = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        collection.upsert(
            ids        = [make_id(c, i + idx) for idx, c in enumerate(batch)],
            embeddings = [v.tolist() for v in vectors],
            documents  = texts,
            metadatas  = [build_metadata(c) for c in batch],
        )

    print(f"\nDone. Collection size: {collection.count()} chunks indexed.")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(
    query:       str,
    top_k:       int = 5,
    source_type: str = None,
    source_url:  str = None,
) -> list[dict]:
    """
    Embed a query and return the top-k most similar chunks.

    Args:
        query:       User question string.
        top_k:       Number of results to return.
        source_type: Optional filter — "atomic" or "standard".
        source_url:  Optional filter — partial URL match e.g. "catalog.tamu.edu".

    Returns:
        List of dicts with text, source_url, source_type, score, metadata.
    """
    model  = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # Build optional where filter
    conditions = []
    if source_type:
        conditions.append({"source_type": {"$eq": source_type}})
    if source_url:
        conditions.append({"source_url": {"$contains": source_url}})

    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    query_vector = model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()

    n_results = min(top_k, collection.count())
    if n_results == 0:
        return []

    results = collection.query(
        query_embeddings = [query_vector],
        n_results        = n_results,
        where            = where,
        include          = ["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":        doc,
            "source_url":  meta.get("source_url", ""),
            "source_type": meta.get("source_type", ""),
            "score":       round(1 - dist, 4),
            "metadata":    {k: v for k, v in meta.items()
                            if k not in ("source_url", "source_type", "text")},
        })

    return sorted(chunks, key=lambda c: c["score"], reverse=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Loading chunks from {CHUNKS_FILE}…")
    chunks = load_chunks(CHUNKS_FILE)
    print(f"Loaded {len(chunks)} chunks.\n")

    embed_and_store(chunks)

    # Quick retrieval smoke test
    print("\n── Smoke test ──")
    test_cases = [
        {"query": "What is Professor Paul Taele rated on RateMyProfessor?",
         "expected": "4.4"},
        {"query": "What classes should be taken during your first semester for a computer science degree?",
         "expected": "CSCE 313, 314, and 350"},
        {"query": "When is tuition due for Summer 2026?",
         "expected": "May 21st, 2026"},
        {"query": "When is the Canek Culinary camp?",
         "expected": "Jun 8th to Jul 24th"},
        {"query": "Why are warnings not given to parking violators?",
         "expected": "Warnings do not work"},
    ]
    for test in test_cases:
        results = retrieve(test["query"], top_k=3)
        print(f"\nQ: {test['query']}")
        print(f"Expected: {test['expected']}")
        for r in results:
            print(f"  score={r['score']:.4f} | {r['source_url']}")
            print(f"  {r['text'][:150]}")