"""
LangChain Integration Module

This module provides LangChain-based orchestration capabilities for the enhanced orchestrator.
"""

from services.common.config.loader import get_env_with_default
from services.common.structured_logging import get_logger

logger = get_logger(__name__)

# LangChain imports
try:
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.memory import ConversationBufferMemory
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.tools import Tool
    from langchain_openai import ChatOpenAI

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Prompt versioning
PROMPT_VERSION = "v1.0"
SYSTEM_PROMPT = """You are Atlas, a helpful voice assistant.
You can search information, control devices, and have natural conversations.
Be concise in voice responses (under 50 words preferred).
Focus on being helpful, accurate, and conversational.

When responding:
- Keep responses conversational and natural
- Be concise but informative
- Ask clarifying questions when needed
- Provide helpful context when appropriate"""


def create_langchain_executor() -> AgentExecutor | None:
    """Create the LangChain agent executor."""
    if not LANGCHAIN_AVAILABLE:
        logger.warning(
            "langchain.not_available", message="LangChain not available, using fallback"
        )
        return None

    try:
        # Get LLM URLs from environment (agnostic service name)
        llm_primary_url = get_env_with_default("LLM_BASE_URL", "http://flan:8100", str)

        # Create LLM client (using primary FLAN-T5 service)
        # Note: FLAN-T5 doesn't support streaming, so disable it explicitly
        llm = ChatOpenAI(
            base_url=f"{llm_primary_url}/v1",
            api_key="dummy",  # FLAN-T5 doesn't require auth
            model="flan-t5-large",
            temperature=0.7,
            max_tokens=512,
            streaming=False,  # Explicitly disable streaming for FLAN-T5
        )

        # Create versioned prompt template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # Define REST API tools
        tools = [
            Tool(
                name="SendDiscordMessage",
                func=send_discord_message,
                description="Send a message to Discord channel",
            ),
            Tool(
                name="SearchWeb",
                func=search_web,
                description="Search the web for information",
            ),
            Tool(
                name="GetCurrentTime",
                func=get_current_time,
                description="Get the current date and time",
            ),
        ]

        # Create memory
        memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

        # Create agent
        agent = create_openai_functions_agent(llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=True,
            return_intermediate_steps=True,
        )

        logger.info("langchain.executor_created", version=PROMPT_VERSION)
        return executor

    except Exception as e:
        logger.error("langchain.executor_creation_failed", error=str(e))
        return None


def send_discord_message(message: str) -> str:
    """Send a message to Discord channel."""
    # This would integrate with the Discord REST API client
    logger.info("discord.message_sent", message=message[:100])
    return f"Message sent to Discord: {message[:50]}..."


def search_web(query: str) -> str:
    """Search the web for information."""
    # This would integrate with a web search tool
    logger.info("web.search_performed", query=query[:100])
    return f"Search results for: {query[:50]}..."


def get_current_time() -> str:
    """Get the current date and time."""
    import datetime

    now = datetime.datetime.now()
    return f"Current time is {now.strftime('%Y-%m-%d %H:%M:%S')}"


async def process_with_langchain(
    transcript: str, session_id: str, executor: AgentExecutor | None
) -> str:
    """Process transcript using LangChain orchestration."""
    if executor is None:
        # Fallback to simple response
        return f"I received your message: {transcript[:100]}..."

    try:
        result = await executor.ainvoke({"input": transcript, "session_id": session_id})

        # Handle different response formats from LangChain
        output = result.get("output")
        if output:
            return str(output)

        # Check intermediate steps for tool usage results
        intermediate_steps = result.get("intermediate_steps", [])
        if intermediate_steps:
            # Extract final action result if available
            last_step = intermediate_steps[-1]
            if isinstance(last_step, tuple) and len(last_step) >= 2:
                tool_result = last_step[1]
                if tool_result:
                    return str(tool_result)

        # Fallback response if no output found
        logger.warning(
            "langchain.no_output_in_result",
            result_keys=list(result.keys()),
            transcript=transcript[:100],
            session_id=session_id,
        )
        return f"I understand you asked about: {transcript[:100]}. Let me help you with that."

    except ValueError as e:
        error_msg = str(e)
        if (
            "No generation chunks" in error_msg
            or "generation chunks" in error_msg.lower()
        ):
            logger.warning(
                "langchain.no_streaming_chunks",
                error=error_msg,
                transcript=transcript[:100],
                session_id=session_id,
                note="FLAN-T5 doesn't support streaming, returning fallback response",
            )
            # Return helpful fallback response
            return f"I received your message: {transcript[:100]}. Let me help you with that."
        # Re-raise if it's a different ValueError
        raise
    except Exception as e:
        logger.error(
            "langchain.processing_failed",
            error=str(e),
            error_type=type(e).__name__,
            transcript=transcript[:100],
            session_id=session_id,
        )
        return f"I encountered an issue processing your request: {str(e)}"
