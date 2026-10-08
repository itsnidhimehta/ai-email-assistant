# ✉️ AI Email Assistant (LangGraph + Groq + Streamlit)

An AI assistant that drafts emails **with a human in the loop**: you describe the email, the AI writes a draft,
you give feedback ("make it shorter", "change the dates"), and it rewrites until you approve.

🔗 **Live demo:** _add your Streamlit link here_
📸 _Add a screenshot here_

## How it works

```
START → draft → human_feedback ──(feedback)──→ draft   (loop, max 5 rewrites)
                               └─(approved)──→ finalize → END
```

- **LangGraph `StateGraph`** holds the email state (request, draft, feedback, rewrite count).
- **`interrupt()`** pauses the graph so a human can review the draft.
- **`Command(resume=...)`** continues the graph with the human's feedback.
- **Checkpointer (`InMemorySaver`)** remembers where each user's conversation paused, using a unique `thread_id` per user.
- **Conditional edge** decides: feedback → rewrite, approval → finish.

## Project structure

```
email_graph.py         # LangGraph workflow (no UI code - easy to test)
app.py                 # Streamlit user interface
tests/                 # pytest tests using a fake LLM (no API key needed)
requirements.txt       # pinned library versions
.env.example           # which settings are needed (copy to .env)
```

## Production-ready touches

- API keys come from `.env` (local) or Streamlit Secrets (cloud), never from the code
- Friendly error message if the AI service fails; details go to server logs only
- Input length limit and a cap of 5 rewrites, to control cost
- Optional `APP_PASSWORD` so strangers can't use up API credits on the public link
- Logic separated from UI, with tests using a fake LLM
- Pinned dependency versions

## Run locally

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # then put your Groq key in .env
streamlit run app.py
```

Run the tests: `pytest`

## Deploy (Streamlit Community Cloud)

1. Push this folder to a public GitHub repo (check `.env` is NOT in it).
2. Go to share.streamlit.io → **Create app** → pick the repo, branch `main`, file `app.py`.
3. **Advanced settings → Secrets**, paste:
   ```
   GROQ_API_KEY = "your-key"
   APP_PASSWORD = "something-you-choose"
   ```
4. Deploy, then put the live link at the top of this README.

## Possible improvements

- Actually send the email via the Gmail API (with OAuth login)
- Store conversations in a database (e.g. Postgres) instead of memory
- Let users pick a tone (formal / friendly) before drafting
