"""Tests du webhook WhatsApp FastAPI (POST /whatsapp/webhook) via Twilio."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.sms_server import main

client = TestClient(main.app)


def _post(message_sid=None, **form):
    """Envoie une requête POST au webhook WhatsApp (Twilio style: MessageSid/From/Body)."""
    data = dict(form)
    if message_sid is not None:
        data["MessageSid"] = message_sid
    return client.post("/whatsapp/webhook", data=data)


def test_rejects_invalid_signature():
    with patch.object(main, "_verify_twilio_signature", return_value=False):
        resp = _post(message_sid="SM1", From="whatsapp:+33612345678", Body="Salut")

    assert resp.status_code == 403


def test_recognized_number_delegates_to_agent_and_sends_reply():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-1",
                "customer_ref": "CLI-1",
                "velmo_user_id": "u-1",
                "full_name": "Alice",
                "email": "alice@example.com",
                "phone": "+33612345678",
            },
        ),
        patch.object(
            main.whatsapp_channel, "receive_message", return_value="Bonjour, comment aider ?"
        ) as mock_recv,
        patch.object(main.whatsapp_channel, "send_message", return_value=True) as mock_send,
    ):
        resp = _post(message_sid="SM1", From="whatsapp:+33612345678", Body="Salut")

    assert resp.status_code == 200
    mock_recv.assert_called_once_with(user_id="u-1", text="Salut")
    mock_send.assert_called_once_with(user_id="u-1", text="Bonjour, comment aider ?")


def test_unknown_number_does_not_call_agent():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(main, "get_customer_by_phone", return_value=None),
        patch.object(main.whatsapp_channel, "receive_message") as mock_recv,
        patch.object(main.whatsapp_channel, "send_message") as mock_send,
    ):
        resp = _post(message_sid="SM2", From="whatsapp:+33600000000", Body="Salut")

    assert resp.status_code == 200
    mock_recv.assert_not_called()
    mock_send.assert_not_called()


def test_duplicate_message_sid_is_ignored():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-1",
                "customer_ref": "CLI-1",
                "velmo_user_id": "u-1",
                "full_name": "Alice",
                "email": "alice@example.com",
                "phone": "+33612345678",
            },
        ),
        patch.object(main.whatsapp_channel, "receive_message", return_value="ok") as mock_recv,
        patch.object(main.whatsapp_channel, "send_message", return_value=True) as mock_send,
    ):
        _post(message_sid="dup-1", From="whatsapp:+33612345678", Body="Salut")
        _post(message_sid="dup-1", From="whatsapp:+33612345678", Body="Salut")

    mock_recv.assert_called_once()
    mock_send.assert_called_once()
