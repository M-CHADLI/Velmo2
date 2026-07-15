import pytest
from langchain_core.messages import AIMessage
from velmo.agent.agent import VelmoAgent, MAX_TOOL_ITERS, FALLBACK_MESSAGE


class StubToolLLM:
    """LLM factice : 1er invoke -> tool_call, 2e invoke -> réponse finale."""
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        msg = self.scripted[min(self.calls, len(self.scripted) - 1)]
        self.calls += 1
        return msg


def _agent_with(stub):
    # évite toute construction réseau/DB : on n'appelle que _generate_with_tools
    agent = VelmoAgent.__new__(VelmoAgent)
    agent.llm = stub
    return agent


def test_tool_loop_executes_tool_then_returns_final(monkeypatch):
    import velmo.business.tools as bt
    # exécuter le vrai outil lookup_order avec le repository mocké
    monkeypatch.setattr(bt.repo, "get_order_by_number",
                        lambda n, db=None: {"order_number": n, "status": "expédiée",
                                            "total_eur": 10.0, "placed_at": "x",
                                            "items": [], "shipment": None})
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "lookup_order",
                                           "args": {"order_number": "CMD-4490"},
                                           "id": "call_1"}]),
        AIMessage(content="Votre commande CMD-4490 est expédiée."),
    ]
    agent = _agent_with(StubToolLLM(scripted))
    from langchain_core.messages import SystemMessage, HumanMessage
    msgs = [SystemMessage(content="sys"), HumanMessage(content="où est CMD-4490 ?")]
    out = agent._generate_with_tools(msgs)
    assert out == "Votre commande CMD-4490 est expédiée."


def test_tool_loop_is_bounded():
    # LLM qui demande TOUJOURS un outil -> doit s'arrêter à MAX_TOOL_ITERS
    always_tool = AIMessage(content="partiel",
                            tool_calls=[{"name": "lookup_order",
                                         "args": {"order_number": "CMD-1"},
                                         "id": "c"}])
    import velmo.business.tools as bt
    bt_repo_backup = bt.repo.get_order_by_number
    try:
        bt.repo.get_order_by_number = lambda n, db=None: None
        agent = _agent_with(StubToolLLM([always_tool]))
        from langchain_core.messages import HumanMessage
        out = agent._generate_with_tools([HumanMessage(content="x")])
        assert agent.llm.calls <= MAX_TOOL_ITERS
        assert out == "partiel"
    finally:
        bt.repo.get_order_by_number = bt_repo_backup


def test_generate_with_tools_falls_back_without_bind_tools():
    class NoBindLLM:
        def bind_tools(self, tools):
            raise NotImplementedError("no tools")
        def invoke(self, messages, config=None):
            return AIMessage(content="réponse simple")
    agent = _agent_with(NoBindLLM())
    from langchain_core.messages import HumanMessage
    out = agent._generate_with_tools([HumanMessage(content="bonjour")])
    assert out == "réponse simple"


class AlwaysToolLLM:
    """LLM factice qui demande toujours un outil (content vide) -> épuise MAX_TOOL_ITERS."""
    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        self.calls += 1
        return AIMessage(content="", tool_calls=[{"name": "lookup_order",
                                                   "args": {"order_number": "CMD-1"},
                                                   "id": f"c{self.calls}"}])


class _StubResponse:
    def __init__(self, message):
        self.message = message


@pytest.fixture
def agent_with_looping_tool(monkeypatch):
    import velmo.business.tools as bt
    from langchain_core.messages import HumanMessage
    monkeypatch.setattr(bt.repo, "get_order_by_number", lambda n, db=None: None)
    agent = _agent_with(AlwaysToolLLM())

    def fake_process_message(self, user_id, message):
        content = self._generate_with_tools([HumanMessage(content=message)])
        return _StubResponse(content)

    monkeypatch.setattr(VelmoAgent, "process_message", fake_process_message)
    return agent


def test_tool_loop_exhaustion_returns_fallback_message(agent_with_looping_tool):
    """Si MAX_TOOL_ITERS est épuisé avec des tool_calls encore présents,
    la réponse ne doit jamais être vide."""
    response = agent_with_looping_tool.process_message("CLI-000001", "boucle")
    assert response.message == FALLBACK_MESSAGE
    assert response.message != ""
