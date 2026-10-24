# Deprecated: `backend/` (legacy monolith)

The FastAPI monolith in this folder predates the microservices in `services/` and is **not used**:

- No compose file builds or runs it, `scripts/deploy/deploy.sh` does not deploy it, and no app,
  dashboard or service calls it.
- It has been removed from CI (`.github/workflows/backend-ci.yml`: the test matrix, ruff and bandit).

The code is kept for reference only. Everything it did lives in a service under `services/`;
make changes there.
