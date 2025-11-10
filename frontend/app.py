"""Streamlit frontend for Splunk MCP RAG Agent."""

import os
import uuid
from typing import Any

import requests
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Splunk MCP RAG Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = None
    
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []


def check_api_health() -> dict[str, Any] | None:
    """
    Check API health status.

    Returns:
        Health status or None if unreachable
    """
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"⚠️ Cannot connect to API: {e}")
        return None


def send_message(message: str) -> dict[str, Any] | None:
    """
    Send message to agent.

    Args:
        message: User message

    Returns:
        API response or None if error
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={"message": message, "thread_id": st.session_state.thread_id},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error sending message: {e}")
        return None


def upload_document(file) -> dict[str, Any] | None:
    """
    Upload document to API.

    Args:
        file: File object from Streamlit file uploader

    Returns:
        Upload response or None if error
    """
    try:
        files = {"file": (file.name, file, file.type)}
        response = requests.post(f"{API_BASE_URL}/upload", files=files, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            st.error(f"Duplicate: {file.name} already exists in the vector store")
        else:
            st.error(f"Error uploading document: {e}")
        return None
    except Exception as e:
        st.error(f"Error uploading document: {e}")
        return None


def upload_documents_bulk(files: list) -> dict[str, Any] | None:
    """
    Upload multiple documents to API.

    Args:
        files: List of file objects from Streamlit file uploader

    Returns:
        Bulk upload response or None if error
    """
    try:
        files_data = [("files", (file.name, file, file.type)) for file in files]
        response = requests.post(f"{API_BASE_URL}/upload-bulk", files=files_data, timeout=300)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error uploading documents: {e}")
        return None


def get_documents() -> dict[str, Any] | None:
    """
    Get list of documents from API.

    Returns:
        Document list response or None if error
    """
    try:
        response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching documents: {e}")
        return None


def delete_document(source_filename: str) -> dict[str, Any] | None:
    """
    Delete a document from the vector store.

    Args:
        source_filename: Source filename to delete

    Returns:
        Delete response or None if error
    """
    try:
        from urllib.parse import quote

        encoded_filename = quote(source_filename, safe="")
        response = requests.delete(
            f"{API_BASE_URL}/documents/{encoded_filename}", timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error deleting document: {e}")
        return None


def approve_action(decisions: list[dict]) -> dict[str, Any] | None:
    """
    Send approval decision to API.

    Args:
        decisions: List of approval decisions

    Returns:
        API response or None if error
    """
    try:
        response = requests.post(
            f"{API_BASE_URL}/approve-action",
            json={
                "thread_id": st.session_state.thread_id,
                "decisions": decisions,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error approving action: {e}")
        return None


def render_document_manager() -> None:
    """Render document management UI."""
    st.subheader("📚 Document Library")

    # Add refresh button
    col1, col2 = st.columns([3, 1])
    with col2:
        refresh = st.button("🔄", help="Refresh document list")

    # Fetch documents
    docs_response = get_documents()

    if docs_response:
        documents = docs_response.get("documents", [])
        total = docs_response.get("total_documents", 0)

        if total > 0:
            st.caption(f"**{total} document(s) indexed**")

            for doc in documents:
                source = doc["source"]
                chunk_count = doc["chunk_count"]

                with st.container():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.text(f"📄 {source}")
                        st.caption(f"{chunk_count} chunks")

                    with col2:
                        # Use unique key for each delete button
                        if st.button("🗑️", key=f"delete_{source}", help=f"Delete {source}"):
                            with st.spinner(f"Deleting {source}..."):
                                result = delete_document(source)
                                if result and result.get("success"):
                                    st.success(f"✅ Deleted {source}")
                                    st.rerun()

                    st.divider()
        else:
            st.info("No documents uploaded yet")
    else:
        st.warning("Could not fetch document list")


def render_sidebar() -> None:
    """Render sidebar with configuration and status."""
    with st.sidebar:
        st.title("🤖 Splunk MCP Agent")

        st.divider()

        # Health status
        st.subheader("System Status")
        health = check_api_health()

        if health:
            st.success("✅ API Connected")
            with st.expander("Component Status"):
                for component, status in health.get("components", {}).items():
                    st.text(f"{component}: {status}")
        else:
            st.error("❌ API Disconnected")

        st.divider()

        # Thread info
        st.subheader("Session Info")
        st.text(f"Thread ID: {st.session_state.thread_id[:8]}...")
        
        # Message count
        st.text(f"Messages: {len(st.session_state.messages)}")
        
        # Saved conversations count
        if st.session_state.conversation_history:
            st.text(f"Saved: {len(st.session_state.conversation_history)}")

        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💬 New Chat", use_container_width=True):
                # Save current conversation if it has messages
                if st.session_state.messages:
                    st.session_state.conversation_history.append({
                        "thread_id": st.session_state.thread_id,
                        "messages": st.session_state.messages.copy(),
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                    })
                
                # Start new conversation
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.messages = []
                st.session_state.pending_approval = None
                st.success("✅ New chat started! Previous chat saved.")
                st.rerun()
        
        with col2:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.messages = []
                st.session_state.pending_approval = None
                st.warning("🗑️ Chat cleared (not saved)")
                st.rerun()
        
        # Show saved conversations
        if st.session_state.conversation_history:
            st.divider()
            st.subheader("💾 Saved Chats")
            
            for i, conv in enumerate(reversed(st.session_state.conversation_history)):
                thread_preview = conv["thread_id"][:8]
                msg_count = len(conv["messages"])
                timestamp = conv.get("timestamp", "Unknown")
                
                # Format timestamp nicely
                try:
                    import datetime
                    dt = datetime.datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%b %d, %H:%M")
                except Exception:
                    time_str = timestamp
                
                if st.button(
                    f"📝 {time_str} ({msg_count} msgs)",
                    key=f"load_conv_{i}",
                    use_container_width=True
                ):
                    # Save current conversation if it has messages
                    if st.session_state.messages:
                        st.session_state.conversation_history.insert(0, {
                            "thread_id": st.session_state.thread_id,
                            "messages": st.session_state.messages.copy(),
                            "timestamp": __import__('datetime').datetime.now().isoformat(),
                        })
                    
                    # Load the selected conversation
                    st.session_state.thread_id = conv["thread_id"]
                    st.session_state.messages = conv["messages"].copy()
                    st.session_state.pending_approval = None
                    st.rerun()

        st.divider()

        # Document upload
        st.subheader("📄 Upload Documents")
        uploaded_files = st.file_uploader(
            "Choose file(s)",
            type=["pdf", "txt", "docx"],
            help="Upload documents for RAG indexing (supports multiple files)",
            accept_multiple_files=True,
        )

        if uploaded_files and st.button("Index Document(s)"):
            if len(uploaded_files) == 1:
                # Single file upload
                with st.spinner("Processing document..."):
                    result = upload_document(uploaded_files[0])
                    if result and result.get("success"):
                        st.success(
                            f"✅ {result['filename']} indexed ({result['chunks_created']} chunks)"
                        )
                        st.rerun()
            else:
                # Bulk upload
                with st.spinner(f"Processing {len(uploaded_files)} documents..."):
                    result = upload_documents_bulk(uploaded_files)
                    if result:
                        total_uploaded = result.get("total_uploaded", 0)
                        total_skipped = result.get("total_skipped", 0)
                        total_failed = result.get("total_failed", 0)

                        # Show summary
                        if total_uploaded > 0:
                            st.success(f"✅ {total_uploaded} document(s) uploaded successfully")
                        if total_skipped > 0:
                            st.warning(f"⚠️ {total_skipped} document(s) skipped (duplicates)")
                        if total_failed > 0:
                            st.error(f"❌ {total_failed} document(s) failed")

                        # Show details
                        with st.expander("View Details"):
                            for file_result in result.get("results", []):
                                status_icon = "✅" if file_result["success"] else "❌"
                                st.text(
                                    f"{status_icon} {file_result['filename']}: {file_result['message']}"
                                )
                        
                        st.rerun()

        st.divider()

        # Document library
        render_document_manager()

        st.divider()

        # About
        with st.expander("ℹ️ About"):
            st.markdown("""
            **Splunk MCP RAG Agent**

            This application demonstrates:
            - LangGraph agent orchestration
            - Splunk & Atlassian MCP integration
            - RAG with ChromaDB
            - Human-in-the-loop approvals
            - LangSmith monitoring
            
            **Special Commands**:
            - `/mcp` - List MCP servers and tools
            - `/tools` - List all available tools
            - `/help` - Show available commands
            """)


def render_approval_ui(approval_details: dict) -> None:
    """
    Render human-in-the-loop approval interface.

    Args:
        approval_details: Details of pending approvals
    """
    st.warning("⚠️ **Action Requires Approval**")

    # Extract action requests
    action_requests = approval_details.get("action_requests", [])

    if not action_requests:
        st.error("No action requests found")
        return

    for i, request in enumerate(action_requests):
        with st.container():
            st.markdown(f"**Action {i + 1}:** {request.get('action', 'Unknown')}")
            st.markdown(f"**Tool:** `{request.get('tool_name', 'Unknown')}`")

            st.json(request.get("arguments", {}))

            st.markdown(request.get("description", "No description provided"))

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("✅ Approve", key=f"approve_{i}"):
                    decisions = [{"type": "approve"}]
                    with st.spinner("Executing..."):
                        result = approve_action(decisions)
                        if result and result.get("success"):
                            st.session_state.pending_approval = None
                            st.session_state.messages.append(
                                {"role": "assistant", "content": result.get("response", "Done")}
                            )
                            st.rerun()

            with col2:
                if st.button("❌ Reject", key=f"reject_{i}"):
                    decisions = [{"type": "reject"}]
                    result = approve_action(decisions)
                    if result:
                        st.session_state.pending_approval = None
                        st.rerun()

            with col3:
                if st.button("✏️ Edit", key=f"edit_{i}"):
                    st.info("Edit functionality coming soon")


def render_chat() -> None:
    """Render chat interface."""
    st.title("💬 Chat with Splunk MCP Agent")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Display pending approval if exists
    if st.session_state.pending_approval:
        render_approval_ui(st.session_state.pending_approval)

    # Chat input with hint
    if prompt := st.chat_input("Ask me anything... (type /help for commands)"):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get agent response
        with st.spinner("Thinking..."):
            response = send_message(prompt)

            if response:
                # Check if approval is required
                if response.get("requires_approval"):
                    st.session_state.pending_approval = response.get("approval_details")
                    st.rerun()
                else:
                    # Add assistant response to chat history
                    assistant_message = response.get("response", "No response")
                    st.session_state.messages.append(
                        {"role": "assistant", "content": assistant_message}
                    )
                    # Rerun to display the new message through the main loop
                    st.rerun()


def main() -> None:
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
