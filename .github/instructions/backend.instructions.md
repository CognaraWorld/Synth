---
applyTo: "backend/**/*.py"
---

# Backend Instructions

- This backend uses Python, FastAPI, SQLAlchemy, and Pydantic-based configuration.
- Keep route handlers thin. Business logic should live in the appropriate `core`, `context`, `meeting`, `models`, or `utils` module.
- Keep environment and settings access centralized in `backend/app/config.py` or an equivalent settings layer.
- Prefer typed, explicit interfaces and small focused functions over ad hoc dictionaries and hidden side effects.
- Public functions and classes should stay readable and documented when behavior is non-obvious.
- Be careful with async boundaries. Do not introduce blocking work inside async request paths without justification.
- For AI or external-service integrations, keep wrappers testable and isolate network-dependent behavior where possible.
- If behavior changes, add or update `pytest` coverage in `backend/tests` where it adds confidence.
- For review comments, prioritize correctness, reliability, async safety, schema drift, and missing tests.
