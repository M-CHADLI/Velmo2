"""Session state helpers."""

import streamlit as st
from datetime import datetime

def init_chat_session():
    """Initialize chat session."""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'conversation_id' not in st.session_state:
        import uuid
        st.session_state.conversation_id = str(uuid.uuid4())
    if 'message_count' not in st.session_state:
        st.session_state.message_count = 0

def add_message(role: str, content: str, metadata: dict = None):
    """Add message to history."""
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
        "metadata": metadata or {}
    })
    st.session_state.message_count += 1

def get_messages():
    """Get all messages."""
    return st.session_state.messages

def clear_messages():
    """Clear chat."""
    st.session_state.messages = []
    st.session_state.message_count = 0
