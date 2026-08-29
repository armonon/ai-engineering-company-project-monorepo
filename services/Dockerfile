FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY packages/incident_analyzer packages/incident_analyzer
COPY packages/shared packages/shared
COPY scripts/seed_incidents.py scripts/incidents-trackflow.csv scripts/
COPY services/requirements.txt services/requirements.txt
COPY services/api services/api

WORKDIR /workspace/services
RUN uv pip install --system -r requirements.txt

WORKDIR /workspace/services/api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
