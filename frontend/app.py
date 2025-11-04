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
    except Exception as e:
        st.error(f"Error uploading document: {e}")
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
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "txt", "docx"],
            help="Upload documents for RAG indexing",
        )

        if uploaded_file and st.button("Index Document"):
            with st.spinner("Processing document..."):
                result = upload_document(uploaded_file)
                if result and result.get("success"):
                    st.success(
                        f"✅ {result['filename']} indexed ({result['chunks_created']} chunks)"
                    )
                else:
                    st.error("Failed to upload document")

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

        with st.chat_message("user"):
            st.markdown(prompt)

        # Get agent response
        with st.chat_message("assistant"), st.spinner("Thinking..."):
            response = send_message(prompt)

            if response:
                # Check if approval is required
                if response.get("requires_approval"):
                    st.session_state.pending_approval = response.get("approval_details")
                    st.rerun()
                else:
                    # Display response
                    assistant_message = response.get("response", "No response")
                    st.markdown(assistant_message)

                    # Add to chat history
                    st.session_state.messages.append(
                        {"role": "assistant", "content": assistant_message}
                    )


def main() -> None:
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
