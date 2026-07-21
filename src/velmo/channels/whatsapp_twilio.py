"""Canal WhatsApp via Twilio — réception et envoi."""
import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from velmo.business.repository import get_customer_by_customer_ref, get_customer_by_velmo_user
from velmo.channels.base import Channel

logger = logging.getLogger(__name__)


def strip_whatsapp_prefix(number: str) -> str:
    """Twilio préfixe les numéros WhatsApp par 'whatsapp:' (ex: 'whatsapp:+33612345678')."""
    return number.removeprefix("whatsapp:")


class TwilioWhatsAppChannel(Channel):
    """Canal WhatsApp : reçoit/envoie via Twilio, délègue le traitement à l'agent."""

    def __init__(self, agent, settings):
        self.agent = agent
        self.settings = settings
        self.twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

    def receive_message(self, user_id: str, text: str) -> str:
        """Traite un message entrant via l'agent et retourne la réponse texte."""
        result = self.agent.process_message(user_id=user_id, message=text)
        return result.message

    def send_message(self, user_id: str, text: str) -> bool:
        """Envoie un message WhatsApp au client. Retourne True si succès."""
        phone = self._lookup_phone_for_user(user_id)
        if not phone:
            logger.warning("send_message: no phone found for user_id=%s", user_id)
            return False

        try:
            self.twilio_client.messages.create(
                body=text,
                from_=self.settings.twilio_whatsapp_number,
                to=f"whatsapp:{phone}",
            )
            logger.info("WhatsApp message sent to %s", phone)
            return True
        except TwilioRestException as e:
            logger.error("Twilio WhatsApp send failed for user_id=%s: %s", user_id, e)
            return False

    def _lookup_phone_for_user(self, user_id: str) -> str | None:
        """Lookup phone by customer ref or velmo user ID."""
        customer = None
        if user_id and user_id.startswith("CLI-"):
            customer = get_customer_by_customer_ref(user_id)
        if not customer:
            customer = get_customer_by_velmo_user(user_id)
        return customer.get("phone") if customer else None
