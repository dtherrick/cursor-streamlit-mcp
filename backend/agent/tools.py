"""Agent tools for RAG retrieval and MCP integration."""

import logging
from typing import Annotated

from langchain_core.tools import tool

from backend.rag.vectorstore import VectorStoreManager

logger = logging.getLogger(__name__)


def create_rag_tool(vectorstore: VectorStoreManager):
    """
    Create a RAG retrieval tool for the agent.

    Args:
        vectorstore: Initialized vector store manager

    Returns:
        LangChain tool for RAG retrieval
    """

    @tool
    def retrieve_documents(
        query: Annotated[str, "The search query to find relevant documents"],
    ) -> str:
        """
        Retrieve relevant documents from the knowledge base.

        Use this tool when you need to find information from uploaded documents
        or the knowledge base to answer user questions.
        """
        logger.info(f"RAG retrieval for query: {query}")

        try:
            # Retrieve documents
            results = vectorstore.similarity_search(query, k=4)

            if not results:
                return "No relevant documents found in the knowledge base."

            # Format results
            formatted_results = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get("source", "Unknown")
                page = doc.metadata.get("page", "N/A")
                content = doc.page_content.strip()

                formatted_results.append(
                    f"[Document {i}] Source: {source}, Page: {page}\n{content}"
                )

            return "\n\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Error during RAG retrieval: {e}")
            return f"Error retrieving documents: {str(e)}"

    return retrieve_documents


def create_document_search_tool(vectorstore: VectorStoreManager):
    """
    Create a document search tool with metadata filtering.

    Args:
        vectorstore: Initialized vector store manager

    Returns:
        LangChain tool for document search
    """

    @tool
    def search_documents(
        query: Annotated[str, "The search query"],
        num_results: Annotated[int, "Number of results to return"] = 4,
    ) -> str:
        """
        Search for documents in the knowledge base with a specific query.

        Use this to find specific information across all uploaded documents.
        Returns formatted excerpts from the most relevant documents.
        """
        logger.info(f"Document search: {query} (k={num_results})")

        try:
            results = vectorstore.similarity_search_with_score(query, k=num_results)

            if not results:
                return "No documents found matching your query."

            formatted_results = []
            for i, (doc, score) in enumerate(results, 1):
                source = doc.metadata.get("source", "Unknown")
                relevance = f"{(1 - score) * 100:.1f}%"  # Convert distance to relevance

                formatted_results.append(
                    f"[{i}] {source} (Relevance: {relevance})\n{doc.page_content.strip()}"
                )

            return "\n\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Error during document search: {e}")
            return f"Error searching documents: {str(e)}"

    return search_documents


# Note: MCP tools are created dynamically by the MCPServerManager
# and registered with the agent. This file contains RAG-specific tools.
#
# The MCP tools (Splunk, Atlassian, etc.) are loaded from backend/mcp/server_manager.py
# and automatically integrated into the agent's toolset.
