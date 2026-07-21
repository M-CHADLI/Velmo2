"""Tests du canal WhatsApp via Twilio (TwilioWhatsAppChannel)."""

from unittest.mock import MagicMock, patch

from twilio.base.exceptions import TwilioRestException

from velmo.channels.whatsapp_twilio import TwilioWhatsAppChannel, strip_whatsapp_prefix


class _FakeSettings:
    twilio_account_sid = "AC-fake"
    twilio_auth_token = "fake-token"
    twilio_whatsapp_number = "whatsapp:+14155238886"


def test_strip_whatsapp_prefix():
    assert strip_whatsapp_prefix("whatsapp:+33612345678") == "+33612345678"
    assert strip_whatsapp_prefix("+33612345678") == "+33612345678"


def test_receive_message_delegates_to_agent():
    agent = MagicMock()
    agent.process_message.return_value.message = "Bonjour, comment aider ?"

    with patch("velmo.channels.whatsapp_twilio.TwilioClient"):
        channel = TwilioWhatsAppChannel(agent=agent, settings=_FakeSettings())

    reply = channel.receive_message(user_id="u-1", text="Salut")

    assert reply == "Bonjour, comment aider ?"
    agent.process_message.assert_called_once_with(user_id="u-1", message="Salut")


def test_send_message_success():
    agent = MagicMock()

    with patch("velmo.channels.whatsapp_twilio.TwilioClient") as MockClient:
        channel = TwilioWhatsAppChannel(agent=agent, settings=_FakeSettings())
        mock_twilio = MockClient.return_value

        with patch.object(
            channel, "_lookup_phone_for_user", return_value="+33612345678"
        ):
            sent = channel.send_message(user_id="CLI-1", text="Votre commande est en route")

    assert sent is True
    mock_twilio.messages.create.assert_called_once_with(
        body="Votre commande est en route",
        from_="whatsapp:+14155238886",
        to="whatsapp:+33612345678",
    )


def test_send_message_no_phone_found():
    agent = MagicMock()

    with patch("velmo.channels.whatsapp_twilio.TwilioClient") as MockClient:
        channel = TwilioWhatsAppChannel(agent=agent, settings=_FakeSettings())
        mock_twilio = MockClient.return_value

        with patch.object(channel, "_lookup_phone_for_user", return_value=None):
            sent = channel.send_message(user_id="CLI-unknown", text="Test")

    assert sent is False
    mock_twilio.messages.create.assert_not_called()


def test_send_message_twilio_exception_caught():
    agent = MagicMock()

    with patch("velmo.channels.whatsapp_twilio.TwilioClient") as MockClient:
        channel = TwilioWhatsAppChannel(agent=agent, settings=_FakeSettings())
        mock_twilio = MockClient.return_value
        mock_twilio.messages.create.side_effect = TwilioRestException(
            status=400, uri="/Messages", msg="boom"
        )

        with patch.object(
            channel, "_lookup_phone_for_user", return_value="+33612345678"
        ):
            sent = channel.send_message(user_id="CLI-1", text="Test")

    assert sent is False
