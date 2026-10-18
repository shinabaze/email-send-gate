"""One person, four senders, printed step by step. Needs DATABASE_URL (see README).

    python examples/walkthrough.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.db import connect, load_schema   # noqa: E402

load_schema()
conn = connect()
cur = conn.cursor()


def ask(email, sender, kind):
    cur.execute("select may_send(%s, %s, %s)", (email, sender, kind))
    answer = cur.fetchone()[0]
    answer.pop("sent_today", None)
    print(f"may_send({email!r}, {sender!r}, {kind!r})\n  -> {json.dumps(answer)}")


def do(sql, note):
    cur.execute(sql)
    print(f"\n-- {note}")


ask("dana@example.com", "newsletter", "marketing")
do("select record_send('dana@example.com', 'newsletter', 'marketing')", "the newsletter goes out")
ask("dana@example.com", "newsletter", "marketing")
ask("dana@example.com", "outbound", "marketing")
ask("dana@example.com", "shop", "transactional")
do("insert into opt_outs (email) values ('dana@example.com')", "Dana unsubscribes")
ask("dana@example.com", "shop", "transactional")
ask("dana@example.com", "newsletter", "marketing")
conn.rollback()
