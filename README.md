# email-send-gate

One Postgres function that every email in your system asks before it goes out. It enforces
unsubscribes, bounce suppression, a cooldown between marketing emails, a daily cap per sender,
"one campaign per person at a time", and "never send sales emails to someone who already pays".
Plus two triggers that stop a lead form from wrecking a customer record.

About 150 lines of SQL. Postgres 13+. Works with anything that can call a function: n8n, a
backend, a cron job, Supabase.

I put these rules in the database because the senders were many and the rules kept drifting
between them. Each automation had its own copy of "don't email people who unsubscribed", and the
copies didn't agree. Now there is one answer, and every sender has to ask for it.

**Run it** against a throwaway Postgres. The tests only touch their own `gate_test` schema:

```bash
docker run --rm -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:17
export PGHOST=localhost PGUSER=postgres PGPASSWORD=postgres
pip install psycopg2-binary
python -m unittest discover -s tests -t .
python examples/walkthrough.py
```

**Use it:** load `sql/schema.sql`, `sql/gate.sql` and `sql/guards.sql`, then:

```sql
select may_send('dana@example.com', 'newsletter', 'marketing');   -- ask first
select record_send('dana@example.com', 'newsletter', 'marketing'); -- after it went out
```

## How it works

`may_send(email, sender, kind)` returns `{"allow": true|false, "reason": "..."}`. The checks run in
this order, and the first one that says no wins:

| Check | Marketing | Transactional (receipts, resets, replies) |
|---|---|---|
| `invalid_email` | blocked | blocked |
| `opted_out` | blocked | allowed: leaving a newsletter isn't refusing a receipt |
| `suppressed` (hard bounce, complaint) | blocked | blocked: a dead address hurts every email you send |
| `paying_customer` | blocked | allowed |
| `owned_by_other_sender` | blocked | skipped |
| `cooldown` (default 24 h) | blocked | skipped |
| `daily_cap` (default 100 per sender) | blocked | blocked |

`record_send()` is the only way a send is written down. A marketing send claims the person for
that sender. A transactional send claims nobody. `release_contact()` hands the person back when a
sequence ends.

`guards.sql` adds two triggers on `customers`. A form that upserts every column can't turn an
active customer into `plan_status = 'none'`, and a blank field can't wipe a stored name or
company. Both correct the write instead of raising an error (see [docs/decisions.md](docs/decisions.md)).

## A worked example

From `python examples/walkthrough.py`:

```
may_send('dana@example.com', 'newsletter', 'marketing')
  -> {"allow": true, "reason": "ok"}

-- the newsletter goes out
may_send('dana@example.com', 'newsletter', 'marketing')
  -> {"allow": false, "detail": "2026-10-18T18:36:50+00:00", "reason": "cooldown"}
may_send('dana@example.com', 'outbound', 'marketing')
  -> {"allow": false, "detail": "newsletter", "reason": "owned_by_other_sender"}
may_send('dana@example.com', 'shop', 'transactional')
  -> {"allow": true, "reason": "ok"}

-- Dana unsubscribes
may_send('dana@example.com', 'shop', 'transactional')
  -> {"allow": true, "reason": "ok"}
may_send('dana@example.com', 'newsletter', 'marketing')
  -> {"allow": false, "reason": "opted_out"}
```

## What I learned

- **A gate that counts the wrong status is blind.** My first version counted only sends marked
  `sent`, and one sender wrote its emails down as `drafted`. The gate never saw them, and some
  people got the same email twice. Now there is one writer, `record_send()`, and no status to
  get wrong.
- **A rule without an exception will block your customers.** "One sender per person" claimed
  people on their first email and nothing ever released them, so in time every contact was owned
  by some campaign, and receipts to real customers were refused. Transactional mail now skips
  that rule, and it never claims anyone.
- **A contact form cancelled a paid plan.** The form upserted every column with its defaults, so a
  paying customer who sent a question came back as a free lead. A trigger now keeps the plan. It
  corrects the write rather than raising, because the form's automation would have swallowed the
  error and lost the message.

## Limits

- The cooldown and cap are per call, not global settings. Pass the same numbers from every sender.
- No time zones: "today" for the cap is the database's day.
- It decides, it doesn't send. If a sender skips `may_send()`, nothing stops it. Give senders a
  database role that can only call these functions.

## Files

```
sql/       schema.sql  gate.sql  guards.sql
tests/     unittest + psycopg2, every test inside a rolled-back transaction
examples/  walkthrough.py
docs/      explained.md, decisions.md
```

MIT licence. Copyright 2026 Shinabaze Ajiya.
