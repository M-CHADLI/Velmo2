"""Tests for velmo config module."""
import os

from velmo.config import Settings


def test_settings_has_twilio_whatsapp_config():
    """Verify that Settings() exposes Twilio WhatsApp configuration attributes."""
    s = Settings()
    assert hasattr(s, "twilio_account_sid")
    assert hasattr(s, "twilio_auth_token")
    assert hasattr(s, "twilio_whatsapp_number")


def test_settings_twilio_whatsapp_defaults_to_empty_strings():
    """Verify that Twilio settings default to empty strings when env vars not set."""
    original_sid = os.environ.pop("TWILIO_ACCOUNT_SID", None)
    original_token = os.environ.pop("TWILIO_AUTH_TOKEN", None)
    original_number = os.environ.pop("TWILIO_WHATSAPP_NUMBER", None)

    try:
        s = Settings()
        assert s.twilio_account_sid == ""
        assert s.twilio_auth_token == ""
        assert s.twilio_whatsapp_number == ""
    finally:
        if original_sid is not None:
            os.environ["TWILIO_ACCOUNT_SID"] = original_sid
        if original_token is not None:
            os.environ["TWILIO_AUTH_TOKEN"] = original_token
        if original_number is not None:
            os.environ["TWILIO_WHATSAPP_NUMBER"] = original_number


def test_settings_twilio_whatsapp_reads_from_env():
    """Verify that Twilio settings read from environment variables."""
    os.environ["TWILIO_ACCOUNT_SID"] = "test_sid"
    os.environ["TWILIO_AUTH_TOKEN"] = "test_token"
    os.environ["TWILIO_WHATSAPP_NUMBER"] = "whatsapp:+14155238886"

    try:
        s = Settings()
        assert s.twilio_account_sid == "test_sid"
        assert s.twilio_auth_token == "test_token"
        assert s.twilio_whatsapp_number == "whatsapp:+14155238886"
    finally:
        os.environ.pop("TWILIO_ACCOUNT_SID", None)
        os.environ.pop("TWILIO_AUTH_TOKEN", None)
        os.environ.pop("TWILIO_WHATSAPP_NUMBER", None)
