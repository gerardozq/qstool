create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  status text not null default 'queued',
  mode text not null default 'full',
  tile_rows integer not null default 10,
  tile_cols integer not null default 10,
  symbols jsonb default '[]'::jsonb,
  input_path text,
  overlay_path text,
  error_message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create table if not exists symbols (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  label text not null,
  count integer not null default 0
);

create table if not exists detections (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  label text not null,
  confidence numeric,
  bbox jsonb not null,
  page_index integer not null default 0
);

create index if not exists jobs_status_idx on jobs(status, created_at);
create index if not exists symbols_job_idx on symbols(job_id);
create index if not exists detections_job_idx on detections(job_id);

alter table jobs disable row level security;
alter table symbols disable row level security;
alter table detections disable row level security;
