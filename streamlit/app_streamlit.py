"""Velmo 2.0 Streamlit Chat Interface."""

import streamlit as st
import sys
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory import load_settings, get_db
from guardrails import GuardrailManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Velmo 2.0 Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🤖 Velmo 2.0 Support Chat")

# Initialize session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = "demo_user"
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

# Initialize app
def initialize_app():
    if st.session_state.initialized:
        return
    try:
        settings = load_settings()
        db = get_db()
        db.init_db()
        st.session_state.guardrail_manager = GuardrailManager()
        st.session_state.initialized = True
    except Exception as e:
        st.error(f"Init failed: {e}")
        st.stop()

initialize_app()

# Placeholder
st.write("Chat interface coming next...")
