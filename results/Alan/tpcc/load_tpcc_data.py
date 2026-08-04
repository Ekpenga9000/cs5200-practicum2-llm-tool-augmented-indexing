"""
TPC-C data loader at the standard smallest scale factor (1 warehouse), loaded
with COPY for speed. Generates an FK-consistent dataset directly against the
schema (tpcc_schema.sql) -- no external py-tpcc repo needed.

Standard TPC-C cardinalities at 1 warehouse (this is the *smallest* real scale
factor; earlier versions of this loader were a toy sub-scale and made every
query sub-microsecond, so index effects were pure noise):
    warehouse   1
    district    10
    customer    3,000 / district   -> 30,000
    item        100,000            (fixed by the spec)
    stock       100,000 / warehouse
    orders      3,000 / district   -> 30,000  (o_id 1..3000, o_c_id = o_id)
    order_line  ~5-15 / order      -> ~300,000
    new_order   o_id 2101..3000/district -> 9,000
    history     1 / customer       -> 30,000

Fully deterministic (seeded `random`, fixed base date), so every teammate
regenerates byte-identical data. Loads in a few seconds via COPY.

Usage:
    py -m pip install psycopg2-binary
    psql -U postgres -c "CREATE DATABASE tpcc;"
    psql -U postgres -d tpcc -f tpcc_schema.sql
    py load_tpcc_data.py
"""

import io
import random
import getpass
from datetime import datetime, timedelta

import psycopg2

NUM_WAREHOUSES = 1
DISTRICTS_PER_WAREHOUSE = 10
CUSTOMERS_PER_DISTRICT = 3000
NUM_ITEMS = 100000
ORDERS_PER_DISTRICT = CUSTOMERS_PER_DISTRICT      # one order per customer
NEW_ORDER_START = 2101                            # orders >= this are undelivered
BASE_DATE = datetime(2024, 1, 1)                  # fixed -> deterministic

random.seed(42)

# Column lists (must match tpcc_schema.sql ordering for COPY).
COLS = {
    "warehouse": ["w_id", "w_name", "w_street_1", "w_street_2", "w_city",
                  "w_state", "w_zip", "w_tax", "w_ytd"],
    "item": ["i_id", "i_im_id", "i_name", "i_price", "i_data"],
    "district": ["d_id", "d_w_id", "d_name", "d_street_1", "d_street_2",
                 "d_city", "d_state", "d_zip", "d_tax", "d_ytd", "d_next_o_id"],
    "customer": ["c_id", "c_d_id", "c_w_id", "c_first", "c_middle", "c_last",
                 "c_street_1", "c_street_2", "c_city", "c_state", "c_zip",
                 "c_phone", "c_since", "c_credit", "c_credit_lim", "c_discount",
                 "c_balance", "c_ytd_payment", "c_payment_cnt",
                 "c_delivery_cnt", "c_data"],
    "history": ["h_c_id", "h_c_d_id", "h_c_w_id", "h_d_id", "h_w_id",
                "h_date", "h_amount", "h_data"],
    "stock": ["s_i_id", "s_w_id", "s_quantity"]
             + [f"s_dist_{i:02d}" for i in range(1, 11)]
             + ["s_ytd", "s_order_cnt", "s_remote_cnt", "s_data"],
    "orders": ["o_id", "o_d_id", "o_w_id", "o_c_id", "o_entry_d",
               "o_carrier_id", "o_ol_cnt", "o_all_local"],
    "new_order": ["no_o_id", "no_d_id", "no_w_id"],
    "order_line": ["ol_o_id", "ol_d_id", "ol_w_id", "ol_number", "ol_i_id",
                   "ol_supply_w_id", "ol_delivery_d", "ol_quantity",
                   "ol_amount", "ol_dist_info"],
}


def fmt(v):
    """Format one value for a tab-separated COPY stream."""
    if v is None:
        return r"\N"
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    return str(v)


def row(*vals):
    return "\t".join(fmt(v) for v in vals) + "\n"


def copy_into(cur, table, buf):
    buf.seek(0)
    cur.copy_from(buf, table, sep="\t", null=r"\N", columns=COLS[table])


def load():
    pw = getpass.getpass("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname="tpcc", user="postgres", password=pw,
                            host="localhost", port=5432)
    conn.autocommit = False
    cur = conn.cursor()
    dist = "x" * 24  # dummy district-info / stock-dist string

    for w_id in range(1, NUM_WAREHOUSES + 1):
        print(f"WAREHOUSE {w_id}...")
        b = io.StringIO()
        b.write(row(w_id, f"WH{w_id}", "1 Main St", "", "Vancouver", "BC",
                    "V6B1A1", 0.0800, 300000.00))
        copy_into(cur, "warehouse", b)

    print(f"ITEM ({NUM_ITEMS:,})...")
    b = io.StringIO()
    for i_id in range(1, NUM_ITEMS + 1):
        b.write(row(i_id, random.randint(1, 10000), f"item{i_id}",
                    round(random.uniform(1, 100), 2), "data"))
    copy_into(cur, "item", b)

    for w_id in range(1, NUM_WAREHOUSES + 1):
        print(f"STOCK for warehouse {w_id} ({NUM_ITEMS:,})...")
        b = io.StringIO()
        for i_id in range(1, NUM_ITEMS + 1):
            b.write(row(i_id, w_id, random.randint(10, 100),
                        dist, dist, dist, dist, dist, dist, dist, dist, dist, dist,
                        0, 0, 0, "data"))
        copy_into(cur, "stock", b)

        print(f"DISTRICT + CUSTOMER + HISTORY (warehouse {w_id})...")
        db, cb, hb = io.StringIO(), io.StringIO(), io.StringIO()
        for d_id in range(1, DISTRICTS_PER_WAREHOUSE + 1):
            db.write(row(d_id, w_id, f"D{d_id}", "1 Side St", "", "Vancouver",
                         "BC", "V6B1A1", 0.0500, 30000.00, ORDERS_PER_DISTRICT + 1))
            for c_id in range(1, CUSTOMERS_PER_DISTRICT + 1):
                cb.write(row(c_id, d_id, w_id, f"first{c_id}", "OE",
                             f"cust{random.randint(1000, 9999)}", "1 Cust St", "",
                             "Vancouver", "BC", "V6B1A1", "6045551234", BASE_DATE,
                             "GC", 50000.00, round(random.uniform(0, 0.5), 4),
                             -10.00, 10.00, 1, 0, "customer data"))
                hb.write(row(c_id, d_id, w_id, d_id, w_id, BASE_DATE, 10.00, "initial"))
        copy_into(cur, "district", db)
        copy_into(cur, "customer", cb)
        copy_into(cur, "history", hb)

        print(f"ORDERS + NEW_ORDER + ORDER_LINE (warehouse {w_id})...")
        ob, nb, lb = io.StringIO(), io.StringIO(), io.StringIO()
        for d_id in range(1, DISTRICTS_PER_WAREHOUSE + 1):
            for o_id in range(1, ORDERS_PER_DISTRICT + 1):
                undelivered = o_id >= NEW_ORDER_START
                carrier = None if undelivered else random.randint(1, 10)
                ol_cnt = random.randint(5, 15)
                entry_d = BASE_DATE - timedelta(days=random.randint(0, 60))
                ob.write(row(o_id, d_id, w_id, o_id, entry_d, carrier, ol_cnt, 1))
                if undelivered:
                    nb.write(row(o_id, d_id, w_id))
                for ol_number in range(1, ol_cnt + 1):
                    deliv = None if undelivered else entry_d
                    lb.write(row(o_id, d_id, w_id, ol_number,
                                 random.randint(1, NUM_ITEMS), w_id, deliv,
                                 random.randint(1, 10),
                                 round(random.uniform(1, 500), 2), dist))
        copy_into(cur, "orders", ob)
        copy_into(cur, "new_order", nb)
        copy_into(cur, "order_line", lb)

    conn.commit()
    print("Refreshing planner statistics (ANALYZE)...")
    conn.autocommit = True
    cur.execute("ANALYZE;")
    cur.close()
    conn.close()
    print("Done. TPC-C (1 warehouse) loaded into tpcc database.")


if __name__ == "__main__":
    load()
