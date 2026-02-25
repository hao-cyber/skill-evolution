-- Skill Evolution Registry — Supabase Setup
-- Run this in your Supabase SQL Editor to create the required tables.

-- Skills table
create table if not exists skills (
  id uuid primary key default gen_random_uuid(),
  name text not null check (name ~ '^[a-z0-9][a-z0-9\-]{0,62}$'),
  variant text not null default 'base' check (variant ~ '^[a-z0-9][a-z0-9\-]{0,62}$'),
  parent_id uuid references skills(id),
  description text not null check (length(description) <= 1000),
  tags text[] default '{}',
  author text not null,

  -- Skill content (stored directly, no external links)
  skill_md text not null,
  file_tree jsonb default '{}',

  -- Dependency declarations
  requires_env text[] default '{}',
  requires_tools text[] default '{}',
  requires_runtime text[] default '{}',
  depends_on text[] default '{}',

  -- Stats
  installs int default 0,
  forks int default 0,

  -- Audit: null = unaudited, timestamp = last passed audit
  audited_at timestamptz default null,

  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  unique(name, variant)
);

-- Full-text search index
alter table skills add column if not exists fts tsvector
  generated always as (
    to_tsvector('english', name || ' ' || description || ' ' || array_to_string(tags, ' '))
  ) stored;
create index if not exists skills_fts_idx on skills using gin(fts);

-- Publisher identity table (API key ↔ author binding)
create table if not exists publishers (
  api_key uuid primary key default gen_random_uuid(),
  author text not null unique,
  created_at timestamptz default now()
);

alter table publishers enable row level security;
-- No policies = anon key cannot read or write directly. Only via RPC.

-- RPC function: register a new publisher (auto-called on first publish)
-- Returns the api_key. If author already exists, raises error.
create or replace function register_publisher(p_author text)
returns jsonb
language plpgsql security definer as $$
declare
  v_key uuid;
begin
  if length(p_author) > 100 then
    raise exception 'author name too long';
  end if;
  if p_author !~ '^[a-z0-9][a-z0-9\-]{0,62}$' then
    raise exception 'invalid author name: must be lowercase alphanumeric + hyphens';
  end if;
  -- Check if already registered
  if exists (select 1 from publishers where author = p_author) then
    raise exception 'author "%" is already registered — use your existing PUBLISHER_KEY', p_author;
  end if;
  insert into publishers (author) values (p_author) returning api_key into v_key;
  return jsonb_build_object('api_key', v_key, 'author', p_author);
end;
$$;

-- RPC function: reset a publisher's API key (admin-only — requires service key)
-- Returns the new key. Old key is invalidated immediately.
create or replace function reset_publisher_key(p_author text)
returns jsonb
language plpgsql security definer as $$
declare
  v_new_key uuid := gen_random_uuid();
  v_role text;
begin
  -- Enforce service_role — anon callers cannot reset keys
  v_role := coalesce(
    current_setting('request.jwt.claims', true)::jsonb ->> 'role',
    current_setting('role', true)
  );
  if v_role is distinct from 'service_role' then
    raise exception 'admin-only: requires service_role key';
  end if;

  update publishers set api_key = v_new_key where author = p_author;
  if not found then
    raise exception 'publisher "%" not found', p_author;
  end if;
  return jsonb_build_object('api_key', v_new_key, 'author', p_author);
end;
$$;

-- Install tracking table (dedup: same skill only counted once per 10min)
create table if not exists install_log (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid references skills(id) on delete cascade,
  log_type text not null default 'install' check (log_type in ('install', 'fork')),
  installed_at timestamptz default now()
);
create index if not exists install_log_skill_time on install_log(skill_id, installed_at);

alter table install_log enable row level security;
-- No policies = anon key cannot read or write directly. Only via RPC.

-- RPC function: increment installs with dedup (security definer = runs as
-- table owner, so anon key can call it without needing INSERT/UPDATE policy)
create or replace function increment_installs(skill_id uuid)
returns void
language plpgsql security definer as $$
begin
  -- Skip if same skill was installed in the last 10 minutes
  if exists (
    select 1 from install_log
    where install_log.skill_id = increment_installs.skill_id
      and log_type = 'install'
      and installed_at > now() - interval '10 minutes'
  ) then
    return;
  end if;
  insert into install_log (skill_id, log_type) values (skill_id, 'install');
  update skills set installs = installs + 1 where id = skill_id;
end;
$$;

-- RPC function: increment forks (with dedup — same skill only counted once per 10min)
create or replace function increment_forks(skill_id uuid)
returns void
language plpgsql security definer as $$
begin
  -- Dedup: same skill only counted once per 10min
  if exists (
    select 1 from install_log
    where install_log.skill_id = increment_forks.skill_id
      and log_type = 'fork'
      and installed_at > now() - interval '10 minutes'
  ) then
    return;
  end if;
  insert into install_log (skill_id, log_type) values (skill_id, 'fork');
  update skills set forks = forks + 1 where id = skill_id;
end;
$$;

-- Row Level Security
-- NOTE: All writes go through security-definer RPCs (publish_skill, etc).
-- Anon key can only SELECT. service_role key bypasses RLS entirely.
alter table skills enable row level security;

-- Anon key can read
create policy "Anyone can read skills" on skills
  for select using (true);

-- No INSERT/UPDATE policies = anon key CANNOT write directly.
-- Writes go through security-definer RPCs (publish_skill, submit_review, etc).

-- Reviews table (Phase 2)
create table if not exists skill_reviews (
  id uuid primary key default gen_random_uuid(),
  skill_id uuid references skills(id) on delete cascade,
  reviewer text not null,
  score int check (score between 1 and 5),
  review_text text,
  task_context text,
  created_at timestamptz default now()
);

alter table skill_reviews enable row level security;

-- Anon can read reviews; writes only through RPC
create policy "Anyone can read reviews" on skill_reviews
  for select using (true);

-- RPC function: submit a review (security definer — requires publisher key)
create or replace function submit_review(
  p_skill_id uuid,
  p_reviewer text,
  p_score int,
  p_api_key uuid default null,
  p_review_text text default null,
  p_task_context text default null
)
returns jsonb
language plpgsql security definer as $$
declare
  v_id uuid;
  v_registered_author text;
begin
  -- Authenticate reviewer via publisher key
  if p_api_key is null then
    raise exception 'PUBLISHER_KEY required to submit reviews — register via publish first';
  end if;
  select author into v_registered_author
    from publishers where api_key = p_api_key;
  if v_registered_author is null then
    raise exception 'invalid PUBLISHER_KEY';
  end if;
  if v_registered_author <> p_reviewer then
    raise exception 'PUBLISHER_KEY does not match reviewer name "%"', p_reviewer;
  end if;

  -- Validate score
  if p_score < 1 or p_score > 5 then
    raise exception 'score must be between 1 and 5';
  end if;
  -- Validate skill exists
  if not exists (select 1 from skills where id = p_skill_id) then
    raise exception 'skill not found';
  end if;
  -- Validate text lengths
  if length(p_reviewer) > 100 then
    raise exception 'reviewer name too long';
  end if;
  if length(p_review_text) > 2000 then
    raise exception 'review text too long (max 2000 chars)';
  end if;

  insert into skill_reviews (skill_id, reviewer, score, review_text, task_context)
  values (p_skill_id, p_reviewer, p_score, p_review_text, p_task_context)
  returning id into v_id;

  return jsonb_build_object('id', v_id, 'status', 'ok');
end;
$$;

-- RPC function: publish or update a skill (security definer — anon key can call)
-- All validation happens server-side so users never need the service_role key.
-- p_api_key authenticates the publisher — must match the registered author.
create or replace function publish_skill(
  p_name text,
  p_variant text,
  p_description text,
  p_author text,
  p_api_key uuid,
  p_tags text[] default '{}',
  p_skill_md text default '',
  p_file_tree jsonb default '{}',
  p_requires_env text[] default '{}',
  p_requires_tools text[] default '{}',
  p_requires_runtime text[] default '{}',
  p_depends_on text[] default '{}',
  p_parent_id uuid default null
)
returns jsonb
language plpgsql security definer as $$
declare
  v_id uuid;
  v_existing record;
  v_action text;
  v_file_tree_size int;
  v_registered_author text;
begin
  -- Authenticate publisher: api_key must exist and match claimed author
  select author into v_registered_author
    from publishers where api_key = p_api_key;
  if v_registered_author is null then
    raise exception 'invalid PUBLISHER_KEY — register first by publishing without a key';
  end if;
  if v_registered_author <> p_author then
    raise exception 'PUBLISHER_KEY does not match author "%". This key belongs to "%".', p_author, v_registered_author;
  end if;

  -- Server-side validation (defense in depth — client also validates)
  if p_name !~ '^[a-z0-9][a-z0-9\-]{0,62}$' then
    raise exception 'invalid skill name: %', p_name;
  end if;
  if p_variant !~ '^[a-z0-9][a-z0-9\-]{0,62}$' then
    raise exception 'invalid variant: %', p_variant;
  end if;
  if length(p_description) > 1000 then
    raise exception 'description too long (% chars, max 1000)', length(p_description);
  end if;
  if length(p_author) > 100 then
    raise exception 'author too long';
  end if;
  if array_length(p_tags, 1) > 15 then
    raise exception 'too many tags (max 15)';
  end if;
  -- file_tree size check: jsonb text representation as proxy
  v_file_tree_size := length(p_file_tree::text);
  if v_file_tree_size > 600000 then
    raise exception 'file_tree too large (% bytes, max ~500KB)', v_file_tree_size;
  end if;

  -- Check if this name+variant already exists
  select id, author into v_existing
    from skills where name = p_name and variant = p_variant;

  if v_existing.id is not null then
    -- Only the original author can update
    if v_existing.author <> p_author then
      raise exception 'variant % already exists by another author', p_variant;
    end if;
    update skills set
      description = p_description,
      tags = p_tags,
      skill_md = p_skill_md,
      file_tree = p_file_tree,
      requires_env = p_requires_env,
      requires_tools = p_requires_tools,
      requires_runtime = p_requires_runtime,
      depends_on = p_depends_on,
      updated_at = now(),
      audited_at = null  -- content changed, needs re-audit
    where id = v_existing.id
    returning id into v_id;
    v_action := 'updated';
  else
    insert into skills (
      name, variant, description, author, tags,
      skill_md, file_tree, requires_env, requires_tools,
      requires_runtime, depends_on, parent_id
    ) values (
      p_name, p_variant, p_description, p_author, p_tags,
      p_skill_md, p_file_tree, p_requires_env, p_requires_tools,
      p_requires_runtime, p_depends_on, p_parent_id
    ) returning id into v_id;
    v_action := 'published';
  end if;

  return jsonb_build_object('id', v_id, 'action', v_action);
end;
$$;

-- RPC function: mark a skill as audited (admin-only — called by audit.py with service key)
create or replace function audit_skill(p_skill_id uuid, p_passed boolean)
returns void
language plpgsql security definer as $$
declare
  v_role text;
begin
  -- Enforce service_role — anon callers cannot mark skills as audited
  v_role := coalesce(
    current_setting('request.jwt.claims', true)::jsonb ->> 'role',
    current_setting('role', true)
  );
  if v_role is distinct from 'service_role' then
    raise exception 'admin-only: requires service_role key';
  end if;

  if p_passed then
    update skills set audited_at = now() where id = p_skill_id;
  else
    update skills set audited_at = null where id = p_skill_id;
  end if;
end;
$$;

