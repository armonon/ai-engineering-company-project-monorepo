-- Ticket DEV-53 — lifecycle and status-based lock for the nightly export.

create extension if not exists pgcrypto;

create table if not exists public.job_runs (
    id uuid primary key default gen_random_uuid(),
    job_name varchar(80) not null,
    target_date date not null,
    status varchar(16) not null
        check (status in ('pending', 'processing', 'completed', 'failed')),
    started_at timestamptz null,
    finished_at timestamptz null,
    error_message text null,
    created_at timestamptz not null default now(),
    constraint uq_job_runs_job_target_date unique (job_name, target_date)
);

create index if not exists ix_job_runs_job_target_date
    on public.job_runs (job_name, target_date);

-- The processing state itself is the distributed lock. This index prevents
-- two dates for the same job from being processed concurrently without adding
-- a second lock table or flag.
create unique index if not exists uq_job_runs_one_processing_job
    on public.job_runs (job_name)
    where status = 'processing';
