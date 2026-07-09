"""Chat message handler with full pipeline."""

import asyncio
import logging
import time
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
                "error": str | None,
                "latency_ms": int,
                "metadata": dict | None
            }
        """
        start_time = time.perf_counter()
        try:
            # 1. Check input guardrails
            input_decision = self.guardrail_manager.check_input(user_message, user_id)
            if not input_decision.allowed:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.warning(f"Input blocked: {input_decision.category}")
                return {
                    "response": input_decision.safe_message or "Cannot process this request.",
                    "blocked_input": True,
                    "blocked_output": False,
                    "error": None,
                    "latency_ms": latency_ms,
                    "metadata": {
                        "input_guard": input_decision.dict()
                    }
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
            agent_metadata = agent_response.get("metadata") if isinstance(agent_response, dict) else None

            # 4. Check output guardrails
            output_decision = self.guardrail_manager.check_output(response_text, user_id)
            if not output_decision.allowed:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.warning(f"Output blocked: {output_decision.category}")
                return {
                    "response": output_decision.safe_message or "Response blocked for safety.",
                    "blocked_input": False,
                    "blocked_output": True,
                    "error": None,
                    "latency_ms": latency_ms,
                    "metadata": {
                        **(agent_metadata or {}),
                        "output_guard": output_decision.dict()
                    }
                }

            # 5. Record assistant message
            self.memory_manager.record_assistant_message(user_id, conversation_id, response_text)

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "response": response_text,
                "blocked_input": False,
                "blocked_output": False,
                "error": None,
                "latency_ms": latency_ms,
                "metadata": agent_metadata
            }

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Chat error: {e}")
            return {
                "response": "Sorry, something went wrong. Please try again.",
                "blocked_input": False,
                "blocked_output": False,
                "error": str(e),
                "latency_ms": latency_ms,
                "metadata": None
            }
