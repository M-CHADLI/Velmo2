# tests/test_agent_e2e_memory.py
import json
from unittest.mock import MagicMock
from velmo.agent.agent import VelmoAgent

def load_memory_cases(path="eval/memory_cases.jsonl"):
    """Load memory test cases."""
    cases = []
    with open(path) as f:
        for line in f:
            cases.append(json.loads(line))
    return cases

def test_memory_recall_r1():
    """Test recall: agent remembers contract ID after first message."""
    classifier = MagicMock()
    classifier.classify.return_value = "legitimate"

    llm = MagicMock()
    bound = MagicMock()
    bound.invoke.side_effect = [
        MagicMock(content="Bonjour, c'est noté : contrat CT-7788.", tool_calls=None),
        MagicMock(content="La commande 4490 est en préparation.", tool_calls=None),
        MagicMock(content="La livraison est gratuite dès 50 euros.", tool_calls=None)
    ]
    llm.bind_tools.return_value = bound

    agent = VelmoAgent(classifier=classifier, llm=llm)

    # Play through turns
    r1 = agent.process_message("u-101", "Bonjour, mon numero de contrat est CT-7788.")
    r2 = agent.process_message("u-101", "Je voudrais suivre ma commande 4490.")
    r3 = agent.process_message("u-101", "Et les frais de port ?")

    # Check turn numbers
    assert r1.turn_number == 1
    assert r2.turn_number == 2
    assert r3.turn_number == 3

    # Verify memory context includes previous messages
    assert len(r2.memory_context.get("short_term", [])) >= 1
    assert len(r3.memory_context.get("short_term", [])) >= 2

def test_memory_isolation():
    """Test isolation: two users don't see each other's data."""
    classifier = MagicMock()
    classifier.classify.return_value = "legitimate"

    llm = MagicMock()
    bound = MagicMock()
    bound.invoke.side_effect = [
        MagicMock(content="Noté : SEC-AAA-111.", tool_calls=None),
        MagicMock(content="Noté : SEC-BBB-222.", tool_calls=None)
    ]
    llm.bind_tools.return_value = bound

    agent = VelmoAgent(classifier=classifier, llm=llm)

    # User A
    r_a = agent.process_message("u-301", "Mon numero secret est SEC-AAA-111.")

    # User B
    r_b = agent.process_message("u-302", "Mon numero secret est SEC-BBB-222.")

    # Memory contexts should be different
    assert r_a.memory_context != r_b.memory_context

def test_memory_forget():
    """Test forget: l'agent supprime réellement le fait sur demande (R5).

    On stocke un fait directement (pour contrôler clé/valeur/contexte), puis on
    envoie la demande d'oubli via l'agent, et on vérifie que le fait a disparu de
    la mémoire active — pas seulement que le compteur de tours a bougé.
    """
    import uuid
    from velmo.memory import get_db
    from velmo.memory.schema import FactData

    get_db().init_db()  # schéma présent (Postgres de CI/dev)

    classifier = MagicMock()
    classifier.classify.return_value = "legitimate"

    llm = MagicMock()
    bound = MagicMock()
    bound.invoke.side_effect = [
        MagicMock(content="C'est supprimé de ma mémoire.", tool_calls=None)
    ]
    llm.bind_tools.return_value = bound

    agent = VelmoAgent(classifier=classifier, llm=llm)
    uid = f"u-forget-{uuid.uuid4().hex[:8]}"

    # Fait stocké : un numéro de commande rangé (comme le fait parfois le Judge)
    # sous la clé 'identifier', avec son contexte d'origine.
    agent.memory.long_term.store_fact(
        user_id=uid,
        conversation_id="conv-forget",
        fact_data=FactData(
            key="identifier", value="4490", type="identifier",
            context="Mon numero de commande est 4490.",
        ),
    )
    assert any(f["value"] == "4490" for f in agent.memory.long_term.inspect_memory(uid))

    # Demande d'oubli via l'agent (déclenche la suppression dans record_user_message)
    r = agent.process_message(uid, "En fait, oublie mon numero de commande.")
    assert r.turn_number == 1

    # Le fait a réellement disparu de la mémoire active
    remaining = [f["value"] for f in agent.memory.long_term.inspect_memory(uid)]
    assert "4490" not in remaining
