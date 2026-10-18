# A send gate, explained from scratch

## The problem

A small business soon has several things that send email: a newsletter, a follow-up sequence for
new leads, a shop that sends receipts, maybe a cold outreach tool. Each one knows only about its
own emails. None of them knows that Dana unsubscribed yesterday through a different one, that
her address bounced last week, or that she got a sales email two hours ago from another sequence.

The fix is one place that knows all of it, and a rule that nothing sends without asking it.

## The four tables

- `contacts`: one row per person. Who currently "owns" them (which sender may market to them) and
  whether their address is suppressed.
- `opt_outs`: everyone who unsubscribed.
- `customers`: who pays, and until when.
- `sends`: every email that actually went out, written by `record_send()`.

## One call, by hand

`may_send('dana@example.com', 'outbound', 'marketing')`, where the newsletter emailed Dana two
hours ago:

1. The address is lower-cased and trimmed, and it looks like an email. Go on.
2. She hasn't unsubscribed. Go on.
3. Her address isn't suppressed. Go on.
4. She isn't a paying customer. Go on.
5. `contacts.owner` is `newsletter`, not `outbound`. Stop: `owned_by_other_sender`.

The same call with kind `transactional` from the shop skips steps 2, 4 and 5 (and the cooldown),
checks the shop's daily cap, and is allowed.

## Why a trigger, and why it corrects

Forms often save with an "upsert": insert the row, or if it exists, overwrite it. Written the
quick way, that overwrites every column, including ones the form knows nothing about, such as the
customer's plan. A `before update` trigger sees both the old row and the new one, so it can put
the plan back before the write lands. It changes the write rather than raising an error,
because the form's automation would otherwise drop the whole submission.

## Rolled-back tests

Each test opens a transaction, sets up the rows it needs, asks the function, and rolls back. The
next test starts from empty tables, and nothing a test writes ever stays in the database.
