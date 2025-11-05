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

    def get_document_list(self) -> list[dict]:
        """
        Get list of all documents in the vector store with chunk counts.

        Returns:
            List of dictionaries with document info: [{source, chunk_count}, ...]
        """
        collection = self.vectorstore._collection
        results = collection.get(include=["metadatas"])

        if not results["ids"]:
            logger.info("No documents in vector store")
            return []

        # Group chunks by source filename
        from collections import defaultdict

        source_counts: dict[str, int] = defaultdict(int)

        for metadata in results["metadatas"]:
            if metadata and "source" in metadata:
                source_counts[metadata["source"]] += 1

        # Convert to list of dicts
        documents = [
            {"source": source, "chunk_count": count}
            for source, count in sorted(source_counts.items())
        ]

        logger.info(f"Found {len(documents)} unique document(s) with {len(results['ids'])} total chunks")

        return documents

    def delete_document_by_source(self, source_filename: str) -> int:
        """
        Delete all chunks associated with a source filename.

        Args:
            source_filename: The source filename to delete

        Returns:
            Number of chunks deleted
        """
        logger.info(f"Deleting document: {source_filename}")

        collection = self.vectorstore._collection

        # Query for all chunks with this source
        results = collection.get(
            where={"source": source_filename},
            include=["metadatas"],
        )

        ids_to_delete = results["ids"]

        if not ids_to_delete:
            logger.warning(f"No chunks found for source: {source_filename}")
            return 0

        # Delete the chunks
        collection.delete(ids=ids_to_delete)

        logger.info(f"Deleted {len(ids_to_delete)} chunk(s) for {source_filename}")

        return len(ids_to_delete)

    def check_document_exists(self, source_filename: str) -> bool:
        """
        Check if a document with the given source filename exists.

        Args:
            source_filename: The source filename to check

        Returns:
            True if document exists, False otherwise
        """
        collection = self.vectorstore._collection

        # Query for any chunks with this source
        results = collection.get(
            where={"source": source_filename},
            limit=1,
        )

        exists = len(results["ids"]) > 0

        logger.debug(f"Document exists check for '{source_filename}': {exists}")

        return exists


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
