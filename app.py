"""
Streamlit UI for the AI Email Assistant.
Run locally with:  streamlit run app.py
"""

import os
import urllib.parse
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from email_graph import MAX_REWRITES, build_graph

load_dotenv()  # reads .env on your laptop; on Streamlit Cloud, Secrets are used instead

MAX_INPUT_CHARS = 1000

st.set_page_config(page_title="AI Email Assistant", page_icon="✉️")
st.title("✉️ AI Email Assistant")
st.caption("Describe an email → review the draft → give feedback → approve. Built with LangGraph + Groq.")


# ---------- helpers ----------
def get_setting(name: str, default: str = "") -> str:
    """Read a setting from environment variables (.env locally) or Streamlit Secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, default)
    except Exception:  # no secrets file exists locally
        return default


def create_graph():
    from langchain_groq import ChatGroq

    api_key = get_setting("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY is missing. Add it to your .env file or Streamlit Secrets.")
        st.stop()
    llm = ChatGroq(
        model=get_setting("GROQ_MODEL", "openai/gpt-oss-20b"),
        api_key=api_key,
        temperature=0.3,
        max_retries=2,
    )
    return build_graph(llm)


def run_graph(graph_input):
    """Run the graph for this user's thread and store the result. Shows a friendly error on failure."""
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    try:
        with st.spinner("Writing..."):
            st.session_state.result = st.session_state.graph.invoke(graph_input, config=config)
    except Exception as e:
        st.error("Sorry, the AI service didn't respond. Please try again in a moment.")
        print(f"[ERROR] graph.invoke failed: {e!r}")  # shows in the server logs, not to the user


def start_over():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.result = None


# ---------- optional password gate (protects your API credits on a public link) ----------
app_password = get_setting("APP_PASSWORD")
if app_password and not st.session_state.get("unlocked"):
    entered = st.text_input("Password", type="password")
    if entered == app_password:
        st.session_state.unlocked = True
        st.rerun()
    elif entered:
        st.error("Wrong password")
    st.stop()


# ---------- per-user session state ----------
if "graph" not in st.session_state:
    st.session_state.graph = create_graph()
if "thread_id" not in st.session_state:
    start_over()

result = st.session_state.result


# ---------- Step 1: describe the email ----------
if result is None:
    with st.form("request"):
        query = st.text_area(
            "What should the email say?",
            placeholder="e.g. Ask my manager for leave from 4th to 7th June for a family function.",
            max_chars=MAX_INPUT_CHARS,
            height=120,
        )
        submitted = st.form_submit_button("Draft email", type="primary")
    if submitted:
        if not query.strip():
            st.warning("Please describe the email first.")
        else:
            run_graph({"query": query.strip()})
            st.rerun()


# ---------- Step 2: graph is paused, waiting for feedback ----------
elif result.get("__interrupt__"):
    draft = result["__interrupt__"][0].value["draft_email"]
    st.subheader("Draft")
    st.text_area("Draft", draft, height=280, disabled=True, label_visibility="collapsed")

    rewrites_left = MAX_REWRITES - result.get("rewrites", 0)
    st.caption(f"Rewrites left: {rewrites_left}")

    feedback = st.text_input(
        "Want changes?",
        placeholder="e.g. Make it shorter and more formal",
        max_chars=MAX_INPUT_CHARS,
    )
    col1, col2, col3 = st.columns(3)
    if col1.button("✅ Approve", type="primary"):
        run_graph(Command(resume="approved"))
        st.rerun()
    if col2.button("✏️ Rewrite", disabled=rewrites_left <= 0):
        if not feedback.strip():
            st.warning("Type what you'd like changed first.")
        else:
            run_graph(Command(resume=feedback.strip()))
            st.rerun()
    if col3.button("↺ Start over"):
        start_over()
        st.rerun()


# ---------- Step 3: approved ----------
else:
    final = result.get("final_response", "")
    st.success("Draft approved! Copy it, or open it in your email app.")
    st.code(final, language=None, wrap_lines=True)  # has a built-in copy button

    subject, body = "", final
    first_line, _, rest = final.partition("\n")
    if first_line.lower().startswith("subject:"):
        subject, body = first_line[len("subject:"):].strip(), rest.strip()
    mailto = "mailto:?" + urllib.parse.urlencode(
        {"subject": subject, "body": body}, quote_via=urllib.parse.quote
    )
    st.link_button("📧 Open in email app", mailto)

    if st.button("Write another email"):
        start_over()
        st.rerun()
