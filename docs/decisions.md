# Decisions

**In the database, not in each sender.** Rules copied into every automation drift apart, and one
copy that is out of date is enough to email someone who unsubscribed. A function in Postgres is
one copy that every sender reaches the same way.

**Two kinds, not one list of exceptions.** Marketing is what a person could reasonably not want.
Transactional is what they asked for. The kinds differ on four checks (see the README table), and
naming the kind at each call is clearer than a list of senders that are "allowed to skip".

**An opt-out only stops marketing.** Someone who leaves a newsletter still needs their receipt
and their password reset. Blocking those is a support problem, and in some places a legal one.

**A bounce stops everything.** Mailing an address that hard-bounced, even with a receipt, lowers
your sender reputation for every email you send after it.

**A receipt claims nobody.** If transactional mail claimed people, the first receipt would lock
every campaign out of that customer for good.

**Unknown kinds are an error.** `may_send(..., 'newsletter')` raises instead of picking a default.
A typo that silently means "marketing" or "transactional" is worse than one that fails loudly.

**The triggers correct, they don't raise.** The writers are usually forms and automations, and
many of them treat a failed insert as done. An error would drop the form fill without anyone
noticing. Correcting the write keeps the new data and the plan.

**A deliberate downgrade opts in.** A refund or a cancellation really does end a plan. That code
runs `set local gate.allow_downgrade = 'on'` inside its own transaction, so the intent is
written down at the place it happens.

**Tests run in their own schema and roll back.** Every test runs in a transaction that is rolled
back, inside a `gate_test` schema the helper rebuilds. Pointing the tests at a database with your
own `contacts` table can't touch it.
