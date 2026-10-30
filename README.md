# NexaHR
AI-powered OpenSource HR Copilot using Agentic RAG and custom ML for intelligent HR policy assistance, employee support, verified citations, and workflow automation.

## Groq model configuration

Set `GROQ_API_KEY` in `.env`. NexaHR uses `openai/gpt-oss-120b` by default; set
`GROQ_MODEL` to another model ID available to your Groq API key if needed.

## Streamlit frontend

The modular Streamlit frontend is in `frontend/` (`auth.py`, `api.py`, `ui.py`,
`config.py`, and `styles.css`) and uses the existing FastAPI backend. Configure
separate admin and employee sign-ins in the project `.env`:

```env
NEXAHR_ADMIN_USERNAME=admin
NEXAHR_ADMIN_PASSWORD=replace-with-a-strong-password
NEXAHR_EMPLOYEE_USERNAME=employee
NEXAHR_EMPLOYEE_PASSWORD=replace-with-a-strong-password
ADMIN_API_KEY=replace-with-a-strong-admin-api-key
API_BASE_URL=http://127.0.0.1:8888
```

Install dependencies with `pip install -r requirements.txt`. In one terminal, start
the backend with `run.bat`. In a second terminal at the project root, run:

```powershell
python -m streamlit run frontend\streamlit_app.py
```

Open the Streamlit URL printed in the terminal. Admin and employee sign-ins share
the policy chat; only the admin workspace shows document ingestion. The chat
streams LangGraph progress to the workflow and trace panel. The existing
non-streaming `/api/chat` endpoint remains available to other clients.

These environment-configured credentials are a basic frontend sign-in for
development and a deployment prototype, not a complete organization identity
system. The FastAPI endpoints are not yet protected by user sessions or role-based
authorization; protect the API and use an organization identity provider before
exposing the app to a network.

### Employee leave-balance demo

The employee frontend includes a local sample record in
`frontend/data/employee_leave_balances.json`: the sample employee is Alex Morgan
(`emp1`, job ID `EMP-001`), a People Operations Associate. They have 20 annual
leave days, have used 8, and have 12 remaining. In development, choose Employee
and sign in with username `emp1` and password `emp1-demo`. This demo login remains
available even if employee credentials are also configured in `.env`. Ask “How many leaves
do I have left?” or “How many days can I apply for?”. Edit the JSON file to change
the sample profile or balance. This development login and the profile are for
demonstration only and are disabled as a fallback when `APP_ENV=production`.
Leave data is frontend-only demonstration data, not an authoritative HR system;
a signed-in employee only sees the record matching their username.
