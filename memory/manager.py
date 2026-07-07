import logging
import time
from typing import Any, Optional
from .config import load_settings
from .short_term import SlidingWindowMemory
from .long_term import LongTermMemory
from .schema import FactData, ExtractionMetadata

logger = logging.getLogger(__name__)


class _JudgeFacade:
    """Thin adapter exposing a simple extract_facts(user_id, turn_count) surface for VelmoAgent."""

    def __init__(self, manager: "VelmoMemoryManager") -> None:
        self._manager = manager

    def extract_facts(self, user_id: str, turn_count: int = 10) -> list[str]:
        return self._manager.trigger_fact_extraction(user_id, conversation_id=user_id)


class VelmoMemoryManager:
    """Orchestrates short-term and long-term memory operations, including Judge fact extraction."""

    def __init__(self, settings=None) -> None:
        self.settings = settings or load_settings()
        self.short_term = SlidingWindowMemory()
        self.long_term = LongTermMemory(self.settings)

        # Local stats/counters for triggering extraction
        self._message_count = 0

        # Facade exposing extract_facts(user_id, turn_count) for the orchestrator (VelmoAgent)
        self.judge = _JudgeFacade(self)

    def get_context(self, user_id: str) -> dict:
        """Return the current memory context for the orchestrator (short-term window)."""
        return {"short_term": self.short_term.history()}

    def add_exchange(self, user_id: str, message: str, response: str) -> int:
        """Record a user/assistant exchange and return the current turn number."""
        self.record_user_message(user_id, conversation_id=user_id, content=message)
        self.record_assistant_message(user_id, conversation_id=user_id, content=response)
        return self._message_count // 2

    def record_user_message(self, user_id: str, conversation_id: str, content: str) -> None:
        """Record user message, increment count, and trigger Judge facts extraction if required."""
        self.short_term.record("user", content)
        self._message_count += 1

        # Check for GDPR forget request in user message
        self.check_and_handle_forget_request(user_id, content)

        # Trigger Judge extraction every 10 messages (5 tours)
        trigger_freq = self.settings.extraction_trigger_frequency * 2
        if self._message_count > 0 and self._message_count % trigger_freq == 0:
            logger.info(f"Triggering Judge fact extraction (message count: {self._message_count})")
            self.trigger_fact_extraction(user_id, conversation_id)

    def record_assistant_message(self, user_id: str, conversation_id: str, content: str) -> None:
        """Record assistant message to short-term memory."""
        self.short_term.record("assistant", content)
        self._message_count += 1

    def trigger_fact_extraction(self, user_id: str, conversation_id: str) -> list[str]:
        """Manually trigger Kimi 2.6 Judge facts extraction on the last 10 messages."""
        from .judge import JudgeAgent
        judge = JudgeAgent(self.settings)

        # Retrieve last 10 messages from sliding window
        history_msgs = self.short_term.history()[-10:]
        if not history_msgs:
            return []

        # Run extraction
        db_start = time.perf_counter()
        extracted_facts, avg_confidence, judge_latency_ms = judge.extract_facts(history_msgs)
        
        valid_facts_count = 0
        stored_ids = []

        # Persist valid facts to long-term memory
        for fact in extracted_facts:
            if fact.confidence >= self.settings.confidence_threshold:
                valid_facts_count += 1
                try:
                    fact_id = self.long_term.store_fact(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        fact_data=fact,
                        extracted_at_msg=self._message_count
                    )
                    stored_ids.append(fact_id)
                except Exception as e:
                    logger.error(f"Failed to persist extracted fact {fact.key}: {e}")

        db_latency_ms = int((time.perf_counter() - db_start) * 1000)

        # Log extraction metadata
        meta = ExtractionMetadata(
            user_id=user_id,
            conversation_id=conversation_id,
            round_number=(self._message_count // 10),
            messages_count=self._message_count,
            judge_confidence=avg_confidence,
            judge_latency_ms=judge_latency_ms,
            facts_extracted=len(extracted_facts),
            facts_valid=valid_facts_count,
            embedding_latency_ms=0,  # Embedded inside store_fact
            embedding_model=self.settings.embedding_model,
            embedding_dimensions=self.settings.embedding_dimensions,
            db_latency_ms=db_latency_ms
        )
        try:
            self.long_term.record_extraction_metadata(meta)
        except Exception as e:
            logger.error(f"Failed to log extraction metadata: {e}")

        return stored_ids

    def get_conversation_context(self, user_id: str, query: str, k: int = 5) -> str:
        """Retrieve relevant long-term facts for query and return them as system prompt context.

        Also registers audit log entries.
        """
        facts = self.long_term.retrieve_context(user_id, query, k=k)
        if not facts:
            return ""

        context_lines = ["Informations connues sur l'utilisateur :"]
        for fact in facts:
            # Only include facts above threshold
            if fact.get("confidence", 0.0) >= self.settings.confidence_threshold:
                # Provide a natural phrasing
                context_lines.append(f"- {fact['key']}: {fact['value']}")
        
        return "\n".join(context_lines)

    def check_and_handle_forget_request(self, user_id: str, content: str) -> bool:
        """Scan user message for GDPR 'forget' commands and delete corresponding facts.

        For example: 'oublie mon numéro de commande' -> soft delete order-related facts.
        """
        content_lower = content.lower()
        forget_keywords = ["oublie", "supprime", "efface", "forget", "delete", "remove"]
        
        # Check if the user is asking to forget something
        if not any(kw in content_lower for kw in forget_keywords):
            return False

        # Identify target categories/keywords to match in facts
        target_keys = []
        if any(term in content_lower for term in ["commande", "order", "numéro de commande"]):
            target_keys.extend(["contract_id", "order_id", "commande", "numero_commande"])
        if any(term in content_lower for term in ["adresse", "address", "code postal", "postal"]):
            target_keys.extend(["address", "address_zip", "adresse", "code_postal"])
        if any(term in content_lower for term in ["tutoyer", "tutoiement", "tutoie", "preference", "pref"]):
            target_keys.extend(["contact_method", "preference", "langue", "tutoiement"])

        # Fetch active facts for the user
        active_facts = self.long_term.inspect_memory(user_id)
        if not active_facts:
            return False

        deleted_any = False
        for fact in active_facts:
            fact_id = fact["fact_id"]
            fact_key = fact["key"].lower()
            fact_val = fact["value"].lower()

            # Match by key type OR if the specific value is mentioned in the forget request
            key_match = any(tk in fact_key for tk in target_keys)
            val_match = (fact_val in content_lower) or any(term in content_lower for term in fact_val.split())

            if key_match or val_match:
                success = self.long_term.delete_fact_gdpr(
                    fact_id=fact_id,
                    user_id=user_id,
                    reason=f"GDPR user request: '{content}'"
                )
                if success:
                    deleted_any = True

        return deleted_any

    def inspect_memory(self, user_id: str) -> list[dict[str, Any]]:
        """Inspection endpoint helper for R6."""
        return self.long_term.inspect_memory(user_id)

    def get_audit_trail(self, user_id: str) -> list[dict[str, Any]]:
        """Audit trail trace helper for R6."""
        return self.long_term.get_audit_trail(user_id)
