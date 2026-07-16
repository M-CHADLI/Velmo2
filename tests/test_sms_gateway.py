from unittest.mock import MagicMock, patch

from velmo.channels.sms_gateway import SMSChannel


def _make_channel():
    """Build an SMSChannel with a mocked Twilio client and agent."""
    agent = MagicMock()
    settings = MagicMock()
    settings.twilio_account_sid = "AC_test"
    settings.twilio_auth_token = "token_test"
    settings.twilio_phone_number = "+15551230000"
    with patch("velmo.channels.sms_gateway.TwilioClient"):
        channel = SMSChannel(agent=agent, settings=settings)
    return channel, agent, settings


def test_receive_message_delegates_to_agent():
    channel, agent, _ = _make_channel()
    agent.process_message.return_value = MagicMock(message="Bonjour!")

    result = channel.receive_message("u-1", "Salut")

    assert result == "Bonjour!"
    agent.process_message.assert_called_once_with(user_id="u-1", message="Salut")


def test_send_message_with_valid_phone():
    channel, _, settings = _make_channel()
    channel._lookup_phone_for_user = MagicMock(return_value="+33612345678")

    ok = channel.send_message("CLI-42", "Votre commande est expédiée")

    assert ok is True
    channel.twilio_client.messages.create.assert_called_once_with(
        body="Votre commande est expédiée",
        from_="+15551230000",
        to="+33612345678",
    )


def test_send_message_no_phone_returns_false():
    channel, _, _ = _make_channel()
    channel._lookup_phone_for_user = MagicMock(return_value=None)

    ok = channel.send_message("u-unknown", "texte")

    assert ok is False
    channel.twilio_client.messages.create.assert_not_called()


def test_send_message_twilio_exception_returns_false():
    from twilio.base.exceptions import TwilioRestException

    channel, _, _ = _make_channel()
    channel._lookup_phone_for_user = MagicMock(return_value="+33612345678")
    channel.twilio_client.messages.create.side_effect = TwilioRestException(
        status=400, uri="/Messages", msg="boom"
    )

    ok = channel.send_message("CLI-42", "texte")

    assert ok is False


def test_lookup_phone_by_customer_ref():
    channel, _, _ = _make_channel()
    with patch(
        "velmo.business.repository.get_customer_by_customer_ref",
        return_value={"phone": "+33611111111"},
    ) as mock_ref, patch(
        "velmo.business.repository.get_customer_by_velmo_user"
    ) as mock_velmo:
        phone = channel._lookup_phone_for_user("CLI-99")

    assert phone == "+33611111111"
    mock_ref.assert_called_once_with("CLI-99")
    mock_velmo.assert_not_called()


def test_lookup_phone_by_velmo_user():
    channel, _, _ = _make_channel()
    with patch(
        "velmo.business.repository.get_customer_by_velmo_user",
        return_value={"phone": "+33622222222"},
    ) as mock_velmo:
        phone = channel._lookup_phone_for_user("u-123")

    assert phone == "+33622222222"
    mock_velmo.assert_called_once_with("u-123")
