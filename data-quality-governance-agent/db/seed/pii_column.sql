-- Eval fixture: pii_column
-- Exercises: PII detection on a generically-named column (`notes`)
-- that nonetheless contains email/phone-shaped values, plus a
-- name-hinted column (`customer_email`). All values are synthetic
-- (.test TLD, obviously fake phone numbers) - never real PII.
drop schema if exists eval_pii_column cascade;
create schema eval_pii_column;

create table eval_pii_column.support_tickets (
    id serial primary key,
    customer_email text,
    notes text
);

insert into eval_pii_column.support_tickets (customer_email, notes) values
    ('grace.green@example.test',  'Called about order #1002, callback at 555-010-1111'),
    ('heidi.hill@example.test',   'Requested refund, ok to email heidi.hill@example.test'),
    ('ivan.ivanov@example.test',  'VIP customer, no issues'),
    ('judy.jones@example.test',   'Callback requested at 555-010-2222'),
    ('kevin.klein@example.test',  'Escalated to tier 2'),
    ('laura.lee@example.test',    'Reachable at 555-010-3333, prefers email');
