"""LangGraph agent state schema."""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State schema for the LangGraph agent.

    Attributes:
        messages: Conversation history (automatically merged)
        retrieved_documents: Documents retrieved from RAG
        pending_approval: Whether there's a pending human approval
        approval_request: Details of the action requiring approval
    """

    # Messages are automatically merged using add_messages
    messages: Annotated[list[BaseMessage], add_messages]

    # Retrieved documents from RAG
    retrieved_documents: list[str]

    # Human-in-the-loop state
    pending_approval: bool
    approval_request: dict | None


class ChatRequest(TypedDict):
    """Schema for chat requests from the API."""

    message: str
    thread_id: str


class ChatResponse(TypedDict):
    """Schema for chat responses to the API."""

    response: str
    thread_id: str
    requires_approval: bool
    approval_details: dict | None


class ApprovalRequest(TypedDict):
    """Schema for human-in-the-loop approval requests."""

    action: str
    tool_name: str
    arguments: dict
    description: str


class ApprovalDecision(TypedDict):
    """Schema for approval decisions."""

    decision: str  # "approve", "reject", or "edit"
    edited_arguments: dict | None
    feedback: str | None
