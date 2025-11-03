"""FastAPI routes for the agent API."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.agent.graph import SplunkMCPAgent
from backend.mcp.server_manager import MCPServerManager
from backend.rag.document_processor import DocumentProcessor
from backend.rag.vectorstore import VectorStoreManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global references (will be set by main.py during startup)
agent: SplunkMCPAgent | None = None
vectorstore: VectorStoreManager | None = None
document_processor: DocumentProcessor | None = None
mcp_manager: MCPServerManager | None = None


def set_dependencies(
    agent_instance: SplunkMCPAgent,
    vectorstore_instance: VectorStoreManager,
    doc_processor_instance: DocumentProcessor,
    mcp_manager_instance: MCPServerManager | None = None,
) -> None:
    """
    Set global dependencies for routes.

    Called during FastAPI startup.

    Args:
        agent_instance: The LangGraph agent
        vectorstore_instance: The vector store manager
        doc_processor_instance: The document processor
        mcp_manager_instance: The MCP server manager (optional)
    """
    global agent, vectorstore, document_processor, mcp_manager
    agent = agent_instance
    vectorstore = vectorstore_instance
    document_processor = doc_processor_instance
    mcp_manager = mcp_manager_instance


# Request/Response Models


class ChatRequest(BaseModel):
    """Chat request schema."""

    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response schema."""

    response: str
    thread_id: str
    requires_approval: bool = False
    approval_details: dict | None = None


class ApprovalRequest(BaseModel):
    """Approval decision schema."""

    thread_id: str
    decisions: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    components: dict[str, str]


class UploadResponse(BaseModel):
    """Document upload response."""

    success: bool
    message: str
    filename: str
    chunks_created: int


# Helper Functions


async def handle_special_command(command: str, thread_id: str) -> ChatResponse:
    """
    Handle special slash commands.

    Args:
        command: The command string (starting with /)
        thread_id: Current thread ID

    Returns:
        ChatResponse with command output
    """
    cmd = command.lower().strip()

    if cmd == "/mcp":
        return await get_mcp_info(thread_id)
    elif cmd == "/tools":
        return await get_tools_info(thread_id)
    elif cmd == "/help":
        return get_help_info(thread_id)
    else:
        return ChatResponse(
            response=f"Unknown command: {command}\n\nType `/help` for available commands.",
            thread_id=thread_id,
            requires_approval=False,
            approval_details=None,
        )


async def get_mcp_info(thread_id: str) -> ChatResponse:
    """Get MCP server and tools information."""
    if not mcp_manager:
        response = (
            "**MCP Server Status**: Not enabled\n\n"
            "MCP servers are currently disabled. To enable:\n"
            "1. Configure servers in `config/mcp_servers.json`\n"
            "2. Uncomment MCP initialization in `backend/main.py`\n"
            "3. Restart the backend"
        )
        return ChatResponse(
            response=response,
            thread_id=thread_id,
            requires_approval=False,
            approval_details=None,
        )

    # Get MCP server information
    enabled_servers = mcp_manager.enabled_servers
    all_tools = mcp_manager.get_all_tools()

    response_parts = ["**MCP Servers**\n"]

    if not enabled_servers:
        response_parts.append("No MCP servers are currently enabled.\n")
    else:
        response_parts.append(f"**Enabled Servers**: {len(enabled_servers)}\n")
        for server_name, server_config in enabled_servers.items():
            server_tools = mcp_manager.get_tools_by_server(server_name)
            response_parts.append(f"\n**{server_name}**")
            response_parts.append(f"  - Command: `{server_config.command}`")
            response_parts.append(f"  - Tools: {len(server_tools)}")
            
            if server_tools:
                response_parts.append(f"  - Available tools:")
                for tool in server_tools[:10]:  # Limit to first 10
                    response_parts.append(f"    • `{tool.name}`: {tool.description[:80]}...")
                if len(server_tools) > 10:
                    response_parts.append(f"    • ... and {len(server_tools) - 10} more")

    response_parts.append(f"\n**Total Tools Available**: {len(all_tools)}")
    response_parts.append("\nUse `/tools` to see all tools across all servers.")

    return ChatResponse(
        response="\n".join(response_parts),
        thread_id=thread_id,
        requires_approval=False,
        approval_details=None,
    )


async def get_tools_info(thread_id: str) -> ChatResponse:
    """Get all available tools information."""
    if not agent:
        return ChatResponse(
            response="Agent not initialized.",
            thread_id=thread_id,
            requires_approval=False,
            approval_details=None,
        )

    tools = agent.tools
    response_parts = ["**Available Tools**\n"]
    response_parts.append(f"**Total Tools**: {len(tools)}\n")

    # Group tools by type
    mcp_tools = [t for t in tools if "-" in t.name and "_" in t.name]
    rag_tools = [t for t in tools if "retrieve" in t.name.lower() or "search" in t.name.lower()]
    other_tools = [t for t in tools if t not in mcp_tools and t not in rag_tools]

    if mcp_tools:
        response_parts.append(f"**MCP Tools** ({len(mcp_tools)}):")
        for tool in mcp_tools:
            response_parts.append(f"  • `{tool.name}`")
            response_parts.append(f"    {tool.description[:100]}...")

    if rag_tools:
        response_parts.append(f"\n**RAG Tools** ({len(rag_tools)}):")
        for tool in rag_tools:
            response_parts.append(f"  • `{tool.name}`")
            response_parts.append(f"    {tool.description[:100]}...")

    if other_tools:
        response_parts.append(f"\n**Other Tools** ({len(other_tools)}):")
        for tool in other_tools:
            response_parts.append(f"  • `{tool.name}`")
            response_parts.append(f"    {tool.description[:100]}...")

    return ChatResponse(
        response="\n".join(response_parts),
        thread_id=thread_id,
        requires_approval=False,
        approval_details=None,
    )


def get_help_info(thread_id: str) -> ChatResponse:
    """Get help information about available commands."""
    response = """**Available Commands**

**Slash Commands**:
  • `/mcp` - List MCP servers and their tools
  • `/tools` - List all available tools
  • `/help` - Show this help message

**MCP Servers**:
  MCP (Model Context Protocol) servers provide external tools and capabilities.
  Use `/mcp` to see which servers are connected and what tools they provide.

**Usage**:
  Just type your question naturally, and the agent will use the appropriate tools.
  For sensitive operations (like Splunk queries), you'll be asked to approve the action.

**Examples**:
  - "What Splunk indexes are available?"
  - "Search for error logs in the last hour"
  - "What does this document say about security?"
"""

    return ChatResponse(
        response=response,
        thread_id=thread_id,
        requires_approval=False,
        approval_details=None,
    )


# Routes


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        Health status of the application
    """
    components = {}

    if agent:
        components["agent"] = "healthy"
    else:
        components["agent"] = "not_initialized"

    if vectorstore:
        try:
            count = vectorstore.get_collection_count()
            components["vectorstore"] = f"healthy ({count} documents)"
        except Exception as e:
            components["vectorstore"] = f"error: {str(e)}"
    else:
        components["vectorstore"] = "not_initialized"

    if document_processor:
        components["document_processor"] = "healthy"
    else:
        components["document_processor"] = "not_initialized"

    return HealthResponse(
        status="healthy"
        if all(c != "not_initialized" for c in components.values())
        else "degraded",
        version="0.1.0",
        components=components,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Chat with the agent.

    Special commands:
    - /mcp - List MCP servers and tools
    - /tools - List all available tools
    - /help - Show available commands

    Args:
        request: Chat request with message and optional thread_id

    Returns:
        Agent response

    Raises:
        HTTPException: If agent is not initialized or error occurs
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Generate thread_id if not provided
    thread_id = request.thread_id or str(uuid.uuid4())

    logger.info(f"Chat request on thread {thread_id}: {request.message[:100]}...")

    # Handle special commands
    if request.message.strip().startswith("/"):
        return await handle_special_command(request.message.strip(), thread_id)

    try:
        # Invoke the agent
        result = await agent.ainvoke(request.message, thread_id)

        # Extract the last message
        messages = result.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="No response from agent")

        last_message = messages[-1]
        response_text = (
            last_message.content if hasattr(last_message, "content") else str(last_message)
        )

        # Check if there's a pending approval
        requires_approval = result.get("pending_approval", False)
        approval_details = result.get("approval_request")

        # Check for interrupts (HITL)
        if "__interrupt__" in result:
            requires_approval = True
            approval_details = result["__interrupt__"]

        return ChatResponse(
            response=response_text,
            thread_id=thread_id,
            requires_approval=requires_approval,
            approval_details=approval_details,
        )

    except Exception as e:
        logger.error(f"Error during chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve-action")
async def approve_action(request: ApprovalRequest) -> dict:
    """
    Approve or reject a pending action.

    Args:
        request: Approval decision

    Returns:
        Result of continuing execution

    Raises:
        HTTPException: If agent is not initialized or error occurs
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    logger.info(f"Approval decision for thread {request.thread_id}")

    try:
        # Resume the agent with the approval decision
        config = {"configurable": {"thread_id": request.thread_id}}

        from langgraph.types import Command

        result = await agent.graph.ainvoke(Command(resume={"decisions": request.decisions}), config)

        # Extract response
        messages = result.get("messages", [])
        last_message = messages[-1] if messages else None
        response_text = (
            last_message.content
            if last_message and hasattr(last_message, "content")
            else "Action completed"
        )

        return {
            "success": True,
            "response": response_text,
            "thread_id": request.thread_id,
        }

    except Exception as e:
        logger.error(f"Error during approval: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a document for RAG indexing.

    Args:
        file: Uploaded file

    Returns:
        Upload status and details

    Raises:
        HTTPException: If upload or processing fails
    """
    if not document_processor or not vectorstore:
        raise HTTPException(status_code=503, detail="Document processing not initialized")

    logger.info(f"Document upload: {file.filename}")

    try:
        # Read file content
        content = await file.read()

        # Process document
        chunks = document_processor.process_from_bytes(content, file.filename or "unknown")

        # Add to vector store
        vectorstore.add_documents(chunks)

        logger.info(f"Successfully processed {file.filename}: {len(chunks)} chunks created")

        return UploadResponse(
            success=True,
            message="Document uploaded and indexed successfully",
            filename=file.filename or "unknown",
            chunks_created=len(chunks),
        )

    except ValueError as e:
        # Unsupported file format
        logger.warning(f"Unsupported file format: {file.filename}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/conversation/{thread_id}")
async def get_conversation(thread_id: str) -> dict:
    """
    Get conversation state for a thread.

    Args:
        thread_id: Conversation thread ID

    Returns:
        Conversation state

    Raises:
        HTTPException: If agent is not initialized
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        state = agent.get_state(thread_id)

        # Extract messages
        messages = []
        if state and "values" in state:
            state_messages = state["values"].get("messages", [])
            for msg in state_messages:
                messages.append(
                    {
                        "type": msg.__class__.__name__,
                        "content": msg.content if hasattr(msg, "content") else str(msg),
                    }
                )

        return {
            "thread_id": thread_id,
            "messages": messages,
            "state": state,
        }

    except Exception as e:
        logger.error(f"Error retrieving conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents")
async def clear_documents() -> dict:
    """
    Clear all documents from the vector store.

    Returns:
        Success message

    Raises:
        HTTPException: If vectorstore is not initialized
    """
    if not vectorstore:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        vectorstore.clear_documents()

        return {
            "success": True,
            "message": "All documents cleared from vector store",
        }

    except Exception as e:
        logger.error(f"Error clearing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
