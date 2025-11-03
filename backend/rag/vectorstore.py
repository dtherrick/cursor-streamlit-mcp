"""ChromaDB vector store integration."""

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    Manage ChromaDB vector store for RAG.

    Handles document indexing, retrieval, and persistence.
    """

    def __init__(
        self,
        persist_directory: str | Path = "./data/chroma_db",
        collection_name: str = "documents",
        embeddings: Embeddings | None = None,
    ) -> None:
        """
        Initialize vector store manager.

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the ChromaDB collection
            embeddings: Embedding model (defaults to OpenAI)
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        # Ensure persist directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Use OpenAI embeddings by default
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-small")

        # Initialize ChromaDB
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=str(self.persist_directory),
        )

        logger.info(
            f"Initialized ChromaDB vector store: {collection_name} at {self.persist_directory}"
        )

    def add_documents(self, documents: list[Document]) -> list[str]:
        """
        Add documents to the vector store.

        Args:
            documents: List of documents to add

        Returns:
            List of document IDs
        """
        if not documents:
            logger.warning("No documents to add")
            return []

        logger.info(f"Adding {len(documents)} document(s) to vector store...")

        ids = self.vectorstore.add_documents(documents)

        logger.info(f"Successfully added {len(ids)} document(s)")

        return ids

    def similarity_search(
        self, query: str, k: int = 4, filter_dict: dict | None = None
    ) -> list[Document]:
        """
        Search for similar documents using semantic similarity.

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filter

        Returns:
            List of similar documents
        """
        logger.debug(f"Similarity search: '{query}' (k={k})")

        results = self.vectorstore.similarity_search(query, k=k, filter=filter_dict)

        logger.debug(f"Found {len(results)} result(s)")

        return results

    def similarity_search_with_score(
        self, query: str, k: int = 4, filter_dict: dict | None = None
    ) -> list[tuple[Document, float]]:
        """
        Search for similar documents with relevance scores.

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filter

        Returns:
            List of (document, score) tuples
        """
        logger.debug(f"Similarity search with scores: '{query}' (k={k})")

        results = self.vectorstore.similarity_search_with_score(query, k=k, filter=filter_dict)

        logger.debug(f"Found {len(results)} result(s)")

        return results

    def as_retriever(self, **kwargs):
        """
        Get a retriever interface for the vector store.

        Args:
            **kwargs: Arguments to pass to the retriever

        Returns:
            Retriever object
        """
        return self.vectorstore.as_retriever(**kwargs)

    def delete_collection(self) -> None:
        """Delete the entire collection."""
        logger.warning(f"Deleting collection: {self.collection_name}")

        self.vectorstore.delete_collection()

        logger.info(f"Collection deleted: {self.collection_name}")

    def get_collection_count(self) -> int:
        """
        Get the number of documents in the collection.

        Returns:
            Number of documents
        """
        # ChromaDB doesn't have a direct count method, so we use the collection
        collection = self.vectorstore._collection
        return collection.count()

    def clear_documents(self) -> None:
        """Clear all documents from the collection."""
        logger.warning("Clearing all documents from vector store...")

        # Get all document IDs and delete them
        collection = self.vectorstore._collection
        all_ids = collection.get()["ids"]

        if all_ids:
            collection.delete(ids=all_ids)
            logger.info(f"Cleared {len(all_ids)} document(s)")
        else:
            logger.info("No documents to clear")


def create_vectorstore(
    persist_directory: str | Path = "./data/chroma_db",
    collection_name: str = "documents",
) -> VectorStoreManager:
    """
    Factory function to create a vector store manager.

    Args:
        persist_directory: Directory to persist ChromaDB data
        collection_name: Name of the ChromaDB collection

    Returns:
        VectorStoreManager instance
    """
    return VectorStoreManager(
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
