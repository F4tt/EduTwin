"""
Vector Service for Document Search
Simple in-memory vector search using sentence transformers
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.model = None
        self.documents = []  # {content, metadata, embedding}
        self.initialized = False
    
    async def initialize(self):
        """Initialize the sentence transformer model"""
        try:
            # Use a lightweight multilingual model
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            self.initialized = True
            logger.info("Vector service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize vector service: {e}")
            self.initialized = False
    
    async def add_document(self, content: str, metadata: Dict[str, Any]):
        """Add document to vector store"""
        if not self.initialized:
            await self.initialize()
        
        if not self.initialized:
            return False
        
        try:
            # Generate embedding
            embedding = self.model.encode(content)
            
            # Store document
            self.documents.append({
                'content': content,
                'metadata': metadata,
                'embedding': embedding
            })
            
            logger.info(f"Added document to vector store: {metadata.get('filename', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document to vector store: {e}")
            return False
    
    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        if not self.initialized or not self.documents:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.model.encode(query)
            
            # Calculate similarities
            similarities = []
            for i, doc in enumerate(self.documents):
                similarity = np.dot(query_embedding, doc['embedding']) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc['embedding'])
                )
                similarities.append((i, similarity))
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            results = []
            for i, similarity in similarities[:top_k]:
                if similarity > 0.1:  # Minimum threshold
                    doc = self.documents[i]
                    results.append({
                        'content': doc['content'],
                        'metadata': doc['metadata'],
                        'similarity': float(similarity)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def delete_document(self, doc_id: str):
        """Delete document by ID"""
        try:
            self.documents = [
                doc for doc in self.documents 
                if doc['metadata'].get('doc_id') != doc_id
            ]
            logger.info(f"Deleted document from vector store: {doc_id}")
        except Exception as e:
            logger.error(f"Failed to delete document from vector store: {e}")

# Global vector service instance
_vector_service = None

def get_vector_service() -> VectorService:
    """Get the global vector service instance"""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service