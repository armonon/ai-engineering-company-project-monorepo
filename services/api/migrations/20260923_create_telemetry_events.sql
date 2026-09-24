-- Company's Telemetry – Storage
-- Idempotent Supabase/PostgreSQL schema matching models.TelemetryEventRecord.

create extension if not exists pgcrypto;

create table if not exists public.telemetry_events (
    id uuid primary key default gen_random_uuid(),
    timestamp timestamptz not null,
    service text not null check (service in ('backoffice', 'api')),
    event_type text not null,
    level text not null default 'info' check (level in ('info', 'warn', 'error')),
    value numeric null,
    message text null,
    tags jsonb not null default '{}'::jsonb
);

create index if not exists ix_telemetry_events_timestamp
    on public.telemetry_events (timestamp);

create index if not exists ix_telemetry_events_event_type
    on public.telemetry_events (event_type);

create index if not exists ix_telemetry_events_tags_gin
    on public.telemetry_events using gin (tags);

-- Telemetry is append-only. The FastAPI service connects through PostgreSQL,
-- while Supabase client roles have no mutation path for historical facts.
revoke update, delete, truncate on table public.telemetry_events
    from anon, authenticated;
