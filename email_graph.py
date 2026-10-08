"""
The "brain" of the app: a LangGraph workflow that drafts an email,
pauses for human feedback, and either rewrites or finalises.

    START -> draft -> human_feedback --(feedback given)--> draft
                                     --(approved)-------> finalize -> END

This file has NO Streamlit code, so it can be tested on its own.
"""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

APPROVE_WORDS = {"approved", "approve", "ok", "okay", "yes"}
MAX_REWRITES = 5  # stops endless loops (and protects API credits)

SYSTEM_PROMPT = (
    "You are an assistant that writes clear, professional emails. "
    "Return ONLY the email: a 'Subject:' line, then the body. "
    "No markdown, no explanations before or after."
)


class MailState(BaseModel):
    query: str = ""            # what the user wants the email to say
    draft: str = ""            # latest draft from the LLM
    human_feedback: str = ""   # empty string means "approved"
    rewrites: int = 0          # how many times we have rewritten
    final_response: str = ""   # the approved email


def build_graph(llm: BaseChatModel):
    """Build and compile the graph. The LLM is passed in, so tests can use a fake one."""

    def draft_email(state: MailState) -> dict:
        if state.human_feedback:
            user_msg = (
                f"Original request: {state.query}\n\n"
                f"Previous draft:\n{state.draft}\n\n"
                f"Rewrite the draft applying this feedback: {state.human_feedback}"
            )
            rewrites = state.rewrites + 1
        else:
            user_msg = state.query
            rewrites = state.rewrites

        response = llm.invoke([("system", SYSTEM_PROMPT), ("user", user_msg)])
        # Nodes return only the fields they change; LangGraph merges them into the state.
        return {"draft": response.content.strip(), "rewrites": rewrites}

    def human_feedback(state: MailState) -> dict:
        # interrupt() pauses the graph here and hands the draft to the UI.
        # When the UI resumes with Command(resume=...), that value is returned here.
        feedback = interrupt({"draft_email": state.draft})
        feedback = (feedback or "").strip()

        if feedback.lower() in APPROVE_WORDS or state.rewrites >= MAX_REWRITES:
            return {"human_feedback": ""}
        return {"human_feedback": feedback}

    def finalize(state: MailState) -> dict:
        return {"final_response": state.draft}

    def route_after_feedback(state: MailState) -> Literal["draft", "finalize"]:
        return "draft" if state.human_feedback else "finalize"

    builder = StateGraph(MailState)
    builder.add_node("draft", draft_email)
    builder.add_node("human_feedback", human_feedback)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "draft")
    builder.add_edge("draft", "human_feedback")
    builder.add_conditional_edges("human_feedback", route_after_feedback)
    builder.add_edge("finalize", END)

    # The checkpointer remembers where each conversation (thread_id) paused.
    return builder.compile(checkpointer=InMemorySaver())
