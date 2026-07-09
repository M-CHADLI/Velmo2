"""Test Streamlit chat interface."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from streamlit.components.chat_handler import ChatHandler

@pytest.mark.asyncio
async def test_chat_handler_allowed_message():
    """Test message goes through full pipeline."""
    agent = Mock()
    guardrail_mgr = Mock()
    memory_mgr = Mock()

    # Mock guardrails to allow
    guardrail_mgr.check_input.return_value = Mock(allowed=True)
    guardrail_mgr.check_output.return_value = Mock(allowed=True)

    # Mock agent
    agent.generate_response = Mock(return_value={"text": "Hello!", "tokens_used": 50})

    handler = ChatHandler(agent, guardrail_mgr, memory_mgr)
    result = await handler.process_message("Hi Velmo", "user_1", "conv_1")

    assert result["blocked_input"] is False
    assert result["blocked_output"] is False
    assert "Hello" in result["response"]
    memory_mgr.record_user_message.assert_called_once()
    memory_mgr.record_assistant_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_handler_blocked_input():
    """Test blocked input returns safe message."""
    agent = Mock()
    guardrail_mgr = Mock()
    memory_mgr = Mock()

    # Mock guardrail to block
    guardrail_mgr.check_input.return_value = Mock(
        allowed=False,
        safe_message="Cannot process this"
    )

    handler = ChatHandler(agent, guardrail_mgr, memory_mgr)
    result = await handler.process_message("hate speech", "user_1", "conv_1")

    assert result["blocked_input"] is True
    assert result["response"] == "Cannot process this"
    memory_mgr.record_user_message.assert_not_called()
