# NexaHR
AI-powered OpenSource HR Copilot using Agentic RAG and custom ML for intelligent HR policy assistance, employee support, verified citations, and workflow automation.

## Groq model configuration

Set `GROQ_API_KEY` in `.env`. NexaHR uses `openai/gpt-oss-120b` by default; set
`GROQ_MODEL` to another model ID available to your Groq API key if needed.

## Streamlit frontend

The Streamlit admin frontend is in `frontend/streamlit_app.py` and uses the existing
FastAPI backend. Add these values to the project `.env` file:

```env
NEXAHR_ADMIN_USERNAME=admin
NEXAHR_ADMIN_PASSWORD=replace-with-a-strong-password
ADMIN_API_KEY=replace-with-a-strong-admin-api-key
API_BASE_URL=http://127.0.0.1:8000
```

Install dependencies with `pip install -r requirements.txt`. In one terminal, start
the backend with `run.bat`. In a second terminal at the project root, run:

```powershell
python -m streamlit run frontend\streamlit_app.py
```

Open the Streamlit URL printed in the terminal. The initial frontend provides an
admin sign-in, policy chat, and document upload. Employee accounts and permissions
are not implemented yet. This initial sign-in gates the Streamlit UI only; protect
the API with proper user authentication and role authorization before deploying
outside a trusted development environment.
