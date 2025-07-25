# ai_conversation_engine/src/services/knowledge_retriever.py
import asyncio
import logging
from typing import List, Dict, Optional, Any, NamedTuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import hashlib
from src.services.embedding_service import EmbeddingService
from shared.config import settings
import os

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """Represents a document with its content and metadata."""
    id: str
    chunk_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.chunk_text or not self.chunk_text.strip():
            raise ValueError("Document chunk_text cannot be empty.")

class SearchResult(NamedTuple):
    """Represents a search result with document and similarity score."""
    document: Document
    similarity: float
    index: int

class KnowledgeRetriever:
    """
    Advanced knowledge retrieval system using embedding-based similarity search.
    """

    def __init__(self, http_client, app_settings: "Settings"):
        """Initialize the knowledge retriever with required services."""
        self.settings = app_settings
        self.embedding_service = EmbeddingService(http_client, app_settings)
        self._documents: List[Document] = []
        self._embeddings: Optional[List[List[float]]] = None
        self._initialized = False
        self._cache_file = Path(getattr(settings, 'EMBEDDINGS_CACHE_FILE', 'cache/embeddings_cache.json'))

    async def initialize(self, documents: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Initialize embeddings asynchronously with optional document loading.
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
                logger.info(f"Loaded {len(self._embeddings)} embeddings from cache.")
            else:
                # Generate new embeddings if cache miss
                logger.info("Generating new embeddings as cache is invalid or missing.")
                await self._generate_and_cache_embeddings()
            
            self._initialized = True
            logger.info(f"Knowledge retriever initialized with {len(self._documents)} documents.")
        except Exception:
            logger.error("Failed to initialize knowledge retriever", exc_info=True)
            raise

    def _load_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Load documents from provided data."""
        self._documents = []
        for i, doc_data in enumerate(documents):
            try:
                doc = Document(
                    id=doc_data.get('id', f"doc_{i}"),
                    chunk_text=doc_data.get('chunk_text', ''),
                    metadata=doc_data.get('metadata', {})
                )
                self._documents.append(doc)
            except ValueError as e:
                logger.warning(f"Skipping invalid document at index {i}", error=str(e))
    
    def _load_default_documents(self) -> None:
        """Load default hardcoded documents from environment or a fallback."""
        try:
            default_docs_str = os.getenv('DEFAULT_DOCS')
            if default_docs_str:
                default_docs = json.loads(default_docs_str)
            else:
                logger.info("No DEFAULT_DOCS in env, using hardcoded fallback.")
                default_docs = [
                    {"id": "return_policy", "chunk_text": "Our return policy allows returns within 30 days of purchase.", "metadata": {"category": "policy"}},
                    {"id": "shipping_info", "chunk_text": "We offer free standard shipping on orders over $50.", "metadata": {"category": "shipping"}},
                    {"id": "refund_timeline", "chunk_text": "Refunds are processed within 5-7 business days.", "metadata": {"category": "policy"}}
                ]
            self._load_documents(default_docs)
        except json.JSONDecodeError:
            logger.error("Failed to parse DEFAULT_DOCS from environment variable.")
            self._documents = []


    def _get_documents_hash(self) -> str:
        """Generate a hash of current documents for cache validation."""
        content = json.dumps([
            {"id": doc.id, "chunk_text": doc.chunk_text} for doc in self._documents
        ], sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    async def _load_cached_embeddings(self) -> bool:
        """
        Load embeddings from cache if available and valid.
        """
        if not self._cache_file.exists():
            return False

        try:
            with open(self._cache_file, 'r') as f:
                cache_data = json.load(f)

            # Validate cache against current documents
            if cache_data.get('documents_hash') != self._get_documents_hash():
                logger.info("Document content has changed, cache is invalid.")
                return False
            
            self._embeddings = cache_data.get('embeddings', [])

            # Validate embeddings count matches documents
            if len(self._embeddings) != len(self._documents):
                logger.warning("Embeddings count in cache does not match documents count.")
                return False
                
            return True
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to load or validate embeddings cache: {e}")
            return False

    async def _generate_and_cache_embeddings(self) -> None:
        """Generate embeddings for all documents and cache them."""
        if not self._documents:
            logger.warning("No documents to generate embeddings for.")
            self._embeddings = []
            return

        texts = [doc.chunk_text for doc in self._documents]
        
        try:
            # Generate embeddings with error handling
            embeddings_results = await self.embedding_service.generate_embeddings_batch(texts, return_results=True)
            
            valid_embeddings = []
            valid_documents = []

            for doc, result in zip(self._documents, embeddings_results):
                if result.success and result.embedding:
                    valid_embeddings.append(result.embedding)
                    valid_documents.append(doc)
                else:
                    logger.warning(f"Failed to generate embedding for document {doc.id}", error=result.error)
            
            self._embeddings = valid_embeddings
            self._documents = valid_documents # Prune documents that failed embedding
            
            # Cache the results
            await self._cache_embeddings()
        except Exception:
            logger.error("Failed to generate and cache embeddings", exc_info=True)
            raise

    async def _cache_embeddings(self) -> None:
        """Cache embeddings to file for future use."""
        if self._embeddings is None:
            return
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
            
            logger.debug(f"Cached {len(self._embeddings)} embeddings to {self._cache_file}")
        except Exception as e:
            logger.warning(f"Failed to write embeddings to cache file: {e}")

    async def search(self, query: str, limit: int = 5, min_similarity: Optional[float] = None) -> List[SearchResult]:
        """
        Search for documents matching the query using embedding similarity.
        """
        if not self._initialized:
            raise RuntimeError("Knowledge retriever not initialized. Call initialize() first.")
        
        if not query.strip() or not self._documents or not self._embeddings:
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)
            if not query_embedding:
                logger.error(f"Failed to generate embedding for query: {query}")
                return []

            # Calculate similarities
            similarities = self.embedding_service.calculate_similarity_batch(query_embedding, self._embeddings)
            
            threshold = min_similarity or self.settings.SIMILARITY_THRESHOLD
            
            results = [
                SearchResult(document=doc, similarity=sim, index=i)
                for i, (doc, sim) in enumerate(zip(self._documents, similarities))
                if sim >= threshold
            ]
            
            # Sort by similarity (highest first) and limit results
            results.sort(key=lambda x: x.similarity, reverse=True)
            return results[:limit]
        except Exception:
            logger.error(f"Search failed for query '{query}'", exc_info=True)
            return []

    async def add_document(self, document_data: Dict[str, Any]) -> bool:
        """
        Add a new document to the knowledge base and update embeddings.
        """
        try:
            new_doc = Document(
                id=document_data.get('id', f"doc_{len(self._documents) + 1}"),
                chunk_text=document_data.get('chunk_text', ''),
                metadata=document_data.get('metadata', {})
            )
            
            # Check for duplicate IDs
            if any(doc.id == new_doc.id for doc in self._documents):
                logger.error(f"Document with ID '{new_doc.id}' already exists.")
                return False

            # Create document
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(new_doc.chunk_text)
            if not embedding:
                logger.error(f"Failed to generate embedding for new document {new_doc.id}")
                return False
            
            # Add to collections
            self._documents.append(new_doc)
            if self._embeddings is None:
                self._embeddings = []
            self._embeddings.append(embedding)

            # Update cache
            await self._cache_embeddings()
            
            logger.info(f"Successfully added and embedded document {new_doc.id}")
            return True
        except (ValueError, Exception) as e:
            logger.error(f"Failed to add document: {e}", exc_info=True)
            return False

    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """Get a document by its ID."""
        return next((doc for doc in self._documents if doc.id == doc_id), None)

    async def clear_cache(self) -> None:
        """Clear the embeddings cache file."""
        try:
            if self._cache_file.exists():
                self._cache_file.unlink()
                logger.info("Embeddings cache file cleared.")
        except Exception as e:
            logger.error(f"Failed to clear embeddings cache: {e}")
            raise