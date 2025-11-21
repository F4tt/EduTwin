from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from services.vector_store import VectorStore

# optional FAISS-backed store
VBACK = os.getenv("VECTOR_BACKEND", "disk").lower()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    base_dir = Path(__file__).resolve().parent.parent / "vector_store"
    if VBACK == "faiss":
        try:
            from services.faiss_vector_store import FaissVectorStore

            return FaissVectorStore(base_dir)
        except Exception as exc:
            print(f"Failed to initialize FAISS backend, falling back to disk VectorStore: {exc}")
    return VectorStore(base_dir)

