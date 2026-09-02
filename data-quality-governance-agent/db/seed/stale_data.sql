-- Eval fixture: stale_data
-- Exercises: timeliness - a table whose freshness timestamp column
-- is uniformly far in the past, indicating a stalled sync pipeline.
drop schema if exists eval_stale_data cascade;
create schema eval_stale_data;

create table eval_stale_data.sync_status (
    id serial primary key,
    source_system text not null,
    last_synced_at timestamptz not null
);

-- All rows last synced ~400 days before this fixture was authored -
-- any reasonable "timeliness" check should flag this table as stale
-- regardless of when the eval actually runs.
insert into eval_stale_data.sync_status (source_system, last_synced_at) values
    ('crm',        now() - interval '410 days'),
    ('billing',    now() - interval '405 days'),
    ('warehouse',  now() - interval '400 days');
