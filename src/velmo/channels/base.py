from abc import ABC, abstractmethod


class Channel(ABC):
    """Interface abstraite pour un canal de communication (SMS, WhatsApp, etc.)."""

    @abstractmethod
    def receive_message(self, user_id: str, text: str) -> str:
        """Traite un message entrant via l'agent et retourne la réponse texte."""
        raise NotImplementedError

    @abstractmethod
    def send_message(self, user_id: str, text: str) -> bool:
        """Envoie un message au client. Retourne True si succès."""
        raise NotImplementedError
