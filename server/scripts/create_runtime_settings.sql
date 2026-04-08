-- Create a simple key/value store for persisted runtime settings.
-- Apply this in Supabase SQL editor.

create table if not exists public.runtime_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

-- Optional: keep updated_at fresh on update
create or replace function public.set_runtime_settings_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists runtime_settings_updated_at on public.runtime_settings;
create trigger runtime_settings_updated_at
before update on public.runtime_settings
for each row execute function public.set_runtime_settings_updated_at();

