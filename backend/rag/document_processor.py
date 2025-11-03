"""Document loading and processing for RAG."""

import logging
from pathlib import Path
from typing import BinaryIO

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Process documents for RAG indexing.

    Supports multiple document formats:
    - PDF (.pdf)
    - Plain text (.txt)
    - Word documents (.docx)
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        """
        Initialize document processor.

        Args:
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

        # Mapping of file extensions to loader classes
        self.loaders = {
            ".pdf": PyPDFLoader,
            ".txt": TextLoader,
            ".docx": UnstructuredWordDocumentLoader,
        }

    def load_document(self, file_path: str | Path) -> list[Document]:
        """
        Load a document from file path.

        Args:
            file_path: Path to the document

        Returns:
            List of Document objects

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in self.loaders:
            raise ValueError(
                f"Unsupported file format: {suffix}. Supported formats: {list(self.loaders.keys())}"
            )

        logger.info(f"Loading document: {file_path}")

        loader_class = self.loaders[suffix]
        loader = loader_class(str(file_path))
        documents = loader.load()

        logger.info(f"Loaded {len(documents)} page(s) from {file_path.name}")

        return documents

    def load_from_bytes(self, file_content: bytes | BinaryIO, filename: str) -> list[Document]:
        """
        Load a document from bytes (e.g., uploaded file).

        Args:
            file_content: File content as bytes or file-like object
            filename: Original filename to determine format

        Returns:
            List of Document objects

        Raises:
            ValueError: If file format is not supported
        """
        suffix = Path(filename).suffix.lower()
        if suffix not in self.loaders:
            raise ValueError(
                f"Unsupported file format: {suffix}. Supported formats: {list(self.loaders.keys())}"
            )

        # For bytes input, we need to write to temporary file
        # since most loaders expect file paths
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            if isinstance(file_content, bytes):
                tmp_file.write(file_content)
            else:
                tmp_file.write(file_content.read())
            tmp_path = tmp_file.name

        try:
            documents = self.load_document(tmp_path)
            # Add source metadata
            for doc in documents:
                doc.metadata["source"] = filename
            return documents
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """
        Split documents into smaller chunks.

        Args:
            documents: List of documents to split

        Returns:
            List of split document chunks
        """
        logger.info(f"Splitting {len(documents)} document(s) into chunks...")

        chunks = self.text_splitter.split_documents(documents)

        logger.info(f"Created {len(chunks)} chunk(s)")

        return chunks

    def process_document(self, file_path: str | Path) -> list[Document]:
        """
        Load and split a document in one step.

        Args:
            file_path: Path to the document

        Returns:
            List of processed document chunks
        """
        documents = self.load_document(file_path)
        chunks = self.split_documents(documents)
        return chunks

    def process_from_bytes(self, file_content: bytes | BinaryIO, filename: str) -> list[Document]:
        """
        Load and split a document from bytes in one step.

        Args:
            file_content: File content as bytes or file-like object
            filename: Original filename

        Returns:
            List of processed document chunks
        """
        documents = self.load_from_bytes(file_content, filename)
        chunks = self.split_documents(documents)
        return chunks

    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported file formats.

        Returns:
            List of supported file extensions
        """
        return list(self.loaders.keys())
