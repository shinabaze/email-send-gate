-- The four tables the gate reads. Emails are stored lower-case and trimmed.

create table if not exists contacts (
  email             text primary key,
  owner             text not null default 'none',   -- the one sender allowed to market to this person
  suppressed        boolean not null default false, -- hard bounce or spam complaint: never mail again
  suppressed_reason text
);

create table if not exists opt_outs (
  email  text primary key,
  at     timestamptz not null default now(),
  reason text
);

create table if not exists customers (
  email       text primary key,
  name        text,
  company     text,
  plan_status text not null default 'none',   -- 'active' while they pay
  paid_until  timestamptz
);

-- Every email that actually went out. record_send() is the only writer.
create table if not exists sends (
  id      bigserial primary key,
  email   text not null,
  sender  text not null,
  kind    text not null check (kind in ('marketing', 'transactional')),
  sent_at timestamptz not null default now()
);
create index if not exists sends_email_at on sends (email, sent_at desc);
create index if not exists sends_sender_at on sends (sender, sent_at desc);
