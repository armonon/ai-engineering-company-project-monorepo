FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY packages/incident_analyzer packages/incident_analyzer
COPY packages/shared packages/shared
COPY data/process data/process
COPY data/pipelines data/pipelines
COPY docs/telemetry/event-schemas.json docs/telemetry/event-schemas.json
COPY docs/company-knowledge-base docs/company-knowledge-base
COPY scripts/seed_incidents.py scripts/incidents-trackflow.csv scripts/
COPY services/requirements.txt services/requirements.txt
COPY services/api services/api
COPY services/telemetry services/telemetry
COPY services/reporting services/reporting
COPY services/job_runner services/job_runner

WORKDIR /workspace/services
RUN uv pip install --system -r requirements.txt

WORKDIR /workspace/services/api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
