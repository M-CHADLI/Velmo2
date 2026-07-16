"""Serveur FastAPI : webhook Twilio pour la réception de SMS.

Twilio appelle POST /sms/webhook à chaque SMS entrant. On valide la signature
HMAC de la requête, on identifie le client par son numéro, puis on délègue au
SMSChannel qui fait tourner l'agent. La réponse est renvoyée en TwiML (XML).
"""

import logging

from fastapi import FastAPI, Request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from velmo.agent.agent import VelmoAgent
from velmo.business.repository import get_customer_by_phone
from velmo.channels.sms_gateway import SMSChannel
from velmo.config import load_settings

logger = logging.getLogger(__name__)

# --- Initialisation au chargement du module (pattern FastAPI standard) ---
settings = load_settings()
agent = VelmoAgent(settings=settings)
sms_channel = SMSChannel(agent=agent, settings=settings)

app = FastAPI(title="Velmo SMS Server")

UNKNOWN_NUMBER_MESSAGE = (
    "Numéro non reconnu. Contactez le support pour associer votre numéro à votre compte."
)


def _verify_twilio_signature(request: Request, form: dict) -> bool:
    """Valide la signature HMAC Twilio de la requête entrante.

    Reconstruit l'URL appelée + les paramètres de formulaire et les compare à
    l'en-tête X-Twilio-Signature via le secret partagé (auth token).
    """
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    return validator.validate(url, form, signature)


def _resolve_user_id(customer: dict) -> str:
    """Détermine l'identifiant utilisateur agent à partir du client."""
    return (
        customer.get("velmo_user_id")
        or customer.get("customer_ref")
        or customer.get("customer_id")
    )


def _twiml(message: str) -> Response:
    resp = MessagingResponse()
    resp.message(message)
    return Response(content=str(resp), media_type="application/xml")


@app.post("/sms/webhook")
async def sms_webhook(request: Request) -> Response:
    form = dict(await request.form())

    if not _verify_twilio_signature(request, form):
        logger.warning("Rejected SMS webhook: invalid Twilio signature")
        return Response(status_code=403, content="Invalid Twilio signature")

    from_number = form.get("From", "")
    body = form.get("Body", "")

    customer = get_customer_by_phone(from_number)
    if not customer:
        logger.info("SMS from unrecognized number %s", from_number)
        return _twiml(UNKNOWN_NUMBER_MESSAGE)

    user_id = _resolve_user_id(customer)
    reply = sms_channel.receive_message(user_id=user_id, text=body)
    return _twiml(reply)
