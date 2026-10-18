import unittest

from tests.db import DbTest


class Basics(DbTest):
    def test_a_new_address_may_get_marketing(self):
        self.assertEqual(self.may_send("new@example.com")["reason"], "ok")

    def test_a_broken_address_never_goes(self):
        for bad in ("", "  ", "no-at-sign", "two@@example.com", "a@b"):
            with self.subTest(bad=bad):
                self.assertEqual(self.may_send(bad)["reason"], "invalid_email")

    def test_addresses_are_compared_lower_case_and_trimmed(self):
        self.run_sql("insert into opt_outs (email) values ('dana@example.com')")
        self.assertEqual(self.may_send("  Dana@Example.COM ")["reason"], "opted_out")

    def test_an_unknown_kind_is_an_error_not_a_default(self):
        with self.assertRaises(Exception):
            self.may_send("a@example.com", kind="newsletter")


class OptOutsAndBounces(DbTest):
    def test_an_opt_out_stops_marketing_but_not_a_receipt(self):
        self.run_sql("insert into opt_outs (email) values ('lee@example.com')")
        self.assertEqual(self.may_send("lee@example.com")["reason"], "opted_out")
        self.assertTrue(self.may_send("lee@example.com", sender="shop", kind="transactional")["allow"])

    def test_a_hard_bounce_stops_everything(self):
        self.run_sql("insert into contacts (email, suppressed, suppressed_reason) values ('gone@example.com', true, 'hard bounce')")
        for kind in ("marketing", "transactional"):
            with self.subTest(kind=kind):
                self.assertEqual(self.may_send("gone@example.com", kind=kind)["reason"], "suppressed")


class PayingCustomers(DbTest):
    def test_no_sales_email_to_someone_who_already_pays(self):
        self.run_sql("insert into customers (email, plan_status, paid_until) values ('pay@example.com', 'active', now() + interval '20 days')")
        self.assertEqual(self.may_send("pay@example.com")["reason"], "paying_customer")
        self.assertTrue(self.may_send("pay@example.com", sender="billing", kind="transactional")["allow"])

    def test_once_the_plan_ends_they_can_hear_offers_again(self):
        self.run_sql("insert into customers (email, plan_status, paid_until) values ('was@example.com', 'active', now() - interval '1 day')")
        self.assertTrue(self.may_send("was@example.com")["allow"])


class OneSenderAtATime(DbTest):
    def test_the_first_marketing_send_claims_the_person(self):
        self.record("sam@example.com", sender="newsletter", hours_ago=48)
        d = self.may_send("sam@example.com", sender="outbound")
        self.assertEqual((d["reason"], d["detail"]), ("owned_by_other_sender", "newsletter"))
        self.assertTrue(self.may_send("sam@example.com", sender="newsletter")["allow"])

    def test_a_receipt_claims_nobody(self):
        # If it did, the first receipt would block every campaign to that customer.
        self.record("buyer@example.com", sender="shop", kind="transactional")
        self.assertTrue(self.may_send("buyer@example.com", sender="newsletter")["allow"])

    def test_release_lets_the_others_in(self):
        self.record("kim@example.com", sender="newsletter", hours_ago=48)
        self.run_sql("select release_contact('kim@example.com', 'newsletter')")
        self.assertTrue(self.may_send("kim@example.com", sender="outbound")["allow"])


class CooldownAndCap(DbTest):
    def test_two_marketing_emails_need_the_cooldown_between_them(self):
        self.record("jo@example.com", hours_ago=2)
        self.assertEqual(self.may_send("jo@example.com")["reason"], "cooldown")
        self.assertTrue(self.may_send("jo@example.com", cooldown_hours=1)["allow"])

    def test_receipts_ignore_the_cooldown(self):
        self.record("jo@example.com", hours_ago=0)
        self.assertTrue(self.may_send("jo@example.com", sender="shop", kind="transactional")["allow"])

    def test_the_daily_cap_counts_every_send_by_that_sender(self):
        for i in range(3):
            self.record(f"p{i}@example.com", sender="outbound")
        self.assertEqual(self.may_send("p9@example.com", sender="outbound", daily_cap=3)["reason"], "daily_cap")
        self.assertTrue(self.may_send("p9@example.com", sender="newsletter", daily_cap=3)["allow"])


if __name__ == "__main__":
    unittest.main()
