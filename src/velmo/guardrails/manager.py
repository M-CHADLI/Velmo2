import logging
from .classifier import KimiClassifier
from .input_guard import check_input as _check_input
from .output_guard import check_output as _check_output
from .audit import write_log
from .schema import GuardDecision

logger = logging.getLogger(__name__)


class GuardrailManager:
    """Orchestre les garde-fous d'entrée et de sortie + journalisation."""

    def __init__(self, settings=None, classifier=None) -> None:
        self.classifier = classifier or KimiClassifier(settings=settings)

    def check_input(self, message: str, user_id: str) -> GuardDecision:
        decision = _check_input(message, self.classifier)
        write_log(user_id, decision)
        return decision

    def check_output(self, response: str, user_id: str) -> GuardDecision:
        decision = _check_output(response)
        write_log(user_id, decision)
        return decision
