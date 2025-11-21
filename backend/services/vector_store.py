from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class VectorItem:
    vector_id: str
    content: str
    metadata: Dict[str, object]


@dataclass
class SearchResult:
    vector_id: str
    score: float
    content: str
    metadata: Dict[str, object]


class VectorStore:
    """Lightweight vector database persisted on disk (can be swapped for FAISS/Pinecone)."""

    def __init__(self, storage_dir: str | Path, model_name: Optional[str] = None) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.model = SentenceTransformer(self.model_name)

        self.index_file = self.storage_dir / "vectors.npy"
        self.meta_file = self.storage_dir / "metadata.json"

        self._vector_ids: List[str] = []
        self._metadata: Dict[str, Dict[str, object]] = {}
        self._vectors: np.ndarray = np.empty((0, 0), dtype=np.float32)

        self._load()

    def _load(self) -> None:
        if not self.meta_file.exists() or not self.index_file.exists():
            return

        try:
            with self.meta_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._vector_ids = data.get("ids", [])
            self._metadata = data.get("metadata", {})
            if self._vector_ids:
                self._vectors = np.load(self.index_file)
                if self._vectors.dtype != np.float32:
                    self._vectors = self._vectors.astype(np.float32)
            else:
                self._vectors = np.empty((0, 0), dtype=np.float32)
        except Exception as exc:  # noqa: BLE001
            print(f"[VectorStore] Failed to load existing index: {exc}")
            self._vector_ids = []
            self._metadata = {}
            self._vectors = np.empty((0, 0), dtype=np.float32)

    def _save(self) -> None:
        if self._vector_ids and self._vectors.size:
            np.save(self.index_file, self._vectors.astype(np.float32))
        else:
            if self.index_file.exists():
                self.index_file.unlink()
        with self.meta_file.open("w", encoding="utf-8") as fh:
            json.dump({"ids": self._vector_ids, "metadata": self._metadata}, fh, ensure_ascii=False, indent=2)

    def encode(self, texts: Iterable[str]) -> np.ndarray:
        embeddings = self.model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)
        return embeddings

    def upsert(self, items: List[VectorItem], embeddings: Optional[np.ndarray] = None) -> None:
        if not items:
            return

        if embeddings is None:
            contents = [item.content for item in items]
            embeddings = self.encode(contents)
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)

        # Initialize empty matrix when needed
        if self._vectors.size == 0:
            self._vectors = np.empty((0, embeddings.shape[1]), dtype=np.float32)

        for item, vector in zip(items, embeddings, strict=True):
            metadata = dict(item.metadata)
            metadata["content"] = item.content
            if item.vector_id in self._vector_ids:
                idx = self._vector_ids.index(item.vector_id)
                self._vectors[idx] = vector
            else:
                self._vectors = np.vstack([self._vectors, vector])
                self._vector_ids.append(item.vector_id)
            self._metadata[item.vector_id] = metadata

        self._save()

    def delete(self, vector_ids: List[str]) -> None:
        if not vector_ids or not self._vector_ids:
            return

        keep_indices = [idx for idx, vid in enumerate(self._vector_ids) if vid not in vector_ids]
        if len(keep_indices) == len(self._vector_ids):
            return
        if keep_indices:
            self._vectors = self._vectors[keep_indices]
        else:
            dim = self._vectors.shape[1] if self._vectors.ndim == 2 else 0
            self._vectors = np.empty((0, dim), dtype=np.float32)
        self._vector_ids = [self._vector_ids[idx] for idx in keep_indices]
        for vid in vector_ids:
            self._metadata.pop(vid, None)

        self._save()

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[SearchResult]:
        if not self._vector_ids or self._vectors.size == 0:
            return []

        query_vec = self.encode([query])[0]
        scores = self._vectors @ query_vec

        ranked = np.argsort(scores)[::-1]
        results: List[SearchResult] = []
        for idx in ranked:
            vector_id = self._vector_ids[idx]
            metadata = self._metadata.get(vector_id, {})

            if filters and any(metadata.get(k) != v for k, v in filters.items()):
                continue

            results.append(
                SearchResult(
                    vector_id=vector_id,
                    score=float(scores[idx]),
                    content=str(metadata.get("content", "")),
                    metadata=metadata,
                )
            )
            if len(results) >= top_k:
                break
        return results

    def reset(self) -> None:
        self._vector_ids = []
        self._metadata = {}
        self._vectors = np.empty((0, 0), dtype=np.float32)
        self._save()

