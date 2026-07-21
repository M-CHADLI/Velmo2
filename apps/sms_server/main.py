"""Serveur FastAPI : webhooks SMS (OVH) et WhatsApp (Twilio).

OVH appelle POST /sms/webhook à chaque SMS entrant, Twilio appelle POST /whatsapp/webhook
à chaque message WhatsApp entrant. On identifie le client par son numéro, puis on délègue
au channel correspondant qui fait tourner l'agent et renvoie la réponse sur le même canal.
"""

import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from velmo.agent.agent import VelmoAgent
from velmo.business.repository import get_customer_by_phone
from velmo.channels.ovh_sms import OVHChannel
from velmo.channels.whatsapp_twilio import TwilioWhatsAppChannel, strip_whatsapp_prefix
from velmo.config import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# --- Initialisation au chargement du module (pattern FastAPI standard) ---
settings = load_settings()
agent = VelmoAgent(settings=settings)
sms_channel = OVHChannel(agent=agent, settings=settings)
whatsapp_channel = TwilioWhatsAppChannel(agent=agent, settings=settings)

app = FastAPI(title="Velmo Messaging Server")

UNKNOWN_NUMBER_MESSAGE = (
    "Numéro non reconnu. Contactez le support pour associer votre numéro à votre compte."
)

# Les providers (OVH, Twilio) retentent l'appel du webhook si notre réponse tarde (ex: appel
# LLM), ce qui redéclenche tout le traitement et renvoie plusieurs messages pour un seul
# message entrant. On répond immédiatement et on traite en tâche de fond, en dédupliquant
# par l'id du message pour ignorer les retries.
_processed_sms_ids: set[str] = set()
_processed_whatsapp_ids: set[str] = set()


def _resolve_user_id(customer: dict) -> str:
    """Détermine l'identifiant utilisateur agent à partir du client."""
    return (
        customer.get("velmo_user_id")
        or customer.get("customer_ref")
        or customer.get("customer_id")
    )


def _handle_sms(sms_id: str, from_number: str, body: str) -> None:
    """Traite le SMS et envoie la réponse. Exécuté en tâche de fond."""
    try:
        customer = get_customer_by_phone(from_number)
        if not customer:
            logger.info("SMS from unrecognized number %s", from_number)
            return

        user_id = _resolve_user_id(customer)
        reply = sms_channel.receive_message(user_id=user_id, text=body)

        sent = sms_channel.send_message(user_id=user_id, text=reply)
        if sent:
            logger.info("SMS reply sent to %s", from_number)
        else:
            logger.error("Failed to send SMS reply to %s", from_number)
    except Exception as e:
        logger.error("SMS background processing error for id=%s: %s", sms_id, e)


@app.post("/sms/webhook")
async def sms_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Accuse réception d'un SMS entrant OVH et traite en tâche de fond.

    On répond immédiatement (avant tout appel LLM) pour éviter qu'OVH ne
    timeout et ne retente l'appel, ce qui dupliquerait le traitement et les
    SMS de réponse.
    """
    try:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            data = await request.json()
        else:
            data = dict(await request.form())

        logger.info("SMS webhook raw payload: %s", data)

        sms_id = data.get("id") or ""
        from_number = data.get("senderid") or data.get("source") or data.get("From") or ""
        body = data.get("message") or data.get("Body") or ""

        logger.info("SMS received from %s: %s", from_number, body[:50])

        if sms_id and sms_id in _processed_sms_ids:
            logger.info("Duplicate SMS id=%s ignored (retry from OVH)", sms_id)
            return Response(content="", status_code=200, media_type="text/plain")
        if sms_id:
            _processed_sms_ids.add(sms_id)

        background_tasks.add_task(_handle_sms, sms_id, from_number, body)

        return Response(content="", status_code=200, media_type="text/plain")
    except Exception as e:
        logger.error("SMS webhook error: %s", e)
        return Response(
            content="Internal server error",
            status_code=500,
            media_type="text/plain"
        )


def _public_request_url(request: Request) -> str:
    """Reconstruit l'URL publique vue par Twilio.

    ngrok termine le HTTPS et relaie en HTTP en interne : `request.url` voit donc
    un scheme "http" alors que Twilio a signé la requête avec "https". On corrige
    via X-Forwarded-Proto (transmis par ngrok) pour que la signature valide.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")
    url = str(request.url)
    if forwarded_proto and url.startswith("http://"):
        url = forwarded_proto + url[len("http:"):]
    return url


def _verify_twilio_signature(request: Request, form_dict: dict) -> bool:
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = _public_request_url(request)
    return validator.validate(url, form_dict, signature)


def _handle_whatsapp(message_sid: str, from_number: str, body: str) -> None:
    """Traite le message WhatsApp et envoie la réponse. Exécuté en tâche de fond."""
    try:
        customer = get_customer_by_phone(from_number)
        if not customer:
            logger.info("WhatsApp message from unrecognized number %s", from_number)
            return

        user_id = _resolve_user_id(customer)
        reply = whatsapp_channel.receive_message(user_id=user_id, text=body)

        sent = whatsapp_channel.send_message(user_id=user_id, text=reply)
        if sent:
            logger.info("WhatsApp reply sent to %s", from_number)
        else:
            logger.error("Failed to send WhatsApp reply to %s", from_number)
    except Exception as e:
        logger.error("WhatsApp background processing error for sid=%s: %s", message_sid, e)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Accuse réception d'un message WhatsApp entrant Twilio et traite en tâche de fond.

    On valide la signature Twilio, puis on répond immédiatement (avant tout appel LLM)
    pour éviter que Twilio ne timeout et ne retente l'appel, ce qui dupliquerait le
    traitement et les messages de réponse.
    """
    try:
        form = await request.form()
        form_dict = dict(form)

        if not _verify_twilio_signature(request, form_dict):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        logger.info("WhatsApp webhook raw payload: %s", form_dict)

        message_sid = form_dict.get("MessageSid") or form_dict.get("SmsSid") or ""
        from_number = strip_whatsapp_prefix(form_dict.get("From", ""))
        body = (form_dict.get("Body") or "").strip()

        logger.info("WhatsApp message received from %s: %s", from_number, body[:50])

        if message_sid and message_sid in _processed_whatsapp_ids:
            logger.info("Duplicate WhatsApp message sid=%s ignored (retry from Twilio)", message_sid)
            return Response(content="", status_code=200, media_type="text/plain")
        if message_sid:
            _processed_whatsapp_ids.add(message_sid)

        background_tasks.add_task(_handle_whatsapp, message_sid, from_number, body)

        return Response(content="", status_code=200, media_type="text/plain")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("WhatsApp webhook error: %s", e)
        return Response(
            content="Internal server error",
            status_code=500,
            media_type="text/plain"
        )
