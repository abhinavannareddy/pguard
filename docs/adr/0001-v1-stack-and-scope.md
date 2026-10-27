# ADR 0001: v1 stack and scope

Status: accepted (2026-10-27)

## Decision

- Hardware: one Windows laptop plus the home router (PRD Foundation section, which the PRD
  says wins any conflict). Radar nodes are out of scope.
- Backend: Python 3.12+, FastAPI, SQLAlchemy (added with the API phase). PostgreSQL in Docker Compose; tests use SQLite.
- Frontend: Next.js, TypeScript, Tailwind, TanStack Query.
- Signal processing: Python reference implementation first (standard library). A C++20 port of the hot
  path is added only if profiling on this laptop shows a need, and must match the Python
  output in a parity test.
- Alert channels: email (baseline) and Telegram or ntfy (fast channel). SMS is excluded as paid.
- Deferred, each needing its own ADR when justified: CSI/breathing, wellbeing layer,
  Go, Rust, mobile apps, Kubernetes, Terraform, CUDA.

## Why

The PRD requires a deliberately small stack with a written reason for each addition, and the
available adapter (MediaTek MT7922) supports Tier 1 only.
