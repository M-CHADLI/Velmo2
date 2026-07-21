"""Tests du webhook SMS FastAPI (POST /sms/webhook) via OVH."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.sms_server import main

client = TestClient(main.app)


def _post(sms_id=None, **form):
    """Envoie une requête POST au webhook SMS (OVH style: id/senderid/message)."""
    data = dict(form)
    if sms_id is not None:
        data["id"] = sms_id
    return client.post("/sms/webhook", data=data)


def test_recognized_number_returns_agent_reply():
    """Numéro reconnu → agent traite le message et envoie la réponse par SMS."""
    with (
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-1",
                "customer_ref": "CLI-1",
                "velmo_user_id": "u-1",
                "full_name": "Alice",
                "email": "alice@example.com",
                "phone": "+33600000000",
            },
        ),
        patch.object(
            main.sms_channel, "receive_message", return_value="Bonjour, comment aider ?"
        ) as mock_recv,
        patch.object(main.sms_channel, "send_message", return_value=True) as mock_send,
    ):
        resp = _post(sms_id="1", senderid="+33612345678", message="Salut")

    assert resp.status_code == 200
    mock_recv.assert_called_once_with(user_id="u-1", text="Salut")
    mock_send.assert_called_once_with(user_id="u-1", text="Bonjour, comment aider ?")


def test_unknown_number_does_not_call_agent():
    """Numéro inconnu → pas d'appel agent, pas d'envoi SMS."""
    with (
        patch.object(main, "get_customer_by_phone", return_value=None),
        patch.object(main.sms_channel, "receive_message") as mock_recv,
        patch.object(main.sms_channel, "send_message") as mock_send,
    ):
        resp = _post(sms_id="2", senderid="+33600000000", message="Salut")

    assert resp.status_code == 200
    mock_recv.assert_not_called()
    mock_send.assert_not_called()


def test_duplicate_sms_id_is_ignored():
    """Un même id de SMS (retry OVH après timeout) n'est traité qu'une fois."""
    with (
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-1",
                "customer_ref": "CLI-1",
                "velmo_user_id": "u-1",
                "full_name": "Alice",
                "email": "alice@example.com",
                "phone": "+33600000000",
            },
        ),
        patch.object(main.sms_channel, "receive_message", return_value="ok") as mock_recv,
        patch.object(main.sms_channel, "send_message", return_value=True) as mock_send,
    ):
        _post(sms_id="dup-1", senderid="+33612345678", message="Salut")
        _post(sms_id="dup-1", senderid="+33612345678", message="Salut")

    mock_recv.assert_called_once()
    mock_send.assert_called_once()


def test_recognized_number_falls_back_to_customer_ref():
    """Fallback: velmo_user_id None → utilise customer_ref."""
    with (
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-2",
                "customer_ref": "CLI-42",
                "velmo_user_id": None,
                "full_name": "Bob",
                "email": "bob@example.com",
                "phone": "+33600000001",
            },
        ),
        patch.object(
            main.sms_channel, "receive_message", return_value="ok"
        ) as mock_recv,
        patch.object(main.sms_channel, "send_message", return_value=True),
    ):
        resp = _post(sms_id="3", senderid="+33612345678", message="Statut commande")

    assert resp.status_code == 200
    mock_recv.assert_called_once_with(user_id="CLI-42", text="Statut commande")


def test_fallback_to_customer_id_when_no_ref_or_velmo():
    """Fallback complet: utilise customer_id si rien d'autre."""
    with (
        patch.object(
            main,
            "get_customer_by_phone",
            return_value={
                "customer_id": "c-uuid-123",
                "customer_ref": None,
                "velmo_user_id": None,
                "full_name": "Charlie",
                "email": "charlie@example.com",
                "phone": "+33600000002",
            },
        ),
        patch.object(
            main.sms_channel, "receive_message", return_value="Réponse"
        ) as mock_recv,
        patch.object(main.sms_channel, "send_message", return_value=True),
    ):
        resp = _post(sms_id="4", senderid="+33612345678", message="Test")

    assert resp.status_code == 200
    mock_recv.assert_called_once_with(user_id="c-uuid-123", text="Test")
