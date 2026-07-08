#!/usr/bin/env python3
"""Quick check of PostgreSQL data for Velmo."""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import io
# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = "localhost"
PORT = 5432
DATABASE = "velmo"
USER = "postgres"
PASSWORD = "postgres"

try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        database=DATABASE,
        user=USER,
        password=PASSWORD
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Get all tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    tables = [t[0] for t in cur.fetchall()]

    print("\n" + "="*80)
    print("DATABASE CHECK: Velmo PostgreSQL")
    print("="*80)

    if not tables:
        print("[ERROR] No tables found! Database may not be initialized.")
        sys.exit(1)

    print(f"\n[OK] Found {len(tables)} tables:\n")

    total_rows = 0
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        total_rows += count

        # Show status
        status = "[+]" if count > 0 else "[ ]"
        print(f"  {status} {table:<30} {count:>6} rows")

    print(f"\n{'─'*80}")
    print(f"Total rows across all tables: {total_rows}")
    print("="*80)

    # Show recent data
    if total_rows > 0:
        print("\n[DATA] RECENT SAMPLES:\n")

        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]

            if count == 0:
                continue

            # Get columns
            cur.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = '{table}' ORDER BY ordinal_position
            """)
            columns = [col[0] for col in cur.fetchall()]

            # Get sample rows (limit columns to first 5)
            cols_limit = ', '.join(columns[:5])
            cur.execute(f"SELECT {cols_limit} FROM {table} LIMIT 2")
            rows = cur.fetchall()

            print(f"[{table}] (latest 2 rows)")
            print(f"  Columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}")
            for row in rows:
                preview = str(row)[:80]
                print(f"    {preview}")
            print()

    cur.close()
    conn.close()

except Exception as e:
    print(f"\n[ERROR] Connection failed: {e}")
    print("\nMake sure Docker is running:")
    print("  docker compose up -d")
    sys.exit(1)
