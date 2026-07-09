"""Velmo 2.0 Streamlit Chat Interface."""

import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import load_settings, get_db, VelmoMemoryManager
from guardrails import GuardrailManager
from streamlit.components.chat_handler import ChatHandler
from streamlit.utils.session_manager import init_chat_session, add_message, get_messages, clear_messages

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

# Create a mock agent if not available
class SimpleAgent:
    def generate_response(self, user_message: str, user_id: str, conversation_id: str):
        # Mock response - replace with real agent
        return {
            "text": f"Thanks for your message: '{user_message}'. This is a test response.",
            "tokens_used": 100
        }

agent = SimpleAgent()  # TODO: Replace with real VelmoResponseAgent

chat_handler = ChatHandler(agent, guardrail_manager, memory_manager)

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
