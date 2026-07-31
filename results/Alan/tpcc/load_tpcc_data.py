"""
Lightweight synthetic TPC-C data loader (Python 3, no external TPC-C repo
needed). py-tpcc's official loader is Python 2 only and doesn't have a
Postgres driver in this fork -- this script generates a small, FK-consistent
dataset directly against the already-created schema (tpcc_schema.sql).

Fully deterministic: seeded `random` only, NO faker / external dependency, so
every teammate regenerates byte-identical data from the same seed. This is what
makes Condition A / B / baseline measurements comparable across machines.

Scale (deliberately small -- "smallest scale factor, just needs to be
queryable", per the assignment):
    1 warehouse, 10 districts, 300 customers/district, 100 items,
    ~10 orders/customer, 5-15 order_lines/order.

Usage:
    py -m pip install psycopg2-binary
    psql -U postgres -c "CREATE DATABASE tpcc;"
    psql -U postgres -d tpcc -f tpcc_schema.sql
    py load_tpcc_data.py
"""

import random
import getpass
import psycopg2
from datetime import datetime, timedelta

NUM_WAREHOUSES = 1
DISTRICTS_PER_WAREHOUSE = 10
CUSTOMERS_PER_DISTRICT = 300
NUM_ITEMS = 100
ORDERS_PER_CUSTOMER = 10

random.seed(42)


def rand_str(prefix, length=10):
    # Deterministic synthetic string -- cosmetic columns only (names, item
    # descriptions); does not affect index selectivity or query cost.
    return f"{prefix}{random.randint(1000, 9999)}"[:length]


def connect():
    pw = getpass.getpass("Postgres password for user 'postgres': ")
    return psycopg2.connect(dbname="tpcc", user="postgres", password=pw, host="localhost", port=5432)


def load():
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    print("Loading WAREHOUSE...")
    for w_id in range(1, NUM_WAREHOUSES + 1):
        cur.execute(
            "INSERT INTO warehouse VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (w_id, f"WH{w_id}", "1 Main St", "", "Vancouver", "BC", "V6B1A1", 0.08, 300000.00),
        )

    print("Loading ITEM...")
    for i_id in range(1, NUM_ITEMS + 1):
        cur.execute(
            "INSERT INTO item VALUES (%s,%s,%s,%s,%s)",
            (i_id, random.randint(1, 10000), rand_str("item"), round(random.uniform(1, 100), 2), "data"),
        )

    for w_id in range(1, NUM_WAREHOUSES + 1):
        print(f"Loading STOCK for warehouse {w_id}...")
        for i_id in range(1, NUM_ITEMS + 1):
            cur.execute(
                "INSERT INTO stock VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (i_id, w_id, random.randint(10, 100),
                 "x" * 24, "x" * 24, "x" * 24, "x" * 24, "x" * 24,
                 "x" * 24, "x" * 24, "x" * 24, "x" * 24, "x" * 24,
                 0, 0, 0, "data"),
            )

        for d_id in range(1, DISTRICTS_PER_WAREHOUSE + 1):
            print(f"Loading DISTRICT {d_id} / WAREHOUSE {w_id}...")
            cur.execute(
                "INSERT INTO district VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (d_id, w_id, f"D{d_id}", "1 Side St", "", "Vancouver", "BC", "V6B1A1",
                 0.05, 30000.00, CUSTOMERS_PER_DISTRICT + 1),
            )

            for c_id in range(1, CUSTOMERS_PER_DISTRICT + 1):
                c_last = rand_str("cust")
                cur.execute(
                    "INSERT INTO customer VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (c_id, d_id, w_id, rand_str("first"), "OE", c_last,
                     "1 Cust St", "", "Vancouver", "BC", "V6B1A1", "6045551234",
                     datetime.now(), "GC", 50000.00, round(random.uniform(0, 0.5), 4),
                     -10.00, 10.00, 1, 0, "customer data"),
                )
                cur.execute(
                    "INSERT INTO history VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (c_id, d_id, w_id, d_id, w_id, datetime.now(), 10.00, "initial"),
                )

                # a handful of orders per customer
                for o_num in range(1, ORDERS_PER_CUSTOMER + 1):
                    o_id = (c_id - 1) * ORDERS_PER_CUSTOMER + o_num
                    ol_cnt = random.randint(5, 15)
                    entry_d = datetime.now() - timedelta(days=random.randint(0, 60))
                    cur.execute(
                        "INSERT INTO orders VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (o_id, d_id, w_id, c_id, entry_d, random.randint(1, 10), ol_cnt, 1),
                    )
                    for ol_number in range(1, ol_cnt + 1):
                        i_id = random.randint(1, NUM_ITEMS)
                        cur.execute(
                            "INSERT INTO order_line VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (o_id, d_id, w_id, ol_number, i_id, w_id,
                             entry_d, random.randint(1, 10), round(random.uniform(1, 500), 2), "x" * 24),
                        )
                    # last few orders per district stay "undelivered" -> new_order
                    if o_num > ORDERS_PER_CUSTOMER - 2:
                        cur.execute(
                            "INSERT INTO new_order VALUES (%s,%s,%s)",
                            (o_id, d_id, w_id),
                        )

    conn.commit()
    cur.close()
    conn.close()
    print("Done. Data loaded into tpcc database.")


if __name__ == "__main__":
    load()
