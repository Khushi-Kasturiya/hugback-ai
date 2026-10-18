# HugBack AI

HugBack AI is organized as a monorepo for submission and review.

## Repository structure

- `frontend/` — Next.js frontend
- `backend/` — FastAPI backend

Each application keeps its own README, dependencies, tests, Dockerfile, and
environment examples. Run application commands from the corresponding
subdirectory.

## Deployment safety

This submission repository is independent from the two repositories currently
connected to the deployed services. Creating or updating this repository does
not redeploy either service.

If deployments are migrated to this monorepo later, configure the frontend and
backend as separate services with `frontend/` and `backend/` as their respective
build contexts.

## Configuration

Use the checked-in example environment files as references. Do not commit local
environment files, service-account credentials, tokens, or other secrets.

