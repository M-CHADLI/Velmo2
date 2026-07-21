import logging
import time
import unicodedata
from typing import Any
from ..config import load_settings
from .short_term import SlidingWindowMemory
from .long_term import LongTermMemory
from .schema import ExtractionMetadata

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents, pour des comparaisons robustes."""
    if not text:
        return ""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


# Mots déclencheurs d'une demande d'oubli (normalisés, sans accent).
_FORGET_KEYWORDS = ["oublie", "supprime", "efface", "forget", "delete", "remove"]

# Catégories d'oubli : (termes reconnus dans le message, sous-chaînes de clé à cibler).
# Les « termes » servent aussi à matcher le CONTEXTE d'origine d'un fait.
_FORGET_CATEGORIES: list[tuple[list[str], list[str]]] = [
    (["commande", "order"], ["order", "commande", "numero_commande"]),
    (["adresse", "address", "code postal", "postal", "zip"],
     ["address", "adresse", "code_postal", "zip"]),
    (["tutoie", "tutoiement", "preference", "langue", "contact", "canal"],
     ["contact_method", "preference", "langue", "language", "relation_type", "tutoiement"]),
]


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
        self.short_term_by_user = {}  # Per-user short-term memory
        self.long_term = LongTermMemory(self.settings)

        # Per-user message counts for triggering extraction
        self._message_count_by_user = {}

        # Facade exposing extract_facts(user_id, turn_count) for the orchestrator (VelmoAgent)
        self.judge = _JudgeFacade(self)

    def _get_user_short_term(self, user_id: str) -> SlidingWindowMemory:
        """Get or create per-user short-term memory."""
        if user_id not in self.short_term_by_user:
            self.short_term_by_user[user_id] = SlidingWindowMemory()
        return self.short_term_by_user[user_id]

    def _get_user_message_count(self, user_id: str) -> int:
        """Get current message count for user."""
        return self._message_count_by_user.get(user_id, 0)

    def _increment_user_message_count(self, user_id: str) -> int:
        """Increment and return message count for user."""
        self._message_count_by_user[user_id] = self._get_user_message_count(user_id) + 1
        return self._message_count_by_user[user_id]

    def get_context(self, user_id: str) -> dict:
        """Return the current memory context for the orchestrator (short-term + long-term facts)."""
        short_term = self._get_user_short_term(user_id)
        try:
            long_term_facts = self.long_term.inspect_memory(user_id) if user_id else []
        except Exception as e:
            logger.error(f"Failed to retrieve long-term facts for user {user_id}: {e}")
            long_term_facts = []
        return {
            "short_term": short_term.history(),
            "long_term": long_term_facts or []
        }

    def add_exchange(self, user_id: str, message: str, response: str) -> int:
        """Record a user/assistant exchange and return the current turn number."""
        self.record_user_message(user_id, conversation_id=user_id, content=message)
        self.record_assistant_message(user_id, conversation_id=user_id, content=response)
        return self._message_count_by_user.get(user_id, 0) // 2

    def record_user_message(self, user_id: str, conversation_id: str, content: str) -> None:
        """Record user message, increment count, and trigger Judge facts extraction if required."""
        short_term = self._get_user_short_term(user_id)
        short_term.record("user", content)
        self._increment_user_message_count(user_id)

        # Check for GDPR forget request in user message
        self.check_and_handle_forget_request(user_id, content)

        # NOTE: Automatic Judge extraction trigger here is intentionally disabled.
        # VelmoAgent (the orchestrator) now owns triggering fact extraction based on its
        # own turn-count logic via `self.judge.extract_facts(...)`. Keeping both triggers
        # active caused duplicate/uncoordinated extraction runs.
        # trigger_freq = self.settings.extraction_trigger_frequency * 2
        # if count > 0 and count % trigger_freq == 0:
        #     logger.info(f"Triggering Judge fact extraction (message count: {count})")
        #     self.trigger_fact_extraction(user_id, conversation_id)

    def record_assistant_message(self, user_id: str, conversation_id: str, content: str) -> None:
        """Record assistant message to short-term memory."""
        short_term = self._get_user_short_term(user_id)
        short_term.record("assistant", content)
        self._increment_user_message_count(user_id)

    def trigger_fact_extraction(self, user_id: str, conversation_id: str) -> list[str]:
        """Manually trigger Kimi 2.6 Judge facts extraction on the last 10 messages."""
        from .judge import JudgeAgent
        judge = JudgeAgent(self.settings)

        # Retrieve last 10 messages from sliding window
        short_term = self._get_user_short_term(user_id)
        history_msgs = short_term.history()[-10:]
        if not history_msgs:
            return []

        # Run extraction
        db_start = time.perf_counter()
        extracted_facts, avg_confidence, judge_latency_ms = judge.extract_facts(history_msgs)

        valid_facts_count = 0
        stored_ids = []

        message_count = self._get_user_message_count(user_id)

        # Persist valid facts to long-term memory
        for fact in extracted_facts:
            if fact.confidence >= self.settings.confidence_threshold:
                valid_facts_count += 1
                try:
                    fact_id = self.long_term.store_fact(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        fact_data=fact,
                        extracted_at_msg=message_count
                    )
                    stored_ids.append(fact_id)
                except Exception as e:
                    logger.error(f"Failed to persist extracted fact {fact.key}: {e}")

        db_latency_ms = int((time.perf_counter() - db_start) * 1000)

        # Log extraction metadata
        meta = ExtractionMetadata(
            user_id=user_id,
            conversation_id=conversation_id,
            round_number=(message_count // 10),
            messages_count=message_count,
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

        Ex. : 'oublie mon numéro de commande' -> soft-delete des faits liés à la commande.

        Un fait est ciblé s'il correspond à la catégorie demandée par au moins un signal :
          - sa CLÉ contient un mot-clé de la catégorie (ex. 'address' dans 'address_zip') ;
          - sa VALEUR est citée explicitement dans le message (ex. 'oublie le 4490') ;
          - son CONTEXTE d'origine mentionne la catégorie (ex. le fait '4490' vient du
            message « Mon numéro de commande est 4490 » -> matché par « commande »).
        Le 3ᵉ signal est déterminant : le Judge range parfois une valeur sous une clé
        inattendue (ex. un numéro de commande sous 'identifier'), ce qui ferait rater
        les deux premiers signaux.
        """
        norm_content = _normalize(content)

        # 1. Est-ce bien une demande d'oubli ?
        if not any(kw in norm_content for kw in _FORGET_KEYWORDS):
            return False

        # 2. Quelles catégories sont visées ? -> mots-clés de clé + termes de contexte.
        target_keys: list[str] = []
        target_terms: list[str] = []
        for terms, keys in _FORGET_CATEGORIES:
            if any(t in norm_content for t in terms):
                target_terms.extend(terms)
                target_keys.extend(keys)

        # 3. Récupérer les faits actifs de l'utilisateur.
        try:
            active_facts = self.long_term.inspect_memory(user_id)
        except Exception as e:
            logger.error(f"Error checking forget request for user {user_id}: {e}")
            return False

        if not active_facts:
            return False

        # 4. Cibler et supprimer.
        deleted_any = False
        for fact in active_facts:
            key = _normalize(fact.get("key") or "")
            value = _normalize(fact.get("value") or "")
            context = _normalize(fact.get("context") or "")

            key_match = bool(target_keys) and any(tk in key for tk in target_keys)
            value_match = bool(value) and value in norm_content
            context_match = bool(target_terms) and any(t in context for t in target_terms)

            if key_match or value_match or context_match:
                try:
                    success = self.long_term.delete_fact_gdpr(
                        fact_id=fact["fact_id"],
                        user_id=user_id,
                        reason=f"GDPR user request: '{content}'",
                    )
                    if success:
                        deleted_any = True
                except Exception as e:
                    logger.error(f"Error deleting fact {fact['fact_id']}: {e}")

        return deleted_any

    def inspect_memory(self, user_id: str) -> list[dict[str, Any]]:
        """Inspection endpoint helper for R6."""
        return self.long_term.inspect_memory(user_id)

    def get_audit_trail(self, user_id: str) -> list[dict[str, Any]]:
        """Audit trail trace helper for R6."""
        return self.long_term.get_audit_trail(user_id)
