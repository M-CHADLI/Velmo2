"""Velmo 2.0 Streamlit Chat Interface."""

import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from memory import load_settings, get_db, VelmoMemoryManager
from guardrails import GuardrailManager
from agent.agent import VelmoAgent
from components.chat_handler import ChatHandler
from components.database_viewer import DatabaseViewer
from utils.session_manager import init_chat_session, add_message, get_messages, clear_messages

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Velmo 2.0 Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

def initialize_app():
    """Initialize dependencies."""
    if st.session_state.initialized:
        return

    try:
        settings = load_settings()
        db = get_db()
        db.init_db()

        st.session_state.settings = settings
        st.session_state.memory_manager = VelmoMemoryManager(settings)
        st.session_state.guardrail_manager = GuardrailManager()
        st.session_state.initialized = True
        logger.info("✅ Velmo initialized")
    except Exception as e:
        st.error(f"❌ Initialization failed: {e}")
        logger.error(f"Init error: {e}")
        st.stop()

initialize_app()
init_chat_session()

# Title
st.title("🤖 Velmo 2.0 Support Chat")
st.markdown("*Ask me anything about your account, orders, or support needs.*")

# Get components
user_id = "demo_user"
conversation_id = st.session_state.get('conversation_id', 'conv_default')
memory_manager = st.session_state.memory_manager
guardrail_manager = st.session_state.guardrail_manager

# Initialize real VelmoAgent
settings = st.session_state.settings
agent = VelmoAgent(settings=settings)

# Wrapper for compatibility with ChatHandler
class AgentWrapper:
    def __init__(self, velmo_agent):
        self.velmo_agent = velmo_agent

    def generate_response(self, user_message: str, user_id: str, conversation_id: str):
        """Wrapper to match ChatHandler interface."""
        response = self.velmo_agent.process_message(user_id, user_message)
        return {
            "text": response.message,
            "tokens_used": 0,  # Not tracked by VelmoAgent
            "metadata": {
                "allowed": response.allowed,
                "guard_decision": response.guard_decision.dict() if response.guard_decision else None,
                "memory_context": response.memory_context,
                "turn_number": response.turn_number,
                "latency_ms": response.latency_ms
            }
        }

agent_wrapper = AgentWrapper(agent)
chat_handler = ChatHandler(agent_wrapper, guardrail_manager, memory_manager)

def format_metadata(metadata):
    """Format agent metadata for display."""
    if not metadata:
        return ""

    parts = []

    # Input guard
    if "input_guard" in metadata:
        ig = metadata["input_guard"]
        status = "🟢 allowed" if ig.get("allowed") else "🔴 blocked"
        parts.append(f"[Input Guard] {status}")

    # Memory context (skip if empty)
    if "memory_context" in metadata:
        mem = metadata["memory_context"]
        short = len(mem.get("short_term", []))
        long = len(mem.get("long_term", []))
        if short > 0 or long > 0:
            parts.append(f"[Memory] short_term: {short} turns, long_term: {long} facts")

    # Output guard
    if "output_guard" in metadata:
        og = metadata["output_guard"]
        status = "🟢 allowed" if og.get("allowed") else "🔴 blocked"
        parts.append(f"[Output Guard] {status}")

    # Turn number and judge trigger (only if turn > 0)
    if "turn_number" in metadata:
        turn = metadata["turn_number"]
        if turn > 0:
            judge_trigger = turn % 5 == 0
            trigger_text = " (judge trigger!)" if judge_trigger else ""
            parts.append(f"[Turn {turn}/5 to judge trigger{trigger_text}]")

    return "\n".join(parts)

# Display chat history
st.write("---")
for msg in get_messages():
    role = msg["role"]
    content = msg["content"]

    if role == "user":
        with st.chat_message("user"):
            st.write(content)
    else:
        with st.chat_message("assistant"):
            st.write(content)

st.write("---")

# Chat input
if prompt := st.chat_input("Ask Velmo..."):
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    add_message("user", prompt)

    # Process through pipeline
    with st.spinner("🤔 Thinking..."):
        try:
            result = asyncio.run(
                chat_handler.process_message(prompt, user_id, conversation_id)
            )

            # Display response
            with st.chat_message("assistant"):
                response_text = result["response"]
                st.write(response_text)

                # Show metadata
                metadata = result.get("metadata")
                if metadata:
                    metadata_text = format_metadata(metadata)
                    if metadata_text:
                        st.divider()
                        st.text(metadata_text)

                # Show latency
                latency_ms = result.get("latency_ms", 0)
                st.caption(f"⏱️ Response time: {latency_ms}ms")

                # Show warnings if blocked
                if result["blocked_input"]:
                    st.warning("⚠️ Input was blocked for safety")
                if result["blocked_output"]:
                    st.warning("⚠️ Response was blocked for safety")

            add_message("assistant", result["response"])

            if result["error"]:
                st.error(f"Error: {result['error']}")

        except Exception as e:
            st.error(f"Failed: {e}")
            logger.error(f"Chat error: {e}")

# Database Viewer
db = get_db()
db_viewer = DatabaseViewer(db, user_id)
db_viewer.render()

# Sidebar
with st.sidebar:
    st.write("**Velmo 2.0**")
    st.write(f"User: {user_id}")
    st.write(f"Messages: {st.session_state.message_count}")

    if st.button("🔄 Clear Chat"):
        clear_messages()
        st.rerun()

    st.divider()
    st.caption("Powered by Kimi 2.6 + PostgreSQL + LangChain")
