"""VelmoAgent — orchestrator for memory + guardrails + DeepSeek."""
import time
from typing import Optional
from agent.schema import VelmoResponse
from guardrails import GuardrailManager
from memory import MemoryManager
from langchain_openai import ChatOpenAI
from memory.config import settings as default_settings
from observability import set_user_context, trace_run


class VelmoAgent:
    """Orchestrator: memory + guardrails + DeepSeek LLM."""

    def __init__(
        self,
        settings=None,
        classifier=None,
        llm: Optional[ChatOpenAI] = None
    ):
        self.settings = settings or default_settings
        self.guardrail = GuardrailManager(settings=self.settings, classifier=classifier)
        self.memory = MemoryManager(settings=self.settings)
        self.llm = llm or ChatOpenAI(
            model=self.settings.azure_openai_deployment_name,
            api_key=self.settings.azure_openai_api_key,
            base_url=self.settings.azure_openai_endpoint,
            temperature=0.5,
            max_tokens=self.settings.response_max_tokens,
        )

    def process_message(self, user_id: str, message: str) -> VelmoResponse:
        """Process message end-to-end: input -> memory -> deepseek -> output -> store."""
        start_time = time.perf_counter()

        # Attach user to all traces produced during this request
        set_user_context(user_id)

        # Stage 1: Input guard
        input_decision = self.guardrail.check_input(message, user_id)
        if not input_decision.allowed:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return VelmoResponse(
                allowed=False,
                message=input_decision.safe_message,
                guard_decision=input_decision,
                memory_context={},
                turn_number=0,
                latency_ms=latency_ms
            )

        # Stage 2: Enrich with memory context
        try:
            context = self.memory.get_context(user_id)
        except Exception:
            context = {}

        # Stage 3: Call DeepSeek
        system_prompt = "You are Velmo, an e-commerce support assistant. Answer briefly and helpfully."
        context_str = ""
        if context.get("short_term"):
            context_str = "\n".join([f"{m['role']}: {m['content']}" for m in context["short_term"]])

        full_prompt = f"{system_prompt}\n\nContext:\n{context_str}\n\nUser: {message}"

        try:
            with trace_run("agent_response") as run:
                llm_message = self.llm.invoke(full_prompt, config=run.config)
                run.log_score(
                    "response_latency_ms",
                    (time.perf_counter() - start_time) * 1000,
                )
            llm_response = llm_message.content if hasattr(llm_message, 'content') else str(llm_message)
        except Exception:
            # Fail-safe on DeepSeek error
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return VelmoResponse(
                allowed=False,
                message="Je ne peux pas traiter cette demande. Je suis l'assistant du support Velmo — reformulez et je vous aide avec plaisir.",
                guard_decision=None,
                memory_context=context,
                turn_number=0,
                latency_ms=latency_ms
            )

        # Stage 4: Output guard
        output_decision = self.guardrail.check_output(llm_response, user_id)
        if not output_decision.allowed:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return VelmoResponse(
                allowed=False,
                message=output_decision.safe_message,
                guard_decision=output_decision,
                memory_context=context,
                turn_number=0,
                latency_ms=latency_ms
            )

        # Stage 5: Store in short-term memory
        try:
            turn_number = self.memory.add_exchange(user_id, message, llm_response)
        except Exception:
            # Memory failure doesn't block response
            turn_number = 0

        # Stage 6: Trigger judge every 5 turns
        if turn_number > 0 and turn_number % 5 == 0:
            try:
                self.memory.judge.extract_facts(user_id, turn_count=10)
            except Exception:
                # Judge failure doesn't block
                pass

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        return VelmoResponse(
            allowed=True,
            message=llm_response,
            guard_decision=None,
            memory_context=context,
            turn_number=turn_number or 1,
            latency_ms=latency_ms
        )
