"""Chat message handler with full pipeline."""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ChatHandler:
    """Orchestrates message through guardrails → memory → LLM → output."""

    def __init__(self, agent, guardrail_manager, memory_manager):
        self.agent = agent
        self.guardrail_manager = guardrail_manager
        self.memory_manager = memory_manager

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Process message through full pipeline.

        Returns:
            {
                "response": str,
                "blocked_input": bool,
                "blocked_output": bool,
                "error": str | None
            }
        """
        try:
            # 1. Check input guardrails
            input_decision = self.guardrail_manager.check_input(user_message, user_id)
            if not input_decision.allowed:
                logger.warning(f"Input blocked: {input_decision.category}")
                return {
                    "response": input_decision.safe_message or "Cannot process this request.",
                    "blocked_input": True,
                    "blocked_output": False,
                    "error": None
                }

            # 2. Record in memory
            self.memory_manager.record_user_message(user_id, conversation_id, user_message)

            # 3. Generate response (sync wrapper)
            if asyncio.iscoroutinefunction(self.agent.generate_response):
                agent_response = await self.agent.generate_response(
                    user_message=user_message,
                    user_id=user_id,
                    conversation_id=conversation_id
                )
            else:
                agent_response = self.agent.generate_response(
                    user_message=user_message,
                    user_id=user_id,
                    conversation_id=conversation_id
                )

            response_text = agent_response.get("text", "") if isinstance(agent_response, dict) else str(agent_response)

            # 4. Check output guardrails
            output_decision = self.guardrail_manager.check_output(response_text, user_id)
            if not output_decision.allowed:
                logger.warning(f"Output blocked: {output_decision.category}")
                return {
                    "response": output_decision.safe_message or "Response blocked for safety.",
                    "blocked_input": False,
                    "blocked_output": True,
                    "error": None
                }

            # 5. Record assistant message
            self.memory_manager.record_assistant_message(user_id, conversation_id, response_text)

            return {
                "response": response_text,
                "blocked_input": False,
                "blocked_output": False,
                "error": None
            }

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "response": "Sorry, something went wrong. Please try again.",
                "blocked_input": False,
                "blocked_output": False,
                "error": str(e)
            }
