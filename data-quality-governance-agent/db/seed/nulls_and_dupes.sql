-- Eval fixture: nulls_and_dupes
-- Exercises: completeness (required column with nulls), uniqueness
-- (an "email should be unique" column that in fact has duplicates).
drop schema if exists eval_nulls_and_dupes cascade;
create schema eval_nulls_and_dupes;

create table eval_nulls_and_dupes.customers (
    id serial primary key,
    email text,
    full_name text,
    signup_date date
);

insert into eval_nulls_and_dupes.customers (email, full_name, signup_date) values
    ('alice@example.test',   'Alice Anderson', '2024-01-05'),
    ('bob@example.test',     'Bob Brown',      '2024-01-06'),
    ('carol@example.test',   'Carol Clark',    '2024-01-07'),
    ('carol@example.test',   'Carol C. Clark', '2024-02-11'), -- duplicate email (uniqueness defect)
    ('dave@example.test',    NULL,             '2024-02-20'), -- missing full_name (completeness defect)
    ('erin@example.test',    NULL,             '2024-02-21'), -- missing full_name (completeness defect)
    ('frank@example.test',   'Frank Foster',   NULL);          -- missing signup_date (completeness defect)
