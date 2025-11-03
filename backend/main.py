"""FastAPI main application with LangSmith integration."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from .env file
load_dotenv()

from backend.agent.graph import create_agent
from backend.agent.tools import create_rag_tool
from backend.api import routes
from backend.mcp.config import load_mcp_config
from backend.mcp.server_manager import MCPServerManager
from backend.rag.document_processor import DocumentProcessor
from backend.rag.vectorstore import create_vectorstore

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
mcp_manager: MCPServerManager | None = None
vectorstore_manager = None
agent_instance = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan context manager for FastAPI application.

    Handles startup and shutdown logic.
    """
    # Startup
    logger.info("Starting Splunk MCP RAG Agent application...")

    global mcp_manager, vectorstore_manager, agent_instance

    try:
        # Configure LangSmith tracing
        os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "true")
        os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "splunk-mcp-agent")

        if os.getenv("LANGCHAIN_API_KEY"):
            logger.info("LangSmith tracing enabled")
        else:
            logger.warning("LANGCHAIN_API_KEY not set, tracing will be disabled")

        # Initialize vector store
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
        logger.info(f"Initializing vector store at {persist_dir}")
        vectorstore_manager = create_vectorstore(persist_directory=persist_dir)

        # Initialize document processor
        doc_processor = DocumentProcessor(chunk_size=1000, chunk_overlap=200)

        # Load MCP configuration (DISABLED for initial testing)
        logger.info("MCP server integration temporarily disabled")
        mcp_manager = None
        
        # Uncomment below to enable MCP servers:
        config_path = Path("config/mcp_servers.json")
        if config_path.exists():
            logger.info(f"Loading MCP configuration from {config_path}")
            mcp_config = load_mcp_config(config_path)
            mcp_manager = MCPServerManager(mcp_config)
            await mcp_manager.initialize()
        else:
            logger.warning(
                f"MCP configuration file not found: {config_path}. "
                "Agent will run without MCP tools."
            )
            mcp_manager = None

        # Collect all tools
        tools = []

        # Add RAG tool
        rag_tool = create_rag_tool(vectorstore_manager)
        tools.append(rag_tool)
        logger.info("Added RAG retrieval tool")

        # Add MCP tools
        if mcp_manager:
            mcp_tools = mcp_manager.get_all_tools()
            tools.extend(mcp_tools)
            logger.info(f"Added {len(mcp_tools)} MCP tool(s)")

        # Create agent
        checkpoint_dir = os.getenv("CHECKPOINT_DIR", "./data/checkpoints")
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
        checkpoint_path = f"{checkpoint_dir}/agent.db"

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        logger.info(f"Creating agent with model {model_name} and {len(tools)} tool(s)")

        agent_instance = create_agent(
            tools=tools, model_name=model_name, checkpoint_path=checkpoint_path
        )

        # Set dependencies for routes
        routes.set_dependencies(agent_instance, vectorstore_manager, doc_processor, mcp_manager)

        logger.info("Application startup complete")

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")

    if mcp_manager:
        await mcp_manager.shutdown()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Splunk MCP RAG Agent",
    description="LangGraph agent with Splunk MCP integration, RAG, and human-in-the-loop",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(_request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# Include routers
app.include_router(routes.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Splunk MCP RAG Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FASTAPI_HOST", "localhost")
    port = int(os.getenv("FASTAPI_PORT", "8000"))

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
