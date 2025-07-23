# ai_conversation_engine/src/services/knowledge_retriever.py

import asyncio
import logging
from typing import List, Dict, Optional, Any, NamedTuple
from dataclasses import dataclass
from pathlib import Path
import json
import hashlib
from src.services.embedding_service import EmbeddingService
from src.config import Settings

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """Represents a document with its content and metadata."""
    id: str
    chunk_text: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class SearchResult(NamedTuple):
    """Represents a search result with document and similarity score."""
    document: Document
    similarity: float
    index: int

class KnowledgeRetriever:
    """
    Advanced knowledge retrieval system using embedding-based similarity search.
    
    Features:
    - Async initialization and search
    - Document caching and persistence
    - Batch processing for better performance
    - Comprehensive error handling
    - Configurable similarity thresholds
    """
    
    def __init__(self, http_client, settings: Settings):
        """Initialize the knowledge retriever with required services."""
        self.settings = settings
        self.embedding_service = EmbeddingService(http_client, settings)
        self._documents: List[Document] = []
        self._embeddings: Optional[List[List[float]]] = None
        self._initialized = False
        self._cache_file = Path(getattr(settings, 'EMBEDDINGS_CACHE_FILE', 'embeddings_cache.json'))
        
    async def initialize(self, documents: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Initialize embeddings asynchronously with optional document loading.
        
        Args:
            documents: Optional list of documents to load. If None, uses default documents.
        """
        if self._initialized:
            logger.info("Knowledge retriever already initialized")
            return
            
        try:
            # Load documents
            if documents:
                self._load_documents(documents)
            else:
                self._load_default_documents()
            
            # Try to load cached embeddings first
            if await self._load_cached_embeddings():
                logger.info("Loaded embeddings from cache")
            else:
                # Generate new embeddings if cache miss
                logger.info("Generating new embeddings")
                await self._generate_and_cache_embeddings()
            
            self._initialized = True
            logger.info(f"Knowledge retriever initialized with {len(self._documents)} documents")
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge retriever: {e}")
            raise

    def _load_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Load documents from provided data."""
        self._documents = []
        for i, doc_data in enumerate(documents):
            doc_id = doc_data.get('id', f"doc_{i}")
            chunk_text = doc_data.get('chunk_text', '')
            metadata = doc_data.get('metadata', {})
            
            if not chunk_text.strip():
                logger.warning(f"Empty chunk_text in document {doc_id}, skipping")
                continue
                
            self._documents.append(Document(
                id=doc_id,
                chunk_text=chunk_text,
                metadata=metadata
            ))

    def _load_default_documents(self) -> None:
        """Load default hardcoded documents."""
        default_docs = [
            {
                "id": "return_policy",
                "chunk_text": "Our return policy allows returns within 30 days of purchase.",
                "metadata": {"category": "policy", "priority": "high"}
            },
            {
                "id": "shipping_policy", 
                "chunk_text": "We offer free standard shipping on all orders over ₹1000.",
                "metadata": {"category": "shipping", "priority": "medium"}
            },
            {
                "id": "refund_timeline",
                "chunk_text": "Once a return is received, refunds are typically processed within 7-10 business days.",
                "metadata": {"category": "policy", "priority": "high"}
            }
        ]
        self._load_documents(default_docs)

    def _get_documents_hash(self) -> str:
        """Generate a hash of current documents for cache validation."""
        content = json.dumps([
            {"id": doc.id, "chunk_text": doc.chunk_text} 
            for doc in self._documents
        ], sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    async def _load_cached_embeddings(self) -> bool:
        """
        Load embeddings from cache if available and valid.
        
        Returns:
            True if cache was loaded successfully, False otherwise.
        """
        if not self._cache_file.exists():
            return False
            
        try:
            with open(self._cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Validate cache against current documents
            if cache_data.get('documents_hash') != self._get_documents_hash():
                logger.info("Document content changed, cache invalid")
                return False
            
            self._embeddings = cache_data.get('embeddings', [])
            
            # Validate embeddings count matches documents
            if len(self._embeddings) != len(self._documents):
                logger.warning("Embeddings count mismatch with documents")
                return False
                
            return True
            
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load embeddings cache: {e}")
            return False

    async def _generate_and_cache_embeddings(self) -> None:
        """Generate embeddings for all documents and cache them."""
        if not self._documents:
            logger.warning("No documents to generate embeddings for")
            self._embeddings = []
            return
            
        texts = [doc.chunk_text for doc in self._documents]
        
        try:
            # Generate embeddings with error handling
            embeddings = await self.embedding_service.generate_embeddings_batch(texts)
            
            # Filter out failed embeddings and corresponding documents
            valid_embeddings = []
            valid_documents = []
            
            for i, (embedding, document) in enumerate(zip(embeddings, self._documents)):
                if embedding is not None:
                    valid_embeddings.append(embedding)
                    valid_documents.append(document)
                else:
                    logger.warning(f"Failed to generate embedding for document {document.id}")
            
            self._embeddings = valid_embeddings
            self._documents = valid_documents
            
            # Cache the results
            await self._cache_embeddings()
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def _cache_embeddings(self) -> None:
        """Cache embeddings to file for future use."""
        try:
            cache_data = {
                'documents_hash': self._get_documents_hash(),
                'embeddings': self._embeddings,
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Ensure cache directory exists
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._cache_file, 'w') as f:
                json.dump(cache_data, f)
                
            logger.debug(f"Cached embeddings to {self._cache_file}")
            
        except Exception as e:
            logger.warning(f"Failed to cache embeddings: {e}")

    async def search(self, query: str, limit: int = 5, min_similarity: Optional[float] = None) -> List[SearchResult]:
        """
        Search for documents matching the query using embedding similarity.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (overrides settings default)
            
        Returns:
            List of SearchResult objects sorted by similarity (highest first)
        """
        if not self._initialized:
            raise RuntimeError("Knowledge retriever not initialized. Call initialize() first.")
            
        if not query.strip():
            logger.warning("Empty query provided")
            return []
            
        if not self._documents or not self._embeddings:
            logger.warning("No documents or embeddings available")
            return []

        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)
            if not query_embedding:
                logger.error(f"Failed to generate embedding for query: {query}")
                return []

            # Calculate similarities
            results = []
            threshold = min_similarity or self.settings.SIMILARITY_THRESHOLD
            
            for i, (doc_embedding, document) in enumerate(zip(self._embeddings, self._documents)):
                try:
                    similarity = self.embedding_service.calculate_similarity(query_embedding, doc_embedding)
                    
                    if similarity >= threshold:
                        results.append(SearchResult(
                            document=document,
                            similarity=similarity,
                            index=i
                        ))
                        
                except Exception as e:
                    logger.warning(f"Failed to calculate similarity for document {document.id}: {e}")
                    continue
            
            # Sort by similarity (highest first) and limit results
            results.sort(key=lambda x: x.similarity, reverse=True)
            limited_results = results[:limit]
            
            logger.debug(f"Found {len(results)} matches for query '{query}', returning top {len(limited_results)}")
            return limited_results
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    async def add_document(self, document: Dict[str, Any]) -> bool:
        """
        Add a new document to the knowledge base.
        
        Args:
            document: Document data with 'chunk_text' and optional 'id', 'metadata'
            
        Returns:
            True if document was added successfully, False otherwise
        """
        try:
            doc_id = document.get('id', f"doc_{len(self._documents)}")
            chunk_text = document.get('chunk_text', '')
            metadata = document.get('metadata', {})
            
            if not chunk_text.strip():
                logger.error("Cannot add document with empty chunk_text")
                return False
            
            # Check for duplicate IDs
            if any(doc.id == doc_id for doc in self._documents):
                logger.error(f"Document with ID '{doc_id}' already exists")
                return False
            
            # Create document
            new_doc = Document(id=doc_id, chunk_text=chunk_text, metadata=metadata)
            
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(chunk_text)
            if not embedding:
                logger.error(f"Failed to generate embedding for new document {doc_id}")
                return False
            
            # Add to collections
            self._documents.append(new_doc)
            if self._embeddings is None:
                self._embeddings = []
            self._embeddings.append(embedding)
            
            # Update cache
            await self._cache_embeddings()
            
            logger.info(f"Successfully added document {doc_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return False

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """Get a document by its ID."""
        return next((doc for doc in self._documents if doc.id == doc_id), None)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        return {
            'total_documents': len(self._documents),
            'initialized': self._initialized,
            'has_embeddings': self._embeddings is not None,
            'cache_file_exists': self._cache_file.exists(),
            'similarity_threshold': self.settings.SIMILARITY_THRESHOLD
        }

    async def clear_cache(self) -> None:
        """Clear the embeddings cache."""
        try:
            if self._cache_file.exists():
                self._cache_file.unlink()
            logger.info("Embeddings cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            raise