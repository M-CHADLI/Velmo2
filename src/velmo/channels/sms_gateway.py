"""Canal SMS via Twilio — réception (webhook) et envoi (API)."""

import logging

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from velmo.channels.base import Channel

logger = logging.getLogger(__name__)


class SMSChannel(Channel):
    """Canal SMS : reçoit/envoie via Twilio, délègue le traitement à l'agent."""

    def __init__(self, agent, settings):
        self.agent = agent
        self.settings = settings
        self.twilio_client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

    def receive_message(self, user_id: str, text: str) -> str:
        result = self.agent.process_message(user_id=user_id, message=text)
        return result.message

    def send_message(self, user_id: str, text: str) -> bool:
        phone = self._lookup_phone_for_user(user_id)
        if not phone:
            logger.warning("send_message: no phone found for user_id=%s", user_id)
            return False
        try:
            self.twilio_client.messages.create(
                body=text, from_=self.settings.twilio_phone_number, to=phone
            )
            return True
        except TwilioRestException as e:
            logger.error("Twilio send failed for user_id=%s: %s", user_id, e)
            return False

    def _lookup_phone_for_user(self, user_id: str) -> str | None:
        from velmo.business.repository import (
            get_customer_by_customer_ref,
            get_customer_by_velmo_user,
        )

        customer = None
        if user_id and user_id.startswith("CLI-"):
            customer = get_customer_by_customer_ref(user_id)
        if not customer:
            customer = get_customer_by_velmo_user(user_id)
        return customer.get("phone") if customer else None
