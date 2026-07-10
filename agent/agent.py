"""VelmoAgent — orchestrator for memory + guardrails + DeepSeek."""
import time
from typing import Optional
from agent.schema import VelmoResponse
from guardrails import GuardrailManager
from memory import MemoryManager
from langchain_openai import ChatOpenAI
from memory.config import settings as default_settings
from observability import set_user_context, trace_run
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from business.tools import TOOLS, set_business_identity, get_discovered_email

MAX_TOOL_ITERS = 3


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

    def _execute_tool(self, call: dict) -> str:
        """Exécuter un tool_call LangChain et renvoyer son texte (jamais lever)."""
        name = call.get("name")
        args = call.get("args", {}) or {}
        tool_map = {t.name: t for t in TOOLS}
        tool = tool_map.get(name)
        if tool is None:
            return f"Outil inconnu : {name}"
        try:
            return tool.invoke(args)
        except Exception as e:  # noqa: BLE001
            return f"Erreur outil {name} : {e}"

    def _generate_with_tools(self, messages: list) -> str:
        """Boucle tool-calling bornée. Retombe sur un invoke simple si le modèle
        ne supporte pas bind_tools."""
        try:
            llm_tools = self.llm.bind_tools(TOOLS)
        except Exception:
            with trace_run("agent_response") as run:
                _t = time.perf_counter()
                ai = self.llm.invoke(messages, config=run.config)
                run.log_score("response_latency_ms", (time.perf_counter() - _t) * 1000)
            return ai.content if hasattr(ai, "content") else str(ai)

        ai = None
        for _ in range(MAX_TOOL_ITERS):
            with trace_run("agent_response") as run:
                _t = time.perf_counter()
                ai = llm_tools.invoke(messages, config=run.config)
                run.log_score("response_latency_ms", (time.perf_counter() - _t) * 1000)
            messages.append(ai)
            tool_calls = getattr(ai, "tool_calls", None)
            if not tool_calls:
                break
            for call in tool_calls:
                result = self._execute_tool(call)
                messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        return ai.content if ai is not None and hasattr(ai, "content") else ""

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
        context_parts = []

        # Include long-term facts first
        if context.get("long_term"):
            long_term_facts = context["long_term"]
            facts_text = "\n".join([f"- {f.get('key', 'fact')}: {f.get('value', '')}" for f in long_term_facts])
            context_parts.append(f"Informations connues sur l'utilisateur:\n{facts_text}")

        # Then include short-term conversation history
        if context.get("short_term"):
            short_term_text = "\n".join([f"{m['role']}: {m['content']}" for m in context["short_term"]])
            context_parts.append(f"Historique récent:\n{short_term_text}")

        context_str = "\n\n".join(context_parts)

        # Set identity for business tools (pre-linked lookup by user_id)
        set_business_identity(user_id)

        # Stage 3: Generate response via bounded tool-calling loop
        try:
            messages = [
                SystemMessage(content=f"{system_prompt}\n\nContext:\n{context_str}"),
                HumanMessage(content=message),
            ]
            llm_response = self._generate_with_tools(messages)
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

        # Persist any discovered customer email as a durable fact (best-effort)
        discovered = get_discovered_email()
        if discovered:
            try:
                from memory.schema import FactData
                self.memory.long_term.store_fact(
                    user_id=user_id,
                    conversation_id=user_id,
                    fact_data=FactData(key="customer_email", value=discovered,
                                       type="identifier", confidence=1.0,
                                       source="tool_lookup"),
                    extracted_at_msg=0,
                )
            except Exception:
                pass

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
