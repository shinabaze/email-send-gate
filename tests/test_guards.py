import unittest

from tests.db import DbTest

# The upsert a typical lead form runs: every column, with the form's own defaults.
FORM_UPSERT = """
insert into customers (email, name, company, plan_status, paid_until)
values (%s, %s, %s, 'none', null)
on conflict (email) do update
  set name = excluded.name, company = excluded.company,
      plan_status = excluded.plan_status, paid_until = excluded.paid_until
"""


class AFormFillCannotDowngradeACustomer(DbTest):
    def setUp(self):
        super().setUp()
        self.run_sql("insert into customers (email, name, company, plan_status, paid_until) "
                     "values ('pay@example.com', 'Ada', 'Ada Bikes', 'active', now() + interval '20 days')")

    def customer(self):
        return self.run_sql("select * from customers where email = 'pay@example.com'")[0]

    def test_the_plan_survives_the_contact_form(self):
        self.run_sql(FORM_UPSERT, "pay@example.com", "Ada", "")
        row = self.customer()
        self.assertEqual(row["plan_status"], "active")
        self.assertIsNotNone(row["paid_until"])
        self.assertEqual(self.may_send("pay@example.com")["reason"], "paying_customer")

    def test_a_blank_field_keeps_what_we_had(self):
        self.run_sql(FORM_UPSERT, "pay@example.com", "  ", "")
        row = self.customer()
        self.assertEqual((row["name"], row["company"]), ("Ada", "Ada Bikes"))

    def test_a_new_value_still_updates(self):
        self.run_sql(FORM_UPSERT, "pay@example.com", "Ada Lovelace", "Ada Cycles")
        self.assertEqual(self.customer()["company"], "Ada Cycles")

    def test_a_deliberate_downgrade_says_so(self):
        # Refunds and cancellations are real. They opt in for their own transaction.
        self.run_sql("set local gate.allow_downgrade = 'on'")
        self.run_sql("update customers set plan_status = 'none', paid_until = null where email = 'pay@example.com'")
        self.assertEqual(self.customer()["plan_status"], "none")

    def test_an_ended_plan_is_not_protected(self):
        self.run_sql("update customers set paid_until = now() - interval '1 day' where email = 'pay@example.com'")
        self.run_sql(FORM_UPSERT, "pay@example.com", "Ada", "")
        self.assertEqual(self.customer()["plan_status"], "none")


if __name__ == "__main__":
    unittest.main()
