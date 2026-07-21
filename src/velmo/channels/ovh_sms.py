"""Canal SMS via OVH — réception et envoi."""
import hashlib
import json
import logging
import time

import requests

from velmo.channels.base import Channel
from velmo.business.repository import get_customer_by_velmo_user, get_customer_by_customer_ref

logger = logging.getLogger(__name__)


class OVHChannel(Channel):
    """Canal SMS via OVH."""

    def __init__(self, agent, settings):
        self.agent = agent
        self.settings = settings
        self.api_url = "https://eu.api.ovh.com/1.0"

    def _signed_headers(self, method: str, url: str, body: str) -> dict:
        """Calcule les en-têtes de signature requis par l'API OVH.

        OVH n'accepte pas de Bearer token simple : chaque requête doit être
        signée avec App Secret + Consumer Key + method + url + body + timestamp
        (voir https://docs.ovh.com/fr/api/first-steps-with-ovh-api/).
        """
        timestamp = str(int(time.time()))
        to_sign = "+".join([
            self.settings.ovh_app_secret,
            self.settings.ovh_consumer_key,
            method,
            url,
            body,
            timestamp,
        ])
        signature = "$1$" + hashlib.sha1(to_sign.encode("utf-8")).hexdigest()
        return {
            "X-Ovh-Application": self.settings.ovh_app_key,
            "X-Ovh-Consumer": self.settings.ovh_consumer_key,
            "X-Ovh-Timestamp": timestamp,
            "X-Ovh-Signature": signature,
            "Content-Type": "application/json",
        }

    def receive_message(self, user_id: str, text: str) -> str:
        """Traite un message entrant via l'agent et retourne la réponse texte."""
        result = self.agent.process_message(user_id=user_id, message=text)
        return result.message

    def send_message(self, user_id: str, text: str) -> bool:
        """Envoie un message au client via OVH. Retourne True si succès."""
        phone = self._lookup_phone_for_user(user_id)
        if not phone:
            logger.warning("send_message: no phone found for user_id=%s", user_id)
            return False

        url = f"{self.api_url}/sms/{self.settings.ovh_service_name}/jobs"
        payload = {
            "message": text,
            "receivers": [phone],
            "senderForResponse": True,
        }
        body = json.dumps(payload)

        try:
            headers = self._signed_headers("POST", url, body)
            logger.info("Sending SMS to %s via OVH (service=%s)", phone, self.settings.ovh_service_name)
            response = requests.post(url, headers=headers, data=body)
            if response.status_code in [200, 201]:
                logger.info("SMS sent to %s: %s", phone, response.text)
                return True
            else:
                logger.error("OVH error %s: %s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("OVH SMS failed for user_id=%s: %s", user_id, e)
            return False

    def _lookup_phone_for_user(self, user_id: str) -> str | None:
        """Lookup phone by customer ref or velmo user ID."""
        customer = None
        if user_id and user_id.startswith("CLI-"):
            customer = get_customer_by_customer_ref(user_id)
        if not customer:
            customer = get_customer_by_velmo_user(user_id)
        return customer.get("phone") if customer else None
