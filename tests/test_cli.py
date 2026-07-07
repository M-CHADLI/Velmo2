"""Test CLI imports without error."""


def test_cli_imports():
    """CLI imports without error."""
    from velmo_cli import cli
    assert cli is not None
