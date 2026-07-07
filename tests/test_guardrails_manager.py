from unittest.mock import MagicMock, patch
from guardrails.manager import GuardrailManager


def _manager_with_category(category):
    clf = MagicMock()
    clf.classify.return_value = category
    return GuardrailManager(classifier=clf)


@patch("guardrails.manager.write_log")
def test_manager_check_input_logs_and_returns(mock_log):
    mgr = _manager_with_category("hate")
    d = mgr.check_input("Sale race.", "u-1")
    assert d.allowed is False
    assert d.category == "hate"
    mock_log.assert_called_once()
    assert mock_log.call_args.args[0] == "u-1"


@patch("guardrails.manager.write_log")
def test_manager_check_output_blocks_pii(mock_log):
    mgr = _manager_with_category("legitimate")
    d = mgr.check_output("Carte 4111 1111 1111 1111.", "u-1")
    assert d.allowed is False
    assert d.category == "pii"
    mock_log.assert_called_once()
