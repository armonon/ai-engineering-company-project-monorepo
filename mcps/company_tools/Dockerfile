FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv==0.9.26

COPY mcps/company_tools/pyproject.toml mcps/company_tools/uv.lock ./
COPY mcps/company_tools/company_tools_mcp ./company_tools_mcp

RUN uv sync --frozen --no-dev

RUN addgroup --system trackflow \
    && adduser --system --ingroup trackflow --home /home/trackflow trackflow \
    && mkdir -p /app/data \
    && chown -R trackflow:trackflow /app

USER trackflow

EXPOSE 8010

CMD ["uv", "run", "uvicorn", "company_tools_mcp.server_app:app", "--host", "0.0.0.0", "--port", "8010"]
