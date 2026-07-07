from guardrails.output_guard import check_output


def test_output_blocks_credit_card():
    d = check_output("Votre carte bancaire est le 4111 1111 1111 1111.")
    assert d.allowed is False
    assert d.category == "pii"
    assert d.where == "output"
    assert d.safe_message is not None


def test_output_allows_clean_response():
    d = check_output("Votre commande 4490 sera livree demain.")
    assert d.allowed is True
    assert d.category == "legitimate"
    assert d.safe_message is None
