-- Eval fixture: orphaned_fk
-- Exercises: consistency (a foreign key constraint declared on the
-- table but violated by existing data - the realistic scenario is a
-- constraint added with NOT VALID after the orphaned rows already
-- existed, which Postgres permits without revalidating history).
drop schema if exists eval_orphaned_fk cascade;
create schema eval_orphaned_fk;

create table eval_orphaned_fk.customers (
    id serial primary key,
    full_name text not null
);

create table eval_orphaned_fk.orders (
    id serial primary key,
    customer_id integer not null,
    order_total numeric(10, 2) not null
);

insert into eval_orphaned_fk.customers (full_name) values
    ('Alice Anderson'), ('Bob Brown'), ('Carol Clark');

insert into eval_orphaned_fk.orders (customer_id, order_total) values
    (1, 49.99),
    (2, 12.00),
    (3, 87.50),
    (99, 5.25); -- orphan: no customer with id 99

-- Add the FK constraint NOT VALID so it documents intent without
-- requiring (or blocking on) a backfill - exactly how this defect
-- shows up in a real production database.
alter table eval_orphaned_fk.orders
    add constraint orders_customer_id_fkey
    foreign key (customer_id) references eval_orphaned_fk.customers (id)
    not valid;
