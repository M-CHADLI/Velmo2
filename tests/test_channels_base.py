import pytest
from velmo.channels.base import Channel


def test_channel_is_abstract():
    with pytest.raises(TypeError):
        Channel()


def test_channel_subclass_must_implement_both_methods():
    class Incomplete(Channel):
        def receive_message(self, user_id, text):
            return "x"
        # send_message manquant

    with pytest.raises(TypeError):
        Incomplete()
