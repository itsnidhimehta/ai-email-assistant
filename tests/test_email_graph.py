"""
Tests use a FAKE LLM, so they run without an API key, cost nothing, and give the same result every time.
Run with:  pytest
"""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.types import Command

from email_graph import MAX_REWRITES, build_graph

CONFIG = {"configurable": {"thread_id": "test"}}


def make_graph(responses):
    return build_graph(FakeListChatModel(responses=responses))


def test_graph_pauses_with_a_draft():
    graph = make_graph(["Subject: Leave\n\nDraft one"])
    result = graph.invoke({"query": "leave email"}, CONFIG)

    assert result["__interrupt__"][0].value["draft_email"] == "Subject: Leave\n\nDraft one"


def test_approve_finalizes_the_current_draft():
    graph = make_graph(["Draft one"])
    graph.invoke({"query": "leave email"}, CONFIG)
    result = graph.invoke(Command(resume="approved"), CONFIG)

    assert result["final_response"] == "Draft one"
    assert "__interrupt__" not in result


def test_feedback_triggers_a_rewrite():
    graph = make_graph(["Draft one", "Draft two"])
    graph.invoke({"query": "leave email"}, CONFIG)
    result = graph.invoke(Command(resume="make it shorter"), CONFIG)

    assert result["__interrupt__"][0].value["draft_email"] == "Draft two"
    assert result["rewrites"] == 1


def test_rewrites_are_capped():
    graph = make_graph([f"Draft {i}" for i in range(MAX_REWRITES + 1)])
    graph.invoke({"query": "leave email"}, CONFIG)
    for _ in range(MAX_REWRITES):
        result = graph.invoke(Command(resume="change it"), CONFIG)

    # Even more feedback after the limit finalises instead of rewriting again.
    result = graph.invoke(Command(resume="change it again"), CONFIG)
    assert result["final_response"] == f"Draft {MAX_REWRITES}"
