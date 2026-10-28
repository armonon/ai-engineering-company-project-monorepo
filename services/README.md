# `services` folder

This folder contains **all the backend services** (APIs and background workers) related to the company for the cross-functional AI Engineering project.

Each subfolder inside `services/` must correspond to **one specific service** (for example: `admin-api`, `data-processor-worker`) and include its own technical and functional documentation.

`job_runner/` is the persistence boundary for the independent nightly
telemetry export. It owns `job_runs` lifecycle/lock operations and is consumed
by `scripts/nightly_export.py`, never by FastAPI's request thread.

The Celery worker is another independent process. Redis is its broker and
result backend, while `api/task_queue_storage.py` owns the durable dead-letter
table. Start Redis, the API, worker, and Flower together from the repository
root with `docker compose up --build`. Stop them with `docker compose down`.
Flower is available at <http://localhost:5555>.

- **Main purpose**: to centralize all the backend logic, APIs, and queue consumers that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the services you add, their objective, the technology used, and how to run them.

> _Spanish version: [README.es.md](./README.es.md)._
