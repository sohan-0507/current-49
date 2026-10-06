# ResearchX — Hackathon Bossmode Final

FastAPI + HTML/CSS/JavaScript prototype for the Collaborative Research Ecosystem.

Run with `python -m pip install -r requirements.txt` and `python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000`, then open `http://127.0.0.1:8000/`. Do not use VS Code Live Server.

Demo accounts: Student `maya@researchx.demo` / `student123` (age 20); Sponsor `sponsor@researchx.demo` / `sponsor123`; Mentor `mentor@researchx.demo` / `mentor123`; Admin `admin@researchx.demo` / `admin123`.

Bossmode additions:
- Project Charter: engagement model, rewards/payment terms, scope/deliverables, roles/eligibility/time, IP/publication, confidentiality/approved AI tools, credit/reward split, exit/disputes, future-commercialisation clause.
- Funded and Stipend / honorarium projects require participants to be 18+; enforced server-side.
- Knowledge-sharing and Institutional credit projects are explicitly non-monetary; joining requires a separate no-payment acknowledgement.
- Editing creates a new charter version; existing participants become `Reaccept required` and can re-accept or leave with accepted contribution credit preserved.
- Charter changes, re-acceptance and leaving are recorded in the hash-chained ledger.
- Admin project management, sponsor marketplace, applications and notifications remain connected.

The participant handout requires a project charter to be visible before applying, explicit acknowledgement of the engagement model, no implied payment on non-monetary projects, versioned terms, and fair credit. The listed corner cases include midway exit, sponsor silence, failed research, AI-heavy work, unfair rejection, contribution gaming, expected pay on unpaid projects, paid-to-unpaid changes, later commercialization, and under-18 paid work.

No real money or real personal data is used; payments are simulated for the hackathon PoC.
