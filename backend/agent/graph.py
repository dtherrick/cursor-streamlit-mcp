"""LangGraph agent implementation with HITL support."""

import logging
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from backend.agent.state import AgentState

logger = logging.getLogger(__name__)

# Tools that require human approval before execution
SENSITIVE_TOOLS = {
    "splunk-mcp_run_splunk_query",  # Splunk queries may be sensitive
    "splunk-mcp_execute_sql",  # Any SQL execution
    "run_splunk_query",  # Legacy placeholder tool name
    "execute_sql",  # Legacy placeholder tool name
}


class SplunkMCPAgent:
    """
    LangGraph agent with RAG, MCP tools, and human-in-the-loop.

    This agent:
    - Uses OpenAI for LLM calls
    - Has access to RAG retrieval tools
    - Can use MCP server tools (Splunk, Atlassian)
    - Supports human-in-the-loop for sensitive operations
    - Persists conversation state with checkpoints
    """

    def __init__(
        self,
        tools: list[BaseTool],
        model_name: str = "gpt-4o",
        checkpoint_path: str = "./data/checkpoints/agent.db",
    ) -> None:
        """
        Initialize the agent.

        Args:
            tools: List of tools available to the agent
            model_name: OpenAI model to use
            checkpoint_path: Path to SQLite checkpoint database
        """
        self.tools = tools
        self.model_name = model_name
        self.checkpoint_path = checkpoint_path

        # Initialize LLM with tools
        self.llm = ChatOpenAI(model_name=model_name, temperature=0)
        self.llm_with_tools = self.llm.bind_tools(tools)

        # Create checkpointer for persistence
        from langgraph.checkpoint.memory import MemorySaver

        self.checkpointer = MemorySaver()
        logger.info(
            "Using in-memory checkpointer (conversation state will not persist across restarts)"
        )

        # Build the graph
        self.graph: Any = self._build_graph()  # CompiledGraph type

        logger.info(f"Initialized SplunkMCPAgent with {len(tools)} tools and model {model_name}")

    def _build_graph(self) -> Any:  # Returns CompiledGraph
        """Build the LangGraph state graph."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("call_model", self._call_model_node)
        workflow.add_node("execute_tools", ToolNode(self.tools))
        workflow.add_node("human_review", self._human_review_node)

        # Set entry point
        workflow.set_entry_point("call_model")

        # Add conditional edges
        workflow.add_conditional_edges(
            "call_model",
            self._should_continue,
            {
                "execute_tools": "execute_tools",
                "human_review": "human_review",
                "end": END,
            },
        )

        # After tool execution, go back to model
        workflow.add_edge("execute_tools", "call_model")

        # After human review, execute tools
        workflow.add_edge("human_review", "execute_tools")

        # Compile with checkpointer
        return workflow.compile(checkpointer=self.checkpointer)

    def _call_model_node(self, state: AgentState) -> dict:
        """
        Call the LLM with current state.

        Args:
            state: Current agent state

        Returns:
            Updated state with new message
        """
        messages = state["messages"]

        logger.debug(f"Calling LLM with {len(messages)} message(s)")

        response = self.llm_with_tools.invoke(messages)

        return {
            "messages": [response],
            "pending_approval": False,
            "approval_request": None,
        }

    def _human_review_node(self, state: AgentState) -> dict:
        """
        Node for human-in-the-loop review.

        This node interrupts execution and waits for human approval
        of sensitive tool calls.

        Args:
            state: Current agent state

        Returns:
            Updated state after approval
        """
        messages = state["messages"]
        last_message = messages[-1]

        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            logger.warning("Human review called but no tool calls found")
            return state

        # Get the tool calls that need approval
        tool_calls = last_message.tool_calls

        # Create approval request
        approval_requests = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            if tool_name in SENSITIVE_TOOLS:
                approval_requests.append(
                    {
                        "action": tool_call["name"],
                        "tool_name": tool_name,
                        "arguments": tool_call["args"],
                        "description": (
                            f"Approve execution of {tool_name} with arguments: {tool_call['args']}"
                        ),
                    }
                )

        if approval_requests:
            logger.info(f"Requesting human approval for {len(approval_requests)} action(s)")

            # Interrupt and wait for approval
            approval = interrupt(
                {
                    "action_requests": approval_requests,
                    "message": "Human approval required for sensitive operations",
                }
            )

            logger.info(f"Received approval decision: {approval}")

            # Process approval decision
            # The approval should contain decisions for each request
            decisions = approval.get("decisions", [])

            for i, decision in enumerate(decisions):
                if decision.get("type") == "reject":
                    # Remove the tool call from the message
                    logger.info(f"Tool call {i} rejected by human")
                    # Add a message indicating rejection
                    return {
                        "messages": [
                            AIMessage(
                                content="The requested operation was rejected by human review."
                            )
                        ],
                        "pending_approval": False,
                        "approval_request": None,
                    }
                elif decision.get("type") == "edit":
                    # Update tool call arguments
                    edited_args = decision.get("edited_arguments", {})
                    tool_calls[i]["args"] = edited_args
                    logger.info(f"Tool call {i} edited by human")

        return {
            "pending_approval": False,
            "approval_request": None,
        }

    def _should_continue(
        self, state: AgentState
    ) -> Literal["execute_tools", "human_review", "end"]:
        """
        Determine next step based on current state.

        Args:
            state: Current agent state

        Returns:
            Next node to execute
        """
        messages = state["messages"]
        last_message = messages[-1]

        # If no tool calls, we're done
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return "end"

        # Check if any tool calls require human approval
        tool_calls = last_message.tool_calls
        needs_approval = any(tool_call["name"] in SENSITIVE_TOOLS for tool_call in tool_calls)

        if needs_approval:
            return "human_review"
        else:
            return "execute_tools"

    async def ainvoke(self, message: str, thread_id: str) -> dict:
        """
        Invoke the agent asynchronously.

        Args:
            message: User message
            thread_id: Conversation thread ID

        Returns:
            Agent response with state
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Create input state
        input_state = {
            "messages": [HumanMessage(content=message)],
            "retrieved_documents": [],
            "pending_approval": False,
            "approval_request": None,
        }

        # Invoke the graph
        result = await self.graph.ainvoke(input_state, config)

        return result

    def invoke(self, message: str, thread_id: str) -> dict:
        """
        Invoke the agent synchronously.

        Args:
            message: User message
            thread_id: Conversation thread ID

        Returns:
            Agent response with state
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Create input state
        input_state = {
            "messages": [HumanMessage(content=message)],
            "retrieved_documents": [],
            "pending_approval": False,
            "approval_request": None,
        }

        # Invoke the graph
        result = self.graph.invoke(input_state, config)

        return result

    async def astream(self, message: str, thread_id: str):
        """
        Stream agent execution.

        Args:
            message: User message
            thread_id: Conversation thread ID

        Yields:
            State updates as they occur
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Create input state
        input_state = {
            "messages": [HumanMessage(content=message)],
            "retrieved_documents": [],
            "pending_approval": False,
            "approval_request": None,
        }

        # Stream the graph execution
        async for event in self.graph.astream(input_state, config):
            yield event

    def get_state(self, thread_id: str) -> dict:
        """
        Get current state for a thread.

        Args:
            thread_id: Conversation thread ID

        Returns:
            Current state
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config)
        return state


def create_agent(
    tools: list[BaseTool],
    model_name: str = "gpt-4o",
    checkpoint_path: str = "./data/checkpoints/agent.db",
) -> SplunkMCPAgent:
    """
    Factory function to create an agent.

    Args:
        tools: List of tools for the agent
        model_name: OpenAI model name
        checkpoint_path: Path to checkpoint database

    Returns:
        Initialized agent
    """
    return SplunkMCPAgent(tools=tools, model_name=model_name, checkpoint_path=checkpoint_path)
