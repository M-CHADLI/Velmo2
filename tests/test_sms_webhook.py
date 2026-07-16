"""Tests du webhook SMS FastAPI (POST /sms/webhook)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.sms_server import main

client = TestClient(main.app)


def _post(**form):
    return client.post("/sms/webhook", data=form)


def test_invalid_signature_returns_403():
    with patch.object(main, "_verify_twilio_signature", return_value=False):
        resp = _post(From="+33612345678", Body="Salut")

    assert resp.status_code == 403


def test_recognized_number_returns_agent_reply():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={"customer_id": "c-1", "velmo_user_id": "u-1"},
        ),
        patch.object(
            main.sms_channel, "receive_message", return_value="Bonjour, comment aider ?"
        ) as mock_recv,
    ):
        resp = _post(From="+33612345678", Body="Salut")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "Bonjour, comment aider ?" in resp.text
    assert "<Response>" in resp.text
    mock_recv.assert_called_once_with(user_id="u-1", text="Salut")


def test_unknown_number_returns_non_reconnu():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(main, "get_customer_by_phone", return_value=None),
        patch.object(main.sms_channel, "receive_message") as mock_recv,
    ):
        resp = _post(From="+33600000000", Body="Salut")

    assert resp.status_code == 200
    assert "Numéro non reconnu" in resp.text
    mock_recv.assert_not_called()


def test_recognized_number_falls_back_to_customer_ref():
    with (
        patch.object(main, "_verify_twilio_signature", return_value=True),
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={"customer_id": "c-2", "customer_ref": "CLI-42"},
        ),
        patch.object(main.sms_channel, "receive_message", return_value="ok") as mock_recv,
    ):
        resp = _post(From="+33612345678", Body="Statut commande")

    assert resp.status_code == 200
    mock_recv.assert_called_once_with(user_id="CLI-42", text="Statut commande")


def test_verify_twilio_signature_uses_request_validator():
    request = MagicMock()
    request.headers = {"X-Twilio-Signature": "sig123"}
    request.url = "https://example.com/sms/webhook"
    form = {"From": "+33612345678", "Body": "Salut"}

    with patch("apps.sms_server.main.RequestValidator") as MockValidator:
        MockValidator.return_value.validate.return_value = True
        ok = main._verify_twilio_signature(request, form)

    assert ok is True
    MockValidator.return_value.validate.assert_called_once()
