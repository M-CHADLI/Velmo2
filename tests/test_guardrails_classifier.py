import pytest
from unittest.mock import MagicMock
from guardrails.classifier import KimiClassifier


def _make_classifier_with_mock(return_content=None, raise_exc=None):
    clf = KimiClassifier.__new__(KimiClassifier)  # bypass __init__ (pas de réseau)
    fake_chain = MagicMock()
    if raise_exc is not None:
        fake_chain.invoke.side_effect = raise_exc
    else:
        fake_resp = MagicMock()
        fake_resp.content = return_content
        fake_chain.invoke.return_value = fake_resp
    clf._chain = fake_chain
    return clf


def test_classify_returns_category():
    clf = _make_classifier_with_mock(return_content="hate")
    assert clf.classify("Sale race, retournez dans votre pays.") == "hate"


def test_classify_normalizes_unknown_to_legitimate():
    clf = _make_classifier_with_mock(return_content="banana")
    assert clf.classify("Bonjour") == "legitimate"


def test_classify_retries_then_raises():
    clf = _make_classifier_with_mock(raise_exc=RuntimeError("api down"))
    with pytest.raises(RuntimeError):
        clf.classify("test")
    assert clf._chain.invoke.call_count == 2
