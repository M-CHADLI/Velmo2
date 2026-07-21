"""Tests du droit à l'oubli (R5) — matching de la demande + suppression réelle.

Deux niveaux :
- Unitaires (long_term mocké) : vérifient que la demande d'oubli cible le bon fait,
  y compris quand le Judge a rangé la valeur sous une clé inattendue (ex. 'identifier').
- Intégration (vraie DB) : vérifient que le fait est réellement soft-deleted,
  absent de la recherche, et tracé dans l'audit.
"""
import uuid

import pytest
from unittest.mock import MagicMock

from velmo.memory.manager import VelmoMemoryManager


# --------------------------------------------------------------------------- #
# Unitaires : logique de correspondance (aucune DB)                            #
# --------------------------------------------------------------------------- #

def _manager_with_facts(facts):
    """Construit un manager sans __init__ (pas de DB), avec un long_term mocké."""
    mgr = object.__new__(VelmoMemoryManager)
    mgr.long_term = MagicMock()
    mgr.long_term.inspect_memory.return_value = facts
    mgr.long_term.delete_fact_gdpr.return_value = True
    return mgr


def _fact(fact_id, key, value, ftype="user_fact", context=None):
    return {"fact_id": fact_id, "key": key, "value": value, "type": ftype, "context": context}


def test_forget_matches_order_stored_under_identifier_key():
    """Le cas critique : '4490' rangé sous la clé 'identifier' (pas 'order_id').
    La demande 'oublie mon numéro de commande' doit quand même le supprimer,
    grâce au contexte d'origine du fait.
    """
    mgr = _manager_with_facts([
        _fact("f1", "identifier", "4490", "identifier",
              context="Mon numéro de commande est 4490."),
    ])

    deleted = mgr.check_and_handle_forget_request("u-1", "En fait, oublie mon numéro de commande.")

    assert deleted is True
    mgr.long_term.delete_fact_gdpr.assert_called_once()
    assert mgr.long_term.delete_fact_gdpr.call_args.kwargs["fact_id"] == "f1"


def test_forget_matches_value_present_in_message():
    """'oublie le 4490' → correspondance directe par la valeur."""
    mgr = _manager_with_facts([
        _fact("f1", "identifier", "4490", "identifier", context=None),
    ])

    deleted = mgr.check_and_handle_forget_request("u-1", "oublie le 4490 stp")

    assert deleted is True
    assert mgr.long_term.delete_fact_gdpr.call_args.kwargs["fact_id"] == "f1"


def test_forget_only_deletes_the_targeted_category():
    """Une commande et un contrat coexistent. 'oublie ma commande' ne doit
    supprimer QUE la commande, pas le contrat.
    """
    mgr = _manager_with_facts([
        _fact("order", "identifier", "4490", "identifier",
              context="Mon numéro de commande est 4490."),
        _fact("contract", "contract_id", "CT-7788", "identifier",
              context="Mon numéro de contrat est CT-7788."),
    ])

    deleted = mgr.check_and_handle_forget_request("u-1", "oublie mon numéro de commande")

    assert deleted is True
    mgr.long_term.delete_fact_gdpr.assert_called_once()
    assert mgr.long_term.delete_fact_gdpr.call_args.kwargs["fact_id"] == "order"


def test_forget_matches_address_by_key():
    """'oublie mon adresse' → correspondance par la clé (address_zip)."""
    mgr = _manager_with_facts([
        _fact("f1", "address_zip", "69003", "user_fact",
              context="Mon adresse est 12 rue des Lilas, 69003."),
    ])

    deleted = mgr.check_and_handle_forget_request("u-1", "oublie mon adresse s'il te plaît")

    assert deleted is True
    assert mgr.long_term.delete_fact_gdpr.call_args.kwargs["fact_id"] == "f1"


def test_non_forget_message_deletes_nothing():
    """Une question ('quel est mon numéro de commande ?') ne déclenche aucun oubli."""
    mgr = _manager_with_facts([
        _fact("f1", "identifier", "4490", "identifier",
              context="Mon numéro de commande est 4490."),
    ])

    deleted = mgr.check_and_handle_forget_request("u-1", "Quel est mon numéro de commande ?")

    assert deleted is False
    mgr.long_term.delete_fact_gdpr.assert_not_called()


# --------------------------------------------------------------------------- #
# Intégration : suppression réelle en base                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def db_schema():
    """S'assure que le schéma existe (Postgres de CI/dev)."""
    from velmo.memory import get_db
    get_db().init_db()


def test_forget_soft_deletes_fact_end_to_end(db_schema):
    """Store un fait, déclenche l'oubli, vérifie qu'il est soft-deleted,
    absent de la recherche, et tracé dans l'audit.
    """
    from velmo.memory.schema import FactData

    mgr = VelmoMemoryManager()
    uid = f"u-forget-{uuid.uuid4().hex[:8]}"

    mgr.long_term.store_fact(
        user_id=uid,
        conversation_id="conv-forget",
        fact_data=FactData(
            key="identifier", value="4490", type="identifier",
            context="Mon numéro de commande est 4490.",
        ),
    )
    # Sanity : le fait est bien présent
    assert any(f["value"] == "4490" for f in mgr.long_term.inspect_memory(uid))

    # Demande d'oubli
    deleted = mgr.check_and_handle_forget_request(uid, "En fait, oublie mon numéro de commande.")
    assert deleted is True

    # Absent de la mémoire active
    assert all(f["value"] != "4490" for f in mgr.long_term.inspect_memory(uid))
    # Absent de la recherche
    assert all(f["value"] != "4490" for f in mgr.long_term.retrieve_context(uid, "numéro de commande"))
    # Tracé dans l'audit (vérifiable)
    actions = [a["action"] for a in mgr.long_term.get_audit_trail(uid)]
    assert "fact_soft_delete" in actions
