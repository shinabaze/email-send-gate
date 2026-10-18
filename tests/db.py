"""A connection with the schema loaded, where every test runs inside a transaction that is rolled back.

Point it at a throwaway Postgres with the usual PGHOST / PGUSER / PGPASSWORD variables, or a
DATABASE_URL (the README shows a one-line docker command). Everything
happens inside its own schema, gate_test, which is dropped and rebuilt on each run: your own
tables are never touched, even if they are called contacts or customers.
"""
import os
import unittest

import psycopg2
import psycopg2.extras

URL = os.environ.get("DATABASE_URL", "")   # empty: libpq reads PGHOST, PGUSER, PGPASSWORD...
SCHEMA = "gate_test"
SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql")


def connect():
    return psycopg2.connect(URL, options=f"-c search_path={SCHEMA}")


def load_schema():
    conn = psycopg2.connect(URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"drop schema if exists {SCHEMA} cascade; create schema {SCHEMA}; set search_path to {SCHEMA}")
        for name in ("schema.sql", "gate.sql", "guards.sql"):
            with open(os.path.join(SQL, name), encoding="utf-8") as fh:
                cur.execute(fh.read())
    conn.close()


class DbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_schema()
        cls.conn = connect()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def tearDown(self):
        self.conn.rollback()   # nothing a test writes survives it

    def run_sql(self, sql, *args):
        self.cur.execute(sql, args or None)
        return self.cur.fetchall() if self.cur.description else None

    def may_send(self, email, sender="newsletter", kind="marketing", **opts):
        cooldown = opts.get("cooldown_hours", 24)
        cap = opts.get("daily_cap", 100)
        return self.run_sql("select may_send(%s, %s, %s, %s, %s) as d", email, sender, kind, cooldown, cap)[0]["d"]

    def record(self, email, sender="newsletter", kind="marketing", hours_ago=0):
        self.run_sql("select record_send(%s, %s, %s)", email, sender, kind)
        if hours_ago:
            self.run_sql("update sends set sent_at = now() - make_interval(hours => %s) "
                         "where id = (select max(id) from sends)", hours_ago)
