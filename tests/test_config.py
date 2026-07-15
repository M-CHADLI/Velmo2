"""Tests for velmo config module."""

def test_settings_has_twilio_config():
    """Verify that Settings() exposes Twilio configuration attributes."""
    from velmo.config import Settings

    s = Settings()
    assert hasattr(s, "twilio_account_sid")
    assert hasattr(s, "twilio_auth_token")
    assert hasattr(s, "twilio_phone_number")


def test_settings_twilio_defaults_to_empty_strings():
    """Verify that Twilio settings default to empty strings when env vars not set."""
    import os
    from velmo.config import Settings

    # Ensure env vars are not set
    original_sid = os.environ.pop("TWILIO_ACCOUNT_SID", None)
    original_token = os.environ.pop("TWILIO_AUTH_TOKEN", None)
    original_phone = os.environ.pop("TWILIO_PHONE_NUMBER", None)

    try:
        s = Settings()
        assert s.twilio_account_sid == ""
        assert s.twilio_auth_token == ""
        assert s.twilio_phone_number == ""
    finally:
        # Restore env vars
        if original_sid is not None:
            os.environ["TWILIO_ACCOUNT_SID"] = original_sid
        if original_token is not None:
            os.environ["TWILIO_AUTH_TOKEN"] = original_token
        if original_phone is not None:
            os.environ["TWILIO_PHONE_NUMBER"] = original_phone


def test_settings_twilio_reads_from_env():
    """Verify that Twilio settings read from environment variables."""
    import os
    from velmo.config import Settings

    os.environ["TWILIO_ACCOUNT_SID"] = "test_sid"
    os.environ["TWILIO_AUTH_TOKEN"] = "test_token"
    os.environ["TWILIO_PHONE_NUMBER"] = "+33123456789"

    try:
        s = Settings()
        assert s.twilio_account_sid == "test_sid"
        assert s.twilio_auth_token == "test_token"
        assert s.twilio_phone_number == "+33123456789"
    finally:
        # Clean up
        os.environ.pop("TWILIO_ACCOUNT_SID", None)
        os.environ.pop("TWILIO_AUTH_TOKEN", None)
        os.environ.pop("TWILIO_PHONE_NUMBER", None)
