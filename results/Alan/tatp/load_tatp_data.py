"""
TATP data loader, COPY-based and fully deterministic (seed 42), against the
schema in tatp_schema.sql. No external TATP repo needed.

Scale: 100,000 subscribers (a realistic OLTP size -- large enough that a lookup
on a non-key column like sub_nbr or a range on vlr_location has real cost, so
index effects are measurable rather than sub-microsecond noise).

Cardinalities:
    subscriber        100,000
    access_info       1-4 per subscriber   (~250,000)
    special_facility  1-4 per subscriber   (~250,000)
    call_forwarding   0-3 per facility     (~300,000)

Usage:
    py -m pip install psycopg2-binary
    psql -U postgres -c "CREATE DATABASE tatp;"
    psql -U postgres -d tatp -f tatp_schema.sql
    py load_tatp_data.py
"""

import io
import os
import random
import getpass

import psycopg2

NUM_SUBSCRIBERS = 100000
LOCATION_MAX = 10000   # msc/vlr location domain -> range predicates are selective but non-trivial

random.seed(42)

COLS = {
    "subscriber": ["s_id", "sub_nbr", "bit_1", "bit_2", "hex_1", "byte2_1",
                   "msc_location", "vlr_location"],
    "access_info": ["s_id", "ai_type", "data1", "data2", "data3", "data4"],
    "special_facility": ["s_id", "sf_type", "is_active", "error_cntrl",
                         "data_a", "data_b"],
    "call_forwarding": ["s_id", "sf_type", "start_time", "end_time", "numberx"],
}

START_TIMES = [0, 8, 16]


def row(*vals):
    return "\t".join("" if v is None else str(v) for v in vals) + "\n"


def copy_into(cur, table, buf):
    buf.seek(0)
    cur.copy_from(buf, table, sep="\t", null="", columns=COLS[table])


def load():
    pw = os.environ.get("PGPASSWORD") or getpass.getpass("Postgres password for user 'postgres': ")
    conn = psycopg2.connect(dbname="tatp", user="postgres", password=pw,
                            host="localhost", port=5432)
    conn.autocommit = False
    cur = conn.cursor()

    print(f"SUBSCRIBER ({NUM_SUBSCRIBERS:,})...")
    sb = io.StringIO()
    for s_id in range(1, NUM_SUBSCRIBERS + 1):
        sb.write(row(s_id, str(s_id).zfill(15),
                     random.randint(0, 1), random.randint(0, 1),
                     random.randint(0, 15), random.randint(0, 255),
                     random.randint(1, LOCATION_MAX), random.randint(1, LOCATION_MAX)))
    copy_into(cur, "subscriber", sb)

    print("ACCESS_INFO + SPECIAL_FACILITY + CALL_FORWARDING...")
    ab, fb, cb = io.StringIO(), io.StringIO(), io.StringIO()
    for s_id in range(1, NUM_SUBSCRIBERS + 1):
        # access_info: ai_type 1..n
        for ai_type in range(1, random.randint(1, 4) + 1):
            ab.write(row(s_id, ai_type, random.randint(0, 255), random.randint(0, 255),
                         "ABC", "XYZ12"))
        # special_facility: sf_type 1..m
        for sf_type in range(1, random.randint(1, 4) + 1):
            is_active = 1 if random.random() < 0.85 else 0
            fb.write(row(s_id, sf_type, is_active, random.randint(0, 255),
                         random.randint(0, 255), "DATAB"))
            # call_forwarding: a subset of start times for this facility
            k = random.randint(0, 3)
            for start in random.sample(START_TIMES, min(k, len(START_TIMES))):
                end = start + random.randint(1, 8)
                cb.write(row(s_id, sf_type, start, end, str(random.randint(0, 10**14)).zfill(15)))
    copy_into(cur, "access_info", ab)
    copy_into(cur, "special_facility", fb)
    copy_into(cur, "call_forwarding", cb)

    conn.commit()
    print("Refreshing planner statistics (ANALYZE)...")
    conn.autocommit = True
    cur.execute("ANALYZE;")
    cur.close()
    conn.close()
    print("Done. TATP loaded into tatp database.")


if __name__ == "__main__":
    load()
